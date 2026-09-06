"""IBKR data vendor: OHLCV bars via TWS/IB Gateway for the ``core_stock_apis`` category.

Selected by setting ``data_vendors.core_stock_apis`` (or the ``get_stock_data``
tool override) to ``"ibkr"``, and requires ``ibkr_enabled: True`` plus a
running TWS/IB Gateway with the API enabled. Only plain US-listed stocks are
supported (see ``IBKRClient.get_historical_bars``); other markets should stay
on yfinance/Alpha Vantage.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

import pandas as pd

from tradingagents.brokers.ibkr_client import IBKRClient, IBKRConfig, IBKRNotConfiguredError

from .config import get_config
from .errors import NoMarketDataError, VendorNotConfiguredError


def get_stock(
    symbol: Annotated[str, "ticker symbol of the company"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
) -> str:
    config = get_config()
    if not config.get("ibkr_enabled"):
        raise VendorNotConfiguredError(
            "IBKR data vendor selected but ibkr_enabled is False in config"
        )

    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    # A couple of days of slack around the requested window absorbs weekends/
    # holidays landing on either edge; rows outside the window are filtered below.
    duration_days = max((end_dt - start_dt).days + 4, 4)

    client = IBKRClient(IBKRConfig.from_app_config(config))
    try:
        bars = client.get_historical_bars(symbol, end_date, duration=f"{duration_days} D")
    except IBKRNotConfiguredError as exc:
        raise VendorNotConfiguredError(str(exc)) from exc

    canonical = symbol.upper()
    if not bars:
        raise NoMarketDataError(symbol, canonical, f"no IBKR bars between {start_date} and {end_date}")

    df = pd.DataFrame(
        {
            "Date": str(b.date),
            "Open": round(b.open, 2),
            "High": round(b.high, 2),
            "Low": round(b.low, 2),
            "Close": round(b.close, 2),
            "Volume": b.volume,
        }
        for b in bars
    )
    df = df[(df["Date"] >= start_date) & (df["Date"] <= end_date)]
    if df.empty:
        raise NoMarketDataError(symbol, canonical, "no rows in the requested window")

    csv_string = df.to_csv(index=False)
    header = f"# Stock data for {canonical} from {start_date} to {end_date} (IBKR)\n"
    header += f"# Total records: {len(df)}\n"
    header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    return header + csv_string
