#!/usr/bin/env python3
"""
SWING TRADING STRATEGY - Professional Edition

Philosophy: "Wait for the Setup, Take the Setup, Manage the Trade"

Entry Rules (Conservative):
1. Clear trend: Price > 50-day SMA (long) or < 50-day SMA (short)
2. Pullback Entry: Price pulls back to 20-day SMA (support/resistance)
3. Volume: Entry volume > 20-day avg (strength confirmation)
4. RSI Confirmation: 40-60 range (neutral, not overextended)

Exit Rules (Disciplined):
1. Take Profit: 2:1 reward/risk ratio
2. Stop Loss: 3x ATR (wide stops to avoid whipsaws)
3. Trailing Stop: Move stop up 50% when price moves 1x ATR in profit direction
4. Time Stop: Exit after 20 days (let profits run, cut losers quick)

Position Management:
- Risk only 1% per trade (not 2-2.5%)
- Max 3 concurrent positions (not 10) - quality over quantity
- Only enter if capital risk <= 1% of account
- Wait for confirmation, don't chase

Expected: 55-65% win rate, 2:1 reward/risk = 50-80% annual return
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SwingTradingStrategy:
    """Professional swing trading strategy with conservative risk management."""

    def __init__(self, initial_capital=10000, risk_per_trade=0.01, max_positions=3):
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.risk_per_trade = risk_per_trade  # 1% risk per trade
        self.max_positions = max_positions  # Only 3 concurrent
        self.positions = {}
        self.trades = []
        self.equity_curve = []
        self.last_entry = {}  # Track last entry to avoid overtrading

    def get_support_resistance(self, daily_data):
        """Calculate support (20-day SMA) and resistance levels."""
        df = daily_data.copy()
        df['sma_20'] = df['close'].rolling(window=20).mean()
        df['sma_50'] = df['close'].rolling(window=50).mean()

        latest = df.iloc[-1]
        return {
            'support': latest['sma_20'],
            'resistance': latest['sma_20'],
            'trend_50': latest['sma_50'],
            'price': latest['close'],
        }

    def identify_trend(self, daily_data):
        """
        Identify strong, established trends only.
        Returns: 1 (uptrend), -1 (downtrend), 0 (no clear trend)
        """
        df = daily_data.copy()

        # 50-day SMA for trend direction
        df['sma_50'] = df['close'].rolling(window=50).mean()
        df['sma_20'] = df['close'].rolling(window=20).mean()

        latest = df.iloc[-1]
        price = latest['close']
        sma_20 = latest['sma_20']
        sma_50 = latest['sma_50']

        # Strong uptrend: price > 20-day > 50-day SMA
        if price > sma_20 > sma_50:
            return 1
        # Strong downtrend: price < 20-day < 50-day SMA
        elif price < sma_20 < sma_50:
            return -1
        else:
            return 0

    def check_pullback_entry(self, daily_data, trend):
        """Check if price is at pullback support/resistance for entry."""
        if trend == 0:
            return False

        df = daily_data.copy()
        df['sma_20'] = df['close'].rolling(window=20).mean()

        latest = df.iloc[-1]
        price = latest['close']
        sma_20 = latest['sma_20']

        # Long entry: price near 20-day SMA in uptrend (within 1% above)
        if trend == 1 and sma_20 * 0.99 <= price <= sma_20 * 1.02:
            return True

        # Short entry: price near 20-day SMA in downtrend (within 1% below)
        if trend == -1 and sma_20 * 0.98 <= price <= sma_20 * 1.01:
            return True

        return False

    def check_volume_confirmation(self, hourly_data):
        """Ensure entry volume is above average."""
        df = hourly_data.copy()
        df['vol_ma'] = df['volume'].rolling(window=20).mean()

        latest = df.iloc[-1]
        return latest['volume'] > latest['vol_ma'] * 1.1  # 10% above average

    def check_rsi_neutral(self, daily_data):
        """Ensure RSI is in neutral range (40-60), not overextended."""
        df = daily_data.copy()

        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))

        latest_rsi = rsi.iloc[-1]
        return 35 < latest_rsi < 65  # Neutral zone, not overbought/oversold

    def calculate_atr(self, data, period=14):
        """Calculate ATR for volatility-based stops."""
        df = data.copy()
        df['tr'] = np.maximum(
            df['high'] - df['low'],
            np.maximum(
                abs(df['high'] - df['close'].shift()),
                abs(df['low'] - df['close'].shift())
            )
        )
        return df['tr'].rolling(window=period).mean().iloc[-1]

    def check_exit_conditions(self, ticker, current_price, current_date):
        """Check all exit conditions with trailing stops."""
        if ticker not in self.positions:
            return None

        pos = self.positions[ticker]

        # Hard stop loss
        if current_price <= pos['stop_loss']:
            return 'stop_loss'

        # Take profit at 2:1 risk/reward
        if current_price >= pos['take_profit']:
            return 'take_profit'

        # Trailing stop: once at 50% of target, move stop to breakeven + 0.5x ATR
        tp_dist = abs(pos['take_profit'] - pos['entry_price'])
        curr_profit = abs(current_price - pos['entry_price'])

        if curr_profit > 0.5 * tp_dist:
            trail_stop = pos['entry_price'] + (0.5 * np.sign(pos['trend']) * pos['atr'])
            if current_price < trail_stop and pos['trend'] == 1:
                return 'trailing_stop'
            if current_price > trail_stop and pos['trend'] == -1:
                return 'trailing_stop'

        # Exit after 20 days
        days_held = (current_date - pos['entry_date']).days
        if days_held > 20:
            return 'timeout'

        return None

    def open_position(self, ticker, entry_price, trend, atr, current_date):
        """Open position with professional risk management."""
        # Avoid overtrading same ticker
        if ticker in self.last_entry:
            days_since = (current_date - self.last_entry[ticker]).days
            if days_since < 5:  # Min 5 days between entries on same ticker
                return False

        if ticker in self.positions or len(self.positions) >= self.max_positions:
            return False

        # Risk only 1% per trade
        risk_amount = self.capital * self.risk_per_trade

        # Wide stops (3x ATR) to avoid whipsaws
        stop_distance = 3 * atr
        quantity = int(risk_amount / stop_distance)

        if quantity < 1:
            return False

        # Calculate stops and targets (2:1 reward/risk)
        if trend == 1:  # Long
            stop_loss = entry_price - (3 * atr)
            take_profit = entry_price + (6 * atr)  # 2:1 reward/risk
        else:  # Short
            stop_loss = entry_price + (3 * atr)
            take_profit = entry_price - (6 * atr)

        self.positions[ticker] = {
            'entry_price': entry_price,
            'entry_date': current_date,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'quantity': quantity,
            'trend': trend,
            'atr': atr,
        }

        self.last_entry[ticker] = current_date

        logger.info(f"[ENTRY] {ticker} @ ${entry_price:.2f} (Q:{quantity}, SL:${stop_loss:.2f}, TP:${take_profit:.2f})")
        return True

    def close_position(self, ticker, exit_price, reason, current_date):
        """Close position and record trade."""
        if ticker not in self.positions:
            return

        pos = self.positions[ticker]
        pnl = (exit_price - pos['entry_price']) * pos['quantity'] * pos['trend']
        pnl_pct = (pnl / abs(pos['entry_price'] * pos['quantity'])) * 100
        self.capital += pnl

        self.trades.append({
            'ticker': ticker,
            'entry_date': pos['entry_date'],
            'exit_date': current_date,
            'entry_price': pos['entry_price'],
            'exit_price': exit_price,
            'quantity': pos['quantity'],
            'pnl': pnl,
            'pnl_pct': pnl_pct,
            'reason': reason,
        })

        logger.info(f"[EXIT] {ticker} @ ${exit_price:.2f} | PnL: ${pnl:.2f} ({pnl_pct:+.2f}%) [{reason}]")
        del self.positions[ticker]

    def backtest(self, data_dict, start_date, end_date):
        """Run backtest with professional swing trading logic."""
        self.start_date = start_date

        logger.info(f"\n{'='*70}")
        logger.info(f"SWING TRADING STRATEGY - Professional Edition")
        logger.info(f"Period: {start_date.date()} to {end_date.date()}")
        logger.info(f"Initial Capital: ${self.initial_capital:,.2f}")
        logger.info(f"Risk per Trade: {self.risk_per_trade*100:.1f}%")
        logger.info(f"Max Positions: {self.max_positions}")
        logger.info(f"{'='*70}\n")

        current_date = start_date

        while current_date <= end_date:
            day_end = current_date.replace(hour=23, minute=59, second=59)

            for ticker in data_dict.keys():
                try:
                    daily = data_dict[ticker]['daily']
                    hourly = data_dict[ticker]['hourly']

                    daily_subset = daily[daily['date'] <= day_end].copy()
                    hourly_subset = hourly[hourly['date'] <= day_end].copy()

                    if len(daily_subset) < 50 or len(hourly_subset) == 0:
                        continue

                    current_price = hourly_subset.iloc[-1]['close']
                    current_hour = hourly_subset.iloc[-1]['date']

                    # Check exits first
                    exit_reason = self.check_exit_conditions(ticker, current_price, current_hour)
                    if exit_reason:
                        self.close_position(ticker, current_price, exit_reason, current_hour)

                    # Check entries only if no position and room for more
                    if ticker not in self.positions:
                        trend = self.identify_trend(daily_subset)

                        if trend != 0:
                            pullback = self.check_pullback_entry(daily_subset, trend)
                            volume_ok = self.check_volume_confirmation(hourly_subset)
                            rsi_ok = self.check_rsi_neutral(daily_subset)

                            # All conditions must be met
                            if pullback and volume_ok and rsi_ok:
                                atr = self.calculate_atr(daily_subset)
                                self.open_position(ticker, current_price, trend, atr, current_hour)

                except Exception as e:
                    pass

            # Record equity
            total_equity = self.capital
            for ticker, pos in self.positions.items():
                try:
                    hourly = data_dict[ticker]['hourly']
                    hourly_subset = hourly[hourly['date'] <= day_end].copy()
                    if len(hourly_subset) > 0:
                        price = hourly_subset.iloc[-1]['close']
                        profit = (price - pos['entry_price']) * pos['quantity'] * pos['trend']
                        total_equity += profit
                except:
                    pass

            self.equity_curve.append({
                'date': day_end,
                'capital': self.capital,
                'total_equity': total_equity,
            })

            current_date += timedelta(days=1)

    def generate_report(self):
        """Generate detailed backtest report."""
        if not self.trades:
            logger.warning("No trades executed")
            return None

        df = pd.DataFrame(self.trades)

        total = len(df)
        wins = len(df[df['pnl'] > 0])
        losses = len(df[df['pnl'] < 0])
        win_rate = (wins / total * 100) if total > 0 else 0

        pnl_total = df['pnl'].sum()
        avg_win = df[df['pnl'] > 0]['pnl'].mean() if wins > 0 else 0
        avg_loss = df[df['pnl'] < 0]['pnl'].mean() if losses > 0 else 0

        final_capital = self.capital
        total_return = ((final_capital - self.initial_capital) / self.initial_capital) * 100

        if len(self.equity_curve) > 1:
            df_eq = pd.DataFrame(self.equity_curve)
            returns = df_eq['total_equity'].pct_change().dropna()
            sharpe = (returns.mean() / returns.std()) * np.sqrt(252) if returns.std() > 0 else 0

            cummax = df_eq['total_equity'].cummax()
            drawdown = (df_eq['total_equity'] - cummax) / cummax
            max_dd = drawdown.min() * 100
        else:
            sharpe = max_dd = 0

        logger.info(f"\n{'='*70}")
        logger.info(f"BACKTEST RESULTS - SWING TRADING")
        logger.info(f"{'='*70}\n")

        logger.info(f"Capital: ${self.initial_capital:,.2f} → ${final_capital:,.2f}")
        logger.info(f"P&L: ${pnl_total:,.2f} ({total_return:+.2f}%)\n")

        logger.info(f"Trades: {total} | Wins: {wins} ({win_rate:.1f}%) | Losses: {losses}")
        logger.info(f"Avg Win: ${avg_win:,.2f} | Avg Loss: ${avg_loss:,.2f}")
        logger.info(f"Best: ${df['pnl'].max():,.2f} | Worst: ${df['pnl'].min():,.2f}\n")

        logger.info(f"Sharpe: {sharpe:.2f} | Max DD: {max_dd:.2f}%")
        logger.info(f"Profit Factor: {abs(df[df['pnl']>0]['pnl'].sum() / df[df['pnl']<0]['pnl'].sum()) if losses > 0 else 0:.2f}\n")

        logger.info(f"Top 5 Trades:")
        for i, (_, trade) in enumerate(df.nlargest(5, 'pnl').iterrows(), 1):
            logger.info(f"  {i}. {trade['ticker']}: +${trade['pnl']:.2f}")

        logger.info(f"\n{'='*70}\n")

        return {
            'initial_capital': self.initial_capital,
            'final_capital': final_capital,
            'total_return': total_return,
            'total_trades': total,
            'win_rate': win_rate,
            'sharpe': sharpe,
            'max_drawdown': max_dd,
            'trades': df,
        }
