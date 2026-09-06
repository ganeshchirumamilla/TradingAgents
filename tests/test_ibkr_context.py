"""build_ibkr_account_context(): fail-open account/position snapshot for prompts."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from tradingagents.brokers.context import build_ibkr_account_context
from tradingagents.brokers.ibkr_client import IBKRNotConfiguredError


@pytest.mark.unit
def test_disabled_ibkr_returns_empty_string():
    assert build_ibkr_account_context("AAPL", {"ibkr_enabled": False}) == ""


@pytest.mark.unit
def test_connection_failure_fails_open_not_raises():
    config = {"ibkr_enabled": True}
    with patch("tradingagents.brokers.context.IBKRClient") as mock_client_cls:
        mock_client_cls.return_value.get_account_summary.side_effect = IBKRNotConfiguredError("no TWS")
        result = build_ibkr_account_context("AAPL", config)
    assert result == ""


@pytest.mark.unit
def test_unexpected_error_also_fails_open():
    config = {"ibkr_enabled": True}
    with patch("tradingagents.brokers.context.IBKRClient") as mock_client_cls:
        mock_client_cls.return_value.get_account_summary.side_effect = RuntimeError("boom")
        result = build_ibkr_account_context("AAPL", config)
    assert result == ""


@pytest.mark.unit
def test_renders_summary_and_position():
    config = {"ibkr_enabled": True, "ibkr_paper": True}
    with patch("tradingagents.brokers.context.IBKRClient") as mock_client_cls:
        mock_client_cls.return_value.get_account_summary.return_value = {
            "account": "DU123456",
            "NetLiquidation": "100000",
            "TotalCashValue": "50000",
        }
        mock_client_cls.return_value.get_position_for_symbol.return_value = {
            "position": 10, "avg_cost": 150.0,
        }
        result = build_ibkr_account_context("AAPL", config)

    assert "PAPER" in result
    assert "DU123456" in result
    assert "100000" in result
    assert "10 shares" in result


@pytest.mark.unit
def test_renders_no_position_when_flat():
    config = {"ibkr_enabled": True}
    with patch("tradingagents.brokers.context.IBKRClient") as mock_client_cls:
        mock_client_cls.return_value.get_account_summary.return_value = {"account": "DU1"}
        mock_client_cls.return_value.get_position_for_symbol.return_value = None
        result = build_ibkr_account_context("AAPL", config)

    assert "none" in result
