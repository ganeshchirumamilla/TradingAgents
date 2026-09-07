#!/usr/bin/env python3
"""
Load market data from PostgreSQL to Redis cache.
- Reads all available data per timeframe
- Stores in Redis with TTL
- Optimized for strategy execution
"""

import sys
import redis
import psycopg2
import pandas as pd
import json
from pathlib import Path
from datetime import datetime, timedelta
import logging

# Setup logging
log_file = Path.home() / ".tradingagents" / "download_logs" / f"redis_load_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
log_file.parent.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
fh = logging.FileHandler(log_file)
ch = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(levelname)-8s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
fh.setFormatter(formatter)
ch.setFormatter(formatter)
logger.addHandler(fh)
logger.addHandler(ch)


class PostgreSQLToRedisLoader:
    """Load PostgreSQL market data to Redis cache."""

    def __init__(self):
        self.pg_conn = None
        self.redis = None
        self.tables = {
            'daily': 'historical_data_daily',
            'hourly': 'historical_data_hourly',
            '5min': 'historical_data_5min',
            '1min': 'historical_data_1min',
        }
        # TTL for cache (in seconds)
        self.ttl = {
            'daily': 30 * 86400,      # 30 days
            'hourly': 7 * 86400,      # 7 days
            '5min': 2 * 86400,        # 2 days
            '1min': 1 * 86400,        # 1 day
        }

    def connect(self):
        """Connect to PostgreSQL and Redis."""
        try:
            self.pg_conn = psycopg2.connect(
                host="localhost", port=5433, database="postgres",
                user="postgres", password="admin"
            )
            logger.info("Connected to PostgreSQL")
        except Exception as e:
            logger.error(f"PostgreSQL connection failed: {e}")
            raise

        try:
            self.redis = redis.Redis(host='localhost', port=6379, password='admin', decode_responses=True)
            self.redis.ping()
            logger.info("Connected to Redis")
        except Exception as e:
            logger.error(f"Redis connection failed: {e}")
            raise

    def load_ticker_timeframe(self, ticker: str, timeframe: str) -> int:
        """Load data for a ticker/timeframe combo to Redis."""
        table = self.tables[timeframe]

        try:
            # Query data from PostgreSQL
            query = f"""
                SELECT date, open, high, low, close, volume
                FROM {table}
                WHERE ticker = %s
                ORDER BY date ASC
            """

            df = pd.read_sql(query, self.pg_conn, params=(ticker,))

            if len(df) == 0:
                logger.info(f"  [{timeframe.upper()}] No data found for {ticker}")
                return 0

            # Convert to JSON-serializable format
            data = {
                'ticker': ticker,
                'timeframe': timeframe,
                'count': len(df),
                'min_date': str(df['date'].min()),
                'max_date': str(df['date'].max()),
                'bars': df.to_dict(orient='records')
            }

            # Convert numpy/datetime objects to strings
            for bar in data['bars']:
                bar['date'] = str(bar['date'])

            # Store in Redis
            key = f"market_data:{ticker}:{timeframe}"
            self.redis.setex(key, self.ttl[timeframe], json.dumps(data))

            logger.info(f"  [{timeframe.upper()}] Loaded {len(df)} bars ({df['date'].min()} to {df['date'].max()})")

            return len(df)

        except Exception as e:
            logger.error(f"  [{timeframe.upper()}] Failed to load {ticker}: {e}")
            return 0

    def get_available_tickers(self) -> list:
        """Get list of available tickers from PostgreSQL (all tables)."""
        try:
            with self.pg_conn.cursor() as cur:
                # Get unique tickers from all tables
                cur.execute("""
                    SELECT DISTINCT ticker FROM (
                        SELECT DISTINCT ticker FROM historical_data_daily
                        UNION
                        SELECT DISTINCT ticker FROM historical_data_hourly
                        UNION
                        SELECT DISTINCT ticker FROM historical_data_5min
                        UNION
                        SELECT DISTINCT ticker FROM historical_data_1min
                    ) all_tickers
                    ORDER BY ticker
                """)
                tickers = [row[0] for row in cur.fetchall()]
                return tickers
        except Exception as e:
            logger.error(f"Failed to get tickers: {e}")
            return []

    def load_all(self):
        """Load all available data to Redis."""
        logger.info("=" * 70)
        logger.info("LOADING POSTGRESQL TO REDIS")
        logger.info("=" * 70)
        logger.info("")

        # Get available tickers
        tickers = self.get_available_tickers()
        logger.info(f"Found {len(tickers)} tickers: {', '.join(tickers)}")
        logger.info("")

        total_records = 0

        # Load data for each ticker/timeframe
        for ticker in tickers:
            logger.info(f"[{ticker}]")
            for timeframe in ['daily', 'hourly', '5min', '1min']:
                records = self.load_ticker_timeframe(ticker, timeframe)
                total_records += records
            logger.info("")

        logger.info("=" * 70)
        logger.info(f"LOAD COMPLETE: {total_records} total records cached")
        logger.info("=" * 70)

    def close(self):
        """Close connections."""
        if self.pg_conn:
            self.pg_conn.close()


if __name__ == "__main__":
    loader = PostgreSQLToRedisLoader()
    try:
        loader.connect()
        loader.load_all()
    finally:
        loader.close()
