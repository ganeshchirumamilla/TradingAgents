#!/usr/bin/env python3
"""
Backtest mean reversion strategy across multiple timeframes.
Loads data from Redis and generates performance reports.
"""

import os
import sys
import redis
import pandas as pd
import numpy as np
from datetime import datetime
import json
from collections import defaultdict

# Redis config
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))

TICKERS = ["AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "TSLA", "AMD", "AVGO", "JPM", "GS", "SPY", "QQQ", "IWM", "DIA"]
TIMEFRAMES = ["1min", "5min", "1h", "1d"]

# Strategy parameters
INITIAL_CAPITAL = 10000
RISK_PER_TRADE = 0.01  # 1% risk per trade
RSI_PERIOD = 14
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70
PROFIT_TARGET_FACTOR = 2.0  # 2:1 reward/risk ratio

class MeanReversionBacktester:
    """Backtest mean reversion strategy."""

    def __init__(self):
        self.redis_conn = None
        self.results = defaultdict(lambda: defaultdict(list))

    def connect_redis(self):
        """Connect to Redis."""
        print(f"[CONNECT] Connecting to Redis at {REDIS_HOST}:{REDIS_PORT}...")
        try:
            self.redis_conn = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)
            self.redis_conn.ping()
            print("[OK] Connected to Redis")
            return True
        except Exception as e:
            print(f"[ERROR] Redis connection failed: {e}")
            return False

    def get_candles(self, ticker, timeframe):
        """Get candles for ticker and timeframe from Redis."""
        pattern = f"candles:{timeframe}:{ticker}:*"
        keys = self.redis_conn.keys(pattern)

        if not keys:
            return None

        candles = []
        for key in sorted(keys):
            data = self.redis_conn.hgetall(key)
            timestamp = int(key.split(':')[-1])
            candles.append({
                'timestamp': timestamp,
                'date': datetime.fromtimestamp(timestamp),
                'open': float(data['open']),
                'high': float(data['high']),
                'low': float(data['low']),
                'close': float(data['close']),
                'volume': int(data['volume'])
            })

        df = pd.DataFrame(candles)
        if df.empty:
            return None

        df.sort_values('timestamp', inplace=True)
        return df

    def calculate_rsi(self, prices, period=14):
        """Calculate RSI indicator."""
        deltas = np.diff(prices)
        seed = deltas[:period+1]
        up = seed[seed >= 0].sum() / period
        down = -seed[seed < 0].sum() / period
        rs = up / down if down != 0 else 0
        rsi = np.zeros_like(prices)
        rsi[:period] = 100. - 100. / (1. + rs)

        for i in range(period, len(prices)):
            delta = deltas[i-1]
            if delta > 0:
                upval = delta
                downval = 0.
            else:
                upval = 0.
                downval = -delta

            up = (up * (period - 1) + upval) / period
            down = (down * (period - 1) + downval) / period
            rs = up / down if down != 0 else 0
            rsi[i] = 100. - 100. / (1. + rs)

        return rsi

    def backtest_ticker(self, ticker, timeframe):
        """Backtest mean reversion strategy for a ticker and timeframe."""
        df = self.get_candles(ticker, timeframe)

        if df is None or len(df) < RSI_PERIOD:
            return None

        # Calculate RSI
        df['rsi'] = self.calculate_rsi(df['close'].values, RSI_PERIOD)
        df['atr'] = self.calculate_atr(df)

        # Trading logic
        trades = []
        position = None
        equity = INITIAL_CAPITAL
        entry_price = 0
        stop_loss = 0
        take_profit = 0

        for idx in range(RSI_PERIOD + 1, len(df)):
            row = df.iloc[idx]
            prev_row = df.iloc[idx - 1]

            # Entry signal: RSI crosses below oversold level (mean reversion setup)
            if position is None and row['rsi'] < RSI_OVERSOLD and prev_row['rsi'] >= RSI_OVERSOLD:
                # Calculate position size based on risk
                atr = row['atr']
                if atr == 0:
                    continue

                risk_amount = equity * RISK_PER_TRADE
                position_size = risk_amount / (atr * 2)  # 2x ATR stop

                entry_price = row['close']
                stop_loss = entry_price - (atr * 2)
                take_profit = entry_price + (atr * 2 * PROFIT_TARGET_FACTOR)

                position = {
                    'entry_date': row['date'],
                    'entry_price': entry_price,
                    'size': position_size,
                    'stop_loss': stop_loss,
                    'take_profit': take_profit,
                    'atr': atr
                }

            # Exit logic
            elif position is not None:
                # Stop loss hit
                if row['low'] <= stop_loss:
                    exit_price = stop_loss
                    pnl = (exit_price - entry_price) * position['size']
                    equity += pnl

                    trades.append({
                        'entry_date': position['entry_date'],
                        'exit_date': row['date'],
                        'entry_price': entry_price,
                        'exit_price': exit_price,
                        'size': position['size'],
                        'pnl': pnl,
                        'return': (exit_price - entry_price) / entry_price,
                        'bars_held': idx - (idx - 1)
                    })

                    position = None

                # Take profit hit
                elif row['high'] >= take_profit:
                    exit_price = take_profit
                    pnl = (exit_price - entry_price) * position['size']
                    equity += pnl

                    trades.append({
                        'entry_date': position['entry_date'],
                        'exit_date': row['date'],
                        'entry_price': entry_price,
                        'exit_price': exit_price,
                        'size': position['size'],
                        'pnl': pnl,
                        'return': (exit_price - entry_price) / entry_price,
                        'bars_held': idx - (idx - 1)
                    })

                    position = None

        # Close any open position at end
        if position is not None:
            exit_price = df.iloc[-1]['close']
            pnl = (exit_price - entry_price) * position['size']
            equity += pnl

            trades.append({
                'entry_date': position['entry_date'],
                'exit_date': df.iloc[-1]['date'],
                'entry_price': entry_price,
                'exit_price': exit_price,
                'size': position['size'],
                'pnl': pnl,
                'return': (exit_price - entry_price) / entry_price,
                'bars_held': len(df) - RSI_PERIOD
            })

        return {
            'ticker': ticker,
            'timeframe': timeframe,
            'trades': trades,
            'final_equity': equity,
            'total_return': (equity - INITIAL_CAPITAL) / INITIAL_CAPITAL
        }

    def calculate_atr(self, df, period=14):
        """Calculate Average True Range."""
        high_low = df['high'] - df['low']
        high_close = abs(df['high'] - df['close'].shift())
        low_close = abs(df['low'] - df['close'].shift())

        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = np.max(ranges, axis=1)
        atr = true_range.rolling(period).mean()

        return atr.fillna(method='bfill')

    def run_backtest(self):
        """Run backtest across all tickers and timeframes."""
        if not self.connect_redis():
            return False

        print(f"\n[BACKTEST] Running mean reversion strategy...")
        print("="*60)
        print(f"Tickers: {len(TICKERS)}")
        print(f"Timeframes: {len(TIMEFRAMES)}")
        print(f"Initial capital: ${INITIAL_CAPITAL:,.2f}")
        print("="*60)

        total_completed = 0
        for timeframe in TIMEFRAMES:
            print(f"\n[{timeframe.upper()}] Backtesting...")
            for ticker in TICKERS:
                result = self.backtest_ticker(ticker, timeframe)

                if result is not None and len(result['trades']) > 0:
                    self.results[timeframe][ticker] = result
                    total_completed += 1
                    print(f"   {ticker}: {len(result['trades'])} trades, "
                          f"Return: {result['total_return']*100:+.2f}%")
                else:
                    print(f"   {ticker}: No trades")

        print("\n" + "="*60)
        print(f"[OK] Backtest complete!")
        print(f"Total timeframe/ticker combinations with trades: {total_completed}")
        print("="*60)

        return True

    def generate_report(self, output_file="backtest_report.json"):
        """Generate backtest report."""
        report = {}

        for timeframe, tickers_data in self.results.items():
            report[timeframe] = {}

            for ticker, result in tickers_data.items():
                trades = result['trades']

                if len(trades) == 0:
                    continue

                trades_df = pd.DataFrame(trades)
                wins = (trades_df['pnl'] > 0).sum()
                losses = (trades_df['pnl'] < 0).sum()
                win_rate = wins / len(trades_df) if len(trades_df) > 0 else 0

                avg_win = trades_df[trades_df['pnl'] > 0]['pnl'].mean() if wins > 0 else 0
                avg_loss = abs(trades_df[trades_df['pnl'] < 0]['pnl'].mean()) if losses > 0 else 0

                profit_factor = avg_win * wins / (avg_loss * losses) if losses > 0 and avg_loss > 0 else float('inf')

                report[timeframe][ticker] = {
                    'total_trades': len(trades_df),
                    'winning_trades': wins,
                    'losing_trades': losses,
                    'win_rate': f"{win_rate*100:.2f}%",
                    'average_win': f"${avg_win:.2f}",
                    'average_loss': f"${avg_loss:.2f}",
                    'profit_factor': f"{profit_factor:.2f}" if profit_factor != float('inf') else "N/A",
                    'total_pnl': f"${trades_df['pnl'].sum():.2f}",
                    'final_equity': f"${result['final_equity']:.2f}",
                    'total_return': f"{result['total_return']*100:+.2f}%"
                }

        # Save report
        with open(output_file, 'w') as f:
            json.dump(report, f, indent=2)

        print(f"\n[REPORT] Saved to: {output_file}")
        return report

def main():
    """Main function."""
    print("\n[MEAN REVERSION] Backtest Engine")
    print("="*60)

    backtester = MeanReversionBacktester()

    if backtester.run_backtest():
        report = backtester.generate_report()

        # Print summary
        print("\n[SUMMARY] Results by Timeframe:")
        print("="*60)
        for timeframe, tickers_data in report.items():
            if tickers_data:
                print(f"\n{timeframe.upper()}:")
                for ticker, metrics in tickers_data.items():
                    print(f"  {ticker}: {metrics['total_trades']} trades, "
                          f"Win Rate: {metrics['win_rate']}, "
                          f"Return: {metrics['total_return']}")

if __name__ == "__main__":
    main()
