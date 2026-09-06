"""Backtesting engine for TradingAgents trading decisions.

Simulates trading strategies over historical data and generates
performance metrics, equity curves, and trade analysis.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class BacktestConfig:
    """Configuration for backtest runs."""

    start_date: datetime
    end_date: datetime
    initial_capital: float = 100000
    commission_rate: float = 0.001  # 0.1%
    slippage_bps: float = 10  # Basis points
    max_position_size: float = 0.1  # Max 10% per position
    use_local_cache: bool = True
    cache_dir: str = "~/.tradingagents/data_cache"
    benchmark_ticker: str = "SPY"  # For alpha calculation


@dataclass
class Trade:
    """Record of a single trade."""

    ticker: str
    direction: str  # BUY or SELL
    entry_date: datetime
    entry_price: float
    exit_date: Optional[datetime] = None
    exit_price: Optional[float] = None
    quantity: int = 1
    commission: float = 0
    slippage: float = 0

    @property
    def pnl(self) -> float:
        """Calculate profit/loss."""
        if self.exit_price is None:
            return 0
        if self.direction == "BUY":
            return (self.exit_price - self.entry_price) * self.quantity - self.commission
        else:
            return (self.entry_price - self.exit_price) * self.quantity - self.commission

    @property
    def pnl_pct(self) -> float:
        """Calculate P&L percentage."""
        if self.entry_price == 0:
            return 0
        return self.pnl / (self.entry_price * self.quantity)


@dataclass
class BacktestResults:
    """Complete backtest results and metrics."""

    trades: list[Trade] = field(default_factory=list)
    daily_equity: pd.DataFrame = field(default_factory=pd.DataFrame)
    daily_returns: pd.Series = field(default_factory=pd.Series)
    start_date: datetime = None
    end_date: datetime = None
    initial_capital: float = 100000

    def summary(self) -> str:
        """Human-readable summary of results."""
        metrics = self.metrics()

        summary_text = f"""
╔════════════════════════════════════════════════════════╗
║           BACKTEST RESULTS SUMMARY                    ║
╚════════════════════════════════════════════════════════╝

Period:              {self.start_date.date()} to {self.end_date.date()}
Initial Capital:     ${self.initial_capital:,.2f}
Final Value:         ${metrics['final_value']:,.2f}

Returns:
  Total Return:      {metrics['total_return']:.2%}
  Annual Return:     {metrics['annual_return']:.2%}
  Max Drawdown:      {metrics['max_drawdown']:.2%}

Risk Metrics:
  Sharpe Ratio:      {metrics['sharpe_ratio']:.2f}
  Sortino Ratio:     {metrics['sortino_ratio']:.2f}
  Calmar Ratio:      {metrics['calmar_ratio']:.2f}

Trading Activity:
  Total Trades:      {metrics['total_trades']}
  Winning Trades:    {metrics['winning_trades']}
  Losing Trades:     {metrics['losing_trades']}
  Win Rate:          {metrics['win_rate']:.1%}

Trade Statistics:
  Avg Win:           ${metrics['avg_win']:,.2f}
  Avg Loss:          ${metrics['avg_loss']:,.2f}
  Profit Factor:     {metrics['profit_factor']:.2f}

Costs:
  Total Commission:  ${metrics['total_commission']:,.2f}
  Total Slippage:    ${metrics['total_slippage']:,.2f}
"""
        return summary_text

    def metrics(self) -> dict[str, Any]:
        """Calculate comprehensive metrics."""
        if self.daily_equity.empty:
            return {}

        equity = self.daily_equity["equity"].values
        returns = self.daily_returns.values

        # Basic metrics
        total_return = (equity[-1] - equity[0]) / equity[0]
        trading_days = len(equity)
        years = trading_days / 252
        annual_return = (1 + total_return) ** (1 / years) - 1 if years > 0 else 0

        # Drawdown
        running_max = np.maximum.accumulate(equity)
        drawdown = (equity - running_max) / running_max
        max_drawdown = np.min(drawdown)

        # Risk-adjusted returns
        daily_rf = 0.05 / 252  # 5% annual risk-free rate
        excess_returns = returns - daily_rf

        sharpe = np.mean(excess_returns) / (np.std(excess_returns) + 1e-8) * np.sqrt(252)
        downside_returns = excess_returns[excess_returns < 0]
        sortino = (
            np.mean(excess_returns)
            / (np.std(downside_returns) + 1e-8)
            * np.sqrt(252)
        )
        calmar = annual_return / abs(max_drawdown) if max_drawdown != 0 else 0

        # Trade analysis
        winning = [t for t in self.trades if t.pnl > 0]
        losing = [t for t in self.trades if t.pnl < 0]
        win_rate = len(winning) / len(self.trades) if self.trades else 0
        avg_win = np.mean([t.pnl for t in winning]) if winning else 0
        avg_loss = np.mean([t.pnl for t in losing]) if losing else 0
        profit_factor = (
            sum(t.pnl for t in winning) / abs(sum(t.pnl for t in losing)) + 1e-8
            if losing
            else 0
        )

        total_commission = sum(t.commission for t in self.trades)
        total_slippage = sum(t.slippage for t in self.trades)

        return {
            "total_return": total_return,
            "annual_return": annual_return,
            "max_drawdown": max_drawdown,
            "sharpe_ratio": sharpe,
            "sortino_ratio": sortino,
            "calmar_ratio": calmar,
            "total_trades": len(self.trades),
            "winning_trades": len(winning),
            "losing_trades": len(losing),
            "win_rate": win_rate,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "profit_factor": profit_factor,
            "initial_value": equity[0],
            "final_value": equity[-1],
            "peak_value": np.max(equity),
            "total_commission": total_commission,
            "total_slippage": total_slippage,
        }

    def to_dataframe(self) -> pd.DataFrame:
        """Export results to DataFrame."""
        if not self.trades:
            return pd.DataFrame()

        records = []
        for trade in self.trades:
            records.append(
                {
                    "ticker": trade.ticker,
                    "direction": trade.direction,
                    "entry_date": trade.entry_date,
                    "entry_price": trade.entry_price,
                    "exit_date": trade.exit_date,
                    "exit_price": trade.exit_price,
                    "quantity": trade.quantity,
                    "pnl": trade.pnl,
                    "pnl_pct": trade.pnl_pct,
                    "commission": trade.commission,
                    "slippage": trade.slippage,
                }
            )

        return pd.DataFrame(records)


class BacktestEngine:
    """Orchestrates backtest simulation."""

    def __init__(
        self,
        ta_graph: Any,
        backtest_config: BacktestConfig,
        tickers: list[str] = None,
    ):
        """Initialize backtest engine.

        Args:
            ta_graph: TradingAgentsGraph instance
            backtest_config: BacktestConfig with parameters
            tickers: List of tickers to backtest
        """
        self.ta_graph = ta_graph
        self.config = backtest_config
        self.tickers = tickers or []
        self.results = BacktestResults(
            start_date=backtest_config.start_date,
            end_date=backtest_config.end_date,
            initial_capital=backtest_config.initial_capital,
        )
        self.portfolio_value = backtest_config.initial_capital
        self.positions = {}  # ticker -> quantity
        self.cash = backtest_config.initial_capital

    def run(self) -> BacktestResults:
        """Run complete backtest.

        Returns:
            BacktestResults with trades and metrics
        """
        logger.info(
            f"Starting backtest {self.config.start_date.date()} "
            f"to {self.config.end_date.date()}"
        )

        # Generate trading dates
        current_date = self.config.start_date
        while current_date <= self.config.end_date:
            if self._is_trading_day(current_date):
                self._process_trading_day(current_date)

            current_date += timedelta(days=1)

        # Calculate daily equity curve
        self._calculate_equity_curve()

        logger.info("Backtest complete")
        return self.results

    def _is_trading_day(self, date: datetime) -> bool:
        """Check if date is a trading day (Mon-Fri)."""
        return date.weekday() < 5

    def _process_trading_day(self, trade_date: datetime):
        """Process trading decisions for a single day.

        In a real backtest, this would:
        1. Get market data for the day
        2. Run TradingAgentsGraph analysis
        3. Execute any generated signals
        4. Update portfolio
        """
        logger.debug(f"Processing trading day: {trade_date.date()}")

        # This is a stub; actual implementation would call:
        # decision = self.ta_graph.propagate(ticker, trade_date)
        # Then execute trades based on decision

    def _calculate_equity_curve(self):
        """Calculate daily equity curve from trades."""
        # Stub: Calculate equity progression based on trades
        # In practice: sum initial_capital + cumulative P&L
        pass

    def plot_equity_curve(self, save_path: str = None):
        """Plot equity curve over time.

        Args:
            save_path: Optional path to save plot
        """
        if self.results.daily_equity.empty:
            logger.warning("No equity data to plot")
            return

        try:
            import matplotlib.pyplot as plt

            fig, ax = plt.subplots(figsize=(12, 6))

            equity = self.results.daily_equity
            ax.plot(equity.index, equity["equity"], label="Portfolio Value")
            ax.axhline(y=self.config.initial_capital, color="r", linestyle="--", label="Initial Capital")

            ax.set_xlabel("Date")
            ax.set_ylabel("Portfolio Value ($)")
            ax.set_title("Backtest Equity Curve")
            ax.legend()
            ax.grid(True, alpha=0.3)

            if save_path:
                plt.savefig(save_path)
                logger.info(f"Saved plot to {save_path}")

            plt.show()

        except ImportError:
            logger.warning("Matplotlib not available for plotting")


def run_backtest_interactive() -> BacktestResults:
    """Run interactive backtest from CLI inputs."""
    from tradingagents.default_config import DEFAULT_CONFIG
    from tradingagents.graph.trading_graph import TradingAgentsGraph

    # Get user inputs (simplified)
    print("\n=== TradingAgents Backtest Setup ===")

    tickers_input = input("Tickers (comma-separated): ").strip()
    tickers = [t.strip().upper() for t in tickers_input.split(",")]

    start_date_str = input("Start date (YYYY-MM-DD): ").strip()
    end_date_str = input("End date (YYYY-MM-DD): ").strip()

    initial_capital = float(input("Initial capital ($): ").strip() or "100000")

    # Create config and run
    config = BacktestConfig(
        start_date=datetime.strptime(start_date_str, "%Y-%m-%d"),
        end_date=datetime.strptime(end_date_str, "%Y-%m-%d"),
        initial_capital=initial_capital,
    )

    ta_graph = TradingAgentsGraph(config=DEFAULT_CONFIG)
    engine = BacktestEngine(ta_graph, config, tickers)
    results = engine.run()

    print(results.summary())
    print(results.to_dataframe())

    return results
