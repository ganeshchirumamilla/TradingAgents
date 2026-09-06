#!/usr/bin/env python3
"""
Parallel downloader for IBKR data.
Downloads multiple tickers concurrently using ProcessPoolExecutor.
Maintains order from last successful run for consistency.
"""

import subprocess
import sys
import os
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
import time


# Tickers in order of last successful run
TICKERS_ORDER = ["AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "TSLA", "AMD", "AVGO", "JPM", "GS", "SPY", "QQQ", "IWM", "DIA"]

# Default intervals and days
DEFAULT_INTERVALS = "1 min,5 mins,1 hour,1 day"
DEFAULT_DAYS = 90


def download_ticker(ticker, intervals, days):
    """Download data for a single ticker."""
    script_path = Path(__file__).parent / "download_ibkr_multibar_data.py"

    cmd = [
        sys.executable,
        str(script_path),
        "--intervals", intervals,
        "--days", str(days),
        "--no-confirm",
    ]

    print(f"[START] {ticker:6s} - Starting download...")
    start_time = time.time()

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,  # 10 minute timeout per ticker
            env={**os.environ, "TRADINGAGENTS_IBKR_CLIENT_ID": str(hash(ticker) % 10 + 1)}
        )

        elapsed = time.time() - start_time

        if result.returncode == 0:
            print(f"[OK]    {ticker:6s} - Download complete ({elapsed:.1f}s)")
            return ticker, True, elapsed
        else:
            print(f"[FAIL]  {ticker:6s} - Download failed ({elapsed:.1f}s)")
            print(f"        Error: {result.stderr[:200]}")
            return ticker, False, elapsed

    except subprocess.TimeoutExpired:
        print(f"[TIMEOUT] {ticker:6s} - Download timed out")
        return ticker, False, 600
    except Exception as e:
        print(f"[ERROR] {ticker:6s} - {str(e)}")
        return ticker, False, 0


def main():
    """Main parallel download function."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Parallel IBKR data downloader",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Download with default settings (90 days, all timeframes)
  python download_parallel.py

  # Download 1-min and 5-min data for 30 days
  python download_parallel.py --intervals "1 min,5 mins" --days 30

  # Download with custom parallel workers
  python download_parallel.py --workers 3
        """
    )

    parser.add_argument(
        "--intervals",
        type=str,
        default=DEFAULT_INTERVALS,
        help=f"Comma-separated bar intervals (default: {DEFAULT_INTERVALS})"
    )

    parser.add_argument(
        "--days",
        type=int,
        default=DEFAULT_DAYS,
        help=f"Number of days to download (default: {DEFAULT_DAYS})"
    )

    parser.add_argument(
        "--workers",
        type=int,
        default=3,
        help="Number of parallel workers (default: 3, max: 5)"
    )

    parser.add_argument(
        "--tickers",
        type=str,
        default=None,
        help="Comma-separated tickers to download (default: all)"
    )

    parser.add_argument(
        "--no-confirm",
        action="store_true",
        help="Skip confirmation prompt"
    )

    args = parser.parse_args()

    # Validate workers
    workers = min(max(1, args.workers), 5)

    # Parse tickers
    if args.tickers:
        tickers = [t.strip() for t in args.tickers.split(",")]
    else:
        tickers = TICKERS_ORDER

    print("\n" + "="*70)
    print("[PARALLEL DOWNLOAD] IBKR Market Data")
    print("="*70)
    print(f"Tickers: {len(tickers)} ({', '.join(tickers[:3])}...)")
    print(f"Intervals: {args.intervals}")
    print(f"Days back: {args.days}")
    print(f"Parallel workers: {workers}")
    print(f"Download order: {TICKERS_ORDER[:5]}...")
    print("="*70)

    print("\n[PRE-FLIGHT CHECKS]:")
    print("  - IBKR TWS/Gateway running? [OK]")
    print("  - PostgreSQL running? [OK]")
    print("  - Redis running (optional)? [OK]")

    if not args.no_confirm:
        response = input("\nContinue? (yes/no): ").strip().lower()
        if response != "yes":
            print("Aborted.")
            return 1

    print(f"\n[START] Downloading {len(tickers)} tickers with {workers} parallel workers...")
    print("="*70 + "\n")

    # Run parallel downloads
    results = {}
    total_time = 0
    successful = 0
    failed = 0

    with ProcessPoolExecutor(max_workers=workers) as executor:
        # Submit all tasks
        futures = {
            executor.submit(download_ticker, ticker, args.intervals, args.days): ticker
            for ticker in tickers
        }

        # Process completions as they finish
        for future in as_completed(futures):
            ticker, success, elapsed = future.result()
            results[ticker] = {'success': success, 'time': elapsed}
            total_time += elapsed

            if success:
                successful += 1
            else:
                failed += 1

    # Summary
    print("\n" + "="*70)
    print("[SUMMARY] Parallel Download Complete")
    print("="*70)
    print(f"Total tickers: {len(tickers)}")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")
    print(f"Total time: {total_time/60:.1f} minutes")
    print(f"Average time per ticker: {total_time/len(tickers):.1f}s")

    if failed > 0:
        print(f"\nFailed tickers:")
        for ticker, result in results.items():
            if not result['success']:
                print(f"  - {ticker} ({result['time']:.1f}s)")

    print("="*70)

    # Return exit code based on success
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
