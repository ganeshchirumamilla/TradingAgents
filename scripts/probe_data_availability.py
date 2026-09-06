#!/usr/bin/env python3
"""
Probe IBKR for data availability of a specific ticker and timeframe.
Helps determine the earliest date where historical data is available.

Usage:
    python probe_data_availability.py --ticker AAPL --timeframe "1 min" --days-back 180
    python probe_data_availability.py --ticker SPY --timeframe "5 mins" --days-back 365
"""

import os
import sys
from datetime import datetime, timedelta
import argparse
import time
import pandas as pd

try:
    from ib_async import *
except ImportError:
    print("[ERROR] ib_async not installed. Run: pip install ib_async")
    sys.exit(1)

# IBKR configuration
IBKR_HOST = os.getenv("TRADINGAGENTS_IBKR_HOST", "127.0.0.1")
IBKR_PORT = int(os.getenv("TRADINGAGENTS_IBKR_PORT", "4002"))
IBKR_CLIENT_ID = int(os.getenv("TRADINGAGENTS_IBKR_CLIENT_ID", "2"))  # Different client ID for probing

class DataAvailabilityProber:
    """Probe IBKR for data availability."""

    def __init__(self):
        self.ib = None

    def connect_ibkr(self):
        """Connect to IBKR API."""
        print(f"[CONNECT] Connecting to IBKR at {IBKR_HOST}:{IBKR_PORT}...")
        self.ib = IB()
        try:
            self.ib.connect(IBKR_HOST, IBKR_PORT, clientId=IBKR_CLIENT_ID)
            print("[OK] Connected to IBKR")
            return True
        except Exception as e:
            print(f"[ERROR] IBKR connection failed: {e}")
            return False

    def probe_data(self, ticker, bar_size, days_back):
        """Probe for earliest available data going back N days."""
        try:
            contract = Stock(ticker, "SMART", "USD")

            # Convert days to IBKR duration format
            if days_back <= 7:
                duration = f"{days_back} D"
            elif days_back <= 30:
                duration = f"{days_back // 7} W"
            elif days_back <= 365:
                duration = f"{days_back // 30} M"
            else:
                duration = f"{days_back // 365} Y"

            print(f"\n[DATA] Probing {ticker} for {bar_size} bars...")
            print(f"       Requesting: duration={duration} (approximately {days_back} days back)")
            print(f"       Connection ID: {IBKR_CLIENT_ID}")

            bars = self.ib.reqHistoricalData(
                contract,
                endDateTime="",  # Today
                durationStr=duration,
                barSizeSetting=bar_size,
                whatToShow="MIDPOINT",
                useRTH=True,
                formatDate=1,
                keepUpToDate=False,
                timeout=60
            )

            # Convert to DataFrame
            df = util.df(bars)

            if df.empty:
                print(f"   [WARNING] No data returned for {ticker}")
                return None

            # Find earliest and latest dates
            df['date'] = pd.to_datetime(df['date'])
            earliest_date = df['date'].min()
            latest_date = df['date'].max()

            print(f"   [OK] Got {len(df)} bars")
            print(f"       Date range: {earliest_date} to {latest_date}")
            print(f"       Earliest date found: {earliest_date.strftime('%Y-%m-%d %H:%M:%S')}")

            return earliest_date

        except Exception as e:
            error_str = str(e)
            if "Timeout" in error_str or "timeout" in error_str:
                print(f"   [ERROR] Timeout - data not available or request too large")
            elif "cancelled" in error_str.lower():
                print(f"   [ERROR] Request cancelled - data not available")
            else:
                print(f"   [ERROR] {error_str}")
            return None

    def probe_with_progressive_windows(self, ticker, bar_size, max_days_back=180):
        """Try progressively smaller windows to find available data."""
        print(f"\n[PROGRESSIVE SEARCH] Finding earliest {bar_size} data for {ticker}...")
        print(f"                      Starting from T-{max_days_back} days\n")

        # Try progressively smaller windows
        windows = [max_days_back, 90, 60, 30, 14, 7, 3, 1]

        for days in windows:
            if days > max_days_back:
                continue

            print(f"[ATTEMPT] Trying T-{days} days window...")
            earliest = self.probe_data(ticker, bar_size, days)

            if earliest is not None:
                print(f"\n[SUCCESS] Found data! Earliest date: {earliest.strftime('%Y-%m-%d')}")
                return earliest

            print()

        print(f"\n[WARNING] No data found in any window (tested: {windows} days)")
        print(f"          IBKR may not have {bar_size} bars for {ticker}")
        return None

    def close(self):
        """Close IBKR connection."""
        if self.ib:
            self.ib.disconnect()

def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Probe IBKR for data availability",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Find earliest 1-min data for AAPL going back 180 days
  python probe_data_availability.py --ticker AAPL --timeframe "1 min" --days-back 180

  # Find earliest 5-min data for SPY going back 1 year
  python probe_data_availability.py --ticker SPY --timeframe "5 mins" --days-back 365
        """
    )

    parser.add_argument(
        "--ticker",
        type=str,
        required=True,
        help="Ticker symbol (e.g., AAPL, SPY)"
    )
    parser.add_argument(
        "--timeframe",
        type=str,
        required=True,
        help='Bar size (e.g., "1 min", "5 mins", "1 hour", "1 day")'
    )
    parser.add_argument(
        "--days-back",
        type=int,
        default=180,
        help="Number of days to go back (default: 180)"
    )

    args = parser.parse_args()

    print("\n[IBKR] Data Availability Prober")
    print("="*60)
    print(f"Ticker: {args.ticker}")
    print(f"Timeframe: {args.timeframe}")
    print(f"Days back: {args.days_back}")
    print(f"IBKR: {IBKR_HOST}:{IBKR_PORT}")
    print("="*60)

    prober = DataAvailabilityProber()

    if not prober.connect_ibkr():
        return

    try:
        earliest_date = prober.probe_with_progressive_windows(
            args.ticker,
            args.timeframe,
            args.days_back
        )

        if earliest_date:
            print("\n" + "="*60)
            print(f"[SUCCESS] Earliest available date for {args.ticker} {args.timeframe}:")
            print(f"          {earliest_date.strftime('%Y-%m-%d')}")
            print("="*60)

            # Save result for later use
            result_file = f"probe_result_{args.ticker}_{args.timeframe.replace(' ', '_')}.txt"
            with open(result_file, 'w') as f:
                f.write(earliest_date.strftime('%Y-%m-%d'))
            print(f"\nResult saved to: {result_file}")
        else:
            print("\n" + "="*60)
            print(f"[FAILED] Could not determine earliest date for {args.ticker} {args.timeframe}")
            print("="*60)
    finally:
        prober.close()

if __name__ == "__main__":
    main()
