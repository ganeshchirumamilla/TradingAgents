#!/usr/bin/env python3
"""
Incremental IBKR data download.
Downloads only new bars since last download (daily updates).
Minimal data transfer, fast execution.
"""

import os
import sys
import logging
from datetime import datetime, timedelta
import psycopg2
from psycopg2.extras import execute_batch
import uuid

# Fix encoding for Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

try:
    from ib_async import *
except ImportError:
    print("[ERROR] ib_async not installed. Run: pip install ib_async")
    sys.exit(1)

# Configure logging
import os as _os
_log_dir = os.getenv("LOG_DIR", "./logs")
_os.makedirs(_log_dir, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join(_log_dir, 'incremental_download.log'), mode='a', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# Configuration
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "tradingagents")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "admin")

IBKR_HOST = os.getenv("TRADINGAGENTS_IBKR_HOST", "127.0.0.1")
IBKR_PORT = int(os.getenv("TRADINGAGENTS_IBKR_PORT", "4002"))
IBKR_CLIENT_ID = int(os.getenv("TRADINGAGENTS_IBKR_CLIENT_ID", "1"))

TICKERS = ["AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "TSLA", "AMD", "AVGO", "JPM", "GS", "SPY", "QQQ", "IWM", "DIA"]

class IncrementalDownloader:
    """Download new data since last update."""

    INTERVALS = {
        "1 day": {
            "name": "daily",
            "table": "historical_data_daily",
            "duration": "1 D",  # Just yesterday + today
        },
        "1 hour": {
            "name": "hourly",
            "table": "historical_data_hourly",
            "duration": "1 D",  # Last 24 hours
        },
        "5 mins": {
            "name": "5min",
            "table": "historical_data_5min",
            "duration": "1 D",  # Last 24 hours
        },
        "1 min": {
            "name": "1min",
            "table": "historical_data_1min",
            "duration": "1 D",  # Last 24 hours
        },
    }

    def __init__(self):
        self.ib = None
        self.db_conn = None
        self.stats = {
            "downloaded": 0,
            "inserted": 0,
            "duplicates": 0,
            "errors": 0,
        }

    def connect_ibkr(self):
        """Connect to IBKR."""
        try:
            logger.info("🔌 Connecting to IBKR...")
            self.ib = IB()
            self.ib.connect(IBKR_HOST, IBKR_PORT, clientId=IBKR_CLIENT_ID)
            logger.info("✅ Connected to IBKR")
            return True
        except Exception as e:
            logger.error(f"❌ IBKR connection failed: {e}")
            return False

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

    def get_last_bar_date(self, table_name, ticker):
        """Get the date of the last bar for a ticker."""
        cursor = self.db_conn.cursor()

        try:
            cursor.execute(f"""
                SELECT MAX(date)
                FROM {table_name}
                WHERE ticker = %s
            """, (ticker,))

            result = cursor.fetchone()[0]
            return result if result else None

        except psycopg2.Error as e:
            logger.warning(f"Could not get last bar date: {e}")
            return None

    def download_ticker_interval(self, ticker, interval_config):
        """Download data for one ticker/interval."""
        try:
            contract = Stock(ticker, "SMART", "USD")

            logger.debug(f"    Downloading {ticker} {interval_config['name']}...", end=" ", flush=True)

            bars = self.ib.reqHistoricalData(
                contract,
                endDateTime="",
                durationStr=interval_config['duration'],
                barSizeSetting=list(self.INTERVALS.keys())[
                    list([v['name'] for v in self.INTERVALS.values()]).index(interval_config['name'])
                ],
                whatToShow="MIDPOINT",
                useRTH=True,
                formatDate=1,
                keepUpToDate=False,
                timeout=30
            )

            if not bars:
                logger.debug("⚠️  No data")
                return None

            logger.debug(f"✅ {len(bars)} bars")
            return bars

        except Exception as e:
            logger.debug(f"❌ Error: {e}")
            self.stats["errors"] += 1
            return None

    def insert_bars(self, ticker, interval_config, bars):
        """Insert bars into database (skip duplicates)."""
        cursor = self.db_conn.cursor()
        table_name = interval_config['table']

        records = []
        for bar in bars:
            try:
                record = (
                    str(uuid.uuid4()),
                    ticker,
                    bar.date,
                    float(bar.open),
                    float(bar.high),
                    float(bar.low),
                    float(bar.close),
                    int(bar.volume) if bar.volume else 0,
                    datetime.now(),
                    'ibkr'
                )
                records.append(record)
            except Exception as e:
                logger.debug(f"      Skipping bar: {e}")
                continue

        if not records:
            return 0

        # Insert with conflict handling
        insert_sql = f"""
            INSERT INTO {table_name}
            (id, ticker, date, open, high, low, close, volume, created_at, data_source)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (ticker, date) DO NOTHING
        """

        try:
            execute_batch(cursor, insert_sql, records, page_size=500)
            self.db_conn.commit()

            inserted = cursor.rowcount
            self.stats["inserted"] += inserted
            self.stats["duplicates"] += len(records) - inserted

            return inserted

        except psycopg2.Error as e:
            self.db_conn.rollback()
            logger.error(f"Error inserting bars: {e}")
            self.stats["errors"] += 1
            return 0

    def download_all(self):
        """Download incremental data for all tickers and intervals."""
        if not self.connect_ibkr():
            return False

        if not self.connect_db():
            return False

        logger.info("\n" + "="*60)
        logger.info("📥 INCREMENTAL DOWNLOAD - " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        logger.info("="*60)

        try:
            for ticker in TICKERS:
                logger.info(f"\n{ticker}:")

                for bar_size, interval_config in self.INTERVALS.items():
                    bars = self.download_ticker_interval(ticker, interval_config)

                    if bars:
                        inserted = self.insert_bars(ticker, interval_config, bars)
                        self.stats["downloaded"] += len(bars)
                        logger.info(f"    Inserted {inserted} new bars")

                    # Small delay between requests
                    import time
                    time.sleep(0.5)

        finally:
            if self.ib:
                self.ib.disconnect()
            if self.db_conn:
                self.db_conn.close()

        # Report
        logger.info("\n" + "="*60)
        logger.info("✅ INCREMENTAL DOWNLOAD COMPLETE")
        logger.info(f"  Downloaded: {self.stats['downloaded']:,} bars")
        logger.info(f"  Inserted: {self.stats['inserted']:,} new bars")
        logger.info(f"  Duplicates: {self.stats['duplicates']:,} (skipped)")
        logger.info(f"  Errors: {self.stats['errors']}")
        logger.info("="*60 + "\n")

        return True


def main():
    """Main entry point."""
    downloader = IncrementalDownloader()
    success = downloader.download_all()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
