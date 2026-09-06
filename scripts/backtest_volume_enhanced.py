#!/usr/bin/env python3
"""
Backtesting framework for volume-enhanced strategies.
Tests all enhanced strategies across all tickers and timeframes with commission.
Runs in parallel using ProcessPoolExecutor.
"""

import os
import sys
import json
import psycopg2
from datetime import datetime
from pathlib import Path
from decimal import Decimal
import pandas as pd
import numpy as np
from concurrent.futures import ProcessPoolExecutor, as_completed
import time

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent))

from backtest_enhanced_strategies import ENHANCED_STRATEGIES

# Database config
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "postgres")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "admin")

# Backtest config
INITIAL_CAPITAL = 10000
COMMISSION = 0.00001  # 0.001%
RISK_PER_TRADE = 0.01  # 1%

TICKERS = ["AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "TSLA", "AMD", "AVGO", "JPM", "GS", "SPY", "QQQ", "IWM", "DIA"]
TIMEFRAMES = {
    "1min": "historical_data_1min",
    "5min": "historical_data_5min",
    "1h": "historical_data_hourly",
    "1d": "historical_data_daily",
}


def get_historical_data(ticker, timeframe):
    """Fetch historical data from PostgreSQL."""
    try:
        conn = psycopg2.connect(
            host=DB_HOST, port=DB_PORT, database=DB_NAME,
            user=DB_USER, password=DB_PASSWORD
        )
        cursor = conn.cursor()

        table_name = TIMEFRAMES.get(timeframe)
        if not table_name:
            return None

        query = f"""
            SELECT date, open, high, low, close, volume
            FROM {table_name}
            WHERE ticker = %s
            ORDER BY date ASC
        """

        df = pd.read_sql_query(query, conn, params=(ticker,))
        conn.close()

        if df.empty:
            return None

        df['date'] = pd.to_datetime(df['date'])
        return df.sort_values('date').reset_index(drop=True)

    except Exception as e:
        print(f"[ERROR] Failed to fetch {ticker} {timeframe}: {e}")
        return None


def backtest_strategy(strategy_class, df, capital=INITIAL_CAPITAL, commission=COMMISSION):
    """Run backtest for a strategy."""
    if df is None or len(df) < 50:
        return None

    try:
        # Generate signals
        strategy = strategy_class()
        signals_df = strategy.generate_signals(df)

        if signals_df is None or signals_df.empty:
            return None

        # Initialize tracking
        position = 0
        equity = capital
        trades = []
        entry_price = 0
        entry_index = 0

        # Execute trades
        for idx, row in signals_df.iterrows():
            if idx < 50:  # Skip first 50 bars for indicator warmup
                continue

            price = row['close']
            volume = row['volume'] if pd.notna(row['volume']) else 1

            # Buy signal
            if row.get('buy', False) and position == 0 and equity > 0:
                position_size = (equity * RISK_PER_TRADE) / (price or 1)
                entry_price = price
                entry_index = idx
                position = position_size
                trades.append({'type': 'buy', 'price': price, 'size': position_size, 'date': row['date']})

            # Sell signal
            elif row.get('sell', False) and position > 0:
                exit_price = price
                pnl = (exit_price - entry_price) * position
                pnl_after_commission = pnl - (abs(position * entry_price) * commission) - (abs(position * exit_price) * commission)
                equity += pnl_after_commission
                trades.append({'type': 'sell', 'price': price, 'size': position, 'pnl': pnl_after_commission, 'date': row['date']})
                position = 0

        # Close open position at end
        if position > 0 and len(signals_df) > 0:
            final_price = signals_df.iloc[-1]['close']
            pnl = (final_price - entry_price) * position
            pnl_after_commission = pnl - (abs(position * entry_price) * commission) - (abs(position * final_price) * commission)
            equity += pnl_after_commission

        # Calculate metrics
        if not trades or len([t for t in trades if t['type'] == 'sell']) == 0:
            return None

        closed_trades = [t for t in trades if t['type'] == 'sell']
        wins = len([t for t in closed_trades if t['pnl'] > 0])
        losses = len([t for t in closed_trades if t['pnl'] <= 0])
        total_trades = len(closed_trades)

        if total_trades == 0:
            return None

        avg_win = np.mean([t['pnl'] for t in closed_trades if t['pnl'] > 0]) if wins > 0 else 0
        avg_loss = np.mean([t['pnl'] for t in closed_trades if t['pnl'] <= 0]) if losses > 0 else 0
        profit_factor = abs(avg_win * wins) / abs(avg_loss * losses) if losses > 0 else np.inf

        pnl = equity - capital
        ret = (pnl / capital) * 100 if capital > 0 else 0

        return {
            'total_trades': total_trades,
            'wins': wins,
            'losses': losses,
            'win_rate': f"{(wins/total_trades)*100:.2f}%" if total_trades > 0 else "0%",
            'avg_win': f"${avg_win:.2f}",
            'avg_loss': f"${avg_loss:.2f}",
            'profit_factor': f"{profit_factor:.2f}" if profit_factor != np.inf else "N/A",
            'total_pnl': f"${pnl:+.2f}",
            'final_equity': f"${equity:.2f}",
            'return': f"{ret:+.2f}%"
        }

    except Exception as e:
        print(f"[ERROR] Backtest error: {e}")
        return None


def run_single_backtest(strategy_name, ticker, timeframe):
    """Run a single backtest combination."""
    try:
        # Get data
        df = get_historical_data(ticker, timeframe)
        if df is None:
            return None

        # Get strategy
        if strategy_name not in ENHANCED_STRATEGIES:
            return None

        strategy_class = ENHANCED_STRATEGIES[strategy_name]

        # Run backtest
        result = backtest_strategy(strategy_class, df)

        return {
            'strategy': strategy_name,
            'ticker': ticker,
            'timeframe': timeframe,
            'result': result
        }

    except Exception as e:
        print(f"[ERROR] {strategy_name} {ticker} {timeframe}: {e}")
        return None


def main():
    """Main function."""
    import argparse

    parser = argparse.ArgumentParser(description="Volume-enhanced strategy backtests")
    parser.add_argument("--workers", type=int, default=4, help="Parallel workers")
    parser.add_argument("--strategies", type=str, default=None, help="Specific strategies (comma-separated)")
    parser.add_argument("--tickers", type=str, default=None, help="Specific tickers (comma-separated)")
    parser.add_argument("--timeframes", type=str, default=None, help="Specific timeframes (comma-separated)")

    args = parser.parse_args()

    # Parse arguments
    strategies = [s.strip() for s in args.strategies.split(",")] if args.strategies else list(ENHANCED_STRATEGIES.keys())
    tickers = [t.strip() for t in args.tickers.split(",")] if args.tickers else TICKERS
    timeframes = [tf.strip() for tf in args.timeframes.split(",")] if args.timeframes else list(TIMEFRAMES.keys())

    print("\n" + "="*70)
    print("[BACKTEST] Volume-Enhanced Strategies")
    print("="*70)
    print(f"Strategies: {len(strategies)}")
    print(f"Tickers: {len(tickers)}")
    print(f"Timeframes: {len(timeframes)}")
    print(f"Total combinations: {len(strategies) * len(tickers) * len(timeframes)}")
    print(f"Workers: {args.workers}")
    print(f"Commission: {COMMISSION*100:.4f}%")
    print(f"Initial capital: ${INITIAL_CAPITAL}")
    print("="*70 + "\n")

    # Create combinations
    combinations = [
        (strategy, ticker, timeframe)
        for strategy in strategies
        for ticker in tickers
        for timeframe in timeframes
    ]

    # Run backtests in parallel
    results_by_strategy = {}
    completed = 0
    start_time = time.time()

    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(run_single_backtest, s, t, tf): (s, t, tf)
            for s, t, tf in combinations
        }

        for future in as_completed(futures):
            strategy, ticker, timeframe = futures[future]
            completed += 1

            try:
                result = future.result()
                if result and result['result']:
                    key = f"{result['strategy']}_{result['ticker']}_{result['timeframe']}"
                    results_by_strategy.setdefault(result['strategy'], {})[key] = result['result']

                    status = "[OK]" if result['result']['wins'] > 0 else "[SKIP]"
                    print(f"{status} [{completed:3d}/{len(combinations)}] {strategy:30s} {ticker:6s} {timeframe:6s}")
                else:
                    print(f"[SKIP] [{completed:3d}/{len(combinations)}] {strategy:30s} {ticker:6s} {timeframe:6s}")

            except Exception as e:
                print(f"[ERROR] {strategy:30s} {ticker:6s} {timeframe:6s}: {e}")

    elapsed = time.time() - start_time

    # Save results
    reports_dir = Path(__file__).parent.parent / "reports"
    reports_dir.mkdir(exist_ok=True)

    report_file = reports_dir / "backtest_volume_enhanced_report.json"
    with open(report_file, 'w') as f:
        json.dump(results_by_strategy, f, indent=2)

    # Summary
    total_results = sum(len(v) for v in results_by_strategy.values())
    print("\n" + "="*70)
    print(f"[COMPLETE] Backtesting finished in {elapsed/60:.1f} minutes")
    print(f"Results saved: {report_file}")
    print(f"Total results: {total_results}/{len(combinations)}")
    print("="*70)


if __name__ == "__main__":
    main()
