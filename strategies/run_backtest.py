#!/usr/bin/env python
"""
Complete Backtesting Script - MA/RSI Strategy

This script:
1. Downloads data from IBKR (or uses cached data)
2. Runs the MA/RSI strategy backtest
3. Generates comprehensive results
4. Exports results to CSV
"""

import logging
import os
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Add strategies directory to path
strategies_dir = Path(__file__).parent
sys.path.insert(0, str(strategies_dir.parent))

from strategies.ma_rsi_strategy import MARSIStrategy
from tradingagents.brokers.ibkr_client import IBKRClient, IBKRConfig, IBKRNotConfiguredError
from tradingagents.dataflows.local_cache import LocalDataCache


def get_data(ticker: str, start_date: str, end_date: str, use_cache: bool = True) -> pd.DataFrame:
    """Get historical data from cache or IBKR."""

    cache = LocalDataCache()

    # Try cache first
    if use_cache:
        logger.info(f"Checking cache for {ticker}...")
        cached_data = cache.get_historical_data(
            ticker,
            data_type="daily",
            start_date=start_date,
            end_date=end_date,
        )

        if cached_data is not None and not cached_data.empty:
            logger.info(f"✓ Loaded {len(cached_data)} bars from cache")

            # Convert to standard format
            df = cached_data.copy()
            if "date" in df.columns:
                df.set_index("date", inplace=True)
                df.index = pd.to_datetime(df.index)

            # Ensure we have required columns
            if "close" not in df.columns:
                logger.error(f"Missing 'close' column in cached data")
                return None

            return df

    # Download from IBKR
    logger.info(f"Downloading {ticker} from IBKR...")
    try:
        config = IBKRConfig(
            host=os.getenv("TRADINGAGENTS_IBKR_HOST", "127.0.0.1"),
            port=int(os.getenv("TRADINGAGENTS_IBKR_PORT", 4002)),
            account=os.getenv("TRADINGAGENTS_IBKR_ACCOUNT"),
        )

        client = IBKRClient(config)

        # Convert date format for IBKR
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")

        bars = client.get_historical_bars(
            symbol=ticker,
            end_date=end_dt.strftime("%Y%m%d"),
            duration="365 D",  # 1 year lookback
            bar_size="1 day",
        )

        if not bars:
            logger.error(f"No data returned from IBKR for {ticker}")
            return None

        # Convert to DataFrame
        df = pd.DataFrame([bar.__dict__ for bar in bars])
        df["date"] = pd.to_datetime(df["date"])
        df.set_index("date", inplace=True)

        # Rename columns to standard format
        df = df.rename(columns={"open": "open", "high": "high", "low": "low", "close": "close", "volume": "volume"})

        # Cache the data
        logger.info(f"Caching {len(df)} bars for {ticker}...")
        cache.store_historical_data(ticker, df.reset_index())

        logger.info(f"✓ Downloaded and cached {len(df)} bars from IBKR")

        return df

    except IBKRNotConfiguredError as e:
        logger.error(f"IBKR connection failed: {e}")
        logger.error("Make sure IB Gateway is running with API enabled")
        return None
    except Exception as e:
        logger.error(f"Error downloading data: {e}")
        return None


def run_backtest(
    ticker: str,
    start_date: str,
    end_date: str,
    initial_capital: float = 100000,
    use_cache: bool = True,
):
    """Run complete backtest for a ticker."""

    print("\n" + "=" * 70)
    print(f"  MA/RSI Strategy Backtest: {ticker}")
    print("=" * 70)

    # Get data
    logger.info(f"Loading data for {ticker} ({start_date} to {end_date})...")
    df = get_data(ticker, start_date, end_date, use_cache=use_cache)

    if df is None or df.empty:
        logger.error(f"No data available for {ticker}")
        return None

    logger.info(f"Loaded {len(df)} bars")

    # Run strategy
    logger.info("Running MA/RSI strategy...")
    strategy = MARSIStrategy(
        sma_short=20,
        sma_long=50,
        rsi_period=14,
        rsi_overbought=70,
        rsi_oversold=30,
        stop_loss_pct=0.02,
        take_profit_pct=0.03,
        position_size_pct=0.05,
    )

    results = strategy.backtest(df, ticker, initial_capital=initial_capital)

    # Print results
    strategy.print_results(results)

    # Export results
    if results["trades"]:
        trades_df = pd.DataFrame(results["trades"])
        output_file = f"backtest_results_{ticker}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        trades_df.to_csv(output_file, index=False)
        logger.info(f"Exported trades to: {output_file}")

    return results


def main():
    """Run backtests for multiple tickers."""

    print("\n" + "=" * 70)
    print("  MA/RSI Strategy Backtester")
    print("=" * 70)

    # Configuration from environment
    start_date = os.getenv("TRADINGAGENTS_BACKTEST_START_DATE", "2024-06-01")
    end_date = os.getenv("TRADINGAGENTS_BACKTEST_END_DATE", "2024-12-31")
    initial_capital = float(os.getenv("TRADINGAGENTS_BACKTEST_INITIAL_CAPITAL", 100000))
    use_cache = os.getenv("TRADINGAGENTS_USE_LOCAL_DATA_CACHE", "true").lower() == "true"

    # Tickers to backtest
    tickers = ["AAPL", "NVDA", "MSFT", "SPY"]

    print(f"\nConfiguration:")
    print(f"  Period:       {start_date} to {end_date}")
    print(f"  Initial Cap:  ${initial_capital:,.2f}")
    print(f"  Use Cache:    {use_cache}")
    print(f"  Tickers:      {', '.join(tickers)}")

    # Run backtests
    all_results = {}
    for ticker in tickers:
        try:
            results = run_backtest(
                ticker,
                start_date,
                end_date,
                initial_capital=initial_capital,
                use_cache=use_cache,
            )
            if results:
                all_results[ticker] = results
        except Exception as e:
            logger.error(f"Error backtesting {ticker}: {e}")
            continue

    # Summary
    print("\n" + "=" * 70)
    print("  BACKTEST SUMMARY")
    print("=" * 70)

    if all_results:
        for ticker, results in all_results.items():
            print(
                f"\n{ticker:>6} | Return: {results['total_return']:>8.2%} | "
                f"Trades: {results['total_trades']:>3} | "
                f"Win Rate: {results['win_rate']:>6.2%}"
            )

    print("\n" + "=" * 70)
    logger.info("Backtest complete!")


if __name__ == "__main__":
    main()
