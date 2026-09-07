#!/usr/bin/env python3
"""
Market Data Downloader with realistic IBKR date range limits.
- Downloads data in manageable chunks
- Properly closes IB connections after each request
- Saves raw and processed data with proper naming format
- Merges files and stores in PostgreSQL
"""

import sys
import time
import pandas as pd
import psycopg2
from psycopg2.extras import execute_batch
from pathlib import Path
from datetime import datetime, timedelta
import uuid

try:
    from ib_async import IB, Stock, util
except ImportError:
    print("[ERROR] ib_async not installed. Run: pip install ib_async")
    sys.exit(1)


class MarketDataDownloader:
    """Download market data with realistic IBKR constraints."""

    def __init__(self, ticker="AAPL"):
        self.ticker = ticker
        self.db_conn = None
        self.run_date = datetime.now().strftime("%Y%m%d_%H%M%S")

        # IBKR connection
        self.ibkr_host = "127.0.0.1"
        self.ibkr_port = 4002

        # Data directory
        self.data_dir = Path.home() / ".tradingagents" / "data_downloads" / ticker / "historical"
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # REALISTIC date ranges based on IBKR limits
        # Format: (timeframe, start_date, end_date, description)
        self.download_ranges = [
            # Daily: Latest 1 year works reliably
            ('daily', (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d'),
             datetime.now().strftime('%Y-%m-%d'), 'Last 365 days'),

            # Hourly: Latest 1 year works reliably
            ('hourly', (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d'),
             datetime.now().strftime('%Y-%m-%d'), 'Last 365 days'),

            # 5-minute: Latest 180 days
            ('5min', (datetime.now() - timedelta(days=180)).strftime('%Y-%m-%d'),
             datetime.now().strftime('%Y-%m-%d'), 'Last 180 days'),

            # 1-minute: Latest 60 days
            ('1min', (datetime.now() - timedelta(days=60)).strftime('%Y-%m-%d'),
             datetime.now().strftime('%Y-%m-%d'), 'Last 60 days'),
        ]

    def connect_db(self) -> bool:
        """Connect to PostgreSQL."""
        try:
            self.db_conn = psycopg2.connect(
                host="localhost",
                port=5433,
                database="postgres",
                user="postgres",
                password="admin"
            )
            print("[OK] PostgreSQL connected")
            return True
        except Exception as e:
            print(f"[ERROR] PostgreSQL: {e}")
            return False

    def download_data(self, timeframe: str, start_date: str, end_date: str,
                     client_id: int) -> pd.DataFrame:
        """Download data from IBKR with proper connection handling."""

        timeframe_map = {
            '1min': '1 min',
            '5min': '5 mins',
            'hourly': '1 hour',
            'daily': '1 day',
        }

        bar_size = timeframe_map.get(timeframe, '1 day')

        print(f"   [{timeframe.upper()}] {start_date} to {end_date}...", end=" ", flush=True)

        ib = None
        try:
            # Connect with unique client ID
            ib = IB()
            ib.connect(self.ibkr_host, self.ibkr_port, clientId=client_id)

            # Calculate days
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')
            days = (end_dt - start_dt).days

            contract = Stock(self.ticker, "SMART", "USD")

            # Request data with proper timeout
            bars = ib.reqHistoricalData(
                contract,
                endDateTime=end_dt.strftime('%Y%m%d %H:%M:%S'),
                durationStr=f"{days} D",
                barSizeSetting=bar_size,
                whatToShow="TRADES",
                useRTH=True,
                formatDate=1,
                timeout=120
            )

            if bars is None or len(bars) == 0:
                print("[EMPTY]")
                return None

            df = util.df(bars)
            if df.empty:
                print("[EMPTY]")
                return None

            print(f"[OK] {len(df):,} bars")
            return df

        except Exception as e:
            error_msg = str(e)[:60]
            print(f"[ERROR] {error_msg}")
            return None

        finally:
            # IMPORTANT: Always close IB connection
            if ib is not None:
                try:
                    ib.disconnect()
                    time.sleep(1)  # Allow connection to fully close
                except:
                    pass

    def save_files(self, timeframe: str, start_date: str, df: pd.DataFrame) -> tuple:
        """Save raw and processed data files."""
        if df is None or df.empty:
            return None, None

        # Format start date for filename
        start_date_formatted = start_date.replace('-', '')

        # Raw data file
        raw_file_name = f"raw_marketdata_{self.ticker}_{timeframe}_{start_date_formatted}_Rundate_{self.run_date}.csv"
        raw_file_path = self.data_dir / raw_file_name

        # Processed data file
        processed_file_name = f"marketdata_{self.ticker}_{timeframe}_{start_date_formatted}_Rundate_{self.run_date}.csv"
        processed_file_path = self.data_dir / processed_file_name

        try:
            # Save raw data
            df.to_csv(raw_file_path, index=False)

            # Save processed data (sorted by date)
            df_sorted = df.sort_values('date')
            df_sorted.to_csv(processed_file_path, index=False)

            raw_size = raw_file_path.stat().st_size / 1024
            processed_size = processed_file_path.stat().st_size / 1024

            print(f"      Raw: {raw_file_name} ({raw_size:.1f} KB)")
            print(f"      Processed: {processed_file_name} ({processed_size:.1f} KB)")

            return raw_file_path, processed_file_path

        except Exception as e:
            print(f"      [ERROR] Could not save files: {e}")
            return None, None

    def save_to_database(self, timeframe: str, df: pd.DataFrame) -> int:
        """Save data to PostgreSQL."""
        if not self.db_conn or df is None or df.empty:
            return 0

        try:
            cursor = self.db_conn.cursor()
            table_name = f"historical_data_{timeframe}"

            # Create table if needed
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

            print(f"      Database: {len(records):,} records inserted to {table_name}")
            return len(records)

        except Exception as e:
            print(f"      [ERROR] Database: {str(e)[:60]}")
            return 0

    def run(self):
        """Execute download process."""
        print("\n" + "="*70)
        print(f"MARKET DATA DOWNLOADER - {self.ticker}")
        print("="*70)

        # Connect to database
        print("\n[SETUP]")
        self.connect_db()
        print(f"  Data dir: {self.data_dir}")
        print(f"  Run date: {self.run_date}")

        # Download each timeframe
        print(f"\n[DOWNLOAD] {len(self.download_ranges)} timeframes")
        print("-"*70)

        total_records = 0
        client_id = 100
        timeframe_data = {}

        for timeframe, start_date, end_date, description in self.download_ranges:
            print(f"\n  {timeframe.upper()} ({description})")

            # Download
            df = self.download_data(timeframe, start_date, end_date, client_id)
            client_id += 1

            if df is not None and not df.empty:
                # Save files
                raw_file, processed_file = self.save_files(timeframe, start_date, df)

                # Save to database
                records = self.save_to_database(timeframe, df)
                total_records += records

                # Store for summary
                timeframe_data[timeframe] = {
                    'bars': len(df),
                    'records': records,
                    'files': (raw_file, processed_file)
                }
            else:
                print("      [SKIP] No data returned")

            # Rate limiting between requests
            time.sleep(3)

        # Summary
        print("\n" + "="*70)
        print("[COMPLETE] Download Summary")
        print("="*70)

        print(f"\nTicker: {self.ticker}")
        print(f"Total Records: {total_records:,}")

        print(f"\nDownloaded:")
        for timeframe, data in timeframe_data.items():
            print(f"  {timeframe:8s}: {data['bars']:7,d} bars, {data['records']:7,d} DB records")

        print(f"\nFile Naming Convention:")
        print(f"  Raw data:       raw_marketdata_{self.ticker}_<timeframe>_<startdate>_Rundate_{self.run_date}.csv")
        print(f"  Processed:      marketdata_{self.ticker}_<timeframe>_<startdate>_Rundate_{self.run_date}.csv")

        print(f"\nData Location:")
        print(f"  Files:     {self.data_dir}")
        print(f"  Database:  PostgreSQL (historical_data_* tables)")

        print("="*70 + "\n")

        # Cleanup
        if self.db_conn:
            self.db_conn.close()


if __name__ == "__main__":
    ticker = "AAPL"
    if len(sys.argv) > 1:
        ticker = sys.argv[1].upper()

    downloader = MarketDataDownloader(ticker=ticker)
    downloader.run()
