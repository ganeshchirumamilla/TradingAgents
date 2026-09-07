#!/usr/bin/env python3
"""Test different date ranges to find what works with IBKR."""

import sys
import time
from ib_async import IB, Stock, util

def test_range(days: int, bar_size: str, client_id: int = 1) -> bool:
    """Test a specific date range."""
    ib = IB()
    try:
        print(f"\n[TEST] {days:4d} days, {bar_size:6s} bars... ", end="", flush=True)
        ib.connect("127.0.0.1", 4002, clientId=client_id)

        contract = Stock("AAPL", "SMART", "USD")
        bars = ib.reqHistoricalData(
            contract,
            endDateTime="",
            durationStr=f"{days} D",
            barSizeSetting=bar_size,
            whatToShow="TRADES",
            useRTH=True,
            formatDate=1,
            timeout=120
        )

        if bars is None:
            print("[FAIL] No data returned")
            return False

        df = util.df(bars)
        if df.empty:
            print("[FAIL] Empty DataFrame")
            return False

        print(f"[OK] {len(df):5d} bars")
        return True

    except Exception as e:
        print(f"[ERROR] {str(e)[:40]}")
        return False

    finally:
        try:
            ib.disconnect()
        except:
            pass


if __name__ == "__main__":
    print("Testing IBKR date range limits...")
    print("=" * 60)

    client_id = 100

    # Test 1-min data (should be limited)
    print("\n1-MINUTE BARS:")
    for days in [1, 7, 14, 30, 60, 90]:
        test_range(days, "1 min", client_id)
        client_id += 1
        time.sleep(2)

    # Test 5-min data
    print("\n5-MINUTE BARS:")
    for days in [7, 30, 90, 180, 365]:
        test_range(days, "5 mins", client_id)
        client_id += 1
        time.sleep(2)

    # Test hourly data
    print("\nHOURLY BARS:")
    for days in [30, 90, 180, 365, 730, 1825]:
        test_range(days, "1 hour", client_id)
        client_id += 1
        time.sleep(2)

    # Test daily data
    print("\nDAILY BARS:")
    for days in [365, 730, 1825, 3650]:
        test_range(days, "1 day", client_id)
        client_id += 1
        time.sleep(2)

    print("\n" + "=" * 60)
    print("Testing complete")
