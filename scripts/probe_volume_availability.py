#!/usr/bin/env python3
"""
Probe IBKR for volume data availability with different whatToShow types.
Compares MIDPOINT vs TRADES to see which provides volume.

Usage:
    python probe_volume_availability.py --ticker AAPL
    python probe_volume_availability.py --ticker AAPL --days 90
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
IBKR_CLIENT_ID = int(os.getenv("TRADINGAGENTS_IBKR_CLIENT_ID", "3"))

class VolumeProber:
    """Probe IBKR for volume data availability."""

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

    def probe_volume(self, ticker, bar_size, what_to_show, days_back):
        """Probe for volume data with specific whatToShow parameter."""
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

            print(f"\n   [REQUEST] whatToShow={what_to_show}, bar_size={bar_size}, duration={duration}")

            bars = self.ib.reqHistoricalData(
                contract,
                endDateTime="",  # Today
                durationStr=duration,
                barSizeSetting=bar_size,
                whatToShow=what_to_show,
                useRTH=True,
                formatDate=1,
                keepUpToDate=False,
                timeout=60
            )

            # Convert to DataFrame
            df = util.df(bars)

            if df.empty:
                print(f"              No data returned")
                return None

            # Check volume column
            if 'volume' in df.columns:
                volume_col = df['volume']
                non_zero_volumes = (volume_col > 0).sum()
                zero_volumes = (volume_col == 0).sum()
                negative_volumes = (volume_col < 0).sum()

                print(f"              Got {len(df)} bars")
                print(f"              Volume stats:")
                print(f"                - Non-zero volume: {non_zero_volumes} bars ({100*non_zero_volumes/len(df):.1f}%)")
                print(f"                - Zero volume: {zero_volumes} bars ({100*zero_volumes/len(df):.1f}%)")
                print(f"                - Negative volume: {negative_volumes} bars ({100*negative_volumes/len(df):.1f}%)")

                if non_zero_volumes > 0:
                    print(f"                - Min volume: {volume_col[volume_col > 0].min():.0f}")
                    print(f"                - Max volume: {volume_col.max():.0f}")
                    print(f"                - Avg volume: {volume_col[volume_col > 0].mean():.0f}")

                # Check dates
                df['date'] = pd.to_datetime(df['date'])
                print(f"              Date range: {df['date'].min()} to {df['date'].max()}")

                return df
            else:
                print(f"              No volume column in data")
                return None

        except Exception as e:
            error_str = str(e)
            if "Timeout" in error_str or "timeout" in error_str:
                print(f"              [ERROR] Timeout - request too large or data unavailable")
            elif "cancelled" in error_str.lower():
                print(f"              [ERROR] Request cancelled")
            else:
                print(f"              [ERROR] {error_str}")
            return None

    def close(self):
        """Close IBKR connection."""
        if self.ib:
            self.ib.disconnect()

def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Probe IBKR for volume data availability",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Check volume for AAPL across different data types
  python probe_volume_availability.py --ticker AAPL

  # Check with longer history
  python probe_volume_availability.py --ticker AAPL --days 90
        """
    )

    parser.add_argument(
        "--ticker",
        type=str,
        default="AAPL",
        help="Ticker symbol (default: AAPL)"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Number of days to go back (default: 30)"
    )

    args = parser.parse_args()

    print("\n" + "="*70)
    print("[IBKR] Volume Data Availability Prober")
    print("="*70)
    print(f"Ticker: {args.ticker}")
    print(f"Days back: {args.days}")
    print(f"IBKR: {IBKR_HOST}:{IBKR_PORT}")
    print("="*70)

    prober = VolumeProber()

    if not prober.connect_ibkr():
        return

    try:
        # Define timeframes to test
        timeframes = [
            ("1 min", "1 min data"),
            ("5 mins", "5-min data"),
            ("1 hour", "hourly data"),
            ("1 day", "daily data"),
        ]

        # Test each timeframe with both MIDPOINT and TRADES
        results = {}

        for bar_size, description in timeframes:
            print(f"\n[PROBE] Testing {description} ({bar_size})")
            print("-" * 70)

            results[bar_size] = {}

            # Test MIDPOINT
            print(f"   Testing MIDPOINT (current setting):")
            df_midpoint = prober.probe_volume(args.ticker, bar_size, "MIDPOINT", args.days)
            results[bar_size]["MIDPOINT"] = df_midpoint is not None

            time.sleep(1)  # Rate limit

            # Test TRADES
            print(f"   Testing TRADES (alternative):")
            df_trades = prober.probe_volume(args.ticker, bar_size, "TRADES", args.days)
            results[bar_size]["TRADES"] = df_trades is not None

            time.sleep(1)  # Rate limit

        # Summary
        print("\n" + "="*70)
        print("[SUMMARY] Volume Data Availability")
        print("="*70)

        for bar_size, data_types in results.items():
            midpoint_ok = data_types.get("MIDPOINT", False)
            trades_ok = data_types.get("TRADES", False)

            print(f"\n{bar_size}:")
            print(f"  MIDPOINT: {'[OK - Has volume]' if midpoint_ok else '[FAIL - No volume (-1)]'}")
            print(f"  TRADES:   {'[OK - Has volume]' if trades_ok else '[FAIL - No volume]'}")

            if trades_ok and not midpoint_ok:
                print(f"  -> RECOMMENDATION: Use TRADES instead of MIDPOINT")

        print("\n" + "="*70)
        print("[CONCLUSION]")
        print("="*70)

        # Check if any timeframe has volume
        has_volume = any(any(v for v in data_types.values()) for data_types in results.values())

        if has_volume:
            print("[OK] IBKR is providing volume data with TRADES")
            print("     Recommend updating whatToShow from 'MIDPOINT' to 'TRADES'")
        else:
            print("[WARNING] IBKR may not be providing volume data")
            print("          Check IBKR subscription levels or data availability")

    finally:
        prober.close()

if __name__ == "__main__":
    main()
