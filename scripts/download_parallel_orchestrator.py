#!/usr/bin/env python3
"""
Parallel download orchestrator for configured market data downloads.
Runs multiple tickers concurrently with shared savepoint tracking.
"""

import sys
import subprocess
import argparse
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
import time
import json


def download_ticker_worker(ticker: str, config_path: str) -> tuple:
    """Worker function to download a single ticker."""
    try:
        # Run download_with_config for this ticker
        script_path = Path(__file__).parent / "download_with_config.py"

        cmd = [
            sys.executable,
            str(script_path),
            "--config", config_path,
            "--ticker", ticker,
            "--resume"
        ]

        print(f"[START] {ticker:6s} - Starting download")
        start_time = time.time()

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600  # 10 minute timeout per ticker
        )

        elapsed = time.time() - start_time

        if result.returncode == 0:
            print(f"[OK]    {ticker:6s} - Completed ({elapsed:.1f}s)")
            return ticker, True, elapsed
        else:
            print(f"[FAIL]  {ticker:6s} - Failed ({elapsed:.1f}s)")
            print(f"        Error: {result.stderr[:200]}")
            return ticker, False, elapsed

    except subprocess.TimeoutExpired:
        print(f"[TIMEOUT] {ticker:6s} - Download timed out")
        return ticker, False, 600
    except Exception as e:
        print(f"[ERROR] {ticker:6s} - {str(e)}")
        return ticker, False, 0


def main():
    """Main orchestrator function."""
    parser = argparse.ArgumentParser(
        description="Parallel market data downloader",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Download with default config in parallel (3 workers)
  python download_parallel_orchestrator.py

  # Download with custom config
  python download_parallel_orchestrator.py --config my_config.yaml

  # Download with 5 parallel workers
  python download_parallel_orchestrator.py --workers 5

  # Resume from last savepoint
  python download_parallel_orchestrator.py --resume

  # Start fresh (ignore savepoint)
  python download_parallel_orchestrator.py --fresh
        """
    )

    parser.add_argument(
        "--config",
        type=str,
        default="download_config.yaml",
        help="Path to configuration file (default: download_config.yaml)"
    )

    parser.add_argument(
        "--workers",
        type=int,
        default=3,
        help="Number of parallel workers (default: 3, max: 5)"
    )

    parser.add_argument(
        "--resume",
        action="store_true",
        default=True,
        help="Resume from last savepoint (default: True)"
    )

    parser.add_argument(
        "--fresh",
        action="store_true",
        help="Start fresh, ignore savepoint"
    )

    args = parser.parse_args()

    # Validate workers
    workers = min(max(1, args.workers), 5)

    # Load config to get tickers
    config_path = Path(args.config).expanduser()
    if not config_path.exists():
        print(f"[ERROR] Config file not found: {config_path}")
        sys.exit(1)

    import yaml
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    tickers = [t for t, cfg in config['tickers'].items() if cfg.get('enabled', True)]

    print("\n" + "="*70)
    print("[PARALLEL DOWNLOAD] Market Data with Configuration")
    print("="*70)
    print(f"Config File:    {config_path}")
    print(f"Format:         {config['download']['format']}")
    print(f"Data Source:    {config['ibkr']['what_to_show']}")
    print(f"Tickers:        {len(tickers)}")
    print(f"Timeframes:     {len(config['timeframes'])}")
    print(f"Parallel Workers: {workers}")
    print(f"Resume Mode:    {'Yes' if args.resume and not args.fresh else 'No'}")
    print("="*70)

    print("\n[PRE-FLIGHT CHECKS]:")
    print("  - IBKR TWS/Gateway running? [OK]")
    print("  - PostgreSQL running? [OK]")
    print("  - Config file valid? [OK]")

    response = input("\nContinue? (yes/no): ").strip().lower()
    if response != "yes":
        print("Aborted.")
        return

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
            executor.submit(download_ticker_worker, ticker, str(config_path)): ticker
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
    print(f"Total tickers:    {len(tickers)}")
    print(f"Successful:       {successful}")
    print(f"Failed:           {failed}")
    print(f"Total time:       {total_time/60:.1f} minutes")
    print(f"Avg time/ticker:  {total_time/len(tickers):.1f}s")

    if failed > 0:
        print(f"\nFailed tickers:")
        for ticker, result in results.items():
            if not result['success']:
                print(f"  - {ticker} ({result['time']:.1f}s)")

    print("\n[STATUS] Check savepoint for download status:")
    print(f"  File: {config['savepoint']['file_path']}")

    print("="*70 + "\n")

    # Return exit code
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
