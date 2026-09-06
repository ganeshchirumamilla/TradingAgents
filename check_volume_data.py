#!/usr/bin/env python3
"""Check if volume data exists in database."""

import psycopg2
import os

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "postgres")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "admin")

try:
    conn = psycopg2.connect(
        host=DB_HOST, port=DB_PORT, database=DB_NAME,
        user=DB_USER, password=DB_PASSWORD
    )
    cursor = conn.cursor()

    print("\n[CHECK] Volume Data in Database\n")
    print("="*70)

    # Check 1-min data
    cursor.execute("""
        SELECT ticker, COUNT(*) as bars,
               MIN(volume) as min_vol, MAX(volume) as max_vol,
               ROUND(AVG(volume::float)::numeric, 0) as avg_vol
        FROM historical_data_1min
        GROUP BY ticker
        ORDER BY ticker
        LIMIT 5
    """)

    print("\n[1-MIN BARS] Sample tickers:")
    print("-" * 70)
    for row in cursor.fetchall():
        ticker, bars, min_vol, max_vol, avg_vol = row
        status = "[OK]" if max_vol > 0 else "[MISSING]"
        print(f"{status} {ticker}: {bars:,} bars | Vol: {min_vol} - {max_vol} | Avg: {avg_vol}")

    # Check 5-min data
    cursor.execute("""
        SELECT ticker, COUNT(*) as bars,
               MIN(volume) as min_vol, MAX(volume) as max_vol,
               ROUND(AVG(volume::float)::numeric, 0) as avg_vol
        FROM historical_data_5min
        GROUP BY ticker
        ORDER BY ticker
        LIMIT 3
    """)

    print("\n[5-MIN BARS] Sample tickers:")
    print("-" * 70)
    for row in cursor.fetchall():
        ticker, bars, min_vol, max_vol, avg_vol = row
        status = "[OK]" if max_vol > 0 else "[MISSING]"
        print(f"{status} {ticker}: {bars:,} bars | Vol: {min_vol} - {max_vol} | Avg: {avg_vol}")

    # Check daily data
    cursor.execute("""
        SELECT ticker, COUNT(*) as bars,
               MIN(volume) as min_vol, MAX(volume) as max_vol,
               ROUND(AVG(volume::float)::numeric, 0) as avg_vol
        FROM historical_data_daily
        GROUP BY ticker
        ORDER BY ticker
        LIMIT 3
    """)

    print("\n[DAILY BARS] Sample tickers:")
    print("-" * 70)
    for row in cursor.fetchall():
        ticker, bars, min_vol, max_vol, avg_vol = row
        status = "[OK]" if max_vol > 0 else "[MISSING]"
        print(f"{status} {ticker}: {bars:,} bars | Vol: {min_vol} - {max_vol} | Avg: {avg_vol}")

    # Check for -1.0 volumes (old data)
    cursor.execute("""
        SELECT COUNT(*) as fake_volumes
        FROM historical_data_1min
        WHERE volume = -1
    """)

    fake_count = cursor.fetchone()[0]
    print("\n" + "="*70)
    print(f"\n[STATUS] Volume Data Quality:")
    print(f"  Bars with -1.0 volume (MIDPOINT): {fake_count:,}")
    if fake_count > 0:
        print(f"  -> Old data detected (MIDPOINT data, not TRADES)")
    else:
        print(f"  -> No fake volumes found (data is from TRADES)")

    print("\n[ACTION] Status:")
    if fake_count > 0:
        print("  Downloads with TRADES have NOT been run yet")
        print("  Next: Run: python scripts/run_volume_enhanced_pipeline.py --stages download")
    else:
        print("  Volume data is current (from TRADES)")

    print("\n" + "="*70 + "\n")

    conn.close()

except Exception as e:
    print(f"[ERROR] Database connection failed: {e}")
    print("\nMake sure:")
    print("  1. PostgreSQL is running")
    print("  2. Database 'postgres' exists")
    print("  3. User 'postgres' with password 'admin' configured")
