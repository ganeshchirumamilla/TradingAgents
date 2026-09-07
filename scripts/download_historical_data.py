#!/usr/bin/env python3
"""
Enhanced historical data downloader with multiple date ranges.
- Downloads data for specified date ranges per timeframe
- Saves raw and processed data with proper file naming
- Merges multiple downloads into single files
- Properly closes IB Gateway connections
"""

import sys
import time
import pandas as pd
import psycopg2
from pathlib import Path
from datetime import datetime, timedelta
import json
import uuid

try:
    from ib_async import IB, Stock, util
except ImportError:
    print("[ERROR] ib_async not installed")
    sys.exit(1)


class HistoricalDataDownloader:
    """Download historical data with multiple date ranges per timeframe."""

    def __init__(self, ticker="AAPL"):
        """Initialize downloader."""
        self.ticker = ticker
        self.db_conn = None
        self.run_date = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Define date ranges for each timeframe
        # Format: (start_date, end_date) - dates as 'YYYY-MM-DD'
        # Note: Break large ranges into chunks to avoid IBKR timeouts
        self.date_ranges = {
            'daily': [
                # Break 2016-2025 into chunks
                ('2016-01-01', '2019-12-31'),  # 4 years
                ('2020-01-01', '2023-12-31'),  # 4 years
                ('2024-01-01', '2025-03-24'),  # 1.25 years
            ],
            'hourly': [
                # Break 2021-2025 into chunks
                ('2021-09-06', '2023-09-05'),  # 2 years
                ('2023-09-06', '2025-03-24'),  # 1.5 years
            ],
            '5min': [
                ('2025-01-01', '2025-03-24'),  # Recent 3 months
            ],
            '1min': [
                # Last 60 days of 1-minute data
                ('last_60_days', None),
            ],
        }

        # IBKR configuration
        self.ibkr_host = "127.0.0.1"
        self.ibkr_port = 4002

        # Data directory
        self.data_dir = Path.home() / ".tradingagents" / "data_downloads" / ticker / "historical"
        self.data_dir.mkdir(parents=True, exist_ok=True)

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
            print("[OK] PostgreSQL connected")
            return True
        except Exception as e:
            print(f"[ERROR] PostgreSQL: {e}")
            return False

    def download_date_range(self, timeframe: str, start_date: str, end_date: str,
                           client_id: int = 100) -> pd.DataFrame:
        """Download data for specific date range using fresh IB connection."""

        # Map timeframe to IBKR format
        timeframe_map = {
            '1min': '1 min',
            '5min': '5 mins',
            'hourly': '1 hour',
            'daily': '1 day',
        }

        bar_size = timeframe_map.get(timeframe, '1 day')

        print(f"\n   [{timeframe.upper()}] {start_date} to {end_date}...", end=" ", flush=True)

        ib = None
        try:
            # Create fresh IB connection
            ib = IB()
            ib.connect(self.ibkr_host, self.ibkr_port, clientId=client_id)

            contract = Stock(self.ticker, "SMART", "USD")

            # Calculate duration
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')
            days = (end_dt - start_dt).days

            # Request historical data
            # IBKR format: YYYYMMDD HH:MM:SS
            end_datetime_str = end_dt.strftime('%Y%m%d %H:%M:%S')

            bars = ib.reqHistoricalData(
                contract,
                endDateTime=end_datetime_str,
                durationStr=f"{days} D",
                barSizeSetting=bar_size,
                whatToShow="TRADES",
                useRTH=True,
                formatDate=1,
                timeout=120
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
            # Properly close IB connection
            if ib is not None:
                try:
                    ib.disconnect()
                    time.sleep(0.5)  # Give it time to fully disconnect
                except:
                    pass

    def download_last_n_days(self, timeframe: str, days: int,
                            client_id: int = 100) -> pd.DataFrame:
        """Download last N days of data."""

        timeframe_map = {
            '1min': '1 min',
            '5min': '5 mins',
            'hourly': '1 hour',
            'daily': '1 day',
        }

        bar_size = timeframe_map.get(timeframe, '1 day')

        print(f"\n   [{timeframe.upper()}] Last {days} days...", end=" ", flush=True)

        ib = None
        try:
            # Create fresh IB connection
            ib = IB()
            ib.connect(self.ibkr_host, self.ibkr_port, clientId=client_id)

            contract = Stock(self.ticker, "SMART", "USD")

            # Request recent data
            bars = ib.reqHistoricalData(
                contract,
                endDateTime="",  # Today
                durationStr=f"{days} D",
                barSizeSetting=bar_size,
                whatToShow="TRADES",
                useRTH=True,
                formatDate=1,
                timeout=120
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
            # Properly close IB connection
            if ib is not None:
                try:
                    ib.disconnect()
                    time.sleep(0.5)
                except:
                    pass

    def save_raw_data(self, timeframe: str, start_date: str, df: pd.DataFrame) -> Path:
        """Save raw data from IB Gateway as CSV."""
        file_name = f"raw_marketdata_{self.ticker}_{timeframe}_{start_date}_Rundate_{self.run_date}.csv"
        file_path = self.data_dir / file_name

        try:
            df.to_csv(file_path, index=False)
            size_kb = file_path.stat().st_size / 1024
            print(f"      Raw data: {file_name} ({size_kb:.1f} KB)")
            return file_path
        except Exception as e:
            print(f"      [ERROR] Could not save raw data: {e}")
            return None

    def save_processed_csv(self, timeframe: str, start_date: str, df: pd.DataFrame) -> Path:
        """Save processed data as CSV."""
        file_name = f"marketdata_{self.ticker}_{timeframe}_{start_date}_Rundate_{self.run_date}.csv"
        file_path = self.data_dir / file_name

        try:
            df.to_csv(file_path, index=False)
            size_kb = file_path.stat().st_size / 1024
            print(f"      Saved: {file_name} ({size_kb:.1f} KB)")
            return file_path
        except Exception as e:
            print(f"      [ERROR] Could not save CSV: {e}")
            return None

    def merge_timeframe_data(self, timeframe: str) -> Path:
        """Merge all CSV files for a timeframe into one."""
        print(f"\n   [MERGE] Merging {timeframe} data files...")

        # Find all CSV files for this timeframe
        csv_files = list(self.data_dir.glob(f"marketdata_{self.ticker}_{timeframe}_*_Rundate_{self.run_date}.csv"))

        if not csv_files:
            print(f"      [WARNING] No files to merge for {timeframe}")
            return None

        if len(csv_files) == 1:
            print(f"      [OK] Only 1 file, no merge needed")
            return csv_files[0]

        # Read and merge
        dfs = []
        for csv_file in sorted(csv_files):
            try:
                df = pd.read_csv(csv_file)
                dfs.append(df)
                print(f"      Read: {csv_file.name} ({len(df)} rows)")
            except Exception as e:
                print(f"      [ERROR] Could not read {csv_file.name}: {e}")

        if not dfs:
            print(f"      [ERROR] No data to merge")
            return None

        # Merge and sort by date
        merged_df = pd.concat(dfs, ignore_index=True)
        merged_df = merged_df.sort_values('date').drop_duplicates(subset=['date']).reset_index(drop=True)

        # Save merged file
        merged_file_name = f"marketdata_{self.ticker}_{timeframe}_merged_Rundate_{self.run_date}.csv"
        merged_file_path = self.data_dir / merged_file_name

        try:
            merged_df.to_csv(merged_file_path, index=False)
            print(f"      [OK] Merged: {merged_file_name} ({len(merged_df):,} rows)")
            return merged_file_path
        except Exception as e:
            print(f"      [ERROR] Could not save merged file: {e}")
            return None

    def save_to_postgres(self, timeframe: str, df: pd.DataFrame) -> int:
        """Save data to PostgreSQL."""
        if not self.db_conn:
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
            from psycopg2.extras import execute_batch
            insert_sql = f"""
                INSERT INTO {table_name}
                (id, ticker, date, open, high, low, close, volume, created_at, data_source)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (ticker, date) DO NOTHING
            """

            execute_batch(cursor, insert_sql, records, page_size=1000)
            self.db_conn.commit()

            return len(records)

        except Exception as e:
            print(f"      [ERROR] DB write: {e}")
            return 0

    def run(self):
        """Run the download process."""
        print("\n" + "="*70)
        print(f"HISTORICAL DATA DOWNLOADER - {self.ticker}")
        print("="*70)

        # Connect to DB
        print("\n[SETUP] Establishing connections...")
        self.connect_db()

        print(f"\nRun date: {self.run_date}")
        print(f"Data directory: {self.data_dir}")

        total_records = 0
        client_id = 100

        # Process each timeframe
        for timeframe, ranges in self.date_ranges.items():
            print(f"\n[{timeframe.upper()}] Processing {len(ranges)} date range(s)...")
            print("-" * 70)

            timeframe_dfs = []

            # Download each range
            for range_info in ranges:
                if len(range_info) == 2 and range_info[0] == 'last_60_days':
                    # Special case: last N days
                    df = self.download_last_n_days(timeframe, 60, client_id)
                    start_date = (datetime.now() - timedelta(days=60)).strftime("%Y%m%d")
                else:
                    # Normal date range
                    start_date_str, end_date_str = range_info[:2]
                    df = self.download_date_range(timeframe, start_date_str, end_date_str, client_id)
                    start_date = start_date_str.replace('-', '')

                client_id += 1

                if df is not None and not df.empty:
                    # Save raw data
                    self.save_raw_data(timeframe, start_date, df)

                    # Save processed CSV
                    self.save_processed_csv(timeframe, start_date, df)

                    # Store for merging
                    timeframe_dfs.append(df)

                    # Save to database
                    records = self.save_to_postgres(timeframe, df)
                    total_records += records

                # Rate limiting
                time.sleep(3)

            # Merge all files for this timeframe
            if len(timeframe_dfs) > 1:
                self.merge_timeframe_data(timeframe)

        # Summary
        print("\n" + "="*70)
        print("[COMPLETE] Download Summary")
        print("="*70)
        print(f"Ticker: {self.ticker}")
        print(f"Total Records Saved: {total_records:,}")
        print(f"Data Location: {self.data_dir}")
        print(f"Run Date: {self.run_date}")

        print(f"\nFiles created:")
        print(f"  Raw data:       raw_marketdata_*_Rundate_{self.run_date}.parquet")
        print(f"  Processed:      marketdata_*_Rundate_{self.run_date}.csv")
        print(f"  Merged:         marketdata_*_merged_Rundate_{self.run_date}.csv")
        print(f"  Database:       PostgreSQL historical_data_* tables")

        print("="*70 + "\n")

        # Cleanup
        if self.db_conn:
            self.db_conn.close()


if __name__ == "__main__":
    ticker = "AAPL"
    if len(sys.argv) > 1:
        ticker = sys.argv[1].upper()

    downloader = HistoricalDataDownloader(ticker=ticker)
    downloader.run()
