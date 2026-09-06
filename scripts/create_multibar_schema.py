#!/usr/bin/env python3
"""
Create PostgreSQL schema for multi-timeframe market data.
Creates separate tables for daily, hourly, 5-minute, and 1-minute bars.
"""

import os
import sys
import psycopg2
from psycopg2 import sql

# Database configuration
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "tradingagents")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "admin")

# Table definitions
TABLES = {
    "historical_data_daily": {
        "description": "Daily OHLCV bars (2017-present)",
        "retention_days": None,  # Keep forever
    },
    "historical_data_hourly": {
        "description": "Hourly OHLCV bars (max available)",
        "retention_days": None,  # Keep forever
    },
    "historical_data_5min": {
        "description": "5-minute OHLCV bars (max available)",
        "retention_days": None,  # Keep forever
    },
    "historical_data_1min": {
        "description": "1-minute OHLCV bars (last 3 years)",
        "retention_days": 90,  # Keep last 90 days only
    },
}

def connect_db():
    """Connect to PostgreSQL."""
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
        print(f"❌ Connection failed: {e}")
        sys.exit(1)

def create_table(conn, table_name, description):
    """Create a historical data table."""
    cursor = conn.cursor()

    create_table_sql = f"""
    CREATE TABLE IF NOT EXISTS {table_name} (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        ticker VARCHAR(20) NOT NULL,
        date TIMESTAMP NOT NULL,
        open DECIMAL(10,4) NOT NULL,
        high DECIMAL(10,4) NOT NULL,
        low DECIMAL(10,4) NOT NULL,
        close DECIMAL(10,4) NOT NULL,
        volume BIGINT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        data_source VARCHAR(50) DEFAULT 'ibkr',
        UNIQUE(ticker, date)
    );

    COMMENT ON TABLE {table_name} IS '{description}';
    """

    try:
        cursor.execute(create_table_sql)
        conn.commit()
        print(f"✅ Created table: {table_name}")
    except psycopg2.Error as e:
        conn.rollback()
        print(f"❌ Error creating table {table_name}: {e}")
        return False

    return True

def create_indexes(conn, table_name):
    """Create indexes for better query performance."""
    cursor = conn.cursor()

    indexes = [
        {
            "name": f"idx_{table_name}_ticker",
            "definition": f"CREATE INDEX IF NOT EXISTS idx_{table_name}_ticker ON {table_name}(ticker)"
        },
        {
            "name": f"idx_{table_name}_date",
            "definition": f"CREATE INDEX IF NOT EXISTS idx_{table_name}_date ON {table_name}(date DESC)"
        },
        {
            "name": f"idx_{table_name}_ticker_date",
            "definition": f"CREATE INDEX IF NOT EXISTS idx_{table_name}_ticker_date ON {table_name}(ticker, date DESC)"
        },
        {
            "name": f"idx_{table_name}_created_at",
            "definition": f"CREATE INDEX IF NOT EXISTS idx_{table_name}_created_at ON {table_name}(created_at DESC)"
        },
    ]

    for idx in indexes:
        try:
            cursor.execute(idx["definition"])
            conn.commit()
            print(f"   ✅ Index: {idx['name']}")
        except psycopg2.Error as e:
            conn.rollback()
            print(f"   ❌ Error creating index {idx['name']}: {e}")

def create_partitions(conn, table_name):
    """Create partitions for large tables (optional, for 1-min and 5-min)."""
    cursor = conn.cursor()

    # Partition by year for 1-min and 5-min tables
    if "1min" in table_name or "5min" in table_name:
        try:
            # Get existing partitions
            cursor.execute(f"""
                SELECT schemaname, tablename FROM pg_tables
                WHERE tablename LIKE '{table_name}_%' AND schemaname = 'public'
            """)
            existing = [row[1] for row in cursor.fetchall()]

            # Create partitions for 2023-2026
            for year in range(2023, 2027):
                partition_name = f"{table_name}_{year}"
                if partition_name not in existing:
                    start_date = f"{year}-01-01"
                    end_date = f"{year + 1}-01-01"

                    partition_sql = f"""
                    CREATE TABLE {partition_name} PARTITION OF {table_name}
                    FOR VALUES FROM ('{start_date}') TO ('{end_date}');
                    """

                    try:
                        cursor.execute(partition_sql)
                        conn.commit()
                        print(f"   ✅ Partition: {partition_name}")
                    except psycopg2.Error as e:
                        conn.rollback()
                        print(f"   ⚠️  Partition {partition_name}: {e}")

        except psycopg2.Error as e:
            print(f"   ⚠️  Error with partitions: {e}")

def create_views(conn):
    """Create useful views for data analysis."""
    cursor = conn.cursor()

    # View: All data unified (UNION of all tables)
    unified_view = """
    CREATE OR REPLACE VIEW v_historical_data_all AS
    SELECT ticker, date, open, high, low, close, volume, created_at, data_source, 'daily' as bar_interval
    FROM historical_data_daily
    UNION ALL
    SELECT ticker, date, open, high, low, close, volume, created_at, data_source, 'hourly'
    FROM historical_data_hourly
    UNION ALL
    SELECT ticker, date, open, high, low, close, volume, created_at, data_source, '5min'
    FROM historical_data_5min
    UNION ALL
    SELECT ticker, date, open, high, low, close, volume, created_at, data_source, '1min'
    FROM historical_data_1min;
    """

    # View: Latest data per ticker
    latest_view = """
    CREATE OR REPLACE VIEW v_latest_data AS
    SELECT DISTINCT ON (ticker, bar_interval)
        ticker, bar_interval, date, open, high, low, close, volume
    FROM v_historical_data_all
    ORDER BY ticker, bar_interval, date DESC;
    """

    # View: Data completeness
    completeness_view = """
    CREATE OR REPLACE VIEW v_data_completeness AS
    SELECT
        'daily' as interval,
        ticker,
        COUNT(*) as total_bars,
        MIN(date) as earliest,
        MAX(date) as latest,
        ROUND(COUNT(*) * 100.0 / 2268, 2)::text || '%' as completeness
    FROM historical_data_daily
    GROUP BY ticker
    UNION ALL
    SELECT 'hourly', ticker, COUNT(*), MIN(date), MAX(date),
        ROUND(COUNT(*) * 100.0 / 14742, 2)::text || '%'
    FROM historical_data_hourly
    GROUP BY ticker
    UNION ALL
    SELECT '5min', ticker, COUNT(*), MIN(date), MAX(date),
        ROUND(COUNT(*) * 100.0 / 177408, 2)::text || '%'
    FROM historical_data_5min
    GROUP BY ticker
    UNION ALL
    SELECT '1min', ticker, COUNT(*), MIN(date), MAX(date),
        ROUND(COUNT(*) * 100.0 / 294840, 2)::text || '%'
    FROM historical_data_1min
    GROUP BY ticker;
    """

    views = [
        ("v_historical_data_all", unified_view),
        ("v_latest_data", latest_view),
        ("v_data_completeness", completeness_view),
    ]

    for view_name, view_sql in views:
        try:
            cursor.execute(view_sql)
            conn.commit()
            print(f"✅ Created view: {view_name}")
        except psycopg2.Error as e:
            conn.rollback()
            print(f"❌ Error creating view {view_name}: {e}")

def get_table_stats(conn):
    """Display table statistics."""
    cursor = conn.cursor()

    print("\n📊 Table Statistics:")
    print("="*60)

    for table_name in TABLES.keys():
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cursor.fetchone()[0]

            cursor.execute(f"""
                SELECT
                    pg_size_pretty(pg_total_relation_size('{table_name}')) as size,
                    pg_size_pretty(pg_relation_size('{table_name}')) as table_size,
                    pg_size_pretty(pg_indexes_size('{table_name}')) as indexes_size
            """)
            result = cursor.fetchone()

            print(f"\n{table_name}:")
            print(f"  Records: {count:,}")
            if result:
                print(f"  Total Size: {result[0]}")
                print(f"  Table Size: {result[1]}")
                print(f"  Indexes Size: {result[2]}")

        except psycopg2.Error as e:
            print(f"  ❌ Error: {e}")

def main():
    """Main function."""
    print("\n🚀 Multi-Bar Historical Data Schema Creator")
    print("="*60)

    # Connect to database
    print("\n🔌 Connecting to PostgreSQL...")
    conn = connect_db()
    print("✅ Connected")

    # Create tables
    print("\n📋 Creating tables...")
    for table_name, config in TABLES.items():
        print(f"\n📊 {table_name}")
        print(f"   Description: {config['description']}")

        if create_table(conn, table_name, config['description']):
            print(f"\n   Creating indexes...")
            create_indexes(conn, table_name)

            # Create partitions for large tables
            if "1min" in table_name or "5min" in table_name:
                print(f"\n   Creating partitions...")
                create_partitions(conn, table_name)

    # Create views
    print("\n📈 Creating views...")
    create_views(conn)

    # Display statistics
    get_table_stats(conn)

    # Close connection
    conn.close()

    # Summary
    print("\n" + "="*60)
    print("✅ SCHEMA CREATION COMPLETE!")
    print("\nTables created:")
    for table_name in TABLES.keys():
        print(f"  ✓ {table_name}")

    print("\nViews created:")
    print("  ✓ v_historical_data_all (unified view of all data)")
    print("  ✓ v_latest_data (latest bars per ticker/interval)")
    print("  ✓ v_data_completeness (data quality report)")

    print("\nReady for data loading:")
    print("  python scripts/download_ibkr_multibar_data.py")
    print("="*60)

if __name__ == "__main__":
    main()
