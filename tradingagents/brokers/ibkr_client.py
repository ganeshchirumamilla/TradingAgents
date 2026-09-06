"""Thin synchronous-style wrapper around ``ib_async`` for TWS / IB Gateway.

``ib_async`` (the maintained fork of ``ib_insync``) exposes a blocking-looking
API backed by its own asyncio event loop, so a plain script can call
``ib.connect()`` / ``ib.reqHistoricalData()`` / ``ib.placeOrder()`` without
managing async machinery itself. This module is a small facade over that,
scoped to what TradingAgents needs: account summary, positions, historical
bars, and order placement.

The dependency is optional (``pip install "tradingagents[ibkr]"``) so the core
install stays free of it; :func:`_import_ib_async` raises
:class:`IBKRNotConfiguredError` when it is missing, which callers treat the
same way a missing vendor API key is treated elsewhere in this codebase.

Each public method opens its own connection and disconnects when done, rather
than holding one open for the life of a run. TWS/Gateway's API socket accepts
one connection per ``clientId`` at a time, and a TradingAgents run makes only
a handful of IBKR calls total, so the added lifecycle complexity of a
long-lived connection is not worth it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class IBKRNotConfiguredError(Exception):
    """The ``ib_async`` package is missing, or the IBKR connection failed."""


def _import_ib_async():
    try:
        from ib_async import IB, LimitOrder, MarketOrder, Stock
    except ImportError as exc:  # pragma: no cover - exercised via monkeypatch in tests
        raise IBKRNotConfiguredError(
            "IBKR integration requires the 'ib_async' package. "
            'Install it with: pip install "tradingagents[ibkr]"'
        ) from exc
    return IB, LimitOrder, MarketOrder, Stock


@dataclass
class IBKRConfig:
    """Connection parameters for one IBKR client, resolved from app config."""

    host: str = "127.0.0.1"
    port: int = 7497
    client_id: int = 1
    account: str | None = None
    paper: bool = True
    timeout: float = 10.0

    @classmethod
    def from_app_config(cls, config: dict) -> IBKRConfig:
        return cls(
            host=config.get("ibkr_host", "127.0.0.1"),
            port=int(config.get("ibkr_port", 7497)),
            client_id=int(config.get("ibkr_client_id", 1)),
            account=config.get("ibkr_account") or None,
            paper=bool(config.get("ibkr_paper", True)),
            timeout=float(config.get("ibkr_timeout", 10.0)),
        )


class IBKRClient:
    """Connects to TWS/IB Gateway on demand to serve one account/data/order call."""

    def __init__(self, ibkr_config: IBKRConfig):
        self.config = ibkr_config

    def _connect(self):
        IB, *_ = _import_ib_async()
        ib = IB()
        try:
            ib.connect(
                self.config.host,
                self.config.port,
                clientId=self.config.client_id,
                timeout=self.config.timeout,
            )
        except Exception as exc:
            raise IBKRNotConfiguredError(
                f"Could not connect to IBKR at {self.config.host}:{self.config.port} "
                f"(is TWS/IB Gateway running with the API enabled?): {exc}"
            ) from exc
        return ib

    def _resolve_account(self, ib) -> str | None:
        if self.config.account:
            return self.config.account
        accounts = ib.managedAccounts()
        return accounts[0] if accounts else None

    def get_account_summary(self) -> dict[str, Any]:
        """Return a dict of account-summary tags (NetLiquidation, TotalCashValue, ...)."""
        ib = self._connect()
        try:
            account = self._resolve_account(ib)
            tags = ib.accountSummary(account) if account else ib.accountSummary()
            summary: dict[str, Any] = {"account": account}
            for item in tags:
                # accountSummary can report the same tag per-currency; keep the
                # base-currency ("BASE") row, which is the one meant for display.
                if item.currency and item.currency not in ("", "BASE"):
                    continue
                summary[item.tag] = item.value
            return summary
        finally:
            ib.disconnect()

    def get_positions(self) -> list[dict[str, Any]]:
        """Return every open position across the configured (or default) account."""
        ib = self._connect()
        try:
            positions = ib.positions(self.config.account) if self.config.account else ib.positions()
            return [
                {
                    "account": p.account,
                    "symbol": p.contract.symbol,
                    "sec_type": p.contract.secType,
                    "exchange": getattr(p.contract, "exchange", None),
                    "currency": p.contract.currency,
                    "position": p.position,
                    "avg_cost": p.avgCost,
                }
                for p in positions
            ]
        finally:
            ib.disconnect()

    def get_position_for_symbol(self, symbol: str) -> dict[str, Any] | None:
        """Return the position dict matching ``symbol``'s root ticker, or ``None``.

        Strips exchange suffixes / crypto pair markers (``.HK``, ``-USD``, ...)
        since IBKR contracts key on the bare root symbol, not the Yahoo-style
        ticker TradingAgents uses elsewhere.
        """
        root = symbol.split(".")[0].split("-")[0].upper()
        for pos in self.get_positions():
            if pos["symbol"].upper() == root:
                return pos
        return None

    def get_historical_bars(
        self,
        symbol: str,
        end_date: str,
        duration: str = "30 D",
        bar_size: str = "1 day",
    ) -> list[Any]:
        """Return IBKR historical bars for ``symbol`` ending at ``end_date``.

        ``duration`` and ``bar_size`` follow IBKR's ``reqHistoricalData`` string
        formats (e.g. ``"30 D"``, ``"1 Y"``, ``"1 day"``, ``"1 hour"``). Only
        plain US stocks (routed through SMART/USD) are supported; other asset
        classes need a different contract and are out of scope here.
        """
        IB, _, _, Stock = _import_ib_async()
        ib = self._connect()
        try:
            contract = Stock(symbol.upper(), "SMART", "USD")
            ib.qualifyContracts(contract)
            return ib.reqHistoricalData(
                contract,
                endDateTime=f"{end_date} 23:59:59",
                durationStr=duration,
                barSizeSetting=bar_size,
                whatToShow="TRADES",
                useRTH=True,
                formatDate=1,
            )
        finally:
            ib.disconnect()

    def place_order(
        self,
        symbol: str,
        action: str,
        quantity: int,
        order_type: str = "MKT",
        limit_price: float | None = None,
    ) -> dict[str, Any]:
        """Submit a BUY/SELL order for ``symbol`` and return its id and status.

        Only plain US-stock market/limit orders are supported. Raises
        ``ValueError`` for an ``LMT`` order without ``limit_price``, and
        ``IBKRNotConfiguredError`` if the connection or package is unavailable.
        """
        if order_type.upper() == "LMT" and limit_price is None:
            raise ValueError("limit_price is required for LMT orders")

        IB, LimitOrder, MarketOrder, Stock = _import_ib_async()
        ib = self._connect()
        try:
            contract = Stock(symbol.upper(), "SMART", "USD")
            ib.qualifyContracts(contract)
            if order_type.upper() == "LMT":
                order = LimitOrder(action.upper(), quantity, limit_price)
            else:
                order = MarketOrder(action.upper(), quantity)
            if self.config.account:
                order.account = self.config.account

            trade = ib.placeOrder(contract, order)
            # Give IBKR a moment to assign an order id and an initial status
            # before we read them back.
            ib.sleep(1)
            return {
                "order_id": trade.order.orderId,
                "status": trade.orderStatus.status,
            }
        finally:
            ib.disconnect()
