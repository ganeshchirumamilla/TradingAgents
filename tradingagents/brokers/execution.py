"""Places an IBKR order for the Portfolio Manager's final decision.

Three independent gates must all pass before any order reaches IBKR:

1. ``ibkr_enabled`` — the broker integration is on at all.
2. ``ibkr_auto_execute`` — this run should act on decisions, not just read
   account context.
3. If ``ibkr_paper`` is ``False`` (live trading configured), the
   ``TRADINGAGENTS_IBKR_CONFIRM_LIVE`` environment variable must also be set.

That third gate is deliberately outside the regular config dict: flipping one
config value (or inheriting a wrong default from a copied config) can never by
itself arm live order placement. It takes a separate, explicit environment
variable that a config file alone cannot set.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass

from tradingagents.agents.utils.rating import is_review
from tradingagents.brokers.ibkr_client import IBKRClient, IBKRConfig, IBKRNotConfiguredError

logger = logging.getLogger(__name__)

# Rating -> IBKR order side. Hold places no order. Overweight/Underweight are
# directional nudges without a target-weight number to size against, so they
# map to the same flat-quantity BUY/SELL as Buy/Sell (see ExecutionResult).
_RATING_TO_ACTION = {
    "Buy": "BUY",
    "Overweight": "BUY",
    "Hold": None,
    "Underweight": "SELL",
    "Sell": "SELL",
}

_CONFIRM_LIVE_ENV = "TRADINGAGENTS_IBKR_CONFIRM_LIVE"
_TRUE_VALUES = ("true", "1", "yes", "on")

_PRICE_TARGET_RE = re.compile(r"\*\*Price Target\*\*:\s*([0-9]+(?:\.[0-9]+)?)")


def _extract_price_target(decision_text: str) -> float | None:
    match = _PRICE_TARGET_RE.search(decision_text or "")
    return float(match.group(1)) if match else None


@dataclass
class ExecutionResult:
    """Outcome of one :func:`execute_decision` call, for logging/display."""

    attempted: bool
    submitted: bool
    action: str | None = None
    quantity: int | None = None
    order_type: str | None = None
    limit_price: float | None = None
    order_id: int | None = None
    status: str | None = None
    reason: str | None = None
    paper: bool = True


def execute_decision(
    ticker: str,
    rating_signal: str,
    decision_text: str,
    config: dict,
) -> ExecutionResult:
    """Place (or skip, with a reason) an IBKR order for a processed rating signal.

    ``rating_signal`` is the 5-tier signal returned by
    ``TradingAgentsGraph.process_signal`` (Buy/Overweight/Hold/Underweight/Sell)
    or the ``REVIEW`` sentinel. ``decision_text`` is the rendered Portfolio
    Manager decision, used only to pull an optional price target for LMT
    orders.
    """
    if not config.get("ibkr_enabled") or not config.get("ibkr_auto_execute"):
        return ExecutionResult(attempted=False, submitted=False, reason="IBKR order execution is not enabled")

    if is_review(rating_signal):
        return ExecutionResult(
            attempted=False, submitted=False,
            reason="Decision was REVIEW (no parseable rating), not a tradeable signal",
        )

    paper = bool(config.get("ibkr_paper", True))
    action = _RATING_TO_ACTION.get(rating_signal)

    if not paper and os.environ.get(_CONFIRM_LIVE_ENV, "").strip().lower() not in _TRUE_VALUES:
        return ExecutionResult(
            attempted=True, submitted=False, action=action, paper=paper,
            reason=(
                f"Live trading is configured (ibkr_paper=False) but {_CONFIRM_LIVE_ENV} "
                "is not set — refusing to place a live order. Set that env var "
                "explicitly to arm live execution."
            ),
        )

    if action is None:
        return ExecutionResult(attempted=True, submitted=False, paper=paper, reason="Hold: no order to place")

    quantity = int(config.get("ibkr_order_quantity", 1))
    order_type = config.get("ibkr_order_type", "MKT")
    limit_price = _extract_price_target(decision_text) if order_type.upper() == "LMT" else None
    if order_type.upper() == "LMT" and limit_price is None:
        logger.warning(
            "ibkr_order_type is LMT but no price target was found in the decision; "
            "falling back to a MKT order for %s.", ticker,
        )
        order_type = "MKT"

    try:
        client = IBKRClient(IBKRConfig.from_app_config(config))
        result = client.place_order(ticker, action, quantity, order_type=order_type, limit_price=limit_price)
    except (IBKRNotConfiguredError, ValueError) as exc:
        logger.warning("IBKR order not placed for %s: %s", ticker, exc)
        return ExecutionResult(
            attempted=True, submitted=False, action=action, quantity=quantity,
            order_type=order_type, limit_price=limit_price, paper=paper, reason=str(exc),
        )
    except Exception as exc:  # noqa: BLE001 - never crash a completed analysis over broker connectivity
        logger.warning("IBKR order failed for %s %s x%s %s: %s", action, ticker, quantity, order_type, exc)
        return ExecutionResult(
            attempted=True, submitted=False, action=action, quantity=quantity,
            order_type=order_type, limit_price=limit_price, paper=paper, reason=str(exc),
        )

    logger.info(
        "IBKR order submitted (%s): %s %s x%s (%s) -> order_id=%s status=%s",
        "paper" if paper else "LIVE", action, ticker, quantity, order_type,
        result.get("order_id"), result.get("status"),
    )
    return ExecutionResult(
        attempted=True, submitted=True, action=action, quantity=quantity,
        order_type=order_type, limit_price=limit_price,
        order_id=result.get("order_id"), status=result.get("status"), paper=paper,
    )
