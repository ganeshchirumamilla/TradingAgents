# IBKR Setup & Local Backtesting Guide

## Table of Contents
1. [IBKR Credentials Setup](#ibkr-credentials-setup)
2. [Downloading Historical Data](#downloading-historical-data)
3. [Local Data Persistence](#local-data-persistence)
4. [Running Backtests](#running-backtests)
5. [Troubleshooting](#troubleshooting)

---

## IBKR Credentials Setup

### Prerequisites
1. Interactive Brokers account (paper or live)
2. TWS (Trader Workstation) or IB Gateway installed
3. Install IBKR integration: `pip install "tradingagents[ibkr]"`

### Step 1: Enable API in TWS/IB Gateway

#### TWS (Trader Workstation)
1. Open TWS
2. Go to **File → Global Configuration**
3. Navigate to **API → Settings**
4. Check: **"Enable ActiveX and Socket Clients"**
5. Add trusted IP (if remote): Add `127.0.0.1` to trusted IPs list
6. Click **OK** to save

#### IB Gateway
1. Open IB Gateway
2. Go to **Main Window → Global Configuration**
3. Navigate to **API → Settings**
4. Check: **"Enable ActiveX and Socket Clients"**
5. Click **OK**

### Step 2: Configure Credentials in `.env`

Copy `.env.example` to `.env` and add IBKR settings:

```bash
cp .env.example .env
```

Edit `.env` and configure:

```bash
# Interactive Brokers (IBKR) Connection Settings
TRADINGAGENTS_IBKR_ENABLED=true

# TWS: 7497 (paper) / 7496 (live)
# IB Gateway: 4002 (paper) / 4001 (live)
TRADINGAGENTS_IBKR_PORT=7497

# Host (usually localhost)
TRADINGAGENTS_IBKR_HOST=127.0.0.1

# Client ID (unique per connection, default 1)
TRADINGAGENTS_IBKR_CLIENT_ID=1

# Account ID (optional; auto-detects if not set)
# Find this in TWS: Account Name field
TRADINGAGENTS_IBKR_ACCOUNT=DU12345678

# Paper trading flag (true/false)
TRADINGAGENTS_IBKR_PAPER=true

# Data Persistence & Backtesting
TRADINGAGENTS_CACHE_DIR=/home/user/.tradingagents
TRADINGAGENTS_USE_LOCAL_DATA_CACHE=true
TRADINGAGENTS_IBKR_DATA_DOWNLOAD_ENABLED=true
```

### Step 3: Find Your Account ID

Run this Python script to identify your account:

```python
from tradingagents.brokers.ibkr_client import IBKRClient, IBKRConfig
import os

config = IBKRConfig(
    host=os.getenv("TRADINGAGENTS_IBKR_HOST", "127.0.0.1"),
    port=int(os.getenv("TRADINGAGENTS_IBKR_PORT", 7497)),
)

client = IBKRClient(config)
try:
    summary = client.get_account_summary()
    print(f"Account ID: {summary.get('account')}")
    print(f"Net Liquidation: ${summary.get('NetLiquidation', 'N/A')}")
    print(f"Available Cash: ${summary.get('TotalCashValue', 'N/A')}")
except Exception as e:
    print(f"Error: {e}")
    print("Make sure TWS/IB Gateway is running with API enabled!")
```

### Step 4: Verify Connection (Optional)

```bash
# Run with IBKR enabled (CLI will show account context in output)
TRADINGAGENTS_IBKR_ENABLED=true tradingagents analyze
```

---

## Downloading Historical Data

### Automatic Download from IBKR

The framework can download and cache historical data directly from IBKR for faster, offline analysis.

#### Configuration

Add to `.env`:

```bash
TRADINGAGENTS_IBKR_DATA_DOWNLOAD_ENABLED=true
TRADINGAGENTS_DATA_CACHE_DIR=~/.tradingagents/data_cache
TRADINGAGENTS_DATA_RETENTION_DAYS=365  # Keep 1 year of data
```

#### Download Script

Create `download_ibkr_data.py`:

```python
#!/usr/bin/env python
"""Download and cache historical data from IBKR."""

from datetime import datetime, timedelta
import os
from pathlib import Path
from tradingagents.brokers.ibkr_client import IBKRClient, IBKRConfig
from tradingagents.dataflows.local_cache import LocalDataCache

# Configuration
IBKR_CONFIG = IBKRConfig(
    host=os.getenv("TRADINGAGENTS_IBKR_HOST", "127.0.0.1"),
    port=int(os.getenv("TRADINGAGENTS_IBKR_PORT", 7497)),
    account=os.getenv("TRADINGAGENTS_IBKR_ACCOUNT"),
)

CACHE_DIR = Path(os.getenv("TRADINGAGENTS_DATA_CACHE_DIR", 
                          "~/.tradingagents/data_cache")).expanduser()

# Tickers to download
TICKERS = ["AAPL", "NVDA", "MSFT", "TSLA", "SPY"]

def download_ticker_data(ticker: str, days_back: int = 365):
    """Download and cache data for a ticker."""
    print(f"\nDownloading {ticker} ({days_back} days)...")
    
    client = IBKRClient(IBKR_CONFIG)
    cache = LocalDataCache(CACHE_DIR)
    
    end_date = datetime.now()
    
    # Download daily bars
    try:
        bars = client.get_historical_bars(
            symbol=ticker,
            end_date=end_date.strftime("%Y%m%d"),
            duration=f"{days_back} D",
            bar_size="1 day",
        )
        
        # Convert to DataFrame format and cache
        cache.store_historical_data(ticker, bars, data_type="daily")
        print(f"✓ Cached {len(bars)} daily bars for {ticker}")
        
    except Exception as e:
        print(f"✗ Error downloading {ticker}: {e}")

def main():
    print("=" * 60)
    print("IBKR Historical Data Downloader")
    print("=" * 60)
    
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    
    for ticker in TICKERS:
        download_ticker_data(ticker, days_back=365)
    
    print("\n" + "=" * 60)
    print("Download complete!")
    print(f"Data cached at: {CACHE_DIR}")
    print("=" * 60)

if __name__ == "__main__":
    main()
```

Run it:
```bash
python download_ibkr_data.py
```

---

## Local Data Persistence

### Architecture

```
~/.tradingagents/
└── data_cache/
    ├── AAPL/
    │   ├── daily_20260101_20261231.csv
    │   ├── metadata.json
    │   └── cache_manifest.json
    ├── NVDA/
    │   └── ...
    └── cache_config.json
```

### Configuration

Add to `default_config.py` or `.env`:

```python
# Local data caching
"use_local_data_cache": True,
"data_cache_dir": "~/.tradingagents/data_cache",
"cache_ttl_days": 7,  # Refresh cache if older than 7 days
"data_download_retries": 3,
```

### API

```python
from tradingagents.dataflows.local_cache import LocalDataCache

cache = LocalDataCache(cache_dir="~/.tradingagents/data_cache")

# Store data
cache.store_historical_data(
    ticker="AAPL",
    data=bars_dataframe,
    data_type="daily",  # or "minute", "hourly"
    start_date="2025-01-01",
    end_date="2026-01-01",
)

# Retrieve cached data
bars = cache.get_historical_data(
    ticker="AAPL",
    data_type="daily",
    start_date="2025-06-01",
    end_date="2025-12-31",
)

# Check if fresh
is_fresh = cache.is_cache_fresh(ticker="AAPL", max_age_days=7)

# Clear old data
cache.cleanup_old_data(older_than_days=30)
```

---

## Running Backtests

### 1. Setup Backtesting Configuration

Add to `.env`:

```bash
# Backtesting Configuration
TRADINGAGENTS_BACKTEST_MODE=true
TRADINGAGENTS_BACKTEST_START_DATE=2025-01-01
TRADINGAGENTS_BACKTEST_END_DATE=2025-12-31
TRADINGAGENTS_BACKTEST_INITIAL_CAPITAL=100000
TRADINGAGENTS_BACKTEST_COMMISSION_RATE=0.001  # 0.1%
TRADINGAGENTS_BACKTEST_SLIPPAGE_BPS=10  # 10 basis points
```

### 2. Backtesting via Python

```python
from tradingagents.backtesting import BacktestEngine, BacktestConfig
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG
from datetime import datetime, timedelta

# Configure backtest
backtest_config = BacktestConfig(
    start_date=datetime(2025, 1, 1),
    end_date=datetime(2025, 12, 31),
    initial_capital=100000,
    commission_rate=0.001,  # 0.1%
    slippage_bps=10,  # 10 basis points
    use_local_cache=True,
)

# Create backtester
backtest_engine = BacktestEngine(
    ta_graph=TradingAgentsGraph(config=DEFAULT_CONFIG),
    backtest_config=backtest_config,
    tickers=["AAPL", "NVDA", "MSFT"],
)

# Run backtest
results = backtest_engine.run()

# Print results
print(results.summary())
print(results.metrics())
backtest_engine.plot_equity_curve()
```

### 3. Backtesting via CLI

```bash
# Interactive CLI backtest
tradingagents backtest \
  --start-date 2025-01-01 \
  --end-date 2025-12-31 \
  --initial-capital 100000 \
  --tickers AAPL NVDA MSFT

# Or use config file
tradingagents backtest --config backtest_config.json
```

### 4. Backtest Configuration File

Create `backtest_config.json`:

```json
{
  "mode": "backtest",
  "start_date": "2025-01-01",
  "end_date": "2025-12-31",
  "initial_capital": 100000,
  "commission_rate": 0.001,
  "slippage_bps": 10,
  "tickers": [
    "AAPL",
    "NVDA",
    "MSFT",
    "TSLA",
    "SPY"
  ],
  "llm_config": {
    "llm_provider": "openai",
    "deep_think_llm": "gpt-4",
    "quick_think_llm": "gpt-4-mini"
  },
  "backtesting": {
    "use_local_cache": true,
    "cache_dir": "~/.tradingagents/data_cache",
    "rebalance_frequency": "weekly",
    "max_position_size": 0.1,
    "stop_loss_pct": 0.05
  }
}
```

### 5. Backtest Results

```python
# Metrics returned
{
    "total_return": 0.25,  # 25% return
    "annual_return": 0.18,  # Annualized
    "sharpe_ratio": 1.5,
    "max_drawdown": -0.12,  # -12%
    "win_rate": 0.62,  # 62% of trades
    "total_trades": 42,
    "winning_trades": 26,
    "losing_trades": 16,
    "avg_win": 2150.50,
    "avg_loss": -950.25,
    "profit_factor": 1.8,
    "equity_peak": 125000,
    "final_value": 125000,
    "total_fees": 1250,
    "slippage_cost": 500,
}
```

---

## Troubleshooting

### Connection Issues

**Error: "Could not connect to IBKR"**

1. Verify TWS/IB Gateway is running
2. Check port is correct (7497 for TWS paper, 4002 for Gateway paper)
3. Verify API is enabled in settings
4. Try connecting from another machine to check firewall
5. Increase timeout:
   ```bash
   TRADINGAGENTS_IBKR_TIMEOUT=30
   ```

**Error: "No managed accounts found"**

1. Your account may not be fully initialized
2. Restart TWS/IB Gateway
3. Explicitly set account ID:
   ```bash
   TRADINGAGENTS_IBKR_ACCOUNT=DU12345678
   ```

### Data Issues

**Cached data is stale**

Clear cache:
```bash
rm -rf ~/.tradingagents/data_cache
```

Or set TTL:
```bash
TRADINGAGENTS_CACHE_TTL_DAYS=3
```

**Missing historical data for ticker**

Download fresh:
```python
from tradingagents.brokers.ibkr_client import IBKRClient, IBKRConfig

client = IBKRClient(IBKRConfig())
bars = client.get_historical_bars("AAPL", "20260101", duration="1 Y")
```

### Backtest Issues

**Backtest runs very slowly**

1. Use local cache (`TRADINGAGENTS_USE_LOCAL_DATA_CACHE=true`)
2. Reduce date range
3. Use fewer tickers
4. Set `llm_max_retries=1` to fail faster on API errors

**Insufficient historical data**

Download more data before backtesting:
```bash
TRADINGAGENTS_DATA_RETENTION_DAYS=730  # 2 years
```

### Rate Limiting

If hitting IBKR rate limits:

```bash
TRADINGAGENTS_IBKR_DATA_DOWNLOAD_DELAY=0.1  # 100ms between requests
TRADINGAGENTS_LLM_MAX_RETRIES=5  # More retries for API calls
```

---

## Advanced: Custom Broker Integration

### Adding Another Broker

Create `tradingagents/brokers/your_broker.py`:

```python
from abc import ABC, abstractmethod
from typing import Any, list

class BrokerClient(ABC):
    @abstractmethod
    def get_account_summary(self) -> dict[str, Any]:
        """Return account balance, equity, etc."""
        pass
    
    @abstractmethod
    def get_positions(self) -> list[dict]:
        """Return list of open positions."""
        pass
    
    @abstractmethod
    def get_historical_bars(self, symbol: str, end_date: str) -> list[Any]:
        """Return historical OHLCV data."""
        pass
    
    @abstractmethod
    def place_order(self, symbol: str, action: str, quantity: int) -> dict:
        """Submit and return order status."""
        pass
```

Then register in `tradingagents/brokers/execution.py`:

```python
BROKER_CLIENTS = {
    "ibkr": IBKRClient,
    "your_broker": YourBrokerClient,
    "alpaca": AlpacaClient,
}
```

---

## Quick Reference

| Task | Command |
|------|---------|
| Download IBKR data | `python download_ibkr_data.py` |
| Run backtest | `tradingagents backtest --start-date 2025-01-01` |
| Check cache status | `python -c "from tradingagents.dataflows.local_cache import LocalDataCache; LocalDataCache().status()"` |
| Clear all caches | `rm -rf ~/.tradingagents/data_cache` |
| Enable offline mode | `TRADINGAGENTS_USE_LOCAL_DATA_CACHE=true` |

---

**Last Updated**: 2026-01-15  
**Version**: 1.0
