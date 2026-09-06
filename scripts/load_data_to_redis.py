#!/usr/bin/env python3
"""
Load historical data from PostgreSQL into Redis for fast backtest access.
Aggregates 1-min bars into 5-min, 1-hour, and 1-day candles.
"""

import os
import sys
import psycopg2
import redis
import pandas as pd
from datetime import datetime, timedelta
import json

# Database config
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "postgres")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "admin")

# Redis config
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))

TICKERS = ["AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "TSLA", "AMD", "AVGO", "JPM", "GS", "SPY", "QQQ", "IWM", "DIA"]

class DataLoaderToRedis:
    """Load data from PostgreSQL to Redis."""

    def __init__(self):
        self.db_conn = None
        self.redis_conn = None

    def connect_db(self):
        """Connect to PostgreSQL."""
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
        print(f"[CONNECT] Connecting to Redis at {REDIS_HOST}:{REDIS_PORT}...")
        try:
            self.redis_conn = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)
            self.redis_conn.ping()
            print("[OK] Connected to Redis")
            return True
        except Exception as e:
            print(f"[ERROR] Redis connection failed: {e}")
            return False

    def load_1min_data(self, ticker):
        """Load 1-minute data from PostgreSQL."""
        query = f"""
            SELECT date, open, high, low, close, volume
            FROM historical_data_1min
            WHERE ticker = %s
            ORDER BY date ASC
        """
        cursor = self.db_conn.cursor()
        cursor.execute(query, (ticker,))
        rows = cursor.fetchall()
        cursor.close()

        if not rows:
            return None

        df = pd.DataFrame(rows, columns=['date', 'open', 'high', 'low', 'close', 'volume'])
        df['date'] = pd.to_datetime(df['date'])
        return df

    def aggregate_candles(self, df, period):
        """Aggregate 1-min candles into higher timeframes."""
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)

        agg_dict = {
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        }

        return df.resample(period).agg(agg_dict).dropna()

    def candle_to_dict(self, row):
        """Convert candle row to dictionary."""
        return {
            'open': float(row['open']),
            'high': float(row['high']),
            'low': float(row['low']),
            'close': float(row['close']),
            'volume': int(row['volume'])
        }

    def load_ticker_to_redis(self, ticker):
        """Load all timeframes for a ticker into Redis."""
        print(f"\n[LOAD] {ticker}")

        # Load 1-min data
        df_1min = self.load_1min_data(ticker)
        if df_1min is None:
            print(f"   [WARNING] No 1-min data found for {ticker}")
            return 0

        total_records = 0

        # Load 1-minute data
        print(f"   Loading 1-min bars...", end=" ", flush=True)
        for idx, row in df_1min.iterrows():
            timestamp = int(idx.timestamp())
            key = f"candles:1min:{ticker}:{timestamp}"
            candle_data = self.candle_to_dict(row)
            self.redis_conn.hset(key, mapping=candle_data)
            self.redis_conn.expire(key, 86400 * 30)  # Expire after 30 days
        print(f"[OK] {len(df_1min)} bars")
        total_records += len(df_1min)

        # Aggregate and load 5-minute data
        print(f"   Loading 5-min bars...", end=" ", flush=True)
        df_5min = self.aggregate_candles(df_1min, '5T')
        for idx, row in df_5min.iterrows():
            timestamp = int(idx.timestamp())
            key = f"candles:5min:{ticker}:{timestamp}"
            candle_data = self.candle_to_dict(row)
            self.redis_conn.hset(key, mapping=candle_data)
            self.redis_conn.expire(key, 86400 * 30)
        print(f"[OK] {len(df_5min)} bars")
        total_records += len(df_5min)

        # Aggregate and load 1-hour data
        print(f"   Loading 1-hour bars...", end=" ", flush=True)
        df_1h = self.aggregate_candles(df_1min, '1H')
        for idx, row in df_1h.iterrows():
            timestamp = int(idx.timestamp())
            key = f"candles:1h:{ticker}:{timestamp}"
            candle_data = self.candle_to_dict(row)
            self.redis_conn.hset(key, mapping=candle_data)
            self.redis_conn.expire(key, 86400 * 30)
        print(f"[OK] {len(df_1h)} bars")
        total_records += len(df_1h)

        # Aggregate and load 1-day data
        print(f"   Loading 1-day bars...", end=" ", flush=True)
        df_1d = self.aggregate_candles(df_1min, '1D')
        for idx, row in df_1d.iterrows():
            timestamp = int(idx.timestamp())
            key = f"candles:1d:{ticker}:{timestamp}"
            candle_data = self.candle_to_dict(row)
            self.redis_conn.hset(key, mapping=candle_data)
            self.redis_conn.expire(key, 86400 * 30)
        print(f"[OK] {len(df_1d)} bars")
        total_records += len(df_1d)

        return total_records

    def load_all(self):
        """Load all tickers to Redis."""
        if not self.connect_db():
            return False

        if not self.connect_redis():
            return False

        total_records = 0

        print(f"\n[DATA] Loading {len(TICKERS)} tickers into Redis...")
        print("="*60)

        for ticker in TICKERS:
            records = self.load_ticker_to_redis(ticker)
            total_records += records

        # Summary
        print("\n" + "="*60)
        print("[OK] LOAD COMPLETE!")
        print(f"Total records loaded: {total_records:,}")
        print("="*60)

        # Close connections
        if self.db_conn:
            self.db_conn.close()
        if self.redis_conn:
            self.redis_conn.close()

        return True

def main():
    """Main function."""
    print("\n[REDIS] Data Loader")
    print("="*60)
    print(f"Tickers: {len(TICKERS)}")
    print(f"PostgreSQL: {DB_USER}@{DB_HOST}:{DB_NAME}")
    print(f"Redis: {REDIS_HOST}:{REDIS_PORT}")
    print("="*60)

    loader = DataLoaderToRedis()
    loader.load_all()

if __name__ == "__main__":
    main()
