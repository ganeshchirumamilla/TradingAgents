"""IBKR as a get_stock_data vendor: registration and the ibkr_enabled gate."""

from __future__ import annotations

import pytest

from tradingagents.dataflows import interface
from tradingagents.dataflows.config import set_config
from tradingagents.dataflows.errors import VendorNotConfiguredError
from tradingagents.dataflows.ibkr import get_stock


@pytest.mark.unit
def test_ibkr_registered_as_core_stock_vendor():
    assert "ibkr" in interface.VENDOR_LIST
    assert "ibkr" in interface.VENDOR_METHODS["get_stock_data"]


@pytest.mark.unit
def test_ibkr_routable_via_data_vendors_config():
    set_config({"data_vendors": {"core_stock_apis": "ibkr"}})
    with pytest.raises(VendorNotConfiguredError):
        # ibkr_enabled defaults to False, so routing to it must fail closed
        # rather than silently attempting a TWS/Gateway connection.
        interface.route_to_vendor("get_stock_data", "AAPL", "2026-01-01", "2026-01-10")


@pytest.mark.unit
def test_get_stock_raises_when_ibkr_disabled():
    set_config({"ibkr_enabled": False})
    with pytest.raises(VendorNotConfiguredError, match="ibkr_enabled"):
        get_stock("AAPL", "2026-01-01", "2026-01-10")
