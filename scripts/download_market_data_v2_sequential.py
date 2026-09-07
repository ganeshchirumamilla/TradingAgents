#!/usr/bin/env python3
"""
Market Data Downloader V2 Sequential
- Database-aware: only downloads missing data
- Intelligent chunking: 1yr daily, 1mo hourly, 5d 5min, 1d 1min
- Retry logic: 3 retries with exponential backoff
- NO concurrency: fully sequential for reliability
- Comprehensive logging
"""

import sys
import time
import logging
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
import psycopg2
from psycopg2.extras import execute_batch
from typing import List, Tuple, Optional

try:
    from ib_async import IB, Stock, util
except ImportError:
    print("[ERROR] ib_async not installed. Run: pip install ib_async")
    sys.exit(1)


class MarketDataDownloaderV2Sequential:
    """Enhanced downloader with chunking and retry logic (no concurrency)."""

    def __init__(self, ticker: str = "AAPL"):
        self.ticker = ticker
        self.run_date = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.db_conn = None
        self.logger = self._setup_logging()
        self.ib = None

        # IBKR settings
        self.ibkr_host = "127.0.0.1"
        self.ibkr_port = 4002

        # Data directory
        self.data_dir = Path.home() / ".tradingagents" / "data_downloads" / ticker / "historical"
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Chunk sizes (configured date ranges)
        self.chunk_sizes = {
            'daily': timedelta(days=365),      # 1 year
            'hourly': timedelta(days=30),      # 1 month
            '5min': timedelta(days=5),         # 5 days
            '1min': timedelta(days=1),         # 1 day
        }

        # Lookback periods (how far back to check in DB)
        self.lookback = {
            'daily': timedelta(days=3650),     # 10 years
            'hourly': timedelta(days=365),     # 1 year
            '5min': timedelta(days=180),       # 6 months
            '1min': timedelta(days=90),        # 90 days
        }

        # Table mapping
        self.table_map = {
            'daily': 'historical_data_daily',
            'hourly': 'historical_data_hourly',
            '5min': 'historical_data_5min',
            '1min': 'historical_data_1min',
        }

        # Timeframe map for IBKR
        self.timeframe_map = {
            'daily': '1 day',
            'hourly': '1 hour',
            '5min': '5 mins',
            '1min': '1 min',
        }

        self.logger.info(f"Initialized MarketDataDownloaderV2Sequential for {ticker}")
        self.logger.info(f"Run date: {self.run_date}")
        self.logger.info(f"Data directory: {self.data_dir}")

    def _setup_logging(self) -> logging.Logger:
        """Setup logging to file and console."""
        log_dir = Path.home() / ".tradingagents" / "download_logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"download_{self.run_date}.log"

        logger = logging.getLogger(f"downloader_{self.run_date}")
        logger.setLevel(logging.DEBUG)
        logger.handlers.clear()

        # File handler
        fh = logging.FileHandler(log_file)
        fh.setLevel(logging.DEBUG)

        # Console handler
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)

        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)-8s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        fh.setFormatter(formatter)
        ch.setFormatter(formatter)

        logger.addHandler(fh)
        logger.addHandler(ch)

        return logger

    def connect_db(self):
        """Connect to PostgreSQL."""
        try:
            self.db_conn = psycopg2.connect(
                host="localhost",
                port=5433,
                database="postgres",
                user="postgres",
                password="admin"
            )
            self.logger.info("Connected to PostgreSQL")
        except Exception as e:
            self.logger.error(f"Database connection failed: {e}")
            raise

    def disconnect_db(self):
        """Disconnect from PostgreSQL."""
        if self.db_conn:
            self.db_conn.close()

    def connect_ib(self):
        """Connect to IB Gateway (single sequential connection)."""
        try:
            self.ib = IB()
            # Use high client ID to avoid conflicts
            client_id = 2000 + int(time.time()) % 1000
            self.ib.connect(self.ibkr_host, self.ibkr_port, clientId=client_id)
            self.logger.info(f"Connected to IB Gateway (client ID: {client_id})")
            time.sleep(0.5)  # Small delay for connection stability
        except Exception as e:
            self.logger.error(f"IB connection failed: {e}")
            raise

    def disconnect_ib(self):
        """Disconnect from IB Gateway."""
        if self.ib:
            try:
                self.ib.disconnect()
                self.logger.info("Disconnected from IB Gateway")
            except:
                pass

    def get_db_date_range(self, timeframe: str) -> Tuple[Optional[datetime], Optional[datetime]]:
        """Get min/max dates from database."""
        table = self.table_map[timeframe]

        try:
            with self.db_conn.cursor() as cur:
                cur.execute(f"""
                    SELECT MIN(date), MAX(date) FROM {table} WHERE ticker = %s
                """, (self.ticker,))
                result = cur.fetchone()

                if result[0] is None:
                    return None, None

                return result[0], result[1]
        except Exception as e:
            self.logger.debug(f"Database query failed for {timeframe}: {e}")
            return None, None

    def generate_chunks(self, timeframe: str) -> List[Tuple[datetime.date, datetime.date]]:
        """Generate download chunks for a timeframe."""
        chunks = []

        # Get existing date range from database
        db_min, db_max = self.get_db_date_range(timeframe)

        # Convert to dates if needed
        if db_min and hasattr(db_min, 'date'):
            db_min = db_min.date()
        if db_max and hasattr(db_max, 'date'):
            db_max = db_max.date()

        # Calculate lookback period
        end_date = datetime.now().date()
        start_date = end_date - self.lookback[timeframe]

        self.logger.info(f"[{timeframe.upper()}] Database range: {db_min} to {db_max}")
        self.logger.info(f"[{timeframe.upper()}] Lookback period: {start_date} to {end_date}")

        if db_min is None:
            # No data in DB, download entire lookback period
            current = start_date
            chunk_size = self.chunk_sizes[timeframe]

            while current < end_date:
                chunk_end = current + chunk_size
                if chunk_end > end_date:
                    chunk_end = end_date
                chunks.append((current, chunk_end))
                current = chunk_end
        else:
            # Data exists, only download new data
            if db_max < end_date:
                current = db_max + timedelta(days=1)
                chunk_size = self.chunk_sizes[timeframe]

                while current <= end_date:
                    chunk_end = current + chunk_size
                    if chunk_end > end_date:
                        chunk_end = end_date
                    chunks.append((current, chunk_end))
                    current = chunk_end + timedelta(days=1)

        self.logger.info(f"[{timeframe.upper()}] Generated {len(chunks)} chunks to download")
        for i, (chunk_start, chunk_end) in enumerate(chunks, 1):
            self.logger.debug(f"  Chunk {i}: {chunk_start} to {chunk_end}")

        return chunks

    def download_chunk(self, timeframe: str, chunk_start, chunk_end,
                       retry: int = 0, max_retries: int = 3) -> Optional[pd.DataFrame]:
        """Download a single chunk with retry logic."""
        if retry > 0:
            # Exponential backoff: 1s, 2s, 4s
            delay = 2 ** (retry - 1)
            self.logger.info(f"[{timeframe.upper()}] Retry {retry}/{max_retries}, waiting {delay}s...")
            time.sleep(delay)

        try:
            contract = Stock(self.ticker, 'SMART', 'USD')

            # Ensure we have date objects
            if hasattr(chunk_start, 'date'):
                chunk_start = chunk_start.date()
            if hasattr(chunk_end, 'date'):
                chunk_end = chunk_end.date()

            # Calculate number of days
            num_days = (chunk_end - chunk_start).days + 1

            self.logger.debug(f"[{timeframe.upper()}] Requesting {num_days} days from {chunk_start} to {chunk_end}")

            # Request historical data
            bars = self.ib.reqHistoricalData(
                contract,
                endDateTime='',  # Empty = today
                durationStr=f'{num_days} D',
                barSizeSetting=self.timeframe_map[timeframe],
                whatToShow='TRADES',  # Include volume
                useRTH=True,
                formatDate=1
            )

            # Convert to DataFrame
            if not bars:
                self.logger.warning(f"[{timeframe.upper()}] No data returned for {chunk_start} to {chunk_end}")
                return None

            df = util.df(bars)
            df['ticker'] = self.ticker
            df['date'] = pd.to_datetime(df['date'])

            self.logger.info(f"[{timeframe.upper()}] Downloaded {len(df)} bars ({chunk_start} to {chunk_end})")
            return df

        except Exception as e:
            self.logger.error(f"[{timeframe.upper()}] Download failed: {e}")

            if retry < max_retries:
                self.logger.info(f"[{timeframe.upper()}] Retrying chunk ({retry + 1}/{max_retries})...")
                return self.download_chunk(timeframe, chunk_start, chunk_end, retry + 1, max_retries)
            else:
                self.logger.error(f"[{timeframe.upper()}] Failed after {max_retries} retries")
                return None

    def save_to_db(self, timeframe: str, df: pd.DataFrame):
        """Save data to PostgreSQL."""
        if df is None or len(df) == 0:
            return

        table = self.table_map[timeframe]

        try:
            with self.db_conn.cursor() as cur:
                # Prepare data
                rows = []
                for _, row in df.iterrows():
                    rows.append((
                        self.ticker,
                        row['date'],
                        row.get('open', 0),
                        row.get('high', 0),
                        row.get('low', 0),
                        row.get('close', 0),
                        row.get('volume', 0),
                    ))

                # Batch insert with ON CONFLICT DO NOTHING
                execute_batch(
                    cur,
                    f"""
                    INSERT INTO {table} (ticker, date, open, high, low, close, volume)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                    """,
                    rows,
                    page_size=1000
                )

                self.db_conn.commit()
                self.logger.info(f"[{timeframe.upper()}] Inserted {len(rows)} records to {table}")

        except Exception as e:
            self.logger.error(f"[{timeframe.upper()}] Database insert failed: {e}")
            self.db_conn.rollback()

    def save_to_csv(self, timeframe: str, chunk_start: datetime.date, df: pd.DataFrame):
        """Save raw and processed CSV files."""
        if df is None or len(df) == 0:
            return

        try:
            # Filenames
            start_str = chunk_start.strftime("%Y%m%d")
            raw_file = self.data_dir / f"raw_marketdata_{self.ticker}_{timeframe}_{start_str}_Rundate_{self.run_date}.csv"
            proc_file = self.data_dir / f"marketdata_{self.ticker}_{timeframe}_{start_str}_Rundate_{self.run_date}.csv"

            # Save both raw and processed (same for now)
            df.to_csv(raw_file, index=False)
            df.to_csv(proc_file, index=False)

            file_size_kb = raw_file.stat().st_size / 1024
            self.logger.debug(f"[{timeframe.upper()}] Saved files: {file_size_kb:.1f} KB")

        except Exception as e:
            self.logger.error(f"[{timeframe.upper()}] File save failed: {e}")

    def download_timeframe(self, timeframe: str):
        """Download all chunks for a timeframe (sequential)."""
        self.logger.info(f"\n[{timeframe.upper()}] Starting download")

        # Generate chunks
        chunks = self.generate_chunks(timeframe)

        if not chunks:
            self.logger.info(f"[{timeframe.upper()}] No chunks to download (data up to date)")
            return

        # Download each chunk sequentially
        total_records = 0
        for i, (chunk_start, chunk_end) in enumerate(chunks, 1):
            self.logger.info(f"[{timeframe.upper()}] Chunk {i}/{len(chunks)}: {chunk_start} to {chunk_end}")

            # Download with retries
            df = self.download_chunk(timeframe, chunk_start, chunk_end)

            if df is not None and len(df) > 0:
                total_records += len(df)
                self.save_to_db(timeframe, df)
                self.save_to_csv(timeframe, chunk_start, df)

            # Small delay between chunks
            if i < len(chunks):
                time.sleep(1)

        self.logger.info(f"[{timeframe.upper()}] Complete: {total_records} total records")

    def run(self):
        """Main execution: download all timeframes sequentially."""
        try:
            # Setup
            self.connect_db()
            self.connect_ib()

            self.logger.info("=" * 70)
            self.logger.info(f"MARKET DATA DOWNLOADER V2 SEQUENTIAL - {self.ticker}")
            self.logger.info("=" * 70)
            self.logger.info("")

            # Download each timeframe sequentially
            for timeframe in ['daily', 'hourly', '5min', '1min']:
                try:
                    self.download_timeframe(timeframe)
                except Exception as e:
                    self.logger.error(f"[{timeframe.upper()}] Failed: {e}")
                    continue

                # Small delay between timeframes
                time.sleep(2)

            self.logger.info("")
            self.logger.info("=" * 70)
            self.logger.info("DOWNLOAD COMPLETE")
            self.logger.info("=" * 70)

        except Exception as e:
            self.logger.error(f"Fatal error: {e}")
        finally:
            self.disconnect_ib()
            self.disconnect_db()


if __name__ == "__main__":
    ticker = sys.argv[1] if len(sys.argv) > 1 else "AAPL"

    downloader = MarketDataDownloaderV2Sequential(ticker)
    downloader.run()
