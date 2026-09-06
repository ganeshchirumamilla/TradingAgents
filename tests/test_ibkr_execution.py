"""execute_decision(): the gating logic that decides whether an IBKR order is placed.

Covers the three independent gates (ibkr_enabled, ibkr_auto_execute, and the
live-trading confirmation env var) plus rating->action mapping, without
requiring a live TWS/Gateway or the ib_async package.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from tradingagents.brokers.execution import execute_decision

BASE_CONFIG = {
    "ibkr_enabled": True,
    "ibkr_auto_execute": True,
    "ibkr_paper": True,
    "ibkr_order_quantity": 3,
    "ibkr_order_type": "MKT",
}


@pytest.mark.unit
def test_disabled_ibkr_skips_execution():
    result = execute_decision("AAPL", "Buy", "", {"ibkr_enabled": False, "ibkr_auto_execute": True})
    assert result.attempted is False
    assert result.submitted is False


@pytest.mark.unit
def test_ibkr_enabled_without_auto_execute_skips():
    result = execute_decision("AAPL", "Buy", "", {"ibkr_enabled": True, "ibkr_auto_execute": False})
    assert result.attempted is False


@pytest.mark.unit
def test_review_signal_is_never_traded():
    result = execute_decision("AAPL", "REVIEW", "", BASE_CONFIG)
    assert result.attempted is False
    assert result.submitted is False


@pytest.mark.unit
def test_hold_places_no_order():
    with patch("tradingagents.brokers.execution.IBKRClient") as mock_client_cls:
        result = execute_decision("AAPL", "Hold", "", BASE_CONFIG)
    assert result.attempted is True
    assert result.submitted is False
    mock_client_cls.assert_not_called()


@pytest.mark.parametrize(
    "rating,expected_action",
    [("Buy", "BUY"), ("Overweight", "BUY"), ("Underweight", "SELL"), ("Sell", "SELL")],
)
@pytest.mark.unit
def test_paper_order_submitted_for_directional_ratings(rating, expected_action):
    with patch("tradingagents.brokers.execution.IBKRClient") as mock_client_cls:
        mock_client_cls.return_value.place_order.return_value = {"order_id": 42, "status": "Submitted"}
        result = execute_decision("AAPL", rating, "", BASE_CONFIG)

    assert result.attempted is True
    assert result.submitted is True
    assert result.action == expected_action
    assert result.quantity == 3
    assert result.order_id == 42
    assert result.paper is True
    mock_client_cls.return_value.place_order.assert_called_once_with(
        "AAPL", expected_action, 3, order_type="MKT", limit_price=None
    )


@pytest.mark.unit
def test_live_order_refused_without_confirmation_env(monkeypatch):
    monkeypatch.delenv("TRADINGAGENTS_IBKR_CONFIRM_LIVE", raising=False)
    live_config = {**BASE_CONFIG, "ibkr_paper": False}
    with patch("tradingagents.brokers.execution.IBKRClient") as mock_client_cls:
        result = execute_decision("AAPL", "Buy", "", live_config)

    assert result.attempted is True
    assert result.submitted is False
    assert "TRADINGAGENTS_IBKR_CONFIRM_LIVE" in result.reason
    mock_client_cls.assert_not_called()


@pytest.mark.unit
def test_live_order_proceeds_when_confirmed(monkeypatch):
    monkeypatch.setenv("TRADINGAGENTS_IBKR_CONFIRM_LIVE", "true")
    live_config = {**BASE_CONFIG, "ibkr_paper": False}
    with patch("tradingagents.brokers.execution.IBKRClient") as mock_client_cls:
        mock_client_cls.return_value.place_order.return_value = {"order_id": 7, "status": "Submitted"}
        result = execute_decision("AAPL", "Sell", "", live_config)

    assert result.submitted is True
    assert result.paper is False


@pytest.mark.unit
def test_broker_failure_is_reported_not_raised():
    with patch("tradingagents.brokers.execution.IBKRClient") as mock_client_cls:
        mock_client_cls.return_value.place_order.side_effect = ConnectionError("TWS unreachable")
        result = execute_decision("AAPL", "Buy", "", BASE_CONFIG)

    assert result.attempted is True
    assert result.submitted is False
    assert "TWS unreachable" in result.reason


@pytest.mark.unit
def test_lmt_uses_price_target_from_decision_text():
    lmt_config = {**BASE_CONFIG, "ibkr_order_type": "LMT"}
    decision_text = "**Rating**: Buy\n\n**Price Target**: 187.5"
    with patch("tradingagents.brokers.execution.IBKRClient") as mock_client_cls:
        mock_client_cls.return_value.place_order.return_value = {"order_id": 1, "status": "Submitted"}
        result = execute_decision("AAPL", "Buy", decision_text, lmt_config)

    assert result.order_type == "LMT"
    assert result.limit_price == 187.5
    mock_client_cls.return_value.place_order.assert_called_once_with(
        "AAPL", "BUY", 3, order_type="LMT", limit_price=187.5
    )


@pytest.mark.unit
def test_lmt_without_price_target_falls_back_to_mkt():
    lmt_config = {**BASE_CONFIG, "ibkr_order_type": "LMT"}
    with patch("tradingagents.brokers.execution.IBKRClient") as mock_client_cls:
        mock_client_cls.return_value.place_order.return_value = {"order_id": 1, "status": "Submitted"}
        result = execute_decision("AAPL", "Buy", "**Rating**: Buy", lmt_config)

    assert result.order_type == "MKT"
    assert result.limit_price is None
