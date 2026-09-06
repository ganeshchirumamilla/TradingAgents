#!/usr/bin/env python3
"""
Daily data pipeline: Download, purge, cache to Redis.
Designed to run daily as a Docker container.

Workflow:
1. Download new data from IBKR (incremental)
2. Purge old data based on retention policy
3. Load hot data to Redis cache
4. Report status
"""

import os
import sys
import logging
from datetime import datetime, timedelta
import psycopg2
from psycopg2.extras import execute_batch
import redis
import json
import uuid

# Fix encoding for Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# Configure logging
import os as _os
_log_dir = os.getenv("LOG_DIR", "./logs")
_os.makedirs(_log_dir, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join(_log_dir, 'daily_pipeline.log'), mode='a', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# Configuration
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "tradingagents")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "admin")

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

TICKERS = ["AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "TSLA", "AMD", "AVGO", "JPM", "GS", "SPY", "QQQ", "IWM", "DIA"]

# Data retention policy (days)
RETENTION_POLICY = {
    "historical_data_daily": 3650,      # Keep daily for 10 years
    "historical_data_hourly": 1095,     # Keep hourly for 3 years
    "historical_data_5min": 365,        # Keep 5-min for 1 year
    "historical_data_1min": 90,         # Keep 1-min for 90 days
}

# Redis cache policy (what to load to Redis)
REDIS_CACHE_POLICY = {
    "daily": {
        "table": "historical_data_daily",
        "days": 3650,  # Load all daily bars
        "ttl": 86400 * 30,  # 30-day TTL in Redis
    },
    "hourly": {
        "table": "historical_data_hourly",
        "days": 1095,  # Load 3 years of hourly
        "ttl": 86400 * 7,  # 7-day TTL
    },
    "5min": {
        "table": "historical_data_5min",
        "days": 365,   # Load 1 year of 5-min
        "ttl": 86400,  # 1-day TTL
    },
    "1min": {
        "table": "historical_data_1min",
        "days": 365,   # Load 1 year of 1-min (or what's available)
        "ttl": 3600,   # 1-hour TTL
    },
}

class DailyDataPipeline:
    """Orchestrate daily data pipeline."""

    def __init__(self):
        self.db_conn = None
        self.redis_conn = None
        self.start_time = datetime.now()
        self.stats = {
            "downloaded": 0,
            "purged": 0,
            "cached": 0,
            "errors": 0,
        }

    def connect_db(self):
        """Connect to PostgreSQL."""
        try:
            self.db_conn = psycopg2.connect(
                host=DB_HOST,
                port=DB_PORT,
                database=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD
            )
            logger.info("✅ Connected to PostgreSQL")
            return True
        except psycopg2.Error as e:
            logger.error(f"❌ PostgreSQL connection failed: {e}")
            return False

    def connect_redis(self):
        """Connect to Redis."""
        try:
            # Try direct connection first
            try:
                self.redis_conn = redis.from_url(REDIS_URL, decode_responses=True)
                self.redis_conn.ping()
                logger.info("[OK] Connected to Redis")
                return True
            except redis.AuthenticationError:
                # If URL auth fails, try with explicit password
                logger.warning("[WARN] URL authentication failed, trying explicit password...")
                # Extract password from URL or use env var
                redis_password = os.getenv("REDIS_PASSWORD", "admin")
                self.redis_conn = redis.Redis(
                    host='localhost',
                    port=6379,
                    db=0,
                    password=redis_password,
                    decode_responses=True
                )
                self.redis_conn.ping()
                logger.info("[OK] Connected to Redis with explicit password")
                return True
        except Exception as e:
            logger.error(f"[ERROR] Redis connection failed: {e}")
            logger.warning("[WARN] Continuing without Redis caching...")
            self.redis_conn = None
            return False

    def download_incremental_data(self):
        """
        Download new data from IBKR.
        This is a placeholder - in production, would use ib_async.
        For now, it checks if data needs updating.
        """
        logger.info("\n[PHASE 1] Download Incremental Data")
        logger.info("="*60)

        try:
            # In production, this would:
            # 1. Check last bar date for each ticker/interval
            # 2. Download only new bars from IBKR
            # 3. Insert into PostgreSQL
            # 4. Return count of new records

            logger.info("⚠️  Incremental download requires IBKR connection")
            logger.info("   Would download: last business day bars for all tickers")
            logger.info("   Tables: daily, hourly, 5min, 1min")

            # For now, just report
            logger.info("✅ Incremental download ready (needs IBKR)")

            return True

        except Exception as e:
            logger.error(f"❌ Download failed: {e}")
            self.stats["errors"] += 1
            return False

    def purge_old_data(self):
        """Remove data older than retention policy."""
        logger.info("\n[PHASE 2] Purge Old Data")
        logger.info("="*60)

        cursor = self.db_conn.cursor()

        for table_name, retention_days in RETENTION_POLICY.items():
            try:
                cutoff_date = datetime.now() - timedelta(days=retention_days)

                # Count old records
                cursor.execute(f"""
                    SELECT COUNT(*) FROM {table_name}
                    WHERE date < %s
                """, (cutoff_date,))

                old_count = cursor.fetchone()[0]

                if old_count > 0:
                    # Delete old records
                    cursor.execute(f"""
                        DELETE FROM {table_name}
                        WHERE date < %s
                    """, (cutoff_date,))

                    self.db_conn.commit()
                    self.stats["purged"] += old_count

                    logger.info(f"{table_name}:")
                    logger.info(f"  Cutoff: {cutoff_date.date()}")
                    logger.info(f"  Deleted: {old_count:,} records")

                else:
                    logger.info(f"{table_name}: No data to purge")

            except psycopg2.Error as e:
                self.db_conn.rollback()
                logger.error(f"❌ Error purging {table_name}: {e}")
                self.stats["errors"] += 1

        logger.info(f"\n✅ Purged {self.stats['purged']:,} old records")

    def load_data_to_redis(self):
        """Load hot data to Redis cache."""
        logger.info("\n[PHASE 3] Load Data to Redis Cache")
        logger.info("="*60)

        cursor = self.db_conn.cursor()

        for interval, policy in REDIS_CACHE_POLICY.items():
            try:
                table_name = policy["table"]
                days = policy["days"]
                ttl = policy["ttl"]

                cutoff_date = datetime.now() - timedelta(days=days)

                logger.info(f"\n{interval.upper()}:")
                logger.info(f"  Table: {table_name}")
                logger.info(f"  Data: Last {days} days")
                logger.info(f"  TTL: {ttl} seconds")

                # Get data for each ticker
                records_loaded = 0
                for ticker in TICKERS:
                    cursor.execute(f"""
                        SELECT date, open, high, low, close, volume
                        FROM {table_name}
                        WHERE ticker = %s AND date >= %s
                        ORDER BY date DESC
                    """, (ticker, cutoff_date))

                    bars = cursor.fetchall()
                    records_loaded += len(bars)

                    if bars:
                        # Create Redis key
                        key = f"market_data:{ticker}:{interval}"

                        # Convert to JSON
                        data = {
                            "ticker": ticker,
                            "interval": interval,
                            "bars": [
                                {
                                    "date": str(bar[0]),
                                    "open": float(bar[1]),
                                    "high": float(bar[2]),
                                    "low": float(bar[3]),
                                    "close": float(bar[4]),
                                    "volume": int(bar[5]) if bar[5] else 0,
                                }
                                for bar in bars
                            ],
                            "count": len(bars),
                            "loaded_at": datetime.now().isoformat(),
                        }

                        # Store in Redis with TTL
                        self.redis_conn.set(
                            key,
                            json.dumps(data),
                            ex=ttl
                        )

                logger.info(f"  [OK] Loaded {records_loaded:,} bars for {len(TICKERS)} tickers")
                self.stats["cached"] += records_loaded

            except psycopg2.Error as e:
                logger.error(f"[ERROR] Error loading {interval}: {e}")
                self.stats["errors"] += 1
            except Exception as e:
                logger.error(f"[ERROR] Redis error for {interval}: {e}")
                self.stats["errors"] += 1

        logger.info(f"\n[OK] Cached {self.stats['cached']:,} bars in Redis")

    def create_cache_summary(self):
        """Create summary of cached data in Redis."""
        logger.info("\n[PHASE 4] Cache Summary")
        logger.info("="*60)

        try:
            if not self.redis_conn:
                logger.warning("[WARN] Redis not available")
                return False

            # Get all market_data keys
            keys = self.redis_conn.keys("market_data:*")

            logger.info(f"Total keys in Redis: {len(keys)}")

            if keys:
                # Group by ticker and interval
                by_ticker = {}
                for key in keys:
                    _, ticker, interval = key.split(":")
                    if ticker not in by_ticker:
                        by_ticker[ticker] = []
                    by_ticker[ticker].append(interval)

                for ticker in sorted(by_ticker.keys()):
                    intervals = by_ticker[ticker]
                    logger.info(f"  {ticker}: {', '.join(sorted(intervals))}")

            return True

        except Exception as e:
            logger.error(f"[ERROR] Error creating cache summary: {e}")
            return False

    def generate_report(self):
        """Generate final report."""
        logger.info("\n" + "="*60)
        logger.info("[OK] DAILY PIPELINE COMPLETE")
        logger.info("="*60)

        elapsed = datetime.now() - self.start_time

        logger.info("\n[SUMMARY]")
        logger.info(f"  Downloaded: {self.stats['downloaded']:,} records")
        logger.info(f"  Purged: {self.stats['purged']:,} records")
        logger.info(f"  Cached in Redis: {self.stats['cached']:,} records")
        logger.info(f"  Errors: {self.stats['errors']}")
        logger.info(f"  Duration: {elapsed}")

        logger.info("\n[INFO] Next Run: Tomorrow at this time")
        logger.info("="*60 + "\n")

    def run(self):
        """Execute pipeline."""
        logger.info("\n" + "="*60)
        logger.info("[START] DAILY DATA PIPELINE - " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        logger.info("="*60)

        # Connect to databases
        if not self.connect_db():
            return False

        if not self.connect_redis():
            logger.warning("[WARN] Redis unavailable, continuing without caching...")

        try:
            # Execute pipeline phases
            if not self.download_incremental_data():
                logger.warning("[WARN] Download phase had issues")

            self.purge_old_data()

            if self.redis_conn:
                self.load_data_to_redis()
                self.create_cache_summary()

            self.generate_report()

            return True

        finally:
            # Close connections
            if self.db_conn:
                self.db_conn.close()
            if self.redis_conn:
                self.redis_conn.close()


def main():
    """Main entry point."""
    pipeline = DailyDataPipeline()
    success = pipeline.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
