#!/usr/bin/env python3
"""
Simple, robust AAPL downloader for all 4 timeframes.
Processes one timeframe at a time with fresh connections.
"""

import sys
import time
import pandas as pd
import psycopg2
import redis
import json
import uuid
from pathlib import Path
from datetime import datetime
import yaml

try:
    from ib_async import IB, Stock, util
except ImportError:
    print("[ERROR] ib_async not installed")
    sys.exit(1)


class SimpleAAAPLDownloader:
    """Simple downloader for AAPL across all timeframes."""

    def __init__(self, config_path: str = "download_config.yaml"):
        self.config_path = Path(config_path).expanduser()
        self.config = self._load_config()
        self.db_conn = None
        self.redis_conn = None

    def _load_config(self) -> dict:
        """Load configuration."""
        with open(self.config_path, 'r') as f:
            return yaml.safe_load(f)

    def connect_db(self) -> bool:
        """Connect to PostgreSQL."""
        try:
            db_cfg = self.config['database']
            self.db_conn = psycopg2.connect(
                host=db_cfg['host'],
                port=db_cfg['port'],
                database=db_cfg['name'],
                user=db_cfg['user'],
                password=db_cfg['password']
            )
            print("[OK] PostgreSQL connected")
            return True
        except Exception as e:
            print(f"[ERROR] PostgreSQL: {e}")
            return False

    def connect_redis(self) -> bool:
        """Connect to Redis."""
        if not self.config['redis']['enabled']:
            print("[SKIP] Redis disabled")
            return False

        try:
            self.redis_conn = redis.Redis(
                host=self.config['redis']['host'],
                port=self.config['redis']['port'],
                db=self.config['redis']['db'],
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5
            )
            self.redis_conn.ping()
            print("[OK] Redis connected")
            return True
        except Exception as e:
            print(f"[WARNING] Redis unavailable: {e}")
            self.redis_conn = None
            return False

    def download_timeframe(self, ticker: str, timeframe: str, client_id: int = 1) -> pd.DataFrame:
        """Download single timeframe using fresh connection."""
        print(f"\n[{timeframe.upper():6s}] Connecting to IBKR...", end=" ", flush=True)
        ib = IB()

        try:
            ibkr_cfg = self.config['ibkr']
            ib.connect(ibkr_cfg['host'], ibkr_cfg['port'], clientId=client_id)
            print("[OK]")

            tf_cfg = self.config['timeframes'][timeframe]
            print(f"           Downloading {tf_cfg['bar_size']} bars ({tf_cfg['default_days']} days)...", end=" ", flush=True)

            contract = Stock(ticker, "SMART", "USD")
            bars = ib.reqHistoricalData(
                contract,
                endDateTime="",
                durationStr=f"{tf_cfg['default_days']} D",
                barSizeSetting=tf_cfg['bar_size'],
                whatToShow=ibkr_cfg['what_to_show'],
                useRTH=ibkr_cfg['use_rth'],
                formatDate=1,
                timeout=90
            )

            if bars is None:
                print("[EMPTY]")
                return None

            df = util.df(bars)
            if df.empty:
                print("[EMPTY]")
                return None

            print(f"[OK] {len(df):,} bars")
            return df

        except Exception as e:
            print(f"[ERROR] {str(e)[:50]}")
            return None

        finally:
            try:
                ib.disconnect()
            except:
                pass

    def save_to_file(self, ticker: str, timeframe: str, df: pd.DataFrame) -> bool:
        """Save to Parquet file."""
        if not self.config['download']['save_files']:
            return False

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

            if self.config['download']['format'] == 'parquet':
                df.to_parquet(file_path, compression=self.config['download']['compression'])
            else:
                df.to_csv(file_path, index=False)

            size_kb = file_path.stat().st_size / 1024
            print(f"           File saved: {size_kb:.1f} KB")
            return True

        except Exception as e:
            print(f"           File save failed: {e}")
            return False

    def save_to_redis(self, ticker: str, timeframe: str, df: pd.DataFrame) -> bool:
        """Save to Redis."""
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

            print(f"           Redis cached: {len(records)} records")
            return True

        except Exception as e:
            print(f"           Redis cache failed: {e}")
            return False

    def save_to_postgres(self, ticker: str, timeframe: str, df: pd.DataFrame) -> int:
        """Save to PostgreSQL."""
        if not self.db_conn:
            return 0

        try:
            cursor = self.db_conn.cursor()
            tf_cfg = self.config['timeframes'][timeframe]
            table_name = tf_cfg['table_name']

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
            from psycopg2.extras import execute_batch
            insert_sql = f"""
                INSERT INTO {table_name}
                (id, ticker, date, open, high, low, close, volume, created_at, data_source)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (ticker, date) DO NOTHING
            """

            execute_batch(cursor, insert_sql, records, page_size=1000)
            self.db_conn.commit()

            print(f"           Database: {len(records):,} records inserted")
            return len(records)

        except Exception as e:
            print(f"           Database write failed: {e}")
            return 0

    def run(self):
        """Run the download."""
        print("\n" + "="*70)
        print("SIMPLE AAPL DOWNLOADER - ALL 4 TIMEFRAMES")
        print("="*70)

        # Setup
        print("\n[SETUP] Establishing connections...")
        self.connect_db()
        self.connect_redis()

        ticker = "AAPL"
        timeframes = list(self.config['timeframes'].keys())
        total_records = 0

        print(f"\n[DOWNLOAD] Processing {len(timeframes)} timeframes...")
        print("="*70)

        for i, timeframe in enumerate(timeframes, 1):
            print(f"\n[{i}/{len(timeframes)}] {timeframe.upper()}")

            # Download with unique client ID
            df = self.download_timeframe(ticker, timeframe, client_id=10+i)
            if df is None or df.empty:
                continue

            # Persist in sequence (not parallel)
            self.save_to_file(ticker, timeframe, df)
            self.save_to_redis(ticker, timeframe, df)
            records = self.save_to_postgres(ticker, timeframe, df)
            total_records += records

            # Rate limiting
            if i < len(timeframes):
                print(f"           Waiting 5s before next timeframe...")
                time.sleep(5)

        # Summary
        print("\n" + "="*70)
        print("[COMPLETE] Download Summary")
        print("="*70)
        print(f"Timeframes: {len(timeframes)}")
        print(f"Total Records: {total_records:,}")
        print(f"Data Locations:")
        print(f"  Files:  ~/.tradingagents/data_downloads/AAPL/*/data_*.parquet")
        print(f"  Redis:  market_data:AAPL:* (4 keys)")
        print(f"  DB:     historical_data_* tables")
        print("="*70 + "\n")

        # Cleanup
        if self.db_conn:
            self.db_conn.close()
        if self.redis_conn:
            self.redis_conn.close()


if __name__ == "__main__":
    downloader = SimpleAAAPLDownloader("download_config.yaml")
    downloader.run()
