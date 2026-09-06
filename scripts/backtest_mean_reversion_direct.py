#!/usr/bin/env python3
"""
Backtest mean reversion strategy - loads data directly from PostgreSQL.
Generates performance reports by timeframe and ticker.
"""

import os
import sys
import psycopg2
import pandas as pd
import numpy as np
from datetime import datetime
import json
from collections import defaultdict

# Database config
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "postgres")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "admin")

TICKERS = ["AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "TSLA", "AMD", "AVGO", "JPM", "GS", "SPY", "QQQ", "IWM", "DIA"]

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
        self.db_conn = None
        self.results = defaultdict(lambda: defaultdict(list))

    def connect_db(self):
        """Connect to PostgreSQL."""
        print(f"[CONNECT] Connecting to PostgreSQL at {DB_HOST}:{DB_PORT}...")
        try:
            self.db_conn = psycopg2.connect(
                host=DB_HOST,
                port=DB_PORT,
                database=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD
            )
            print("[OK] Connected to PostgreSQL")
            return True
        except Exception as e:
            print(f"[ERROR] Database connection failed: {e}")
            return False

    def get_1min_candles(self, ticker):
        """Get 1-minute candles from PostgreSQL."""
        query = f"""
            SELECT date, open, high, low, close, volume
            FROM historical_data_1min
            WHERE ticker = %s
            ORDER BY date ASC
        """
        cursor = self.db_conn.cursor()
        cursor.execute(query, (ticker,))
        rows = cursor.fetchall()
        cursor.close()

        if not rows:
            return None

        df = pd.DataFrame(rows, columns=['date', 'open', 'high', 'low', 'close', 'volume'])
        df['date'] = pd.to_datetime(df['date'])
        # Convert numeric columns to float
        df['open'] = df['open'].astype(float)
        df['high'] = df['high'].astype(float)
        df['low'] = df['low'].astype(float)
        df['close'] = df['close'].astype(float)
        df['volume'] = df['volume'].astype(int)
        return df

    def get_5min_candles(self, ticker):
        """Get 5-minute candles from PostgreSQL."""
        query = f"""
            SELECT date, open, high, low, close, volume
            FROM historical_data_5min
            WHERE ticker = %s
            ORDER BY date ASC
        """
        cursor = self.db_conn.cursor()
        cursor.execute(query, (ticker,))
        rows = cursor.fetchall()
        cursor.close()

        if not rows:
            return None

        df = pd.DataFrame(rows, columns=['date', 'open', 'high', 'low', 'close', 'volume'])
        df['date'] = pd.to_datetime(df['date'])
        # Convert numeric columns to float
        df['open'] = df['open'].astype(float)
        df['high'] = df['high'].astype(float)
        df['low'] = df['low'].astype(float)
        df['close'] = df['close'].astype(float)
        df['volume'] = df['volume'].astype(int)
        return df

    def aggregate_candles(self, df, period):
        """Aggregate candles into higher timeframes."""
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)

        agg_dict = {
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        }

        result = df.resample(period).agg(agg_dict).dropna()
        result.reset_index(inplace=True)
        return result

    def calculate_rsi(self, prices, period=14):
        """Calculate RSI indicator."""
        deltas = np.diff(prices)
        seed = deltas[:period+1]
        up = seed[seed >= 0].sum() / period
        down = -seed[seed < 0].sum() / period
        rs = up / down if down != 0 else 0
        rsi = np.zeros_like(prices, dtype=float)
        rsi[:period] = 100. - 100. / (1. + rs) if rs != 0 else 50.

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
            rsi[i] = 100. - 100. / (1. + rs) if rs != 0 else 50.

        return rsi

    def calculate_atr(self, df, period=14):
        """Calculate Average True Range."""
        high_low = df['high'] - df['low']
        high_close = abs(df['high'] - df['close'].shift())
        low_close = abs(df['low'] - df['close'].shift())

        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = np.max(ranges.values, axis=1)
        atr = pd.Series(true_range).rolling(period).mean()

        return atr.bfill().values

    def backtest_ticker(self, ticker, df, timeframe_name):
        """Backtest mean reversion strategy for a ticker."""
        if df is None or len(df) < RSI_PERIOD:
            return None

        df = df.reset_index(drop=True)

        # Calculate indicators
        df['rsi'] = self.calculate_rsi(df['close'].values, RSI_PERIOD)
        df['atr'] = self.calculate_atr(df, 14)

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

            # Entry signal: RSI crosses below oversold level
            if position is None and row['rsi'] < RSI_OVERSOLD and prev_row['rsi'] >= RSI_OVERSOLD:
                atr = row['atr']
                if pd.isna(atr) or atr == 0:
                    continue

                risk_amount = equity * RISK_PER_TRADE
                position_size = risk_amount / (atr * 2)

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
                        'return_pct': (exit_price - entry_price) / entry_price * 100
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
                        'return_pct': (exit_price - entry_price) / entry_price * 100
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
                'return_pct': (exit_price - entry_price) / entry_price * 100
            })

        return {
            'ticker': ticker,
            'timeframe': timeframe_name,
            'trades': trades,
            'final_equity': equity,
            'total_return': (equity - INITIAL_CAPITAL) / INITIAL_CAPITAL
        }

    def run_backtest(self):
        """Run backtest across all tickers and timeframes."""
        if not self.connect_db():
            return False

        print(f"\n[BACKTEST] Running mean reversion strategy...")
        print("="*60)
        print(f"Tickers: {len(TICKERS)}")
        print(f"Initial capital: ${INITIAL_CAPITAL:,.2f}")
        print("="*60)

        total_completed = 0

        # 1-minute timeframe
        print(f"\n[1-MIN] Backtesting...")
        for ticker in TICKERS:
            df = self.get_1min_candles(ticker)
            result = self.backtest_ticker(ticker, df, "1min")

            if result is not None and len(result['trades']) > 0:
                self.results["1min"][ticker] = result
                total_completed += 1
                print(f"   {ticker}: {len(result['trades'])} trades, "
                      f"Return: {result['total_return']*100:+.2f}%")
            else:
                print(f"   {ticker}: No trades")

        # 5-minute timeframe
        print(f"\n[5-MIN] Backtesting...")
        for ticker in TICKERS:
            df = self.get_5min_candles(ticker)
            result = self.backtest_ticker(ticker, df, "5min")

            if result is not None and len(result['trades']) > 0:
                self.results["5min"][ticker] = result
                total_completed += 1
                print(f"   {ticker}: {len(result['trades'])} trades, "
                      f"Return: {result['total_return']*100:+.2f}%")
            else:
                print(f"   {ticker}: No trades")

        # 1-hour timeframe (aggregated from 1-min)
        print(f"\n[1-HOUR] Backtesting...")
        for ticker in TICKERS:
            df_1min = self.get_1min_candles(ticker)
            if df_1min is not None:
                df_1h = self.aggregate_candles(df_1min.copy(), '1h')
                result = self.backtest_ticker(ticker, df_1h, "1h")

                if result is not None and len(result['trades']) > 0:
                    self.results["1h"][ticker] = result
                    total_completed += 1
                    print(f"   {ticker}: {len(result['trades'])} trades, "
                          f"Return: {result['total_return']*100:+.2f}%")
                else:
                    print(f"   {ticker}: No trades")

        # 1-day timeframe (aggregated from 1-min)
        print(f"\n[1-DAY] Backtesting...")
        for ticker in TICKERS:
            df_1min = self.get_1min_candles(ticker)
            if df_1min is not None:
                df_1d = self.aggregate_candles(df_1min.copy(), '1D')
                result = self.backtest_ticker(ticker, df_1d, "1d")

                if result is not None and len(result['trades']) > 0:
                    self.results["1d"][ticker] = result
                    total_completed += 1
                    print(f"   {ticker}: {len(result['trades'])} trades, "
                          f"Return: {result['total_return']*100:+.2f}%")
                else:
                    print(f"   {ticker}: No trades")

        print("\n" + "="*60)
        print(f"[OK] Backtest complete!")
        print(f"Total timeframe/ticker combinations with trades: {total_completed}")
        print("="*60)

        if self.db_conn:
            self.db_conn.close()

        return True

    def generate_report(self, output_file="backtest_report.json"):
        """Generate backtest report by timeframe."""
        report = {}

        for timeframe in ["1min", "5min", "1h", "1d"]:
            report[timeframe] = {
                'summary': {},
                'tickers': {}
            }

            tickers_data = self.results.get(timeframe, {})

            if not tickers_data:
                report[timeframe]['summary'] = {'status': 'No trades'}
                continue

            all_trades = []
            total_pnl = 0

            for ticker, result in tickers_data.items():
                trades = result['trades']
                all_trades.extend(trades)
                total_pnl += sum([t['pnl'] for t in trades])

                trades_df = pd.DataFrame(trades)
                wins = int((trades_df['pnl'] > 0).sum())
                losses = int((trades_df['pnl'] < 0).sum())
                win_rate = wins / len(trades_df) if len(trades_df) > 0 else 0

                avg_win = float(trades_df[trades_df['pnl'] > 0]['pnl'].mean()) if wins > 0 else 0
                avg_loss = float(abs(trades_df[trades_df['pnl'] < 0]['pnl'].mean())) if losses > 0 else 0

                profit_factor = avg_win * wins / (avg_loss * losses) if losses > 0 and avg_loss > 0 else float('inf')

                report[timeframe]['tickers'][ticker] = {
                    'total_trades': int(len(trades_df)),
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

            # Summary stats
            if all_trades:
                all_trades_df = pd.DataFrame(all_trades)
                total_wins = int((all_trades_df['pnl'] > 0).sum())
                total_losses = int((all_trades_df['pnl'] < 0).sum())

                report[timeframe]['summary'] = {
                    'total_trades': int(len(all_trades_df)),
                    'total_wins': total_wins,
                    'total_losses': total_losses,
                    'overall_win_rate': f"{(total_wins/len(all_trades_df)*100):.2f}%",
                    'total_pnl': f"${total_pnl:.2f}",
                    'avg_trade': f"${total_pnl/len(all_trades_df):.2f}"
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

        # Print detailed summary
        print("\n[SUMMARY] Results by Timeframe:")
        print("="*80)

        for timeframe in ["1min", "5min", "1h", "1d"]:
            if timeframe not in report or not report[timeframe].get('tickers'):
                continue

            print(f"\n{timeframe.upper()} RESULTS:")
            print("-" * 80)

            summary = report[timeframe].get('summary', {})
            if summary:
                print(f"Total Trades: {summary.get('total_trades', 'N/A')} | "
                      f"Wins: {summary.get('total_wins', 'N/A')} | "
                      f"Losses: {summary.get('total_losses', 'N/A')} | "
                      f"Win Rate: {summary.get('overall_win_rate', 'N/A')}")
                print(f"Total P&L: {summary.get('total_pnl', 'N/A')} | "
                      f"Avg Trade: {summary.get('avg_trade', 'N/A')}")

            print(f"\n{'Ticker':<8} {'Trades':<8} {'Wins':<6} {'Loss':<6} {'WR%':<8} {'P&L':<12} {'Return':<10}")
            print("-" * 80)

            for ticker, metrics in report[timeframe]['tickers'].items():
                print(f"{ticker:<8} {metrics['total_trades']:<8} "
                      f"{metrics['winning_trades']:<6} {metrics['losing_trades']:<6} "
                      f"{metrics['win_rate']:<8} {metrics['total_pnl']:<12} {metrics['total_return']:<10}")

        print("\n" + "="*80)

if __name__ == "__main__":
    main()
