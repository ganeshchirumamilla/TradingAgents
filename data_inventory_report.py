#!/usr/bin/env python3
"""Comprehensive data inventory report - Database, Redis, and file cache."""

import psycopg2
import redis
import os
import json
from pathlib import Path
from datetime import datetime

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "postgres")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "admin")

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))

CACHE_DIR = Path.home() / ".tradingagents" / "data_cache_multibar"

def get_postgres_data():
    """Get data inventory from PostgreSQL."""
    print("\n" + "="*80)
    print("POSTGRESQL DATABASE INVENTORY")
    print("="*80)

    try:
        conn = psycopg2.connect(
            host=DB_HOST, port=DB_PORT, database=DB_NAME,
            user=DB_USER, password=DB_PASSWORD
        )
        cursor = conn.cursor()

        tables = {
            'historical_data_1min': '1-minute',
            'historical_data_5min': '5-minute',
            'historical_data_hourly': '1-hour',
            'historical_data_daily': '1-day'
        }

        total_records = 0
        total_with_volume = 0

        for table_name, timeframe in tables.items():
            print(f"\n[{timeframe.upper()}]")
            print("-" * 80)

            # Check if table exists
            cursor.execute(f"""
                SELECT COUNT(*) as total,
                       COUNT(*) FILTER (WHERE volume > 0) as with_volume,
                       COUNT(DISTINCT ticker) as tickers,
                       MIN(date) as earliest_date,
                       MAX(date) as latest_date,
                       MIN(volume) FILTER (WHERE volume > 0) as min_vol,
                       MAX(volume) as max_vol
                FROM {table_name}
            """)

            row = cursor.fetchone()
            if row[0] == 0:
                print(f"  Status: [EMPTY] No data")
                continue

            total, with_volume, tickers, earliest, latest, min_vol, max_vol = row

            total_records += total
            total_with_volume += with_volume

            print(f"  Total Records: {total:,}")
            print(f"  Records with Volume: {with_volume:,} ({100*with_volume/total:.1f}%)")
            print(f"  Tickers: {tickers}")
            print(f"  Date Range: {earliest} to {latest}")
            if min_vol and max_vol:
                print(f"  Volume Range: {min_vol:,.0f} - {max_vol:,.0f}")
                print(f"  Avg Volume: {cursor.execute(f'SELECT AVG(volume::float)::int FROM {table_name} WHERE volume > 0') or 'N/A'}")
                cursor.execute(f'SELECT AVG(volume::float)::int FROM {table_name} WHERE volume > 0')
                avg_vol = cursor.fetchone()[0]
                if avg_vol:
                    print(f"  Avg Volume: {avg_vol:,.0f}")

            # Records by ticker
            cursor.execute(f"""
                SELECT ticker, COUNT(*),
                       MIN(date), MAX(date),
                       MIN(volume) FILTER (WHERE volume > 0),
                       MAX(volume)
                FROM {table_name}
                GROUP BY ticker
                ORDER BY ticker
            """)

            print(f"\n  Breakdown by Ticker:")
            for ticker, count, min_date, max_date, min_v, max_v in cursor.fetchall():
                vol_info = f"{min_v:,.0f}-{max_v:,.0f}" if min_v else "No volume"
                print(f"    {ticker:6s}: {count:5,} bars | {min_date} to {max_date} | Vol: {vol_info}")

        print("\n" + "="*80)
        print(f"TOTAL: {total_records:,} records ({total_with_volume:,} with real volume)")
        print("="*80)

        conn.close()
        return total_records, total_with_volume

    except Exception as e:
        print(f"[ERROR] {e}")
        return 0, 0

def get_redis_data():
    """Get data inventory from Redis."""
    print("\n" + "="*80)
    print("REDIS CACHE INVENTORY")
    print("="*80)

    try:
        r = redis.Redis(
            host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB,
            decode_responses=True
        )
        r.ping()
        print("\n[OK] Connected to Redis")

        # Get all market_data keys
        cursor = 0
        all_keys = []
        while True:
            cursor, keys = r.scan(cursor, match="market_data:*", count=100)
            all_keys.extend(keys)
            if cursor == 0:
                break

        if not all_keys:
            print("\n[EMPTY] No market data in Redis")
            return

        # Organize by timeframe
        timeframes = {}
        for key in all_keys:
            # Key format: market_data:TICKER:TIMEFRAME
            parts = key.split(':')
            if len(parts) == 3:
                ticker = parts[1]
                timeframe = parts[2]
                if timeframe not in timeframes:
                    timeframes[timeframe] = {}
                timeframes[timeframe][ticker] = key

        # Print statistics
        total_redis_records = 0

        for timeframe in sorted(timeframes.keys()):
            print(f"\n[{timeframe.upper()}]")
            print("-" * 80)
            print(f"  Tickers Cached: {len(timeframes[timeframe])}")

            timeframe_records = 0
            for ticker, key in sorted(timeframes[timeframe].items()):
                try:
                    data = r.get(key)
                    if data:
                        records = json.loads(data)
                        count = len(records)
                        timeframe_records += count

                        # Get date range
                        dates = [r['date'] for r in records]
                        dates.sort()
                        min_date = dates[0] if dates else "N/A"
                        max_date = dates[-1] if dates else "N/A"

                        # Get volume info
                        volumes = [r['volume'] for r in records if r['volume'] > 0]
                        vol_info = f"{min(volumes):,.0f}-{max(volumes):,.0f}" if volumes else "No volume"

                        print(f"    {ticker}: {count:5,} bars | {min_date} to {max_date} | Vol: {vol_info}")
                except Exception as e:
                    print(f"    {ticker}: [ERROR] {e}")

            total_redis_records += timeframe_records
            print(f"  Subtotal: {timeframe_records:,} records")

        print("\n" + "="*80)
        print(f"TOTAL REDIS: {total_redis_records:,} records")
        print("="*80)

    except Exception as e:
        print(f"[WARNING] Redis not available: {e}")
        print("(Redis is optional for caching)")

def get_file_cache_data():
    """Get data inventory from file cache."""
    print("\n" + "="*80)
    print("FILE CACHE INVENTORY")
    print("="*80)

    if not CACHE_DIR.exists():
        print(f"\n[EMPTY] Cache directory not found: {CACHE_DIR}")
        return

    tickers = [d for d in CACHE_DIR.iterdir() if d.is_dir()]
    if not tickers:
        print(f"\n[EMPTY] No cached data in {CACHE_DIR}")
        return

    print(f"\n[OK] Cache directory: {CACHE_DIR}")
    print(f"  Total tickers cached: {len(tickers)}")

    total_records = 0
    total_files = 0

    # Organize by timeframe
    timeframes_data = {}

    for ticker_dir in sorted(tickers):
        ticker = ticker_dir.name
        timeframe_dirs = [d for d in ticker_dir.iterdir() if d.is_dir()]

        for tf_dir in timeframe_dirs:
            timeframe = tf_dir.name
            csv_file = tf_dir / "data.csv"

            if csv_file.exists():
                if timeframe not in timeframes_data:
                    timeframes_data[timeframe] = []

                # Read CSV to get stats
                try:
                    import pandas as pd
                    df = pd.read_csv(csv_file)
                    records = len(df)
                    vol_count = (df['volume'] > 0).sum() if 'volume' in df.columns else 0
                    min_date = df['date'].min() if 'date' in df.columns else "N/A"
                    max_date = df['date'].max() if 'date' in df.columns else "N/A"

                    total_records += records
                    total_files += 1

                    timeframes_data[timeframe].append({
                        'ticker': ticker,
                        'records': records,
                        'with_volume': vol_count,
                        'min_date': min_date,
                        'max_date': max_date,
                        'file_size_kb': csv_file.stat().st_size / 1024
                    })
                except Exception as e:
                    print(f"  [ERROR] {ticker}/{timeframe}: {e}")

    # Print organized by timeframe
    for timeframe in sorted(timeframes_data.keys()):
        print(f"\n[{timeframe.upper()}]")
        print("-" * 80)
        print(f"  Tickers: {len(timeframes_data[timeframe])}")

        for data in sorted(timeframes_data[timeframe], key=lambda x: x['ticker']):
            print(f"    {data['ticker']:6s}: {data['records']:5,} bars | "
                  f"{data['min_date']} to {data['max_date']} | "
                  f"Vol: {data['with_volume']:5,} | "
                  f"Size: {data['file_size_kb']:.1f} KB")

        subtotal = sum(d['records'] for d in timeframes_data[timeframe])
        print(f"  Subtotal: {subtotal:,} records")

    print("\n" + "="*80)
    print(f"TOTAL FILES: {total_files} CSV files")
    print(f"TOTAL RECORDS: {total_records:,} bars")
    print(f"CACHE DIRECTORY: {CACHE_DIR}")
    print("="*80)

    return total_files, total_records

def main():
    """Generate complete data inventory report."""
    print("\n")
    print("="*80)
    print("DATA INVENTORY REPORT - DATABASE, REDIS & FILE CACHE")
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)

    # Get data from all sources
    db_total, db_volume = get_postgres_data()
    get_redis_data()
    file_total, file_records = get_file_cache_data()

    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"\nPostgreSQL Database:")
    print(f"  Total Records: {db_total:,}")
    print(f"  With Real Volume: {db_volume:,} ({100*db_volume/db_total:.1f}%)" if db_total > 0 else "  No data")

    print(f"\nFile Cache:")
    print(f"  CSV Files: {file_total}")
    print(f"  Total Records: {file_records:,}")
    print(f"  Benefit: Fast reload without re-downloading from IBKR")

    print(f"\nData Ready for:")
    print(f"  [OK] Backtesting (Database: {db_total:,} bars)")
    print(f"  [OK] Quick reload (File cache: {file_records:,} bars)")
    print(f"  [OK] Redis caching (Real-time access)")

    print("\n" + "="*80 + "\n")

if __name__ == "__main__":
    main()
