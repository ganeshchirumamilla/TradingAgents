"""Builds the IBKR account/position snapshot injected into agent prompts.

Mirrors the fail-open pattern used for deterministic instrument identity
resolution (``tradingagents.agents.utils.agent_utils.resolve_instrument_identity``):
a broken or unreachable IBKR connection must never block an analysis run,
since this context is an enrichment the Trader and Portfolio Manager use when
present, not a data dependency the graph requires.
"""

from __future__ import annotations

import logging

from tradingagents.brokers.ibkr_client import IBKRClient, IBKRConfig, IBKRNotConfiguredError

logger = logging.getLogger(__name__)

_SUMMARY_TAGS = (
    ("NetLiquidation", "Net liquidation value"),
    ("TotalCashValue", "Cash"),
    ("BuyingPower", "Buying power"),
    ("GrossPositionValue", "Gross position value"),
)


def build_ibkr_account_context(ticker: str, config: dict) -> str:
    """Return a markdown snapshot of the IBKR account and any position in ``ticker``.

    Returns ``""`` when ``ibkr_enabled`` is off, the ``ib_async`` package is
    missing, or the account cannot be reached (a stopped TWS/Gateway, a wrong
    port, ...) — logged as a warning either way, but never raised.
    """
    if not config.get("ibkr_enabled"):
        return ""

    try:
        client = IBKRClient(IBKRConfig.from_app_config(config))
        summary = client.get_account_summary()
        position = client.get_position_for_symbol(ticker)
    except IBKRNotConfiguredError as exc:
        logger.warning("IBKR account context unavailable: %s", exc)
        return ""
    except Exception as exc:  # noqa: BLE001 - fail open, never block the run
        logger.warning("Could not fetch IBKR account context for %s: %s", ticker, exc)
        return ""

    mode = "PAPER" if config.get("ibkr_paper", True) else "LIVE"
    lines = [f"**IBKR Account ({mode})**"]
    if summary.get("account"):
        lines.append(f"- Account: {summary['account']}")
    for tag, label in _SUMMARY_TAGS:
        if tag in summary:
            lines.append(f"- {label}: {summary[tag]}")

    if position:
        lines.append(
            f"- Current position in {ticker}: {position['position']} shares "
            f"@ avg cost {position['avg_cost']}"
        )
    else:
        lines.append(f"- Current position in {ticker}: none")

    return "\n".join(lines)
