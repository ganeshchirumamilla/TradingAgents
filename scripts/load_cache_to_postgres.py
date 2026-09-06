#!/usr/bin/env python3
"""
Load cached market data from CSV files into PostgreSQL.
This script reads from ~/.tradingagents/data_cache and persists to the database.
"""

import os
import sys
import pandas as pd
import psycopg2
from psycopg2.extras import execute_batch
from datetime import datetime
from pathlib import Path
import uuid

# Configuration
CACHE_DIR = os.path.expanduser("~/.tradingagents/data_cache")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "tradingagents")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "admin")

def connect_db():
    """Connect to PostgreSQL database."""
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        return conn
    except psycopg2.Error as e:
        print(f"❌ Database connection error: {e}")
        sys.exit(1)

def load_csv_file(filepath):
    """Load CSV file and return dataframe."""
    try:
        df = pd.read_csv(filepath)
        return df
    except Exception as e:
        print(f"❌ Error reading {filepath}: {e}")
        return None

def insert_data_to_postgres(conn, ticker, df):
    """Insert market data into historical_data table."""
    cursor = conn.cursor()

    # Auto-detect column names (case insensitive)
    df.columns = df.columns.str.lower()

    # Find date column (could be 'date', 'timestamp', 'datetime', etc)
    date_col = None
    for col in df.columns:
        if 'date' in col or 'time' in col:
            date_col = col
            break

    if date_col is None:
        print(f"❌ No date column found in {ticker}. Columns: {list(df.columns)}")
        return 0

    # Find ohlcv columns
    ohlcv_cols = {
        'open': [c for c in df.columns if 'open' in c][0] if any('open' in c for c in df.columns) else None,
        'high': [c for c in df.columns if 'high' in c][0] if any('high' in c for c in df.columns) else None,
        'low': [c for c in df.columns if 'low' in c][0] if any('low' in c for c in df.columns) else None,
        'close': [c for c in df.columns if 'close' in c][0] if any('close' in c for c in df.columns) else None,
        'volume': [c for c in df.columns if 'volume' in c][0] if any('volume' in c for c in df.columns) else None,
    }

    if None in ohlcv_cols.values():
        print(f"❌ Missing OHLCV columns for {ticker}. Found: {list(df.columns)}")
        return 0

    print(f"   Using columns: date={date_col}, open={ohlcv_cols['open']}, high={ohlcv_cols['high']}, low={ohlcv_cols['low']}, close={ohlcv_cols['close']}, volume={ohlcv_cols['volume']}")

    # Prepare data for insertion
    records = []
    for _, row in df.iterrows():
        try:
            # Parse date
            date_val = row[date_col]
            if isinstance(date_val, str):
                date = pd.to_datetime(date_val).date()
            else:
                date = date_val

            record = (
                str(uuid.uuid4()),  # id
                ticker,  # ticker
                date,  # date
                float(row[ohlcv_cols['open']]),  # open
                float(row[ohlcv_cols['high']]),  # high
                float(row[ohlcv_cols['low']]),  # low
                float(row[ohlcv_cols['close']]),  # close
                int(row[ohlcv_cols['volume']]) if pd.notna(row[ohlcv_cols['volume']]) else 0,  # volume
                datetime.now(),  # created_at
                'ibkr'  # data_source
            )
            records.append(record)
        except Exception as e:
            print(f"⚠️  Skipping row for {ticker}: {e}")
            continue

    if not records:
        print(f"⚠️  No valid records for {ticker}")
        return 0

    # Insert data
    sql = """
        INSERT INTO historical_data
        (id, ticker, date, open, high, low, close, volume, created_at, data_source)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (ticker, date) DO NOTHING
    """

    try:
        execute_batch(cursor, sql, records, page_size=1000)
        conn.commit()
        print(f"✅ Inserted {len(records)} records for {ticker}")
        return len(records)
    except psycopg2.Error as e:
        conn.rollback()
        print(f"❌ Error inserting data for {ticker}: {e}")
        return 0

def main():
    """Main function to load all cached data."""

    # Check if cache directory exists
    if not os.path.exists(CACHE_DIR):
        print(f"❌ Cache directory not found: {CACHE_DIR}")
        print("📝 Run this first to download market data:")
        print("   python scripts/download_ibkr_data.py --tickers AAPL NVDA MSFT SPY --days 365")
        sys.exit(1)

    # Connect to database
    print("🔌 Connecting to PostgreSQL...")
    conn = connect_db()
    print("✅ Connected to PostgreSQL")

    # Get list of cached tickers
    tickers = [d for d in os.listdir(CACHE_DIR)
               if os.path.isdir(os.path.join(CACHE_DIR, d))]

    if not tickers:
        print(f"❌ No cached data found in {CACHE_DIR}")
        sys.exit(1)

    print(f"📊 Found {len(tickers)} tickers: {', '.join(tickers)}")

    # Load data for each ticker
    total_inserted = 0
    for ticker in sorted(tickers):
        ticker_dir = os.path.join(CACHE_DIR, ticker)
        csv_file = os.path.join(ticker_dir, "daily_all_current.csv")

        if not os.path.exists(csv_file):
            print(f"⚠️  No data file found for {ticker}")
            continue

        print(f"\n📥 Loading {ticker}...")
        df = load_csv_file(csv_file)

        if df is None:
            continue

        print(f"   Rows in CSV: {len(df)}")

        inserted = insert_data_to_postgres(conn, ticker, df)
        total_inserted += inserted

    # Close connection
    conn.close()

    # Summary
    print("\n" + "="*50)
    print(f"✅ SUCCESS!")
    print(f"   Total records inserted: {total_inserted}")
    print(f"   Database: {DB_NAME}")
    print(f"   Table: historical_data")
    print("="*50)

    # Verify in database
    print("\n🔍 Verifying data in PostgreSQL...")
    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute("SELECT ticker, COUNT(*) as count FROM historical_data GROUP BY ticker ORDER BY ticker")
    results = cursor.fetchall()

    if results:
        print("\n📊 Data by ticker:")
        for ticker, count in results:
            print(f"   {ticker}: {count} records")

    cursor.close()
    conn.close()

if __name__ == "__main__":
    main()
