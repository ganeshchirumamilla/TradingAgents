# IBKR & Backtesting Quick Start Guide

## 🚀 5-Minute Setup

### Step 1: Install IBKR Support
```bash
pip install "tradingagents[ibkr]"
```

### Step 2: Configure IBKR Credentials

**Copy and edit `.env`:**
```bash
cp .env.example .env
```

**Edit `.env` and add:**
```bash
# IBKR Connection Settings
TRADINGAGENTS_IBKR_ENABLED=true
TRADINGAGENTS_IBKR_PORT=7497          # TWS paper trading
TRADINGAGENTS_IBKR_HOST=127.0.0.1
TRADINGAGENTS_IBKR_ACCOUNT=DU12345678 # Find in TWS
TRADINGAGENTS_IBKR_PAPER=true

# Data Caching
TRADINGAGENTS_USE_LOCAL_DATA_CACHE=true
TRADINGAGENTS_IBKR_DATA_DOWNLOAD_ENABLED=true
```

### Step 3: Enable API in TWS/IB Gateway

1. Open **TWS** or **IB Gateway**
2. Go to **File → Global Configuration → API → Settings**
3. ✓ Check **"Enable ActiveX and Socket Clients"**
4. Click **OK**

### Step 4: Verify Connection

```python
from tradingagents.brokers.ibkr_client import IBKRClient, IBKRConfig

config = IBKRConfig(port=7497)  # Adjust port if needed
client = IBKRClient(config)

try:
    summary = client.get_account_summary()
    print(f"✓ Connected!")
    print(f"Account: {summary.get('account')}")
    print(f"Balance: ${summary.get('NetLiquidation')}")
except Exception as e:
    print(f"✗ Connection failed: {e}")
    print("Make sure TWS/IB Gateway is running with API enabled!")
```

---

## 📥 Download Historical Data

### Option 1: Command Line (Recommended)

```bash
# Download 1 year of data for multiple tickers
python scripts/download_ibkr_data.py \
  --tickers AAPL NVDA MSFT TSLA SPY \
  --days 365 \
  --cache-dir ~/.tradingagents/data_cache
```

### Option 2: Python Script

```python
from tradingagents.brokers.ibkr_client import IBKRClient, IBKRConfig
from tradingagents.dataflows.local_cache import LocalDataCache
from datetime import datetime

# Connect to IBKR
config = IBKRConfig(port=7497)
client = IBKRClient(config)
cache = LocalDataCache()

# Download and cache
tickers = ["AAPL", "NVDA", "MSFT"]
for ticker in tickers:
    print(f"Downloading {ticker}...")
    bars = client.get_historical_bars(
        ticker, 
        datetime.now().strftime("%Y%m%d"),
        duration="1 Y"
    )
    cache.store_historical_data(ticker, bars)
    print(f"✓ Cached {len(bars)} bars for {ticker}")

# Check cache status
print(cache.status())
```

### Option 3: Check Cached Data

```python
from tradingagents.dataflows.local_cache import LocalDataCache

cache = LocalDataCache()
print(cache.status())

# Get cached data
aapl_data = cache.get_historical_data("AAPL", "daily")
print(f"AAPL: {len(aapl_data)} bars")
```

---

## 🎯 Run Backtests

### Option 1: Interactive CLI

```bash
tradingagents backtest
```

You'll be prompted for:
- Start date (YYYY-MM-DD)
- End date (YYYY-MM-DD)
- Tickers (comma-separated)
- Initial capital ($)

### Option 2: Configuration File

Create `backtest_config.json`:

```json
{
  "mode": "backtest",
  "start_date": "2025-01-01",
  "end_date": "2025-12-31",
  "initial_capital": 100000,
  "commission_rate": 0.001,
  "slippage_bps": 10,
  "tickers": ["AAPL", "NVDA", "MSFT", "TSLA"],
  "llm_config": {
    "llm_provider": "openai",
    "deep_think_llm": "gpt-4",
    "quick_think_llm": "gpt-4-mini"
  }
}
```

Run:
```bash
tradingagents backtest --config backtest_config.json
```

### Option 3: Python

```python
from tradingagents.backtesting import BacktestEngine, BacktestConfig
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG
from datetime import datetime

# Configure
config = BacktestConfig(
    start_date=datetime(2025, 1, 1),
    end_date=datetime(2025, 12, 31),
    initial_capital=100000,
    commission_rate=0.001,
    use_local_cache=True,
)

# Run
ta_graph = TradingAgentsGraph(config=DEFAULT_CONFIG)
engine = BacktestEngine(ta_graph, config, tickers=["AAPL", "NVDA", "MSFT"])
results = engine.run()

# Results
print(results.summary())
print(results.metrics())
```

---

## 📊 Backtest Results

After running a backtest, you'll get:

```
╔════════════════════════════════════════════════════════╗
║           BACKTEST RESULTS SUMMARY                    ║
╚════════════════════════════════════════════════════════╝

Period:              2025-01-01 to 2025-12-31
Initial Capital:     $100,000.00
Final Value:         $125,000.00

Returns:
  Total Return:      25.00%
  Annual Return:     24.50%
  Max Drawdown:      -8.50%

Risk Metrics:
  Sharpe Ratio:      1.50
  Sortino Ratio:     2.10
  Calmar Ratio:      2.88

Trading Activity:
  Total Trades:      42
  Winning Trades:    26
  Losing Trades:     16
  Win Rate:          61.9%

Trade Statistics:
  Avg Win:           $2,150.50
  Avg Loss:          -$950.25
  Profit Factor:     1.80

Costs:
  Total Commission:  $1,250.00
  Total Slippage:    $500.00
```

Export results:
```python
df = results.to_dataframe()
df.to_csv("backtest_results.csv")

# Plot
results.plot_equity_curve(save_path="equity_curve.png")
```

---

## 🔧 Configuration Reference

### IBKR Settings

| Env Variable | Default | Description |
|---|---|---|
| `TRADINGAGENTS_IBKR_ENABLED` | `false` | Enable IBKR connection |
| `TRADINGAGENTS_IBKR_HOST` | `127.0.0.1` | IBKR host (localhost) |
| `TRADINGAGENTS_IBKR_PORT` | `7497` | Port (7497=TWS paper, 7496=TWS live, 4002=Gateway paper, 4001=Gateway live) |
| `TRADINGAGENTS_IBKR_CLIENT_ID` | `1` | Client ID for connection |
| `TRADINGAGENTS_IBKR_ACCOUNT` | `None` | Account ID (auto-detected if not set) |
| `TRADINGAGENTS_IBKR_PAPER` | `true` | Paper trading mode |
| `TRADINGAGENTS_IBKR_AUTO_EXECUTE` | `false` | Place real orders (requires explicit opt-in) |

### Data Caching

| Env Variable | Default | Description |
|---|---|---|
| `TRADINGAGENTS_USE_LOCAL_DATA_CACHE` | `false` | Enable local caching |
| `TRADINGAGENTS_LOCAL_DATA_CACHE_DIR` | `~/.tradingagents/data_cache` | Cache directory |
| `TRADINGAGENTS_CACHE_TTL_DAYS` | `7` | Cache freshness (days) |
| `TRADINGAGENTS_IBKR_DATA_DOWNLOAD_ENABLED` | `false` | Enable IBKR downloads |

### Backtesting

| Env Variable | Default | Description |
|---|---|---|
| `TRADINGAGENTS_BACKTEST_MODE` | `false` | Enable backtest mode |
| `TRADINGAGENTS_BACKTEST_START_DATE` | `None` | Start date (YYYY-MM-DD) |
| `TRADINGAGENTS_BACKTEST_END_DATE` | `None` | End date (YYYY-MM-DD) |
| `TRADINGAGENTS_BACKTEST_INITIAL_CAPITAL` | `100000` | Starting capital ($) |
| `TRADINGAGENTS_BACKTEST_COMMISSION_RATE` | `0.001` | Commission (0.1%) |
| `TRADINGAGENTS_BACKTEST_SLIPPAGE_BPS` | `10` | Slippage (10 bps) |

---

## 🐛 Troubleshooting

### "Could not connect to IBKR"

✓ Make sure TWS/IB Gateway is running
✓ API is enabled (File → Global Configuration → API → Settings)
✓ Port is correct (7497 for TWS paper)
✓ Try restarting TWS/IB Gateway

### "No managed accounts found"

✓ Restart TWS/IB Gateway
✓ Explicitly set account ID:
```bash
TRADINGAGENTS_IBKR_ACCOUNT=DU12345678
```

### "No cached data for ticker"

✓ Download first:
```bash
python scripts/download_ibkr_data.py --tickers AAPL
```

✓ Or disable cache:
```bash
TRADINGAGENTS_USE_LOCAL_DATA_CACHE=false
```

### Slow backtest

✓ Use local cache: `TRADINGAGENTS_USE_LOCAL_DATA_CACHE=true`
✓ Reduce date range
✓ Use fewer tickers
✓ Set `TRADINGAGENTS_LLM_MAX_RETRIES=1` to fail faster

---

## 📚 Full Documentation

- **Technical Flow**: See `TECHNICAL_FLOW.md`
- **IBKR Setup**: See `IBKR_SETUP_AND_BACKTESTING.md`
- **Local Cache API**: See `tradingagents/dataflows/local_cache.py`
- **Backtest Engine**: See `tradingagents/backtesting.py`

---

## 🎓 Examples

### Example 1: Download 1 Year of Data

```bash
python scripts/download_ibkr_data.py \
  --tickers AAPL NVDA MSFT TSLA SPY \
  --days 365
```

### Example 2: Backtest with Cached Data

```python
from tradingagents.backtesting import BacktestEngine, BacktestConfig
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG
from datetime import datetime

config = BacktestConfig(
    start_date=datetime(2025, 1, 1),
    end_date=datetime(2025, 12, 31),
    initial_capital=50000,
    commission_rate=0.001,
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

### Example 3: Live Trading with IBKR

```bash
# Enable IBKR in .env
TRADINGAGENTS_IBKR_ENABLED=true
TRADINGAGENTS_IBKR_AUTO_EXECUTE=false  # Start with paper trading

# Run analysis
tradingagents analyze
```

When ready for live trading:
```bash
# Set all three flags
TRADINGAGENTS_IBKR_ENABLED=true
TRADINGAGENTS_IBKR_AUTO_EXECUTE=true
TRADINGAGENTS_IBKR_PAPER=false
TRADINGAGENTS_IBKR_CONFIRM_LIVE=true

tradingagents analyze
```

---

## ✅ Verification Checklist

- [ ] `pip install "tradingagents[ibkr]"` completed
- [ ] `.env` configured with IBKR settings
- [ ] TWS/IB Gateway running with API enabled
- [ ] Test connection successful (see Step 4)
- [ ] Historical data downloaded: `python scripts/download_ibkr_data.py`
- [ ] Cache status verified: `cache.status()`
- [ ] Sample backtest ran: `tradingagents backtest`

---

**Need Help?**
- See full setup guide: `IBKR_SETUP_AND_BACKTESTING.md`
- Check technical architecture: `TECHNICAL_FLOW.md`
- Report issues: https://github.com/TauricResearch/TradingAgents/issues
