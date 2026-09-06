#!/usr/bin/env python3
"""
Utility for managing multi-timeframe market data in PostgreSQL.
Includes: querying, verification, cleanup, archiving, and reporting.
"""

import os
import sys
import psycopg2
from datetime import datetime, timedelta
import pandas as pd

# Database configuration
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "tradingagents")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "admin")

class MultiBarDataManager:
    """Manage multi-timeframe market data."""

    TABLES = {
        "daily": "historical_data_daily",
        "hourly": "historical_data_hourly",
        "5min": "historical_data_5min",
        "1min": "historical_data_1min",
    }

    def __init__(self):
        self.conn = None

    def connect(self):
        """Connect to database."""
        try:
            self.conn = psycopg2.connect(
                host=DB_HOST,
                port=DB_PORT,
                database=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD
            )
            return True
        except psycopg2.Error as e:
            print(f"❌ Connection failed: {e}")
            return False

    def disconnect(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()

    def get_stats(self):
        """Get overall statistics."""
        cursor = self.conn.cursor()

        print("\n📊 DATABASE STATISTICS")
        print("="*60)

        total_records = 0
        total_size = 0

        for interval, table_name in self.TABLES.items():
            try:
                # Get record count
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                count = cursor.fetchone()[0]
                total_records += count

                # Get size
                cursor.execute(f"""
                    SELECT pg_total_relation_size('{table_name}')
                """)
                size = cursor.fetchone()[0]
                total_size += size

                size_mb = size / (1024 * 1024)
                print(f"\n{interval:8s} ({table_name})")
                print(f"  Records: {count:,}")
                print(f"  Size: {size_mb:.2f} MB")

            except psycopg2.Error as e:
                print(f"  ❌ Error: {e}")

        print("\n" + "-"*60)
        total_size_mb = total_size / (1024 * 1024)
        print(f"TOTAL: {total_records:,} records, {total_size_mb:.2f} MB")
        print("="*60)

    def get_data_completeness(self):
        """Check data completeness by ticker and interval."""
        cursor = self.conn.cursor()

        print("\n📈 DATA COMPLETENESS")
        print("="*60)

        try:
            cursor.execute("SELECT * FROM v_data_completeness ORDER BY interval, ticker")
            results = cursor.fetchall()

            if not results:
                print("⚠️  No data found. Run: python scripts/download_ibkr_multibar_data.py")
                return

            current_interval = None
            for row in results:
                interval, ticker, count, earliest, latest, completeness = row

                if current_interval != interval:
                    current_interval = interval
                    print(f"\n{interval.upper()}:")

                print(f"  {ticker:6s}: {count:7,} bars | {earliest.date()} to {latest.date()} | {completeness}")

            print("\n" + "="*60)

        except psycopg2.Error as e:
            print(f"❌ Error: {e}")

    def get_latest_bars(self, ticker=None, limit=5):
        """Get latest bars for ticker(s)."""
        cursor = self.conn.cursor()

        print(f"\n📊 LATEST BARS (limit: {limit})")
        print("="*60)

        for interval, table_name in self.TABLES.items():
            try:
                if ticker:
                    sql = f"""
                        SELECT ticker, date, open, high, low, close, volume
                        FROM {table_name}
                        WHERE ticker = %s
                        ORDER BY date DESC
                        LIMIT %s
                    """
                    cursor.execute(sql, (ticker, limit))
                else:
                    sql = f"""
                        SELECT ticker, date, open, high, low, close, volume
                        FROM {table_name}
                        ORDER BY date DESC
                        LIMIT %s
                    """
                    cursor.execute(sql, (limit,))

                results = cursor.fetchall()
                if results:
                    print(f"\n{interval.upper()}:")
                    for row in results:
                        t, d, o, h, l, c, v = row
                        print(f"  {t} {d}: O:{o} H:{h} L:{l} C:{c} V:{v}")

            except psycopg2.Error as e:
                print(f"  ❌ Error: {e}")

        print("="*60)

    def export_to_csv(self, ticker, interval, output_file=None):
        """Export data to CSV file."""
        cursor = self.conn.cursor()

        if interval not in self.TABLES:
            print(f"❌ Unknown interval: {interval}. Use: {', '.join(self.TABLES.keys())}")
            return

        table_name = self.TABLES[interval]

        try:
            if output_file is None:
                output_file = f"{ticker}_{interval}_{datetime.now().strftime('%Y%m%d')}.csv"

            sql = f"""
                SELECT ticker, date, open, high, low, close, volume
                FROM {table_name}
                WHERE ticker = %s
                ORDER BY date
            """
            cursor.execute(sql, (ticker,))

            # Fetch all data
            rows = cursor.fetchall()
            if not rows:
                print(f"❌ No data found for {ticker} ({interval})")
                return

            # Create DataFrame and save
            df = pd.DataFrame(rows, columns=['ticker', 'date', 'open', 'high', 'low', 'close', 'volume'])
            df.to_csv(output_file, index=False)

            print(f"✅ Exported {len(df)} rows to {output_file}")

        except psycopg2.Error as e:
            print(f"❌ Error: {e}")

    def cleanup_old_1min_data(self, keep_days=90):
        """Remove 1-minute bars older than specified days."""
        cursor = self.conn.cursor()

        cutoff_date = datetime.now() - timedelta(days=keep_days)

        try:
            cursor.execute(f"""
                DELETE FROM historical_data_1min
                WHERE date < %s
            """, (cutoff_date,))

            deleted_count = cursor.rowcount
            self.conn.commit()

            print(f"✅ Deleted {deleted_count:,} 1-minute bars older than {keep_days} days")
            print(f"   Cutoff date: {cutoff_date.date()}")

        except psycopg2.Error as e:
            self.conn.rollback()
            print(f"❌ Error: {e}")

    def analyze_performance(self, ticker, interval, metric="close"):
        """Analyze performance metrics."""
        cursor = self.conn.cursor()

        if interval not in self.TABLES:
            print(f"❌ Unknown interval: {interval}")
            return

        table_name = self.TABLES[interval]

        try:
            sql = f"""
                SELECT
                    MIN(low) as min_price,
                    MAX(high) as max_price,
                    AVG(close) as avg_close,
                    STDDEV(close) as volatility,
                    SUM(volume) as total_volume,
                    COUNT(*) as bar_count,
                    MIN(date) as earliest,
                    MAX(date) as latest
                FROM {table_name}
                WHERE ticker = %s
            """
            cursor.execute(sql, (ticker,))

            result = cursor.fetchone()
            if not result:
                print(f"❌ No data for {ticker}")
                return

            min_p, max_p, avg, vol, total_vol, count, earliest, latest = result

            print(f"\n📈 PERFORMANCE ANALYSIS: {ticker} ({interval})")
            print("="*60)
            print(f"  Period: {earliest.date()} to {latest.date()}")
            print(f"  Bar Count: {count:,}")
            print(f"  Price Range: ${min_p:.2f} - ${max_p:.2f}")
            print(f"  Average Close: ${avg:.2f}")
            print(f"  Volatility (Std Dev): ${vol:.2f}")
            print(f"  Total Volume: {total_vol:,}")
            print("="*60)

        except psycopg2.Error as e:
            print(f"❌ Error: {e}")

    def generate_report(self):
        """Generate comprehensive data report."""
        print("\n" + "="*60)
        print("🚀 MULTI-BAR HISTORICAL DATA REPORT")
        print("="*60)

        self.get_stats()
        self.get_data_completeness()
        self.get_latest_bars(limit=3)

        print("\n" + "="*60)
        print("✅ Report Complete")
        print("="*60)

def main():
    """Main menu."""
    import argparse

    parser = argparse.ArgumentParser(description="Multi-Bar Data Manager")
    parser.add_argument("--stats", action="store_true", help="Show statistics")
    parser.add_argument("--completeness", action="store_true", help="Show data completeness")
    parser.add_argument("--latest", action="store_true", help="Show latest bars")
    parser.add_argument("--latest-ticker", help="Show latest bars for ticker")
    parser.add_argument("--export", nargs=2, metavar=("TICKER", "INTERVAL"), help="Export to CSV")
    parser.add_argument("--cleanup", type=int, metavar="DAYS", help="Clean old 1-min data (keep N days)")
    parser.add_argument("--analyze", nargs=2, metavar=("TICKER", "INTERVAL"), help="Analyze performance")
    parser.add_argument("--report", action="store_true", help="Generate full report")

    args = parser.parse_args()

    manager = MultiBarDataManager()
    if not manager.connect():
        sys.exit(1)

    try:
        if args.report:
            manager.generate_report()
        elif args.stats:
            manager.get_stats()
        elif args.completeness:
            manager.get_data_completeness()
        elif args.latest:
            manager.get_latest_bars()
        elif args.latest_ticker:
            manager.get_latest_bars(ticker=args.latest_ticker.upper())
        elif args.export:
            manager.export_to_csv(args.export[0].upper(), args.export[1].lower())
        elif args.cleanup:
            manager.cleanup_old_1min_data(args.cleanup)
        elif args.analyze:
            manager.analyze_performance(args.analyze[0].upper(), args.analyze[1].lower())
        else:
            # Default: show report
            manager.generate_report()

    finally:
        manager.disconnect()

if __name__ == "__main__":
    main()
