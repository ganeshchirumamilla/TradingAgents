# 🚀 START HERE - IBKR & Backtesting Setup

Welcome! I've implemented a complete IBKR integration with backtesting. Here's your roadmap:

---

## 📍 Where Are You?

### ❌ If you haven't read anything yet:
👉 **Read this file** (2 minutes)  
👉 Then read `IBKR_QUICKSTART.md` (5 minutes)  
👉 Then follow the 4-step setup

### ✅ If you've read docs:
👉 Run the example: `python examples/ibkr_backtest_example.py`  
👉 Download data: `python scripts/download_ibkr_data.py`  
👉 Create your `.env` file

### 🎓 If you want details:
👉 Read `IBKR_SETUP_AND_BACKTESTING.md` (complete reference)  
👉 Review `IMPLEMENTATION_SUMMARY.md` (technical overview)  
👉 Check code in `tradingagents/dataflows/local_cache.py`

---

## ⚡ 5-Minute Quick Start

### Step 1: Install
```bash
pip install "tradingagents[ibkr]"
```

### Step 2: Configure (Create `.env`)
```bash
cp .env.example .env

# Edit .env and add:
TRADINGAGENTS_IBKR_ENABLED=true
TRADINGAGENTS_IBKR_PORT=7497
TRADINGAGENTS_IBKR_ACCOUNT=DU12345678  # Your account ID
TRADINGAGENTS_IBKR_PAPER=true
TRADINGAGENTS_USE_LOCAL_DATA_CACHE=true
```

### Step 3: Enable API
**In TWS or IB Gateway:**
1. File → Global Configuration → API → Settings
2. ✓ Check "Enable ActiveX and Socket Clients"
3. Click OK

### Step 4: Test Connection
```python
from tradingagents.brokers.ibkr_client import IBKRClient, IBKRConfig

client = IBKRClient(IBKRConfig())
try:
    print(client.get_account_summary())
    print("✓ Connected!")
except Exception as e:
    print(f"✗ Error: {e}")
```

---

## 🎯 Common Workflows

### 🔽 Download Historical Data

```bash
# Download 1 year of data
python scripts/download_ibkr_data.py \
  --tickers AAPL NVDA MSFT \
  --days 365
```

**Or in Python:**
```python
from tradingagents.brokers.ibkr_client import IBKRClient, IBKRConfig
from tradingagents.dataflows.local_cache import LocalDataCache

client = IBKRClient(IBKRConfig())
cache = LocalDataCache()

for ticker in ["AAPL", "NVDA", "MSFT"]:
    bars = client.get_historical_bars(ticker, "20260101", "365 D")
    cache.store_historical_data(ticker, bars)
    print(f"✓ Cached {len(bars)} bars for {ticker}")
```

### 📊 Run Backtest

```bash
# Interactive backtest
python examples/ibkr_backtest_example.py
```

**Or in Python:**
```python
from tradingagents.backtesting import BacktestEngine, BacktestConfig
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG
from datetime import datetime

config = BacktestConfig(
    start_date=datetime(2025, 1, 1),
    end_date=datetime(2025, 12, 31),
    initial_capital=100000,
    use_local_cache=True,
)

engine = BacktestEngine(
    TradingAgentsGraph(config=DEFAULT_CONFIG),
    config,
    tickers=["AAPL", "NVDA", "MSFT"],
)

results = engine.run()
print(results.summary())
```

### 📈 Check Cached Data

```python
from tradingagents.dataflows.local_cache import LocalDataCache

cache = LocalDataCache()
print(cache.status())

# Get specific data
data = cache.get_historical_data("AAPL", start_date="2025-06-01")
print(f"AAPL: {len(data)} bars")
```

### 💹 Live Trading (Paper)

```bash
# Verify setup with paper trading
tradingagents analyze
```

In `.env`:
```bash
TRADINGAGENTS_IBKR_ENABLED=true
TRADINGAGENTS_IBKR_AUTO_EXECUTE=false  # No real orders
TRADINGAGENTS_IBKR_PAPER=true          # Paper trading
```

### 🔴 Live Trading (REAL MONEY)

⚠️ **Only after you're confident!**

```bash
# Requires ALL three flags:
TRADINGAGENTS_IBKR_ENABLED=true
TRADINGAGENTS_IBKR_AUTO_EXECUTE=true
TRADINGAGENTS_IBKR_PAPER=false
TRADINGAGENTS_IBKR_CONFIRM_LIVE=true

# Then run
tradingagents analyze
```

---

## 📚 Documentation Map

### For Beginners
```
START_HERE.md (this file)
    ↓
IBKR_QUICKSTART.md (5 min)
    ↓
Run examples/ibkr_backtest_example.py
    ↓
Read IBKR_SETUP_AND_BACKTESTING.md
```

### For Developers
```
IMPLEMENTATION_SUMMARY.md
    ↓
TECHNICAL_FLOW.md
    ↓
Code: tradingagents/dataflows/local_cache.py
Code: tradingagents/backtesting.py
```

### For Reference
```
Configuration options → .env.example or default_config.py
API documentation → Docstrings in Python files
Troubleshooting → IBKR_SETUP_AND_BACKTESTING.md
```

---

## 🗂️ What Was Created

### New Code
- `tradingagents/dataflows/local_cache.py` - Cache market data locally
- `tradingagents/backtesting.py` - Run simulated trades
- `scripts/download_ibkr_data.py` - Download data from IBKR
- `examples/ibkr_backtest_example.py` - Complete working example

### New Documentation
- `IBKR_QUICKSTART.md` - 5-minute setup
- `IBKR_SETUP_AND_BACKTESTING.md` - Complete reference (400 lines)
- `IMPLEMENTATION_SUMMARY.md` - Technical overview
- `START_HERE.md` - This file

### Updated Files
- `.env.example` - Added 20 new configuration options
- `tradingagents/default_config.py` - Added backtesting configuration

---

## ✨ Key Features

### Local Data Caching
✓ Download from IBKR  
✓ Store as CSV with metadata  
✓ Automatic TTL (time-to-live)  
✓ Quick retrieval for backtesting  
✓ Works offline  

### Backtesting Engine
✓ Sharpe, Sortino, Calmar ratios  
✓ Trade-level P&L tracking  
✓ Commission & slippage modeling  
✓ Equity curve generation  
✓ Win rate & profit factor  
✓ Export to DataFrame/CSV  

### Credential Management
✓ Environment variables  
✓ .env file support  
✓ Separate opt-in for live trading  
✓ Account auto-detection  
✓ Safe defaults (paper trading)  

---

## 🔧 Configuration Quick Ref

| What | Env Variable | Default |
|-----|-----|-----|
| IBKR Enable | `TRADINGAGENTS_IBKR_ENABLED` | `false` |
| IBKR Port | `TRADINGAGENTS_IBKR_PORT` | `7497` |
| Cache Enable | `TRADINGAGENTS_USE_LOCAL_DATA_CACHE` | `false` |
| Backtest Mode | `TRADINGAGENTS_BACKTEST_MODE` | `false` |
| Initial Capital | `TRADINGAGENTS_BACKTEST_INITIAL_CAPITAL` | `100000` |

See `IBKR_QUICKSTART.md` for complete table.

---

## 🎓 Example: Complete Workflow

```python
#!/usr/bin/env python
"""Complete workflow: Download → Cache → Backtest"""

from datetime import datetime
from tradingagents.brokers.ibkr_client import IBKRClient, IBKRConfig
from tradingagents.dataflows.local_cache import LocalDataCache
from tradingagents.backtesting import BacktestEngine, BacktestConfig
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

print("=" * 60)
print("Complete Workflow Example")
print("=" * 60)

# Step 1: Connect to IBKR
print("\n1️⃣  Connecting to IBKR...")
client = IBKRClient(IBKRConfig(port=7497))
summary = client.get_account_summary()
print(f"   ✓ Account: {summary.get('account')}")

# Step 2: Download historical data
print("\n2️⃣  Downloading historical data...")
tickers = ["AAPL", "NVDA", "MSFT"]
cache = LocalDataCache()

for ticker in tickers:
    bars = client.get_historical_bars(
        ticker, 
        datetime.now().strftime("%Y%m%d"),
        "365 D"
    )
    cache.store_historical_data(ticker, bars)
    print(f"   ✓ {ticker}: {len(bars)} bars")

# Step 3: Run backtest
print("\n3️⃣  Running backtest...")
config = BacktestConfig(
    start_date=datetime(2025, 1, 1),
    end_date=datetime(2025, 12, 31),
    initial_capital=100000,
    use_local_cache=True,
)

engine = BacktestEngine(
    TradingAgentsGraph(config=DEFAULT_CONFIG),
    config,
    tickers=tickers,
)

results = engine.run()

# Step 4: Show results
print("\n4️⃣  Results:")
metrics = results.metrics()
print(f"   Total Return: {metrics['total_return']:.2%}")
print(f"   Sharpe Ratio: {metrics['sharpe_ratio']:.2f}")
print(f"   Max Drawdown: {metrics['max_drawdown']:.2%}")

print("\n" + "=" * 60)
print("✅ Complete Workflow Finished!")
print("=" * 60)
```

---

## 🆘 Troubleshooting

### Connection Failed
```
Error: "Could not connect to IBKR"

Fix:
  ✓ Start TWS or IB Gateway
  ✓ Enable API in settings
  ✓ Check TRADINGAGENTS_IBKR_PORT (7497 for TWS paper)
```

### No Data Downloaded
```
Error: "No bars returned from IBKR"

Fix:
  ✓ Make sure IBKR connection works first
  ✓ Check date format (YYYYMMDD)
  ✓ Try different ticker
  ✓ Check IBKR data subscription
```

### Slow Backtest
```
Speed Issue: Takes too long to run

Fix:
  ✓ Use local cache (faster than IBKR)
  ✓ Reduce date range
  ✓ Use fewer tickers
  ✓ Lower LLM max_retries
```

More help: See `IBKR_SETUP_AND_BACKTESTING.md`

---

## ✅ Verification Checklist

Before going live, verify:

- [ ] Python 3.10+ installed
- [ ] `pip install "tradingagents[ibkr]"` completed
- [ ] `.env` file created and configured
- [ ] TWS/IB Gateway running with API enabled
- [ ] IBKR connection test passed
- [ ] Historical data downloaded successfully
- [ ] Sample backtest ran without errors
- [ ] Backtest results look reasonable

---

## 📞 Getting Help

### Quick Questions
→ See `IBKR_QUICKSTART.md` (fast answers)

### Setup Issues
→ See `IBKR_SETUP_AND_BACKTESTING.md` (detailed guide)

### Technical Details
→ See `IMPLEMENTATION_SUMMARY.md` (how it works)

### Architecture Questions
→ See `TECHNICAL_FLOW.md` (system design)

### Need More Help
→ Check `examples/ibkr_backtest_example.py` (working code)

---

## 🎯 Next Steps

### Right Now (5 min)
1. Run the 4-step setup above
2. Test IBKR connection
3. Feel accomplished! ✅

### Next 30 Minutes
1. Download historical data
2. Run example backtest
3. Review results

### Next Few Hours
1. Read complete documentation
2. Customize backtest parameters
3. Test with your tickers

### Next Few Days
1. Run paper trading
2. Verify decisions align with real market
3. Consider live trading (⚠️ carefully!)

---

## 🎉 You're All Set!

Everything you need is implemented and ready:

✅ IBKR credentials management  
✅ Local data persistence  
✅ Backtesting engine  
✅ Complete documentation  
✅ Working examples  
✅ CLI tools  

**Now go build something amazing! 🚀**

---

## 📖 Reading Order

1. **This file** (START_HERE.md) ← You are here
2. **IBKR_QUICKSTART.md** (5 min, practical)
3. **Run example** (examples/ibkr_backtest_example.py)
4. **IBKR_SETUP_AND_BACKTESTING.md** (detailed reference)
5. **IMPLEMENTATION_SUMMARY.md** (how it works)
6. **TECHNICAL_FLOW.md** (system architecture)

---

**Last Updated**: 2026-01-15  
**Status**: ✅ Complete & Ready  
**Version**: 1.0  

**Questions?** Check the docs. Everything is documented! 📚
