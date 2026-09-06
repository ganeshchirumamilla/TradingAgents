#!/usr/bin/env python3
"""
Download market data from IBKR with multiple bar intervals and persist to PostgreSQL.

Usage:
    python download_ibkr_multibar_data.py --intervals "1 min,5 mins,1 hour,1 day" --days 90
    python download_ibkr_multibar_data.py --intervals "5 mins" --days 365
    python download_ibkr_multibar_data.py --intervals "1 min" --days 30

Default: downloads daily + hourly data for 2 years
"""

import os
import sys
from datetime import datetime, timedelta
import pandas as pd
import psycopg2
from psycopg2.extras import execute_batch
import uuid
from pathlib import Path
import argparse
import json

# IBKR imports (requires: pip install ib_async)
try:
    from ib_async import *
except ImportError:
    print("[ERROR] ib_async not installed. Run: pip install ib_async")
    sys.exit(1)

# Redis import (optional)
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

# Configuration
TICKERS = ["AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "TSLA", "AMD", "AVGO", "JPM", "GS", "SPY", "QQQ", "IWM", "DIA"]

# All available bar configurations
ALL_BAR_CONFIGS = {
    "1 day": {
        "name": "daily",
        "bar_size": "1 day",
        "what_to_show": "TRADES",
        "default_duration": "20 Y",
        "keep_up_to_date": False,
    },
    "1 hour": {
        "name": "hourly",
        "bar_size": "1 hour",
        "what_to_show": "TRADES",
        "default_duration": "2 Y",
        "keep_up_to_date": False,
    },
    "5 mins": {
        "name": "5min",
        "bar_size": "5 mins",
        "what_to_show": "TRADES",
        "default_duration": "1 Y",
        "keep_up_to_date": False,
    },
    "1 min": {
        "name": "1min",
        "bar_size": "1 min",
        "what_to_show": "TRADES",
        "default_duration": "3 M",
        "keep_up_to_date": False,
    },
}

# Database configuration
DB_HOST = os.getenv("DB_HOST", "localhost")  # Use localhost for Docker
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "postgres")  # Default postgres database
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "admin")

# IBKR configuration
IBKR_HOST = os.getenv("TRADINGAGENTS_IBKR_HOST", "127.0.0.1")
IBKR_PORT = int(os.getenv("TRADINGAGENTS_IBKR_PORT", "4002"))
IBKR_CLIENT_ID = int(os.getenv("TRADINGAGENTS_IBKR_CLIENT_ID", "1"))

# Redis configuration
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))

# Cache directory
CACHE_DIR = os.path.expanduser("~/.tradingagents/data_cache_multibar")

class IBKRDataDownloader:
    """Download historical data from Interactive Brokers."""

    def __init__(self):
        self.ib = None
        self.db_conn = None
        self.redis_conn = None

    def connect_ibkr(self):
        """Connect to IBKR API."""
        print(f"[CONNECT] Connecting to IBKR at {IBKR_HOST}:{IBKR_PORT}...")
        self.ib = IB()
        try:
            self.ib.connect(IBKR_HOST, IBKR_PORT, clientId=IBKR_CLIENT_ID)
            print("[OK] Connected to IBKR")
            return True
        except Exception as e:
            print(f"[ERROR] IBKR connection failed: {e}")
            return False

    def connect_db(self):
        """Connect to PostgreSQL database."""
        print(f"[CONNECT] Connecting to PostgreSQL at {DB_HOST}:{DB_PORT}...")
        try:
            self.db_conn = psycopg2.connect(
                host=DB_HOST,
                port=DB_PORT,
                database=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD
            )
            print("[OK] Connected to PostgreSQL")
            return True
        except Exception as e:
            print(f"[ERROR] Database connection failed: {e}")
            return False

    def connect_redis(self):
        """Connect to Redis."""
        if not REDIS_AVAILABLE:
            print("[WARNING] Redis not available (python-redis not installed)")
            return False

        print(f"[CONNECT] Connecting to Redis at {REDIS_HOST}:{REDIS_PORT}...")
        try:
            self.redis_conn = redis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                db=REDIS_DB,
                decode_responses=True
            )
            self.redis_conn.ping()
            print("[OK] Connected to Redis")
            return True
        except Exception as e:
            print(f"[WARNING] Redis connection failed: {e} (continuing without Redis)")
            self.redis_conn = None
            return False

    def create_cache_dir(self):
        """Create cache directory."""
        Path(CACHE_DIR).mkdir(parents=True, exist_ok=True)

    def download_historical_data(self, ticker, bar_config):
        """Download historical data for a ticker with specific bar size."""
        try:
            # Create contract
            contract = Stock(ticker, "SMART", "USD")

            # Request historical data
            print(f"   Downloading {ticker} {bar_config['name']} bars...", end=" ", flush=True)

            bars = self.ib.reqHistoricalData(
                contract,
                endDateTime="",  # Today
                durationStr=bar_config['duration'],
                barSizeSetting=bar_config['bar_size'],
                whatToShow=bar_config['what_to_show'],
                useRTH=True,
                formatDate=1,
                keepUpToDate=bar_config['keep_up_to_date'],
                timeout=60
            )

            # Convert to DataFrame
            df = util.df(bars)
            if df.empty:
                print(f"[WARNING]  No data")
                return None

            print(f"[OK] {len(df)} bars")
            return df

        except Exception as e:
            print(f"[ERROR] Error: {e}")
            return None

    def save_to_cache(self, ticker, bar_config, df):
        """Save data to CSV cache."""
        ticker_dir = os.path.join(CACHE_DIR, ticker, bar_config['name'])
        Path(ticker_dir).mkdir(parents=True, exist_ok=True)

        cache_file = os.path.join(ticker_dir, "data.csv")
        try:
            df.to_csv(cache_file, index=False)
            return True
        except Exception as e:
            print(f"[ERROR] Error saving cache: {e}")
            return False

    def save_to_redis(self, ticker, bar_config, df):
        """Save data to Redis with volume data."""
        if not self.redis_conn:
            return False

        try:
            # Create a key for this ticker/timeframe combination
            redis_key = f"market_data:{ticker}:{bar_config['name']}"

            # Convert dataframe to list of dicts with volume included
            records = []
            for _, row in df.iterrows():
                record = {
                    'date': str(row['date']),
                    'open': float(row['open']),
                    'high': float(row['high']),
                    'low': float(row['low']),
                    'close': float(row['close']),
                    'volume': int(row['volume']) if pd.notna(row['volume']) else 0,
                    'barCount': int(row['barCount']) if 'barCount' in row and pd.notna(row['barCount']) else -1,
                }
                records.append(record)

            # Store as JSON in Redis
            redis_data = json.dumps(records)
            self.redis_conn.set(redis_key, redis_data)
            self.redis_conn.expire(redis_key, 86400 * 7)  # Expire after 7 days

            return True
        except Exception as e:
            print(f"[WARNING] Error saving to Redis: {e}")
            return False

    def insert_to_postgres(self, ticker, bar_config, df):
        """Insert data into PostgreSQL."""
        cursor = self.db_conn.cursor()

        # Create table if not exists
        table_name = f"historical_data_{bar_config['name']}"
        create_table_sql = f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                id UUID PRIMARY KEY,
                ticker VARCHAR(20) NOT NULL,
                date TIMESTAMP NOT NULL,
                open DECIMAL(10,4) NOT NULL,
                high DECIMAL(10,4) NOT NULL,
                low DECIMAL(10,4) NOT NULL,
                close DECIMAL(10,4) NOT NULL,
                volume BIGINT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                data_source VARCHAR(50),
                UNIQUE(ticker, date)
            );
            CREATE INDEX IF NOT EXISTS idx_{table_name}_ticker ON {table_name}(ticker);
            CREATE INDEX IF NOT EXISTS idx_{table_name}_date ON {table_name}(date DESC);
        """

        try:
            cursor.execute(create_table_sql)
            self.db_conn.commit()
        except Exception as e:
            print(f"[ERROR] Error creating table: {e}")
            return 0

        # Prepare data
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

        try:
            execute_batch(cursor, insert_sql, records, page_size=1000)
            self.db_conn.commit()
            return len(records)
        except Exception as e:
            self.db_conn.rollback()
            print(f"[ERROR] Error inserting data: {e}")
            return 0

    def download_all(self, bar_configs):
        """Download data for all tickers and bar intervals."""

        if not self.connect_ibkr():
            return False

        if not self.connect_db():
            return False

        # Try to connect to Redis (optional)
        self.connect_redis()

        self.create_cache_dir()

        total_records = {}
        redis_stored = {}
        for bar_size, bar_config in bar_configs.items():
            total_records[bar_config['name']] = 0
            redis_stored[bar_config['name']] = 0

        print(f"\n[DATA] Downloading data for {len(TICKERS)} tickers with {len(bar_configs)} bar intervals...")
        print("="*60)

        for ticker in TICKERS:
            print(f"\n[DOWNLOAD] {ticker}")
            for bar_size, bar_config in bar_configs.items():
                df = self.download_historical_data(ticker, bar_config)

                if df is not None:
                    # Save to cache
                    self.save_to_cache(ticker, bar_config, df)

                    # Insert to database
                    inserted = self.insert_to_postgres(ticker, bar_config, df)
                    total_records[bar_config['name']] += inserted

                    # Save to Redis
                    if self.redis_conn and self.save_to_redis(ticker, bar_config, df):
                        redis_stored[bar_config['name']] += 1

        # Close connections
        if self.ib:
            self.ib.disconnect()
        if self.db_conn:
            self.db_conn.close()
        if self.redis_conn:
            self.redis_conn.close()

        # Summary
        print("\n" + "="*60)
        print("[OK] DOWNLOAD COMPLETE!")
        print("\nRecords inserted by interval (PostgreSQL):")
        grand_total = 0
        for interval, count in total_records.items():
            print(f"   {interval:10s}: {count:,} records")
            grand_total += count
        print(f"\n   {'TOTAL':10s}: {grand_total:,} records")

        if self.redis_conn:
            print("\nTickers stored in Redis by interval:")
            for interval, count in redis_stored.items():
                print(f"   {interval:10s}: {count} tickers")

        print("="*60)

        return True

def main():
    """Main function with argument parsing."""
    parser = argparse.ArgumentParser(
        description="Download IBKR data with specified bar intervals and date range",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Download 1-min and 5-min bars for last 90 days
  python download_ibkr_multibar_data.py --intervals "1 min,5 mins" --days 90

  # Download 5-min bars for last year
  python download_ibkr_multibar_data.py --intervals "5 mins" --days 365

  # Download 1-min bars for last month only
  python download_ibkr_multibar_data.py --intervals "1 min" --days 30

  # Download daily + hourly (default)
  python download_ibkr_multibar_data.py
        """
    )

    parser.add_argument(
        "--intervals",
        type=str,
        default="1 day,1 hour",
        help='Comma-separated list of bar intervals (default: "1 day,1 hour"). '
             'Options: "1 min", "5 mins", "1 hour", "1 day"'
    )
    parser.add_argument(
        "--days",
        type=int,
        default=None,
        help="Number of days to download (overrides default durations). "
             "IBKR limits: 1-min (few months), 5-min (~1 year), hourly (~2 years), daily (20 years)"
    )
    parser.add_argument(
        "--no-confirm",
        action="store_true",
        help="Skip confirmation prompt"
    )

    args = parser.parse_args()

    # Convert days to duration string
    def days_to_duration(days):
        if days <= 7:
            return f"{days} D"
        elif days <= 30:
            return f"{days // 7} W"
        elif days <= 365:
            return f"{days // 30} M"
        else:
            return f"{days // 365} Y"

    # Parse requested intervals
    requested_intervals = [i.strip() for i in args.intervals.split(",")]

    # Build bar configs for requested intervals
    bar_configs = {}
    for interval in requested_intervals:
        if interval in ALL_BAR_CONFIGS:
            config = ALL_BAR_CONFIGS[interval].copy()
            # Override duration if --days specified
            if args.days:
                config['duration'] = days_to_duration(args.days)
            else:
                config['duration'] = config['default_duration']
            bar_configs[interval] = config
        else:
            print(f"[ERROR] Unknown interval: {interval}")
            print(f"   Available: {', '.join(ALL_BAR_CONFIGS.keys())}")
            return

    print("\n[IBKR] Multi-Bar Historical Data Downloader")
    print("="*60)
    print(f"Tickers: {', '.join(TICKERS)}")
    print(f"Bar intervals: {', '.join(bar_configs.keys())}")
    print(f"Date range: {', '.join(f'{v['duration']}' for v in bar_configs.values())}")
    print(f"Database: {DB_USER}@{DB_HOST}:{DB_NAME}")
    print("="*60)

    print("\n[WARNING]  PRE-FLIGHT CHECKS:")
    print("[CHECK] Make sure IBKR TWS/Gateway is running and API is enabled")
    print("[CHECK] Make sure PostgreSQL is running")
    print("[CHECK] Make sure you have sufficient data available in IBKR")

    estimated_time = len(bar_configs) * 3  # ~3 min per interval per ticker
    print(f"\nEstimated time: {estimated_time}-{estimated_time*2} minutes")
    print(f"Estimated storage: {len(bar_configs)*10} MB-{len(bar_configs)*100} MB per interval in PostgreSQL")

    if not args.no_confirm:
        response = input("\nContinue? (yes/no): ").strip().lower()
        if response != "yes":
            print("Aborted.")
            return

    print("\n[OK] Starting download...")
    downloader = IBKRDataDownloader()
    downloader.download_all(bar_configs)

if __name__ == "__main__":
    main()
