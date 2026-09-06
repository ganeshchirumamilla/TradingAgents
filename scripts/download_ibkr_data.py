#!/usr/bin/env python
"""Download and cache historical data from Interactive Brokers (IBKR).

This script connects to TWS or IB Gateway and downloads historical data
for specified tickers, persisting them locally for offline backtesting.

Usage:
    python download_ibkr_data.py --tickers AAPL NVDA MSFT --days 365
    python download_ibkr_data.py --tickers-file tickers.txt --days 252
"""

import argparse
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description="Download historical data from IBKR and cache locally"
    )
    parser.add_argument(
        "--tickers",
        nargs="+",
        default=["AAPL", "NVDA", "MSFT", "TSLA", "SPY"],
        help="Tickers to download (space-separated)",
    )
    parser.add_argument(
        "--tickers-file",
        help="File with tickers (one per line)",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=365,
        help="Number of days of history to download",
    )
    parser.add_argument(
        "--cache-dir",
        default=os.path.expanduser("~/.tradingagents/data_cache"),
        help="Directory to cache data",
    )
    parser.add_argument(
        "--host",
        default=os.getenv("TRADINGAGENTS_IBKR_HOST", "127.0.0.1"),
        help="IBKR host",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("TRADINGAGENTS_IBKR_PORT", 7497)),
        help="IBKR port (7497=TWS paper, 4002=Gateway paper)",
    )
    parser.add_argument(
        "--client-id",
        type=int,
        default=int(os.getenv("TRADINGAGENTS_IBKR_CLIENT_ID", 1)),
        help="IBKR client ID",
    )
    parser.add_argument(
        "--account",
        default=os.getenv("TRADINGAGENTS_IBKR_ACCOUNT"),
        help="IBKR account ID",
    )

    args = parser.parse_args()

    # Load tickers from file if provided
    if args.tickers_file:
        with open(args.tickers_file) as f:
            args.tickers = [line.strip() for line in f if line.strip()]

    # Import after arg parsing so --help works without IBKR installed
    try:
        from tradingagents.brokers.ibkr_client import IBKRClient, IBKRConfig
        from tradingagents.dataflows.local_cache import LocalDataCache
    except ImportError as e:
        logger.error(
            f"Import error: {e}\n"
            "Make sure IBKR is installed: pip install 'tradingagents[ibkr]'"
        )
        return 1

    # Setup
    ibkr_config = IBKRConfig(
        host=args.host,
        port=args.port,
        client_id=args.client_id,
        account=args.account,
    )

    cache = LocalDataCache(cache_dir=args.cache_dir)
    client = IBKRClient(ibkr_config)

    logger.info("=" * 70)
    logger.info("IBKR Historical Data Downloader")
    logger.info("=" * 70)
    logger.info(f"IBKR Connection: {args.host}:{args.port} (client_id={args.client_id})")
    logger.info(f"Cache Directory: {args.cache_dir}")
    logger.info(f"Lookback Period: {args.days} days")
    logger.info(f"Tickers: {', '.join(args.tickers)}")
    logger.info("=" * 70)

    # Download for each ticker
    downloaded = 0
    failed = 0

    for ticker in args.tickers:
        try:
            logger.info(f"\n📥 Downloading {ticker}...")

            end_date = datetime.now()
            duration = f"{args.days} D"

            # Download daily bars
            bars = client.get_historical_bars(
                symbol=ticker,
                end_date=end_date.strftime("%Y%m%d"),
                duration=duration,
                bar_size="1 day",
            )

            if not bars:
                logger.warning(f"  ✗ No data returned for {ticker}")
                failed += 1
                continue

            # Cache the data
            start_date = (end_date - timedelta(days=args.days)).strftime("%Y-%m-%d")
            end_date_str = end_date.strftime("%Y-%m-%d")

            success = cache.store_historical_data(
                ticker=ticker,
                data=bars,
                data_type="daily",
                start_date=start_date,
                end_date=end_date_str,
            )

            if success:
                logger.info(f"  ✓ {ticker}: Cached {len(bars)} daily bars")
                downloaded += 1
            else:
                logger.warning(f"  ✗ Failed to cache {ticker}")
                failed += 1

        except Exception as e:
            logger.error(f"  ✗ Error downloading {ticker}: {e}")
            failed += 1
            continue

    # Summary
    logger.info("\n" + "=" * 70)
    logger.info(f"Download Complete: {downloaded} succeeded, {failed} failed")
    logger.info("=" * 70)

    # Print cache status
    logger.info("\nCache Status:")
    print(cache.status())

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    exit(main())
