#!/usr/bin/env python3
"""
Comprehensive Backtest Engine - Test 30+ trading strategies in parallel
with realistic commission (0.001% per trade)
"""

import os
import psycopg2
import pandas as pd
import numpy as np
from datetime import datetime
import json
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing

# Database config
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "postgres")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "admin")

TICKERS = ["AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "TSLA", "AMD", "AVGO", "JPM", "GS", "SPY", "QQQ", "IWM", "DIA"]
TIMEFRAMES = ["1min", "5min", "1h", "1d"]
COMMISSION = 0.001 / 100  # 0.001% = 0.00001

INITIAL_CAPITAL = 10000
RISK_PER_TRADE = 0.01

class DatabaseHelper:
    """Handle all database operations."""

    def __init__(self):
        self.conn = None

    def connect(self):
        self.conn = psycopg2.connect(
            host=DB_HOST, port=DB_PORT, database=DB_NAME,
            user=DB_USER, password=DB_PASSWORD
        )

    def get_1min_data(self, ticker):
        query = "SELECT date, open, high, low, close, volume FROM historical_data_1min WHERE ticker = %s ORDER BY date ASC"
        df = pd.read_sql(query, self.conn, params=(ticker,))
        if df.empty:
            return None
        df['date'] = pd.to_datetime(df['date'])
        df[['open', 'high', 'low', 'close']] = df[['open', 'high', 'low', 'close']].astype(float)
        df['volume'] = df['volume'].astype(int)
        return df

    def get_5min_data(self, ticker):
        query = "SELECT date, open, high, low, close, volume FROM historical_data_5min WHERE ticker = %s ORDER BY date ASC"
        df = pd.read_sql(query, self.conn, params=(ticker,))
        if df.empty:
            return None
        df['date'] = pd.to_datetime(df['date'])
        df[['open', 'high', 'low', 'close']] = df[['open', 'high', 'low', 'close']].astype(float)
        df['volume'] = df['volume'].astype(int)
        return df

    def aggregate_candles(self, df, period):
        df_copy = df.copy()
        df_copy['date'] = pd.to_datetime(df_copy['date'])
        df_copy.set_index('date', inplace=True)

        result = df_copy.resample(period).agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        }).dropna()

        result.reset_index(inplace=True)
        return result

    def close(self):
        if self.conn:
            self.conn.close()

class StrategyBase:
    """Base class for all trading strategies."""

    def __init__(self, df, initial_capital=INITIAL_CAPITAL):
        self.df = df.reset_index(drop=True)
        self.initial_capital = initial_capital
        self.equity = initial_capital
        self.trades = []
        self.position = None
        self.entry_price = 0

    def calculate_rsi(self, prices, period=14):
        deltas = np.diff(prices)
        seed = deltas[:period+1]
        up = seed[seed >= 0].sum() / period
        down = -seed[seed < 0].sum() / period
        rs = up / down if down != 0 else 0
        rsi = np.zeros_like(prices, dtype=float)
        rsi[:period] = 100. - 100. / (1. + rs) if rs != 0 else 50.

        for i in range(period, len(prices)):
            delta = deltas[i-1]
            upval = delta if delta > 0 else 0.
            downval = -delta if delta < 0 else 0.
            up = (up * (period - 1) + upval) / period
            down = (down * (period - 1) + downval) / period
            rs = up / down if down != 0 else 0
            rsi[i] = 100. - 100. / (1. + rs) if rs != 0 else 50.

        return rsi

    def calculate_atr(self, period=14):
        high_low = self.df['high'] - self.df['low']
        high_close = abs(self.df['high'] - self.df['close'].shift())
        low_close = abs(self.df['low'] - self.df['close'].shift())

        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = np.max(ranges.values, axis=1)
        atr = pd.Series(true_range).rolling(period).mean()
        return atr.bfill().values

    def calculate_commission(self, price, quantity):
        return price * quantity * COMMISSION

    def backtest(self):
        raise NotImplementedError

    def get_results(self):
        if len(self.trades) == 0:
            return None

        trades_df = pd.DataFrame(self.trades)
        wins = int((trades_df['pnl'] > 0).sum())
        losses = int((trades_df['pnl'] < 0).sum())
        win_rate = wins / len(trades_df) if len(trades_df) > 0 else 0

        total_pnl = float(trades_df['pnl'].sum())
        avg_win = float(trades_df[trades_df['pnl'] > 0]['pnl'].mean()) if wins > 0 else 0
        avg_loss = float(abs(trades_df[trades_df['pnl'] < 0]['pnl'].mean())) if losses > 0 else 0

        profit_factor = avg_win * wins / (avg_loss * losses) if losses > 0 and avg_loss > 0 else float('inf')

        return {
            'total_trades': int(len(trades_df)),
            'wins': wins,
            'losses': losses,
            'win_rate': f"{win_rate*100:.2f}%",
            'total_pnl': f"${total_pnl:.2f}",
            'avg_win': f"${avg_win:.2f}",
            'avg_loss': f"${avg_loss:.2f}",
            'profit_factor': f"{profit_factor:.2f}" if profit_factor != float('inf') else "N/A",
            'final_equity': f"${self.equity:.2f}",
            'return': f"{((self.equity - self.initial_capital) / self.initial_capital * 100):+.2f}%"
        }

# ============================================================================
# STRATEGY IMPLEMENTATIONS
# ============================================================================

class MeanReversionRSI(StrategyBase):
    def backtest(self):
        self.df['rsi'] = self.calculate_rsi(self.df['close'].values, 14)

        for idx in range(15, len(self.df)):
            row = self.df.iloc[idx]
            prev_row = self.df.iloc[idx - 1]

            if self.position is None and row['rsi'] < 30 and prev_row['rsi'] >= 30:
                self.entry_price = row['close']
                self.position = {'entry_idx': idx, 'entry_price': self.entry_price}

            elif self.position is not None:
                if row['close'] > self.entry_price * 1.02:
                    exit_price = row['close']
                    qty = 1
                    comm = self.calculate_commission(exit_price, qty)
                    pnl = (exit_price - self.entry_price) * qty - comm
                    self.equity += pnl
                    self.trades.append({'entry_price': self.entry_price, 'exit_price': exit_price, 'pnl': pnl})
                    self.position = None

class MovingAverageCrossover(StrategyBase):
    def backtest(self):
        self.df['sma20'] = self.df['close'].rolling(20).mean()
        self.df['sma50'] = self.df['close'].rolling(50).mean()

        for idx in range(50, len(self.df)):
            row = self.df.iloc[idx]
            prev_row = self.df.iloc[idx - 1]

            # Golden cross - buy signal
            if self.position is None and prev_row['sma20'] <= prev_row['sma50'] and row['sma20'] > row['sma50']:
                self.entry_price = row['close']
                self.position = {'entry_idx': idx, 'entry_price': self.entry_price}

            # Death cross - sell signal
            elif self.position is not None and prev_row['sma20'] >= prev_row['sma50'] and row['sma20'] < row['sma50']:
                exit_price = row['close']
                qty = 1
                comm = self.calculate_commission(exit_price, qty)
                pnl = (exit_price - self.entry_price) * qty - comm
                self.equity += pnl
                self.trades.append({'entry_price': self.entry_price, 'exit_price': exit_price, 'pnl': pnl})
                self.position = None

class BollingerBandMeanReversion(StrategyBase):
    def backtest(self):
        self.df['sma'] = self.df['close'].rolling(20).mean()
        self.df['std'] = self.df['close'].rolling(20).std()
        self.df['upper_band'] = self.df['sma'] + (self.df['std'] * 2)
        self.df['lower_band'] = self.df['sma'] - (self.df['std'] * 2)

        for idx in range(20, len(self.df)):
            row = self.df.iloc[idx]

            if self.position is None and row['close'] < row['lower_band']:
                self.entry_price = row['close']
                self.position = {'entry_idx': idx}

            elif self.position is not None and row['close'] > row['sma']:
                exit_price = row['close']
                qty = 1
                comm = self.calculate_commission(exit_price, qty)
                pnl = (exit_price - self.entry_price) * qty - comm
                self.equity += pnl
                self.trades.append({'entry_price': self.entry_price, 'exit_price': exit_price, 'pnl': pnl})
                self.position = None

class BreakoutStrategy(StrategyBase):
    def backtest(self):
        self.df['high_20'] = self.df['high'].rolling(20).max()
        self.df['low_20'] = self.df['low'].rolling(20).min()

        for idx in range(20, len(self.df)):
            row = self.df.iloc[idx]
            prev_row = self.df.iloc[idx - 1]

            if self.position is None and row['close'] > row['high_20'] and prev_row['close'] <= prev_row['high_20']:
                self.entry_price = row['close']
                self.position = {'entry_idx': idx, 'type': 'long'}

            elif self.position is not None and self.position['type'] == 'long':
                if row['close'] > self.entry_price * 1.03 or row['close'] < self.entry_price * 0.98:
                    exit_price = row['close']
                    qty = 1
                    comm = self.calculate_commission(exit_price, qty)
                    pnl = (exit_price - self.entry_price) * qty - comm
                    self.equity += pnl
                    self.trades.append({'entry_price': self.entry_price, 'exit_price': exit_price, 'pnl': pnl})
                    self.position = None

class MacdStrategy(StrategyBase):
    def backtest(self):
        ema12 = self.df['close'].ewm(span=12).mean()
        ema26 = self.df['close'].ewm(span=26).mean()
        self.df['macd'] = ema12 - ema26
        self.df['signal'] = self.df['macd'].ewm(span=9).mean()

        for idx in range(26, len(self.df)):
            row = self.df.iloc[idx]
            prev_row = self.df.iloc[idx - 1]

            if self.position is None and prev_row['macd'] <= prev_row['signal'] and row['macd'] > row['signal']:
                self.entry_price = row['close']
                self.position = {'entry_idx': idx}

            elif self.position is not None and prev_row['macd'] >= prev_row['signal'] and row['macd'] < row['signal']:
                exit_price = row['close']
                qty = 1
                comm = self.calculate_commission(exit_price, qty)
                pnl = (exit_price - self.entry_price) * qty - comm
                self.equity += pnl
                self.trades.append({'entry_price': self.entry_price, 'exit_price': exit_price, 'pnl': pnl})
                self.position = None

class RsiDivergence(StrategyBase):
    def backtest(self):
        self.df['rsi'] = self.calculate_rsi(self.df['close'].values, 14)

        for idx in range(30, len(self.df)):
            row = self.df.iloc[idx]

            if self.position is None and row['rsi'] > 70:
                self.entry_price = row['close']
                self.position = {'entry_idx': idx}

            elif self.position is not None and row['rsi'] < 50:
                exit_price = row['close']
                qty = 1
                comm = self.calculate_commission(exit_price, qty)
                pnl = (exit_price - self.entry_price) * qty - comm
                self.equity += pnl
                self.trades.append({'entry_price': self.entry_price, 'exit_price': exit_price, 'pnl': pnl})
                self.position = None

class VolatilityBreakout(StrategyBase):
    def backtest(self):
        self.df['atr'] = self.calculate_atr(14)
        self.df['atr_avg'] = self.df['atr'].rolling(20).mean()

        for idx in range(34, len(self.df)):
            row = self.df.iloc[idx]

            if self.position is None and row['atr'] > row['atr_avg'] * 1.5:
                self.entry_price = row['close']
                self.position = {'entry_idx': idx}

            elif self.position is not None:
                if row['close'] > self.entry_price * 1.02 or row['close'] < self.entry_price * 0.99:
                    exit_price = row['close']
                    qty = 1
                    comm = self.calculate_commission(exit_price, qty)
                    pnl = (exit_price - self.entry_price) * qty - comm
                    self.equity += pnl
                    self.trades.append({'entry_price': self.entry_price, 'exit_price': exit_price, 'pnl': pnl})
                    self.position = None

# ============================================================================
# BACKTEST RUNNER
# ============================================================================

def run_backtest(args):
    """Run a single backtest combination."""
    strategy_class, ticker, timeframe, df = args

    if df is None or len(df) < 50:
        return None

    try:
        strategy = strategy_class(df)
        strategy.backtest()
        results = strategy.get_results()

        if results is None:
            return None

        return {
            'strategy': strategy_class.__name__,
            'ticker': ticker,
            'timeframe': timeframe,
            'results': results
        }
    except Exception as e:
        return None

def main():
    print("\n[BACKTEST] Multi-Strategy Parallel Backtester")
    print("=" * 80)
    print(f"Commission: 0.001% per trade")
    print(f"Initial Capital: ${INITIAL_CAPITAL:,.2f}")
    print(f"Strategies: 7 (more can be added)")
    print(f"Tickers: {len(TICKERS)}")
    print(f"Timeframes: {len(TIMEFRAMES)}")
    print("=" * 80)

    strategies = [
        MeanReversionRSI,
        MovingAverageCrossover,
        BollingerBandMeanReversion,
        BreakoutStrategy,
        MacdStrategy,
        RsiDivergence,
        VolatilityBreakout
    ]

    db = DatabaseHelper()
    db.connect()

    print(f"\n[LOAD] Loading data for {len(TICKERS)} tickers...")

    # Prepare all data
    data_cache = {}
    for ticker in TICKERS:
        print(f"  {ticker}...", end=" ", flush=True)
        df_1min = db.get_1min_data(ticker)
        if df_1min is not None:
            data_cache[f"{ticker}_1min"] = df_1min
            data_cache[f"{ticker}_5min"] = db.get_5min_data(ticker)
            data_cache[f"{ticker}_1h"] = db.aggregate_candles(df_1min.copy(), '1h')
            data_cache[f"{ticker}_1d"] = db.aggregate_candles(df_1min.copy(), '1D')
            print("OK")
        else:
            print("SKIP")

    db.close()

    # Prepare backtest jobs
    print(f"\n[PREPARE] Preparing {len(strategies)} strategies × {len(TICKERS)} tickers × {len(TIMEFRAMES)} timeframes...")

    jobs = []
    for strategy in strategies:
        for ticker in TICKERS:
            for timeframe in TIMEFRAMES:
                key = f"{ticker}_{timeframe}"
                if key in data_cache:
                    df = data_cache[key]
                    if df is not None:
                        jobs.append((strategy, ticker, timeframe, df))

    print(f"Total jobs: {len(jobs)}")

    # Run in parallel
    print(f"\n[RUN] Running {len(jobs)} backtests in parallel...")
    print("=" * 80)

    results = defaultdict(lambda: defaultdict(dict))
    completed = 0

    with ProcessPoolExecutor(max_workers=multiprocessing.cpu_count()) as executor:
        futures = {executor.submit(run_backtest, job): job for job in jobs}

        for future in as_completed(futures):
            result = future.result()
            completed += 1

            if result is not None:
                strategy_name = result['strategy']
                ticker = result['ticker']
                timeframe = result['timeframe']

                results[strategy_name][f"{ticker}_{timeframe}"] = result['results']

                if completed % 50 == 0:
                    print(f"  Progress: {completed}/{len(jobs)} backtests completed...")

    print(f"\nCompleted: {completed}/{len(jobs)} backtests")

    # Generate summary
    print("\n" + "=" * 80)
    print("[SUMMARY] Top 10 Best Performing Strategy/Ticker/Timeframe Combinations")
    print("=" * 80)

    all_combos = []
    for strategy_name, combinations in results.items():
        for combo_name, metrics in combinations.items():
            if metrics:
                try:
                    return_pct = float(metrics['return'].strip('%+-'))
                    all_combos.append({
                        'strategy': strategy_name,
                        'combo': combo_name,
                        'trades': int(metrics['total_trades']),
                        'win_rate': metrics['win_rate'],
                        'pnl': metrics['total_pnl'],
                        'return': metrics['return'],
                        'return_pct': return_pct
                    })
                except:
                    pass

    all_combos.sort(key=lambda x: x['return_pct'], reverse=True)

    print(f"\n{'Rank':<5} {'Strategy':<30} {'Combo':<20} {'Trades':<8} {'Win%':<8} {'P&L':<12} {'Return'}")
    print("-" * 95)

    for i, combo in enumerate(all_combos[:10], 1):
        print(f"{i:<5} {combo['strategy']:<30} {combo['combo']:<20} "
              f"{combo['trades']:<8} {combo['win_rate']:<8} {combo['pnl']:<12} {combo['return']}")

    # Save detailed report to reports folder
    print("\n[REPORT] Saving detailed report...")
    import os
    os.makedirs('../reports', exist_ok=True)
    report_path = '../reports/backtest_all_strategies_report.json'
    with open(report_path, 'w') as f:
        json.dump(dict(results), f, indent=2)

    print(f"Saved to: {report_path}")
    print("\n" + "=" * 80)
    print(f"Total Combinations Tested: {len(all_combos)}")
    print(f"Profitable Combos: {len([c for c in all_combos if c['return_pct'] > 0])}")
    print("=" * 80)

if __name__ == "__main__":
    main()
