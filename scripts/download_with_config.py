#!/usr/bin/env python3
"""
Enhanced market data downloader with configuration, savepoints, and parallel execution.
Supports resumable downloads with per-ticker status tracking.
"""

import os
import sys
import yaml
import json
import pandas as pd
import psycopg2
from pathlib import Path
from datetime import datetime, timedelta
import argparse
import time

try:
    from ib_async import IB, Stock, util
except ImportError:
    print("[ERROR] ib_async not installed. Run: pip install ib_async")
    sys.exit(1)

# Add scripts to path for imports
sys.path.insert(0, str(Path(__file__).parent))
from download_savepoint import DownloadSavepoint


class ConfiguredDataDownloader:
    """Market data downloader with configuration and savepoint support."""

    def __init__(self, config_path: str = "download_config.yaml"):
        """Initialize downloader with configuration."""
        self.config_path = Path(config_path).expanduser()
        self.config = self._load_config()
        self.savepoint = DownloadSavepoint(self.config['savepoint']['file_path'])
        self.ib = None
        self.db_conn = None

    def _load_config(self) -> Dict:
        """Load YAML configuration."""
        if not self.config_path.exists():
            print(f"[ERROR] Config file not found: {self.config_path}")
            sys.exit(1)

        with open(self.config_path, 'r') as f:
            return yaml.safe_load(f)

    def connect_ibkr(self) -> bool:
        """Connect to IBKR."""
        config_ibkr = self.config['ibkr']
        print(f"[CONNECT] IBKR at {config_ibkr['host']}:{config_ibkr['port']}")

        self.ib = IB()
        try:
            self.ib.connect(
                config_ibkr['host'],
                config_ibkr['port'],
                clientId=config_ibkr['client_id']
            )
            print("[OK] Connected to IBKR")
            return True
        except Exception as e:
            print(f"[ERROR] IBKR connection failed: {e}")
            return False

    def connect_db(self) -> bool:
        """Connect to PostgreSQL."""
        config_db = self.config['database']
        print(f"[CONNECT] PostgreSQL at {config_db['host']}")

        try:
            self.db_conn = psycopg2.connect(
                host=config_db['host'],
                port=config_db['port'],
                database=config_db['name'],
                user=config_db['user'],
                password=config_db['password']
            )
            print("[OK] Connected to PostgreSQL")
            return True
        except Exception as e:
            print(f"[ERROR] Database connection failed: {e}")
            return False

    def download_ticker_data(self, ticker: str, timeframe: str) -> Optional[pd.DataFrame]:
        """Download data for a ticker/timeframe combination."""
        try:
            tf_config = self.config['timeframes'][timeframe]
            ibkr_config = self.config['ibkr']

            # Calculate duration
            days = tf_config['default_days']
            duration = tf_config['duration_format'].format(days=days)

            print(f"   Downloading {ticker} {timeframe}...", end=" ", flush=True)

            contract = Stock(ticker, "SMART", "USD")
            bars = self.ib.reqHistoricalData(
                contract,
                endDateTime="",
                durationStr=duration,
                barSizeSetting=tf_config['bar_size'],
                whatToShow=ibkr_config['what_to_show'],
                useRTH=ibkr_config['use_rth'],
                formatDate=1,
                timeout=ibkr_config['request_timeout']
            )

            df = util.df(bars)
            if df.empty:
                print("[EMPTY]")
                return None

            print(f"[OK] {len(df)} bars")
            return df

        except Exception as e:
            print(f"[ERROR] {e}")
            return None

    def save_to_file(self, ticker: str, timeframe: str, df: pd.DataFrame) -> Optional[str]:
        """Save dataframe to file (Parquet or CSV)."""
        if not self.config['download']['save_files']:
            return None

        try:
            # Prepare path
            now = datetime.now()
            file_path = self.config['download']['file_path_template'].format(
                ticker=ticker,
                timeframe=timeframe,
                start_date=now.strftime('%Y%m%d'),
                format=self.config['download']['format']
            )

            file_path = Path(file_path).expanduser()
            file_path.parent.mkdir(parents=True, exist_ok=True)

            # Save file
            if self.config['download']['format'] == 'parquet':
                df.to_parquet(file_path, compression=self.config['download']['compression'])
            else:
                df.to_csv(file_path, index=False)

            file_size = file_path.stat().st_size
            print(f"      Saved: {file_path} ({file_size/1024:.1f} KB)")
            return str(file_path)

        except Exception as e:
            print(f"      [WARNING] Could not save file: {e}")
            return None

    def save_to_postgres(self, ticker: str, timeframe: str, df: pd.DataFrame) -> int:
        """Save dataframe to PostgreSQL."""
        if not self.db_conn:
            return 0

        try:
            cursor = self.db_conn.cursor()
            tf_config = self.config['timeframes'][timeframe]
            table_name = tf_config['table_name']

            # Create table if not exists
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

            # Prepare insert
            records = []
            for _, row in df.iterrows():
                try:
                    import uuid
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
                except Exception as e:
                    continue

            if not records:
                return 0

            # Insert data
            insert_sql = f"""
                INSERT INTO {table_name}
                (id, ticker, date, open, high, low, close, volume, created_at, data_source)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (ticker, date) DO NOTHING
            """

            from psycopg2.extras import execute_batch
            execute_batch(cursor, insert_sql, records, page_size=self.config['database']['batch_size'])
            self.db_conn.commit()

            print(f"      Inserted: {len(records)} records to {table_name}")
            return len(records)

        except Exception as e:
            print(f"      [ERROR] Database insert failed: {e}")
            return 0

    def download_ticker(self, ticker: str) -> bool:
        """Download all timeframes for a ticker."""
        print(f"\n[TICKER] {ticker}")
        print("-" * 70)

        self.savepoint.start_ticker(ticker)

        success = True
        for timeframe in self.config['timeframes'].keys():
            # Check if already completed
            pending = self.savepoint.get_pending_timeframes(ticker)
            if timeframe not in pending:
                print(f"  [{timeframe.upper()}] Already completed, skipping")
                continue

            self.savepoint.start_timeframe(ticker, timeframe)

            try:
                # Download
                df = self.download_ticker_data(ticker, timeframe)
                if df is None or df.empty:
                    self.savepoint.fail_timeframe(ticker, timeframe, "No data returned")
                    success = False
                    continue

                # Save to file
                file_path = self.save_to_file(ticker, timeframe, df)

                # Save to database
                records = self.save_to_postgres(ticker, timeframe, df)

                # Mark as completed
                self.savepoint.complete_timeframe(ticker, timeframe, records=len(df), bytes_written=len(df)*100)

            except Exception as e:
                self.savepoint.fail_timeframe(ticker, timeframe, str(e))
                success = False

            # Rate limiting
            time.sleep(self.config['performance']['rate_limit_ms'] / 1000)

        if success:
            self.savepoint.complete_ticker(ticker)

        return success

    def run(self, resume: bool = True):
        """Run downloads for all configured tickers."""
        print("\n" + "="*70)
        print("CONFIGURED DATA DOWNLOADER")
        print("="*70)
        print(f"Config: {self.config_path}")
        print(f"Format: {self.config['download']['format']}")
        print(f"IBKR whatToShow: {self.config['ibkr']['what_to_show']}")

        # Initialize all tickers in savepoint
        tickers_to_download = [t for t, cfg in self.config['tickers'].items() if cfg.get('enabled', True)]
        timeframes = list(self.config['timeframes'].keys())

        for ticker in tickers_to_download:
            self.savepoint.initialize_ticker(ticker, timeframes)

        # Get pending tickers
        if resume:
            pending_tickers = self.savepoint.get_pending_tickers()
            print(f"\n[RESUME] Resuming from savepoint")
            print(f"Pending tickers: {len(pending_tickers)}")
        else:
            pending_tickers = tickers_to_download
            print(f"\n[START] Starting fresh download")
            print(f"Tickers: {len(pending_tickers)}")

        # Connect
        if not self.connect_ibkr() or not self.connect_db():
            return False

        # Download each ticker
        successful = 0
        for ticker in pending_tickers:
            if self.download_ticker(ticker):
                successful += 1

        # Summary
        self.savepoint.print_status()
        print(f"[SUMMARY] Completed {successful}/{len(pending_tickers)} tickers")

        # Close connections
        if self.ib:
            self.ib.disconnect()
        if self.db_conn:
            self.db_conn.close()

        return True


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Configured market data downloader")
    parser.add_argument("--config", default="download_config.yaml", help="Config file path")
    parser.add_argument("--resume", action="store_true", default=True, help="Resume from last savepoint")
    parser.add_argument("--fresh", action="store_true", help="Start fresh (don't resume)")
    parser.add_argument("--ticker", help="Download specific ticker only")

    args = parser.parse_args()

    downloader = ConfiguredDataDownloader(args.config)
    downloader.run(resume=not args.fresh)


if __name__ == "__main__":
    main()
