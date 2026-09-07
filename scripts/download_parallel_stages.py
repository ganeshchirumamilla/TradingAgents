#!/usr/bin/env python3
"""
Enhanced downloader with parallel stage processing.
Downloads data, then parallelizes: File Save, Redis Write, DB Write.
"""

import os
import sys
import yaml
import json
import pandas as pd
import psycopg2
import redis
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse
import time

try:
    from ib_async import IB, Stock, util
except ImportError:
    print("[ERROR] ib_async not installed. Run: pip install ib_async")
    sys.exit(1)

sys.path.insert(0, str(Path(__file__).parent))
from download_savepoint import DownloadSavepoint


class ParallelStageDownloader:
    """Downloader with parallel persistence stages."""

    def __init__(self, config_path: str = "download_config.yaml"):
        """Initialize with configuration."""
        self.config_path = Path(config_path).expanduser()
        self.config = self._load_config()
        self.savepoint = DownloadSavepoint(self.config['savepoint']['file_path'])
        self.ib = None
        self.db_conn = None
        self.redis_conn = None

    def _load_config(self) -> dict:
        """Load YAML configuration."""
        if not self.config_path.exists():
            print(f"[ERROR] Config not found: {self.config_path}")
            sys.exit(1)

        with open(self.config_path, 'r') as f:
            return yaml.safe_load(f)

    def connect_all(self) -> bool:
        """Connect to IBKR, PostgreSQL, and Redis."""
        print("\n[CONNECT] Establishing connections...")
        print("-" * 70)

        # IBKR
        config_ibkr = self.config['ibkr']
        self.ib = IB()
        try:
            self.ib.connect(config_ibkr['host'], config_ibkr['port'], clientId=config_ibkr['client_id'])
            print("[OK] IBKR Gateway connected")
        except Exception as e:
            print(f"[ERROR] IBKR failed: {e}")
            return False

        # PostgreSQL
        config_db = self.config['database']
        try:
            self.db_conn = psycopg2.connect(
                host=config_db['host'],
                port=config_db['port'],
                database=config_db['name'],
                user=config_db['user'],
                password=config_db['password']
            )
            print("[OK] PostgreSQL connected")
        except Exception as e:
            print(f"[ERROR] PostgreSQL failed: {e}")
            return False

        # Redis (optional)
        if self.config['redis']['enabled']:
            try:
                self.redis_conn = redis.Redis(
                    host=self.config['redis']['host'],
                    port=self.config['redis']['port'],
                    db=self.config['redis']['db'],
                    decode_responses=True
                )
                self.redis_conn.ping()
                print("[OK] Redis cache connected")
            except Exception as e:
                print(f"[WARNING] Redis unavailable: {e}")
                self.redis_conn = None
        else:
            print("[SKIP] Redis disabled in config")

        print("-" * 70)
        return True

    def download_data(self, ticker: str, timeframe: str, retry_count: int = 0, max_retries: int = 2) -> pd.DataFrame:
        """Download data from IBKR with retry logic."""
        try:
            tf_config = self.config['timeframes'][timeframe]
            ibkr_config = self.config['ibkr']

            days = tf_config['default_days']
            duration = tf_config['duration_format'].format(days=days)

            contract = Stock(ticker, "SMART", "USD")

            # Increase timeout for larger date ranges
            timeout = max(60, ibkr_config['request_timeout'])

            bars = self.ib.reqHistoricalData(
                contract,
                endDateTime="",
                durationStr=duration,
                barSizeSetting=tf_config['bar_size'],
                whatToShow=ibkr_config['what_to_show'],
                useRTH=ibkr_config['use_rth'],
                formatDate=1,
                timeout=timeout
            )

            if bars is None:
                if retry_count < max_retries:
                    print(f"   [RETRY] Attempt {retry_count + 1}/{max_retries + 1}...")
                    time.sleep(2 ** retry_count)  # Exponential backoff
                    return self.download_data(ticker, timeframe, retry_count + 1, max_retries)
                else:
                    print(f"   [ERROR] No data after {max_retries + 1} attempts")
                    return None

            df = util.df(bars)
            return df if not df.empty else None

        except Exception as e:
            if retry_count < max_retries:
                print(f"   [RETRY] {str(e)[:60]}... Attempt {retry_count + 1}/{max_retries + 1}")
                time.sleep(2 ** retry_count)  # Exponential backoff
                return self.download_data(ticker, timeframe, retry_count + 1, max_retries)
            else:
                print(f"   [ERROR] Download failed after {max_retries + 1} attempts: {e}")
                return None

    def save_to_file(self, ticker: str, timeframe: str, df: pd.DataFrame) -> tuple:
        """Save DataFrame to file (Parquet or CSV)."""
        if not self.config['download']['save_files']:
            return None, 0

        try:
            now = datetime.now()
            file_path = self.config['download']['file_path_template'].format(
                ticker=ticker,
                timeframe=timeframe,
                start_date=now.strftime('%Y%m%d'),
                format=self.config['download']['format']
            )

            file_path = Path(file_path).expanduser()
            file_path.parent.mkdir(parents=True, exist_ok=True)

            # Save
            if self.config['download']['format'] == 'parquet':
                df.to_parquet(file_path, compression=self.config['download']['compression'])
            else:
                df.to_csv(file_path, index=False)

            file_size = file_path.stat().st_size
            return str(file_path), file_size

        except Exception as e:
            return None, 0

    def write_to_redis(self, ticker: str, timeframe: str, df: pd.DataFrame) -> bool:
        """Write DataFrame to Redis."""
        if not self.redis_conn:
            return False

        try:
            redis_key = f"market_data:{ticker}:{timeframe}"

            records = []
            for _, row in df.iterrows():
                record = {
                    'date': str(row['date']),
                    'open': float(row['open']),
                    'high': float(row['high']),
                    'low': float(row['low']),
                    'close': float(row['close']),
                    'volume': int(row['volume']) if pd.notna(row['volume']) else 0,
                }
                records.append(record)

            redis_data = json.dumps(records)
            self.redis_conn.set(redis_key, redis_data)
            self.redis_conn.expire(redis_key, self.config['redis']['ttl_seconds'])

            return True

        except Exception as e:
            print(f"   [WARNING] Redis write failed: {e}")
            return False

    def write_to_postgres(self, ticker: str, timeframe: str, df: pd.DataFrame) -> int:
        """Write DataFrame to PostgreSQL."""
        if not self.db_conn:
            return 0

        try:
            cursor = self.db_conn.cursor()
            tf_config = self.config['timeframes'][timeframe]
            table_name = tf_config['table_name']

            # Create table
            create_sql = f"""
                CREATE TABLE IF NOT EXISTS {table_name} (
                    id UUID PRIMARY KEY,
                    ticker VARCHAR(20) NOT NULL,
                    date TIMESTAMP NOT NULL,
                    open DECIMAL(10,4),
                    high DECIMAL(10,4),
                    low DECIMAL(10,4),
                    close DECIMAL(10,4),
                    volume BIGINT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    data_source VARCHAR(50),
                    UNIQUE(ticker, date)
                )
            """
            cursor.execute(create_sql)
            self.db_conn.commit()

            # Prepare records
            import uuid
            records = []
            for _, row in df.iterrows():
                try:
                    record = (
                        str(uuid.uuid4()),
                        ticker,
                        pd.to_datetime(row['date']),
                        float(row['open']),
                        float(row['high']),
                        float(row['low']),
                        float(row['close']),
                        int(row['volume']) if pd.notna(row['volume']) else 0,
                        datetime.now(),
                        'ibkr'
                    )
                    records.append(record)
                except:
                    continue

            if not records:
                return 0

            # Insert
            insert_sql = f"""
                INSERT INTO {table_name}
                (id, ticker, date, open, high, low, close, volume, created_at, data_source)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (ticker, date) DO NOTHING
            """

            from psycopg2.extras import execute_batch
            execute_batch(cursor, insert_sql, records, page_size=self.config['database']['batch_size'])
            self.db_conn.commit()

            return len(records)

        except Exception as e:
            print(f"   [ERROR] DB write failed: {e}")
            return 0

    def run_parallel_stages(self, ticker: str, timeframe: str, df: pd.DataFrame) -> dict:
        """Run persistence stages in parallel."""
        print(f"\n   [STAGES] Running parallel persistence for {timeframe}...")
        start_time = time.time()

        # Prepare stage tasks
        def stage_file():
            path, size = self.save_to_file(ticker, timeframe, df)
            return 'file', path, size

        def stage_redis():
            success = self.write_to_redis(ticker, timeframe, df)
            return 'redis', success

        def stage_postgres():
            records = self.write_to_postgres(ticker, timeframe, df)
            return 'postgres', records

        # Run stages in parallel
        results = {}
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {
                executor.submit(stage_file): 'File Save',
                executor.submit(stage_redis): 'Redis Cache',
                executor.submit(stage_postgres): 'PostgreSQL'
            }

            for future in as_completed(futures):
                stage_name = futures[future]
                try:
                    result = future.result()
                    stage_type = result[0]

                    if stage_type == 'file':
                        _, path, size = result
                        if path:
                            print(f"      [OK] {stage_name:15s}: {size/1024:.1f} KB")
                            results['file'] = path
                        else:
                            print(f"      [SKIP] {stage_name:15s}: Disabled")
                    elif stage_type == 'redis':
                        _, success = result
                        if success:
                            print(f"      [OK] {stage_name:15s}: Cached")
                            results['redis'] = True
                        else:
                            print(f"      [SKIP] {stage_name:15s}: Not available")
                    elif stage_type == 'postgres':
                        _, records = result
                        if records > 0:
                            print(f"      [OK] {stage_name:15s}: {records:,} records inserted")
                            results['postgres'] = records
                        else:
                            print(f"      [SKIP] {stage_name:15s}: No data")

                except Exception as e:
                    print(f"      [ERROR] {futures[future]}: {e}")

        elapsed = time.time() - start_time
        print(f"   [TIME] Stages completed in {elapsed:.1f}s")
        return results

    def run(self):
        """Run AAPL download for all timeframes."""
        print("\n" + "="*70)
        print("PARALLEL STAGE DOWNLOADER - AAPL ONLY")
        print("="*70)

        ticker = "AAPL"
        print(f"\nDownloading: {ticker}")
        print(f"Config: {self.config_path}")
        print(f"Format: {self.config['download']['format']}")
        print(f"Stages: File → Redis → PostgreSQL (parallel)")

        # Initialize savepoint
        self.savepoint.initialize_ticker(ticker, list(self.config['timeframes'].keys()))

        # Connect
        if not self.connect_all():
            print("\n[ERROR] Connection failed. Aborting.")
            return False

        # Download each timeframe
        timeframes = list(self.config['timeframes'].keys())
        print(f"\n[DOWNLOAD] Processing {len(timeframes)} timeframes for {ticker}...")
        print("="*70)

        total_records = 0
        total_bytes = 0
        completed_timeframes = 0

        for timeframe in timeframes:
            self.savepoint.start_timeframe(ticker, timeframe)

            print(f"\n[{timeframe.upper():6s}] Downloading from IBKR...", end=" ", flush=True)
            start = time.time()

            df = self.download_data(ticker, timeframe)
            if df is None or df.empty:
                print(f"[EMPTY] (0 bars)")
                self.savepoint.fail_timeframe(ticker, timeframe, "No data returned")
                continue

            download_time = time.time() - start
            print(f"[OK] {len(df):,} bars ({download_time:.1f}s)")

            # Run parallel persistence stages
            results = self.run_parallel_stages(ticker, timeframe, df)

            # Mark as completed
            records = results.get('postgres', 0)
            bytes_written = results.get('file', 0) if isinstance(results.get('file'), int) else len(df) * 100
            if isinstance(results.get('file'), str):
                try:
                    bytes_written = Path(results['file']).stat().st_size
                except:
                    bytes_written = 0

            self.savepoint.complete_timeframe(ticker, timeframe, records=records, bytes_written=bytes_written)

            total_records += records
            total_bytes += bytes_written
            completed_timeframes += 1

            # Rate limiting - increase delay between requests to avoid IBKR throttling
            delay = max(3.0, self.config['performance']['rate_limit_ms'] / 1000)
            print(f"   [WAIT] {delay:.1f}s before next request...")
            time.sleep(delay)

        # Mark ticker as completed
        self.savepoint.complete_ticker(ticker)

        # Summary
        print("\n" + "="*70)
        print("[SUMMARY] AAPL Download Complete")
        print("="*70)
        print(f"\nTimeframes Completed: {completed_timeframes}/{len(timeframes)}")
        print(f"Total Records: {total_records:,}")
        print(f"Total File Size: {total_bytes / (1024*1024):.1f} MB")

        # Storage locations
        print(f"\nData Locations:")
        print(f"  Files:     ~/.tradingagents/data_downloads/AAPL/*/data_*.parquet")
        print(f"  Redis:     market_data:AAPL:* (4 keys)")
        print(f"  Database:  PostgreSQL tables")
        print(f"  Savepoint: ~/.tradingagents/download_status.json")

        self.savepoint.print_status()

        # Close connections
        if self.ib:
            self.ib.disconnect()
        if self.db_conn:
            self.db_conn.close()
        if self.redis_conn:
            self.redis_conn.close()

        print("[OK] All connections closed\n")
        return True


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Parallel stage downloader for AAPL")
    parser.add_argument("--config", default="download_config.yaml", help="Config file path")

    args = parser.parse_args()

    downloader = ParallelStageDownloader(args.config)
    success = downloader.run()

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
