"""IBKRClient: config resolution and behavior that doesn't require a live TWS/Gateway."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

import pytest

from tradingagents.brokers.ibkr_client import IBKRClient, IBKRConfig, IBKRNotConfiguredError


@pytest.mark.unit
def test_config_from_app_config_defaults():
    cfg = IBKRConfig.from_app_config({})
    assert cfg.host == "127.0.0.1"
    assert cfg.port == 7497
    assert cfg.client_id == 1
    assert cfg.account is None
    assert cfg.paper is True


@pytest.mark.unit
def test_config_from_app_config_overrides():
    cfg = IBKRConfig.from_app_config({
        "ibkr_host": "10.0.0.5",
        "ibkr_port": "4001",
        "ibkr_client_id": "7",
        "ibkr_account": "DU123456",
        "ibkr_paper": False,
        "ibkr_timeout": "5",
    })
    assert cfg.host == "10.0.0.5"
    assert cfg.port == 4001
    assert cfg.client_id == 7
    assert cfg.account == "DU123456"
    assert cfg.paper is False
    assert cfg.timeout == 5.0


@pytest.mark.unit
def test_empty_account_string_is_none():
    # A blank TRADINGAGENTS_IBKR_ACCOUNT should not be treated as a real account id.
    cfg = IBKRConfig.from_app_config({"ibkr_account": ""})
    assert cfg.account is None


@pytest.mark.unit
def test_missing_ib_async_raises_helpful_error(monkeypatch):
    monkeypatch.setitem(sys.modules, "ib_async", None)  # force ImportError on import
    client = IBKRClient(IBKRConfig())
    with pytest.raises(IBKRNotConfiguredError, match="ib_async"):
        client.get_account_summary()


@pytest.mark.unit
def test_get_position_for_symbol_matches_root_ticker(monkeypatch):
    client = IBKRClient(IBKRConfig())
    monkeypatch.setattr(
        client,
        "get_positions",
        lambda: [
            {"symbol": "AAPL", "position": 10, "avg_cost": 150.0},
            {"symbol": "MSFT", "position": 5, "avg_cost": 300.0},
        ],
    )
    assert client.get_position_for_symbol("aapl")["position"] == 10
    assert client.get_position_for_symbol("0700.HK") is None


@pytest.mark.unit
def test_place_order_lmt_without_price_raises(monkeypatch):
    fake_ib_async = MagicMock()
    monkeypatch.setitem(sys.modules, "ib_async", fake_ib_async)
    client = IBKRClient(IBKRConfig())
    with pytest.raises(ValueError, match="limit_price"):
        client.place_order("AAPL", "BUY", 1, order_type="LMT", limit_price=None)
