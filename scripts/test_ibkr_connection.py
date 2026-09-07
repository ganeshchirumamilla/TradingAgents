#!/usr/bin/env python3
"""Test IBKR connection and basic functionality."""

import sys
import time
from pathlib import Path

try:
    from ib_async import IB, Stock, util
except ImportError:
    print("[ERROR] ib_async not installed")
    sys.exit(1)

def test_connection():
    """Test IBKR connection."""
    print("Testing IBKR Connection")
    print("-" * 70)

    ib = IB()

    try:
        print("[TEST] Connecting to IBKR at 127.0.0.1:4002...")
        ib.connect("127.0.0.1", 4002, clientId=1)
        print("[OK] Connected successfully")

        # Test simple contract
        print("\n[TEST] Testing historical data request...")
        contract = Stock("AAPL", "SMART", "USD")

        print("  - Contract: AAPL")
        print("  - Duration: 1 D (1 day)")
        print("  - Bar size: 1 hour")
        print("  - What to show: TRADES")
        print("  - Use RTH: True")
        print("  - Request timeout: 60s")

        bars = ib.reqHistoricalData(
            contract,
            endDateTime="",
            durationStr="1 D",
            barSizeSetting="1 hour",
            whatToShow="TRADES",
            useRTH=True,
            formatDate=1,
            timeout=60
        )

        if bars:
            df = util.df(bars)
            print(f"\n[OK] Received {len(df)} bars")
            print("\nSample data:")
            print(df.head())
        else:
            print("\n[WARNING] No data returned (bars is None)")

        print("\n[SUCCESS] Connection test passed!")
        return True

    except Exception as e:
        print(f"\n[ERROR] {str(e)}")
        return False

    finally:
        try:
            ib.disconnect()
            print("\n[OK] Disconnected")
        except:
            pass

if __name__ == "__main__":
    success = test_connection()
    sys.exit(0 if success else 1)
