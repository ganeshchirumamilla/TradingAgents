#!/usr/bin/env python
"""
Complete example: IBKR setup → Download data → Run backtest

This example demonstrates the full workflow:
1. Connect to IBKR and verify account
2. Download historical data from IBKR
3. Cache data locally
4. Run backtest using cached data
5. Analyze results
"""

import logging
import os
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def section(title: str):
    """Print a section header."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def example_1_verify_ibkr_connection():
    """Example 1: Verify IBKR connection."""
    section("1. Verify IBKR Connection")

    from tradingagents.brokers.ibkr_client import IBKRClient, IBKRConfig, IBKRNotConfiguredError

    try:
        config = IBKRConfig(
            host=os.getenv("TRADINGAGENTS_IBKR_HOST", "127.0.0.1"),
            port=int(os.getenv("TRADINGAGENTS_IBKR_PORT", 7497)),
            account=os.getenv("TRADINGAGENTS_IBKR_ACCOUNT"),
        )

        client = IBKRClient(config)
        print(f"\n📍 Connecting to IBKR at {config.host}:{config.port}...")

        summary = client.get_account_summary()
        account_id = summary.get("account")
        nlv = summary.get("NetLiquidation", 0)
        cash = summary.get("CashBalance", 0)

        print(f"✓ Connection successful!")
        print(f"  Account ID: {account_id}")
        print(f"  Net Liquidation Value: ${nlv:,.2f}")
        print(f"  Available Cash: ${cash:,.2f}")

        # Get positions
        positions = client.get_positions()
        if positions:
            print(f"\n  Open Positions ({len(positions)}):")
            for pos in positions:
                print(f"    {pos['symbol']}: {pos['position']} shares @ ${pos['avg_cost']:.2f}")
        else:
            print(f"\n  No open positions")

        return client, config

    except IBKRNotConfiguredError as e:
        print(f"✗ IBKR Connection Failed: {e}")
        print("\nTo fix:")
        print("  1. Install: pip install 'tradingagents[ibkr]'")
        print("  2. Start TWS or IB Gateway with API enabled")
        print("  3. Set TRADINGAGENTS_IBKR_PORT=7497 (TWS paper)")
        return None, None


def example_2_download_data(client):
    """Example 2: Download historical data from IBKR."""
    section("2. Download Historical Data")

    if client is None:
        print("Skipped (IBKR not connected)")
        return None

    tickers = ["AAPL", "NVDA", "MSFT"]
    downloaded_data = {}

    print(f"\n📥 Downloading data for {len(tickers)} tickers (365 days)...\n")

    for ticker in tickers:
        try:
            print(f"  Downloading {ticker}...", end="", flush=True)

            bars = client.get_historical_bars(
                symbol=ticker,
                end_date=datetime.now().strftime("%Y%m%d"),
                duration="365 D",
                bar_size="1 day",
            )

            if bars:
                downloaded_data[ticker] = bars
                print(f" ✓ ({len(bars)} bars)")
            else:
                print(f" ✗ (no data)")

        except Exception as e:
            print(f" ✗ ({e})")

    return downloaded_data


def example_3_cache_data(downloaded_data):
    """Example 3: Cache data locally."""
    section("3. Cache Data Locally")

    if not downloaded_data:
        print("Skipped (no data)")
        return None

    from tradingagents.dataflows.local_cache import LocalDataCache

    cache = LocalDataCache()

    print(f"\n💾 Caching {len(downloaded_data)} tickers...\n")

    for ticker, bars in downloaded_data.items():
        try:
            success = cache.store_historical_data(
                ticker=ticker,
                data=bars,
                data_type="daily",
            )
            if success:
                print(f"  {ticker}: ✓ Cached {len(bars)} bars")
            else:
                print(f"  {ticker}: ✗ Cache failed")
        except Exception as e:
            print(f"  {ticker}: ✗ ({e})")

    # Show cache status
    print("\n📊 Cache Status:")
    print(cache.status())

    return cache


def example_4_backtest(cache):
    """Example 4: Run backtest with cached data."""
    section("4. Run Backtest")

    if cache is None:
        print("Skipped (no cache)")
        return None

    from tradingagents.backtesting import BacktestEngine, BacktestConfig
    from tradingagents.graph.trading_graph import TradingAgentsGraph
    from tradingagents.default_config import DEFAULT_CONFIG

    print("\n🎯 Configuring backtest...")

    # Create backtest config
    config = BacktestConfig(
        start_date=datetime(2024, 1, 1),
        end_date=datetime(2024, 12, 31),
        initial_capital=100000,
        commission_rate=0.001,  # 0.1%
        slippage_bps=10,  # 10 basis points
        use_local_cache=True,
    )

    print(f"  Period: {config.start_date.date()} → {config.end_date.date()}")
    print(f"  Initial Capital: ${config.initial_capital:,.2f}")
    print(f"  Commission: {config.commission_rate:.2%}")
    print(f"  Slippage: {config.slippage_bps} bps")

    # Create engine
    print("\n  Initializing TradingAgentsGraph...")
    ta_graph = TradingAgentsGraph(
        config=DEFAULT_CONFIG,
        debug=False,
    )

    engine = BacktestEngine(
        ta_graph=ta_graph,
        backtest_config=config,
        tickers=["AAPL", "NVDA", "MSFT"],
    )

    print("\n▶️  Running backtest...\n")

    try:
        results = engine.run()
        return results
    except Exception as e:
        logger.error(f"Backtest failed: {e}")
        return None


def example_5_analyze_results(results):
    """Example 5: Analyze backtest results."""
    section("5. Backtest Results")

    if results is None:
        print("Skipped (no results)")
        return

    # Print summary
    print(results.summary())

    # Get metrics
    metrics = results.metrics()
    if metrics:
        print("\n📈 Detailed Metrics:")
        print(f"  Equity Peak: ${metrics.get('peak_value', 0):,.2f}")
        print(f"  Final Equity: ${metrics.get('final_value', 0):,.2f}")

    # Export trades
    df = results.to_dataframe()
    if not df.empty:
        print(f"\n📋 Trades ({len(df)}):")
        print(df.head(10).to_string())

        # Save to CSV
        csv_path = "/tmp/backtest_trades.csv"
        df.to_csv(csv_path, index=False)
        print(f"\n💾 Saved to: {csv_path}")


def example_6_live_trading_setup():
    """Example 6: Setup for live trading."""
    section("6. Live Trading Setup (Paper → Live)")

    print("""
To transition from backtesting/paper trading to live trading:

1. Start with PAPER TRADING (safest):
   TRADINGAGENTS_IBKR_ENABLED=true
   TRADINGAGENTS_IBKR_PAPER=true
   TRADINGAGENTS_IBKR_AUTO_EXECUTE=false  # No real orders yet

   Run: tradingagents analyze

2. Test with SMALL LIVE ORDERS (if feeling confident):
   TRADINGAGENTS_IBKR_ENABLED=true
   TRADINGAGENTS_IBKR_PAPER=false  # Live mode
   TRADINGAGENTS_IBKR_AUTO_EXECUTE=true
   TRADINGAGENTS_IBKR_ORDER_QUANTITY=1  # Start small!
   TRADINGAGENTS_IBKR_CONFIRM_LIVE=true

   Run: tradingagents analyze

3. IMPORTANT SAFETY CHECKS:
   ✓ Account is funded
   ✓ Position limits are set
   ✓ Stop losses are in place
   ✓ You understand the analysis
   ✓ You can manually stop the bot

See IBKR_SETUP_AND_BACKTESTING.md for full details.
    """)


def main():
    """Run complete example."""
    print("""
╔════════════════════════════════════════════════════════╗
║  IBKR + TradingAgents Complete Workflow Example       ║
╚════════════════════════════════════════════════════════╝

This script demonstrates:
  1. Verify IBKR connection
  2. Download historical data
  3. Cache data locally
  4. Run backtest
  5. Analyze results
  6. Setup for live trading
    """)

    # Example 1: Verify connection
    client, config = example_1_verify_ibkr_connection()

    # Example 2: Download data
    downloaded_data = example_2_download_data(client)

    # Example 3: Cache data
    cache = example_3_cache_data(downloaded_data)

    # Example 4: Run backtest
    results = example_4_backtest(cache)

    # Example 5: Analyze results
    example_5_analyze_results(results)

    # Example 6: Live trading
    example_6_live_trading_setup()

    print("\n" + "=" * 70)
    print("  ✓ Example Complete!")
    print("=" * 70)
    print("\nNext Steps:")
    print("  1. Review backtest results")
    print("  2. Adjust strategy if needed")
    print("  3. Read IBKR_SETUP_AND_BACKTESTING.md for full details")
    print("  4. Consider live trading with caution")
    print("\nDocumentation:")
    print("  - TECHNICAL_FLOW.md: Architecture & flow")
    print("  - IBKR_SETUP_AND_BACKTESTING.md: Complete setup guide")
    print("  - IBKR_QUICKSTART.md: Quick reference")


if __name__ == "__main__":
    main()
