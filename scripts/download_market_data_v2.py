#!/usr/bin/env python3
"""
Enhanced Market Data Downloader v2
- Intelligent date range detection from database
- Parallel chunk-based downloads with client pooling
- 3 retries per chunk
- Comprehensive logging to file
- Skip already-downloaded dates
"""

import sys
import time
import logging
from pathlib import Path
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
import psycopg2
from psycopg2.extras import execute_batch
import uuid
from typing import Tuple, List, Optional
from queue import Queue

try:
    from ib_async import IB, Stock, util
except ImportError:
    print("[ERROR] ib_async not installed. Run: pip install ib_async")
    sys.exit(1)


class IBClientPool:
    """Pool of reusable IB connections."""

    def __init__(self, host: str, port: int, max_clients: int = 5):
        self.host = host
        self.port = port
        self.max_clients = max_clients
        self.available_clients = Queue(maxsize=max_clients)
        self.logger = logging.getLogger(__name__)

        # Create initial clients with unique IDs
        import time as time_module
        for i in range(max_clients):
            try:
                # Use high client IDs to avoid conflicts
                client_id = 2000 + i + int(time_module.time()) % 1000
                ib = IB()
                ib.connect(host, port, clientId=client_id)
                self.available_clients.put((i, ib), timeout=2)
                if self.logger:
                    self.logger.info(f"Created IB client {i} (ID: {client_id})")
            except Exception as e:
                print(f"[ERROR] Failed to create client {i}: {e}")
                time_module.sleep(1)  # Wait before retry

    def get_client(self, timeout: int = 5) -> Optional[Tuple[int, IB]]:
        """Get a client from the pool."""
        try:
            client_id, ib = self.available_clients.get(timeout=timeout)
            return client_id, ib
        except:
            return None

    def return_client(self, client_id: int, ib: IB):
        """Return a client to the pool."""
        try:
            self.available_clients.put((client_id, ib), timeout=1)
        except:
            try:
                ib.disconnect()
            except:
                pass

    def close_all(self):
        """Close all clients."""
        while not self.available_clients.empty():
            try:
                _, ib = self.available_clients.get_nowait()
                ib.disconnect()
            except:
                pass


class MarketDataDownloaderV2:
    """Enhanced downloader with chunking and pooling."""

    def __init__(self, ticker: str = "AAPL", log_file: str = None):
        self.ticker = ticker
        self.run_date = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.db_conn = None
        self.logger = self._setup_logging(log_file)

        # IBKR settings
        self.ibkr_host = "127.0.0.1"
        self.ibkr_port = 4002
        self.client_pool = None

        # Data directory
        self.data_dir = Path.home() / ".tradingagents" / "data_downloads" / ticker / "historical"
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Chunk sizes
        self.chunk_sizes = {
            'daily': timedelta(days=365),      # 1 year
            'hourly': timedelta(days=30),      # 1 month
            '5min': timedelta(days=5),         # 5 days
            '1min': timedelta(days=1),         # 1 day
        }

        # Timeframe map
        self.timeframe_map = {
            '1min': '1 min',
            '5min': '5 mins',
            'hourly': '1 hour',
            'daily': '1 day',
        }

        self.logger.info(f"Initialized MarketDataDownloaderV2 for {ticker}")
        self.logger.info(f"Run date: {self.run_date}")
        self.logger.info(f"Data directory: {self.data_dir}")

    def _setup_logging(self, log_file: str = None) -> logging.Logger:
        """Setup logging to file and console."""
        if log_file is None:
            log_file = Path.home() / ".tradingagents" / "download_logs" / f"download_{self.run_date}.log"

        log_file.parent.mkdir(parents=True, exist_ok=True)

        logger = logging.getLogger(f"downloader_{self.run_date}")
        logger.setLevel(logging.DEBUG)

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

    def connect_db(self) -> bool:
        """Connect to PostgreSQL."""
        try:
            self.db_conn = psycopg2.connect(
                host="localhost",
                port=5432,
                database="postgres",
                user="postgres",
                password="admin"
            )
            self.logger.info("Connected to PostgreSQL")
            return True
        except Exception as e:
            self.logger.error(f"PostgreSQL connection failed: {e}")
            return False

    def get_date_range_from_db(self, timeframe: str) -> Tuple[Optional[datetime], Optional[datetime]]:
        """Get min and max dates from database for this ticker/timeframe."""
        try:
            cursor = self.db_conn.cursor()
            table_name = f"historical_data_{timeframe}"

            # Check if table exists
            cursor.execute(f"""
                SELECT EXISTS(
                    SELECT FROM information_schema.tables
                    WHERE table_name = '{table_name}'
                )
            """)
            if not cursor.fetchone()[0]:
                self.logger.info(f"  Table {table_name} does not exist (no prior data)")
                cursor.close()
                return None, None

            # Get date range
            cursor.execute(f"""
                SELECT MIN(date), MAX(date)
                FROM {table_name}
                WHERE ticker = '{self.ticker}'
            """)
            result = cursor.fetchone()
            cursor.close()

            if result[0] is None:
                self.logger.info(f"  No data in {table_name} for {self.ticker}")
                return None, None

            min_date = result[0]
            max_date = result[1]

            row_count_cursor = self.db_conn.cursor()
            row_count_cursor.execute(f"SELECT COUNT(*) FROM {table_name} WHERE ticker = '{self.ticker}'")
            count = row_count_cursor.fetchone()[0]
            row_count_cursor.close()

            self.logger.info(f"  {table_name}: {count:,} rows from {min_date.date()} to {max_date.date()}")
            return min_date, max_date

        except Exception as e:
            self.logger.warning(f"Could not get date range: {e}")
            return None, None

    def generate_chunks(self, timeframe: str, min_date: Optional[datetime],
                       max_date: Optional[datetime]) -> List[Tuple[datetime, datetime]]:
        """Generate date chunks to download."""
        chunk_size = self.chunk_sizes[timeframe]
        chunks = []

        # Start from today and work backwards
        today = datetime.now().date()
        current_end = datetime.combine(today, datetime.min.time())

        # Go back based on IBKR practical limits
        if timeframe == 'daily':
            lookback = timedelta(days=365)  # 1 year
        elif timeframe == 'hourly':
            lookback = timedelta(days=365)  # 1 year
        elif timeframe == '5min':
            lookback = timedelta(days=180)  # 6 months
        else:  # 1min
            lookback = timedelta(days=60)   # 2 months

        current_start = current_end - lookback

        # Generate chunks
        while current_start < current_end:
            chunk_end = min(current_start + chunk_size, current_end)

            # Skip if already in database
            if min_date and max_date:
                chunk_min = chunk_start = current_start
                chunk_max = chunk_end
                db_min = min_date
                db_max = max_date

                # If chunk is completely within database range, skip
                if chunk_min >= db_min and chunk_max <= db_max:
                    self.logger.debug(f"  Skipping {chunk_start.date()} to {chunk_end.date()} (already in DB)")
                    current_start = chunk_end
                    continue

            chunks.append((current_start, chunk_end))
            self.logger.debug(f"  Chunk: {current_start.date()} to {chunk_end.date()}")
            current_start = chunk_end

        return chunks

    def download_chunk(self, timeframe: str, start_date: datetime, end_date: datetime,
                      retry: int = 0, max_retries: int = 3) -> Optional[pd.DataFrame]:
        """Download a single date chunk."""
        if retry > 0:
            self.logger.info(f"    Retry {retry}/{max_retries} for {start_date.date()} to {end_date.date()}")

        bar_size = self.timeframe_map[timeframe]

        # Get client from pool
        client_info = self.client_pool.get_client()
        if not client_info:
            self.logger.error(f"  No available IB clients")
            return None

        client_id, ib = client_info

        try:
            # Calculate days
            days = (end_date - start_date).days
            if days == 0:
                days = 1

            contract = Stock(self.ticker, "SMART", "USD")

            self.logger.debug(f"    Requesting {days} days of {bar_size} data (client {client_id})")

            bars = ib.reqHistoricalData(
                contract,
                endDateTime=end_date.strftime('%Y%m%d %H:%M:%S'),
                durationStr=f"{days} D",
                barSizeSetting=bar_size,
                whatToShow="TRADES",
                useRTH=True,
                formatDate=1,
                timeout=120
            )

            if bars is None or len(bars) == 0:
                self.logger.warning(f"    No data returned")
                return None

            df = util.df(bars)
            if df.empty:
                self.logger.warning(f"    Empty DataFrame")
                return None

            self.logger.info(f"    Downloaded {len(df):,} bars")
            return df

        except Exception as e:
            error_msg = str(e)[:100]
            self.logger.warning(f"    Download failed: {error_msg}")

            if retry < max_retries:
                time.sleep(2 ** retry)  # Exponential backoff
                return self.download_chunk(timeframe, start_date, end_date, retry + 1, max_retries)
            else:
                self.logger.error(f"    Failed after {max_retries} retries")
                return None

        finally:
            # Return client to pool
            self.client_pool.return_client(client_id, ib)

    def save_files(self, timeframe: str, start_date: datetime, df: pd.DataFrame) -> Tuple[Path, Path]:
        """Save raw and processed data files."""
        if df is None or df.empty:
            return None, None

        start_date_formatted = start_date.strftime('%Y%m%d')

        raw_file_name = f"raw_marketdata_{self.ticker}_{timeframe}_{start_date_formatted}_Rundate_{self.run_date}.csv"
        raw_file_path = self.data_dir / raw_file_name

        processed_file_name = f"marketdata_{self.ticker}_{timeframe}_{start_date_formatted}_Rundate_{self.run_date}.csv"
        processed_file_path = self.data_dir / processed_file_name

        try:
            df.to_csv(raw_file_path, index=False)
            df_sorted = df.sort_values('date')
            df_sorted.to_csv(processed_file_path, index=False)

            raw_size = raw_file_path.stat().st_size / 1024
            self.logger.debug(f"    Saved files: {raw_size:.1f} KB")

            return raw_file_path, processed_file_path

        except Exception as e:
            self.logger.error(f"    File save failed: {e}")
            return None, None

    def save_to_database(self, timeframe: str, df: pd.DataFrame) -> int:
        """Save data to PostgreSQL."""
        if not self.db_conn or df is None or df.empty:
            return 0

        try:
            cursor = self.db_conn.cursor()
            table_name = f"historical_data_{timeframe}"

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
                        self.ticker,
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

            execute_batch(cursor, insert_sql, records, page_size=1000)
            self.db_conn.commit()

            self.logger.debug(f"    Inserted {len(records):,} records to {table_name}")
            return len(records)

        except Exception as e:
            self.logger.error(f"    Database write failed: {e}")
            return 0

    def process_timeframe(self, timeframe: str, executor: ThreadPoolExecutor) -> dict:
        """Process all chunks for a timeframe."""
        self.logger.info(f"\n[{timeframe.upper()}] Starting download")

        # Get existing date range from DB
        self.logger.info(f"  Checking database for existing data...")
        min_date, max_date = self.get_date_range_from_db(timeframe)

        # Generate chunks
        self.logger.info(f"  Generating chunks...")
        chunks = self.generate_chunks(timeframe, min_date, max_date)
        self.logger.info(f"  Generated {len(chunks)} chunks to download")

        if not chunks:
            self.logger.info(f"  No new chunks to download")
            return {'timeframe': timeframe, 'chunks': 0, 'bars': 0, 'records': 0}

        # Submit all chunk downloads
        futures = {}
        for i, (start, end) in enumerate(chunks):
            future = executor.submit(
                self.download_chunk,
                timeframe, start, end
            )
            futures[future] = (i, start, end)

        # Process results
        total_bars = 0
        total_records = 0
        successful_chunks = 0

        for future in as_completed(futures):
            chunk_idx, start, end = futures[future]
            try:
                self.logger.info(f"  Chunk {chunk_idx+1}/{len(chunks)}: {start.date()} to {end.date()}")
                df = future.result()

                if df is not None and not df.empty:
                    # Save files
                    self.save_files(timeframe, start, df)

                    # Save to database
                    records = self.save_to_database(timeframe, df)
                    total_bars += len(df)
                    total_records += records
                    successful_chunks += 1
                else:
                    self.logger.warning(f"  Chunk {chunk_idx+1}: No data")

            except Exception as e:
                self.logger.error(f"  Chunk {chunk_idx+1} processing failed: {e}")

            time.sleep(2)  # Rate limiting

        self.logger.info(f"  Completed {successful_chunks}/{len(chunks)} chunks")

        return {
            'timeframe': timeframe,
            'chunks': len(chunks),
            'successful': successful_chunks,
            'bars': total_bars,
            'records': total_records
        }

    def run(self, num_workers: int = 3):
        """Execute download process."""
        self.logger.info("="*70)
        self.logger.info(f"MARKET DATA DOWNLOADER V2 - {self.ticker}")
        self.logger.info("="*70)

        # Connect to database
        if not self.connect_db():
            self.logger.error("Database connection failed. Aborting.")
            return False

        # Initialize client pool
        self.logger.info(f"\nInitializing IB client pool with {num_workers} clients...")
        self.client_pool = IBClientPool(self.ibkr_host, self.ibkr_port, max_clients=num_workers)

        # Process each timeframe in parallel
        self.logger.info(f"\nStarting parallel downloads with {num_workers} workers...")

        results = {}
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = {}
            for timeframe in ['daily', 'hourly', '5min', '1min']:
                future = executor.submit(self.process_timeframe, timeframe, executor)
                futures[future] = timeframe

            for future in as_completed(futures):
                try:
                    result = future.result()
                    results[result['timeframe']] = result
                except Exception as e:
                    self.logger.error(f"Timeframe processing failed: {e}")

        # Summary
        self.logger.info("\n" + "="*70)
        self.logger.info("[COMPLETE] Download Summary")
        self.logger.info("="*70)

        total_bars = 0
        total_records = 0

        for timeframe in ['daily', 'hourly', '5min', '1min']:
            if timeframe in results:
                r = results[timeframe]
                self.logger.info(f"{timeframe:8s}: {r['chunks']:3d} chunks, "
                               f"{r['successful']:3d} successful, "
                               f"{r['bars']:8,d} bars, "
                               f"{r['records']:8,d} records")
                total_bars += r['bars']
                total_records += r['records']

        self.logger.info(f"\nTotal: {total_bars:,} bars, {total_records:,} records")
        self.logger.info(f"Log file: {self.logger.handlers[0].baseFilename}")

        # Cleanup
        if self.client_pool:
            self.client_pool.close_all()

        if self.db_conn:
            self.db_conn.close()

        self.logger.info("="*70 + "\n")
        return True


if __name__ == "__main__":
    ticker = "AAPL"
    workers = 3

    if len(sys.argv) > 1:
        ticker = sys.argv[1].upper()

    if len(sys.argv) > 2:
        try:
            workers = int(sys.argv[2])
        except:
            pass

    downloader = MarketDataDownloaderV2(ticker=ticker)
    downloader.run(num_workers=workers)
