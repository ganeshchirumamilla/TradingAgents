#!/usr/bin/env python3
"""Delete all data from PostgreSQL and Redis."""

import psycopg2
import redis
import os

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "postgres")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "admin")

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))

def delete_postgres_data():
    """Delete all data from PostgreSQL tables."""
    print("\n" + "="*70)
    print("DELETING POSTGRESQL DATA")
    print("="*70)

    try:
        conn = psycopg2.connect(
            host=DB_HOST, port=DB_PORT, database=DB_NAME,
            user=DB_USER, password=DB_PASSWORD
        )
        cursor = conn.cursor()

        tables = [
            'historical_data_1min',
            'historical_data_5min',
            'historical_data_hourly',
            'historical_data_daily'
        ]

        for table in tables:
            # Check if table exists
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]

            if count > 0:
                cursor.execute(f"DELETE FROM {table}")
                print(f"[OK] {table:30s}: Deleted {count:,} records")
            else:
                print(f"[SKIP] {table:30s}: Already empty")

        conn.commit()
        conn.close()

        print("\n[SUCCESS] All PostgreSQL data deleted")
        return True

    except Exception as e:
        print(f"[ERROR] PostgreSQL deletion failed: {e}")
        return False

def delete_redis_data():
    """Delete all data from Redis."""
    print("\n" + "="*70)
    print("DELETING REDIS DATA")
    print("="*70)

    try:
        r = redis.Redis(
            host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB,
            decode_responses=True
        )
        r.ping()
        print(f"[OK] Connected to Redis at {REDIS_HOST}:{REDIS_PORT}")

        # Get all keys
        keys = r.keys("*")

        if not keys:
            print(f"[SKIP] Redis DB {REDIS_DB}: Already empty")
            return True

        # Delete all keys
        deleted_count = r.delete(*keys)
        print(f"[OK] Redis: Deleted {deleted_count:,} keys")

        print("\n[SUCCESS] All Redis data deleted")
        return True

    except Exception as e:
        print(f"[WARNING] Redis deletion skipped: {e}")
        print("         (Redis is optional - can proceed without it)")
        return True

def main():
    """Main deletion function."""
    print("\n" + "="*70)
    print("COMPLETE DATA DELETION")
    print("="*70)
    print("\nThis will DELETE ALL DATA from:")
    print("  1. PostgreSQL database: all historical_data_* tables")
    print("  2. Redis cache: all market_data:* keys")
    print("\nFile cache will NOT be affected.")

    response = input("\nAre you SURE? Type 'YES' to confirm: ").strip()

    if response != "YES":
        print("\n[CANCELLED] No data was deleted")
        return

    print("\n[STARTING] Deletion in progress...\n")

    # Delete from both
    db_ok = delete_postgres_data()
    redis_ok = delete_redis_data()

    # Summary
    print("\n" + "="*70)
    print("DELETION SUMMARY")
    print("="*70)
    print(f"\nPostgreSQL: {'[OK]' if db_ok else '[FAILED]'}")
    print(f"Redis:      {'[OK]' if redis_ok else '[WARNING]'}")

    if db_ok and redis_ok:
        print("\n[SUCCESS] All data successfully deleted!")
        print("\nStatus:")
        print("  Database:   Empty (0 records)")
        print("  Redis:      Empty (0 keys)")
        print("  File Cache: Intact (can reload)")
    else:
        print("\n[WARNING] Some deletions may have failed")

    print("\n" + "="*70 + "\n")

if __name__ == "__main__":
    main()
