#!/usr/bin/env python3
"""Verify AAPL data in all storage layers."""

import sys
import yaml
import psycopg2
import json
from pathlib import Path
from datetime import datetime

def verify_database():
    """Check data in PostgreSQL."""
    print("\n[DATABASE] Checking PostgreSQL...")
    print("-" * 70)

    with open("download_config.yaml", 'r') as f:
        config = yaml.safe_load(f)

    db_cfg = config['database']

    try:
        conn = psycopg2.connect(
            host=db_cfg['host'],
            port=db_cfg['port'],
            database=db_cfg['name'],
            user=db_cfg['user'],
            password=db_cfg['password']
        )
        cursor = conn.cursor()

        for timeframe, tf_cfg in config['timeframes'].items():
            table_name = tf_cfg['table_name']

            # Check if table exists
            cursor.execute(
                "SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name = %s)",
                (table_name,)
            )
            exists = cursor.fetchone()[0]

            if not exists:
                print(f"  {table_name:30s} - [NOT CREATED]")
                continue

            # Count records
            cursor.execute(f"SELECT count(*) FROM {table_name} WHERE ticker = 'AAPL'")
            count = cursor.fetchone()[0]

            # Check volume data
            cursor.execute(f"SELECT min(volume), max(volume) FROM {table_name} WHERE ticker = 'AAPL'")
            min_vol, max_vol = cursor.fetchone()

            # Date range
            cursor.execute(f"SELECT min(date), max(date) FROM {table_name} WHERE ticker = 'AAPL'")
            min_date, max_date = cursor.fetchone()

            if count > 0:
                print(f"  {table_name:30s} - [OK] {count:6d} records")
                print(f"    Volume:    {min_vol:12.0f} - {max_vol:12.0f}")
                print(f"    Dates:     {min_date} to {max_date}")
            else:
                print(f"  {table_name:30s} - [EMPTY]")

        conn.close()

    except Exception as e:
        print(f"  [ERROR] {e}")


def verify_files():
    """Check CSV files."""
    print("\n[FILES] Checking downloaded CSV files...")
    print("-" * 70)

    data_dir = Path.home() / ".tradingagents" / "data_downloads" / "AAPL"

    if not data_dir.exists():
        print("  [NO FILES] Download directory not found")
        return

    total_size = 0
    total_records = 0

    for timeframe_dir in data_dir.glob("*"):
        if not timeframe_dir.is_dir():
            continue

        timeframe = timeframe_dir.name
        csv_files = list(timeframe_dir.glob("*.csv"))

        if not csv_files:
            print(f"  {timeframe:15s} - [NO FILES]")
            continue

        for csv_file in csv_files:
            size_kb = csv_file.stat().st_size / 1024
            # Count lines (approximate records)
            with open(csv_file, 'r') as f:
                lines = len(f.readlines()) - 1  # Subtract header

            print(f"  {timeframe:15s} - {size_kb:8.1f} KB, {lines:6d} records")
            total_size += size_kb
            total_records += lines

    if total_size > 0:
        print(f"  {'TOTAL':15s} - {total_size:8.1f} KB, {total_records:6d} records")


def verify_redis():
    """Check Redis cache."""
    print("\n[REDIS] Checking Redis cache...")
    print("-" * 70)

    try:
        import redis
        with open("download_config.yaml", 'r') as f:
            config = yaml.safe_load(f)

        redis_cfg = config['redis']
        r = redis.Redis(
            host=redis_cfg['host'],
            port=redis_cfg['port'],
            db=redis_cfg['db'],
            decode_responses=True,
            socket_connect_timeout=5
        )

        r.ping()

        # Find AAPL keys
        keys = r.keys("market_data:AAPL:*")

        if not keys:
            print("  [NO DATA] No AAPL keys found in Redis")
            return

        for key in sorted(keys):
            data = r.get(key)
            if data:
                records = json.loads(data)
                print(f"  {key:35s} - [OK] {len(records):6d} records")
            else:
                print(f"  {key:35s} - [EMPTY]")

    except Exception as e:
        print(f"  [UNAVAILABLE] {e}")


def main():
    """Main verification."""
    print("\n" + "="*70)
    print("AAPL DATA VERIFICATION")
    print("="*70)

    verify_database()
    verify_files()
    verify_redis()

    print("\n" + "="*70)
    print("Verification Complete")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()
