"""
Moving Average Crossover + RSI Strategy

A popular and proven trading strategy that combines:
1. Moving Average Crossover (SMA 20/50)
2. RSI (Relative Strength Index) confirmation
3. Dynamic position sizing based on volatility

Entry Signals:
- LONG: SMA20 > SMA50 AND RSI < 70 (not overbought)
- SHORT: SMA20 < SMA50 AND RSI > 30 (not oversold)

Exit Signals:
- Stop Loss: 2% below entry
- Take Profit: 3% above entry OR crossing back

Risk/Reward Ratio: 1:1.5
"""

import logging
from typing import Optional, Tuple
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


class MARSIStrategy:
    """Moving Average + RSI Strategy for backtesting."""

    def __init__(
        self,
        sma_short: int = 20,
        sma_long: int = 50,
        rsi_period: int = 14,
        rsi_overbought: float = 70,
        rsi_oversold: float = 30,
        stop_loss_pct: float = 0.02,  # 2%
        take_profit_pct: float = 0.03,  # 3%
        position_size_pct: float = 0.05,  # 5% of capital per trade
    ):
        """Initialize strategy parameters."""
        self.sma_short = sma_short
        self.sma_long = sma_long
        self.rsi_period = rsi_period
        self.rsi_overbought = rsi_overbought
        self.rsi_oversold = rsi_oversold
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        self.position_size_pct = position_size_pct

        self.positions = {}  # ticker -> position info
        self.trades = []  # all trades
        self.signals = []  # all signals

        logger.info(f"MARSIStrategy initialized with SMA({sma_short}/{sma_long}), RSI({rsi_period})")

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate SMA and RSI indicators."""
        df = df.copy()

        # Moving Averages
        df["sma_short"] = df["close"].rolling(window=self.sma_short).mean()
        df["sma_long"] = df["close"].rolling(window=self.sma_long).mean()

        # RSI
        df["rsi"] = self._calculate_rsi(df["close"], period=self.rsi_period)

        # Volatility (for position sizing)
        df["volatility"] = df["close"].pct_change().rolling(window=20).std()

        return df

    @staticmethod
    def _calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
        """Calculate Relative Strength Index."""
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """Generate buy/sell signals based on strategy rules."""
        df = self.calculate_indicators(df)

        # Initialize signal column
        df["signal"] = 0  # 0=hold, 1=buy, -1=sell

        # Generate signals (skip first few rows where indicators are NaN)
        min_rows = max(self.sma_long, self.rsi_period) + 1

        for i in range(min_rows, len(df)):
            sma_short = df["sma_short"].iloc[i]
            sma_long = df["sma_long"].iloc[i]
            rsi = df["rsi"].iloc[i]
            prev_sma_short = df["sma_short"].iloc[i - 1]
            prev_sma_long = df["sma_long"].iloc[i - 1]

            # Skip if any NaN values
            if pd.isna(sma_short) or pd.isna(sma_long) or pd.isna(rsi):
                continue

            # BUY Signal: SMA20 crosses above SMA50 and RSI < 70
            if (
                prev_sma_short <= prev_sma_long
                and sma_short > sma_long
                and rsi < self.rsi_overbought
            ):
                df.at[df.index[i], "signal"] = 1
                self.signals.append(
                    {
                        "date": df.index[i],
                        "type": "BUY",
                        "price": df["close"].iloc[i],
                        "sma_short": sma_short,
                        "sma_long": sma_long,
                        "rsi": rsi,
                    }
                )

            # SELL Signal: SMA20 crosses below SMA50 and RSI > 30
            elif (
                prev_sma_short >= prev_sma_long
                and sma_short < sma_long
                and rsi > self.rsi_oversold
            ):
                df.at[df.index[i], "signal"] = -1
                self.signals.append(
                    {
                        "date": df.index[i],
                        "type": "SELL",
                        "price": df["close"].iloc[i],
                        "sma_short": sma_short,
                        "sma_long": sma_long,
                        "rsi": rsi,
                    }
                )

        return df

    def calculate_position_size(self, capital: float, volatility: float) -> float:
        """Calculate position size based on capital and volatility."""
        # Reduce position size in high volatility
        volatility_adjustment = max(0.5, 1.0 - (volatility * 10))
        position_size = capital * self.position_size_pct * volatility_adjustment
        return position_size

    def backtest(self, df: pd.DataFrame, ticker: str, initial_capital: float = 100000) -> dict:
        """Run backtest on historical data."""
        logger.info(f"Starting backtest for {ticker} ({len(df)} bars)")

        # Generate signals
        df = self.generate_signals(df)

        capital = initial_capital
        position = None  # Current position: {entry_price, entry_date, shares, stop_loss, take_profit}
        equity_curve = []
        trades_executed = []

        for i in range(len(df)):
            current_price = df["close"].iloc[i]
            current_date = df.index[i]
            signal = df["signal"].iloc[i] if "signal" in df.columns else 0
            volatility = df["volatility"].iloc[i] if "volatility" in df.columns else 0.01

            # Check stop loss / take profit for open position
            if position:
                pnl = (current_price - position["entry_price"]) * position["shares"]
                pnl_pct = (current_price - position["entry_price"]) / position["entry_price"]

                # Stop Loss
                if current_price <= position["stop_loss"]:
                    logger.debug(f"STOP LOSS hit at {current_price} for {ticker}")
                    capital += pnl
                    trades_executed.append(
                        {
                            "ticker": ticker,
                            "entry_date": position["entry_date"],
                            "exit_date": current_date,
                            "entry_price": position["entry_price"],
                            "exit_price": current_price,
                            "shares": position["shares"],
                            "pnl": pnl,
                            "pnl_pct": pnl_pct,
                            "reason": "Stop Loss",
                        }
                    )
                    position = None

                # Take Profit
                elif current_price >= position["take_profit"]:
                    logger.debug(f"TAKE PROFIT hit at {current_price} for {ticker}")
                    capital += pnl
                    trades_executed.append(
                        {
                            "ticker": ticker,
                            "entry_date": position["entry_date"],
                            "exit_date": current_date,
                            "entry_price": position["entry_price"],
                            "exit_price": current_price,
                            "shares": position["shares"],
                            "pnl": pnl,
                            "pnl_pct": pnl_pct,
                            "reason": "Take Profit",
                        }
                    )
                    position = None

            # Execute BUY signal
            if signal == 1 and position is None:
                position_size = self.calculate_position_size(capital, volatility)
                shares = int(position_size / current_price)

                if shares > 0:
                    capital -= shares * current_price  # Deduct from cash
                    position = {
                        "entry_date": current_date,
                        "entry_price": current_price,
                        "shares": shares,
                        "stop_loss": current_price * (1 - self.stop_loss_pct),
                        "take_profit": current_price * (1 + self.take_profit_pct),
                    }
                    logger.info(
                        f"BUY {shares} shares of {ticker} at ${current_price:.2f} "
                        f"(SL: ${position['stop_loss']:.2f}, TP: ${position['take_profit']:.2f})"
                    )

            # Execute SELL signal
            elif signal == -1 and position is not None:
                pnl = (current_price - position["entry_price"]) * position["shares"]
                capital += current_price * position["shares"]
                pnl_pct = (current_price - position["entry_price"]) / position["entry_price"]

                logger.info(
                    f"SELL {position['shares']} shares of {ticker} at ${current_price:.2f} "
                    f"(P&L: ${pnl:.2f}, {pnl_pct*100:.2f}%)"
                )

                trades_executed.append(
                    {
                        "ticker": ticker,
                        "entry_date": position["entry_date"],
                        "exit_date": current_date,
                        "entry_price": position["entry_price"],
                        "exit_price": current_price,
                        "shares": position["shares"],
                        "pnl": pnl,
                        "pnl_pct": pnl_pct,
                        "reason": "Signal",
                    }
                )
                position = None

            # Calculate current equity
            if position:
                unrealized_pnl = (current_price - position["entry_price"]) * position["shares"]
            else:
                unrealized_pnl = 0

            current_equity = capital + unrealized_pnl
            equity_curve.append(
                {"date": current_date, "equity": current_equity, "cash": capital}
            )

        # Close any open position at end
        if position:
            final_price = df["close"].iloc[-1]
            pnl = (final_price - position["entry_price"]) * position["shares"]
            capital += pnl
            pnl_pct = (final_price - position["entry_price"]) / position["entry_price"]

            trades_executed.append(
                {
                    "ticker": ticker,
                    "entry_date": position["entry_date"],
                    "exit_date": df.index[-1],
                    "entry_price": position["entry_price"],
                    "exit_price": final_price,
                    "shares": position["shares"],
                    "pnl": pnl,
                    "pnl_pct": pnl_pct,
                    "reason": "End of Backtest",
                }
            )

        # Calculate metrics
        equity_df = pd.DataFrame(equity_curve)
        total_return = (capital - initial_capital) / initial_capital
        winning_trades = [t for t in trades_executed if t["pnl"] > 0]
        losing_trades = [t for t in trades_executed if t["pnl"] < 0]

        results = {
            "ticker": ticker,
            "initial_capital": initial_capital,
            "final_capital": capital,
            "total_return": total_return,
            "total_trades": len(trades_executed),
            "winning_trades": len(winning_trades),
            "losing_trades": len(losing_trades),
            "win_rate": len(winning_trades) / len(trades_executed) if trades_executed else 0,
            "avg_win": np.mean([t["pnl"] for t in winning_trades]) if winning_trades else 0,
            "avg_loss": np.mean([t["pnl"] for t in losing_trades]) if losing_trades else 0,
            "max_profit": max([t["pnl"] for t in trades_executed]) if trades_executed else 0,
            "max_loss": min([t["pnl"] for t in trades_executed]) if trades_executed else 0,
            "trades": trades_executed,
            "equity_curve": equity_df,
            "signals": self.signals,
        }

        logger.info(f"Backtest complete: {results['total_return']*100:.2f}% return, {results['total_trades']} trades")

        return results

    def print_results(self, results: dict):
        """Print backtest results in human-readable format."""
        print("\n" + "=" * 70)
        print(f"  BACKTEST RESULTS: {results['ticker']}")
        print("=" * 70)

        print(f"\nCapital:")
        print(f"  Initial:  ${results['initial_capital']:>12,.2f}")
        print(f"  Final:    ${results['final_capital']:>12,.2f}")
        print(f"  Return:   {results['total_return']:>12.2%}")

        print(f"\nTrading Activity:")
        print(f"  Total Trades:    {results['total_trades']}")
        print(f"  Winning Trades:  {results['winning_trades']}")
        print(f"  Losing Trades:   {results['losing_trades']}")
        print(f"  Win Rate:        {results['win_rate']:.2%}")

        print(f"\nProfits & Losses:")
        print(f"  Average Win:     ${results['avg_win']:>12,.2f}")
        print(f"  Average Loss:    ${results['avg_loss']:>12,.2f}")
        print(f"  Max Profit:      ${results['max_profit']:>12,.2f}")
        print(f"  Max Loss:        ${results['max_loss']:>12,.2f}")

        if results["total_trades"] > 0:
            print(f"\nTop 5 Trades:")
            top_trades = sorted(results["trades"], key=lambda x: x["pnl"], reverse=True)[:5]
            for i, trade in enumerate(top_trades, 1):
                print(
                    f"  {i}. {trade['entry_price']:.2f} → {trade['exit_price']:.2f} "
                    f"({trade['pnl_pct']*100:>6.2f}%) = ${trade['pnl']:>10,.2f} "
                    f"[{trade['reason']}]"
                )

        print("=" * 70 + "\n")
