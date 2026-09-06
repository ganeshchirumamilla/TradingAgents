#!/usr/bin/env python3
"""
Run Multi-Timeframe Momentum Strategy backtest for past 1 year.
Uses daily and hourly data from PostgreSQL.
Initial capital: $10,000
Re-invests all profits.
"""

import os
import sys
import pandas as pd
import psycopg2
from datetime import datetime, timedelta
import logging

from multi_timeframe_momentum import MultiTimeframeMomentumStrategy

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database configuration
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "tradingagents")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "admin")

TICKERS = ["AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "TSLA", "AMD", "AVGO", "JPM", "GS", "SPY", "QQQ", "IWM", "DIA"]

def fetch_data_from_postgres(ticker, interval, days_back=365):
    """Fetch market data from PostgreSQL."""
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )

        table_name = f"historical_data_{interval}"
        cutoff_date = datetime.now() - timedelta(days=days_back)

        query = f"""
            SELECT date, open, high, low, close, volume
            FROM {table_name}
            WHERE ticker = %s AND date >= %s
            ORDER BY date ASC
        """

        df = pd.read_sql_query(
            query,
            conn,
            params=(ticker, cutoff_date)
        )

        conn.close()

        if df.empty:
            logger.warning(f"No data for {ticker} {interval}")
            return None

        df['date'] = pd.to_datetime(df['date'])
        return df

    except Exception as e:
        logger.error(f"Error fetching {ticker} {interval}: {e}")
        return None

def main():
    """Run backtest."""
    logger.info(f"\n{'='*60}")
    logger.info(f"Multi-Timeframe Momentum Strategy - 1 Year Backtest")
    logger.info(f"Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"{'='*60}\n")

    # Fetch data for all tickers
    logger.info(f"Fetching data for {len(TICKERS)} tickers...")
    data_dict = {}

    for ticker in TICKERS:
        daily = fetch_data_from_postgres(ticker, "daily", days_back=365)
        hourly = fetch_data_from_postgres(ticker, "hourly", days_back=365)

        if daily is not None and hourly is not None:
            data_dict[ticker] = {
                'daily': daily,
                'hourly': hourly,
            }
            logger.info(f"  {ticker}: {len(daily)} daily bars, {len(hourly)} hourly bars")
        else:
            logger.warning(f"  {ticker}: Skipping (insufficient data)")

    if not data_dict:
        logger.error("No data available for backtest")
        sys.exit(1)

    logger.info(f"\nReady to backtest on {len(data_dict)} tickers\n")

    # Calculate date range
    all_dates = []
    for ticker in data_dict:
        all_dates.extend(data_dict[ticker]['daily']['date'].tolist())

    if not all_dates:
        logger.error("No dates found")
        sys.exit(1)

    start_date = min(all_dates)
    end_date = max(all_dates)

    logger.info(f"Data Range: {start_date.date()} to {end_date.date()}")
    logger.info(f"Duration: {(end_date - start_date).days} days\n")

    # Initialize strategy
    strategy = MultiTimeframeMomentumStrategy(
        initial_capital=10000,
        risk_per_trade=0.02,  # 2% risk per trade
        max_positions=5       # Max 5 concurrent positions
    )

    # Run backtest
    logger.info("Running backtest...\n")
    strategy.backtest(data_dict, start_date, end_date)

    # Generate report
    logger.info("\nGenerating report...")
    report = strategy.generate_report()

    # Export results to CSV
    if report and not report['trades'].empty:
        output_file = f"backtest_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        report['trades'].to_csv(output_file, index=False)
        logger.info(f"Trades exported to: {output_file}")

        # Export equity curve
        equity_file = f"equity_curve_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        pd.DataFrame(report['equity_curve']).to_csv(equity_file, index=False)
        logger.info(f"Equity curve exported to: {equity_file}")

    logger.info(f"\n{'='*60}")
    logger.info(f"Backtest Complete: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"{'='*60}\n")

if __name__ == "__main__":
    main()
