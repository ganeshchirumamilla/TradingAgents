# Backtest Results Storage Locations

## Overview

Backtest results are stored in **3 key locations**:

```
🖥️ Working Directory (C:\Trading\TradingAgents)
   ├── backtest_results_AAPL_20260905_*.csv
   ├── backtest_results_NVDA_20260905_*.csv
   ├── backtest_results_MSFT_20260905_*.csv
   └── backtest_results_SPY_20260905_*.csv

💾 Data Cache (~/.tradingagents/data_cache/)
   ├── AAPL/daily_all_current.csv (365 days)
   ├── NVDA/daily_all_current.csv (365 days)
   ├── MSFT/daily_all_current.csv (365 days)
   └── SPY/daily_all_current.csv (365 days)

🔄 Memory (Python Runtime)
   └── Results dictionary with equity curves and signals
```

---

## 1. CSV Export Files (Trade Results)

### Location
```
C:\Trading\TradingAgents\backtest_results_<TICKER>_<TIMESTAMP>.csv
```

### Format
```
backtest_results_NVDA_20260905_182750.csv
backtest_results_MSFT_20260905_182802.csv
backtest_results_SPY_20260905_182814.csv
```

### File Contents
Each CSV contains every trade executed:

| Column | Meaning |
|--------|---------|
| `ticker` | Stock symbol |
| `entry_date` | When position opened |
| `exit_date` | When position closed |
| `entry_price` | Entry price per share |
| `exit_price` | Exit price per share |
| `shares` | Number of shares traded |
| `pnl` | Profit/Loss in dollars |
| `pnl_pct` | Profit/Loss percentage |
| `reason` | Take Profit / Stop Loss / Signal / End |

### Example
```csv
ticker,entry_date,exit_date,entry_price,exit_price,shares,pnl,pnl_pct,reason
NVDA,2024-05-20,2024-05-23,94.78,103.799,38,342.72,0.0952,Take Profit
NVDA,2024-09-06,2024-09-09,102.83,106.47,28,101.92,0.0354,Take Profit
MSFT,2024-06-03,2024-06-06,429.17,417.13,10,-120.40,-0.0281,Stop Loss
SPY,2024-06-04,2024-06-07,552.08,540.36,8,-93.76,-0.0170,Stop Loss
```

### How to Read Results
```bash
# View results for NVDA
cat backtest_results_NVDA_20260905_182750.csv

# View results for all tickers
cat backtest_results_*.csv

# Import into Python
import pandas as pd
results = pd.read_csv("backtest_results_NVDA_20260905_182750.csv")
print(results)
print(f"Total P&L: ${results['pnl'].sum():.2f}")
print(f"Win Rate: {(results['pnl'] > 0).mean():.2%}")
```

---

## 2. Local Data Cache (Historical Data)

### Location
```
C:\Users\vinod\.tradingagents\data_cache\
```

or via environment:
```bash
$env:TRADINGAGENTS_LOCAL_DATA_CACHE_DIR  # PowerShell
$TRADINGAGENTS_LOCAL_DATA_CACHE_DIR      # bash
```

### Structure
```
~/.tradingagents/data_cache/
├── AAPL/
│   └── daily_all_current.csv (365 bars)
├── NVDA/
│   └── daily_all_current.csv (365 bars)
├── MSFT/
│   └── daily_all_current.csv (365 bars)
├── SPY/
│   └── daily_all_current.csv (365 bars)
└── cache_manifest.json (metadata)
```

### Cache Manifest
Shows what's cached and when:
```json
{
  "tickers": {
    "NVDA": {
      "daily": {
        "filename": "daily_all_current.csv",
        "rows": 365,
        "start_date": "2023-09-05",
        "end_date": "2024-09-05",
        "cached_at": "2026-09-05T18:27:39.365000"
      }
    }
  },
  "last_updated": "2026-09-05T18:28:14.140000"
}
```

### View Cache Content
```bash
# Check cache status
python -c "
from tradingagents.dataflows.local_cache import LocalDataCache
cache = LocalDataCache()
print(cache.status())
"

# View cached NVDA data
head -20 ~/.tradingagents/data_cache/NVDA/daily_all_current.csv

# Load cache into Python
import pandas as pd
nvda = pd.read_csv("~/.tradingagents/data_cache/NVDA/daily_all_current.csv")
print(nvda.head())
print(f"Records: {len(nvda)}")
```

---

## 3. Runtime Results (In-Memory)

### What's Stored
When you run the backtest, results are stored in memory:

```python
from strategies.ma_rsi_strategy import MARSIStrategy

strategy = MARSIStrategy()
results = strategy.backtest(df, "NVDA")

# Dictionary with:
results = {
    "ticker": "NVDA",
    "initial_capital": 100000,
    "final_capital": 90862.81,
    "total_return": -0.0914,
    "total_trades": 3,
    "winning_trades": 3,
    "losing_trades": 0,
    "win_rate": 1.0,
    "avg_win": 184.21,
    "avg_loss": 0.0,
    "max_profit": 342.72,
    "max_loss": -101.92,
    "trades": [  # List of all trades
        {
            "ticker": "NVDA",
            "entry_date": datetime(...),
            "exit_date": datetime(...),
            "entry_price": 94.78,
            "exit_price": 103.799,
            "pnl": 342.72,
            "reason": "Take Profit"
        },
        # ... more trades
    ],
    "equity_curve": pd.DataFrame([  # Daily equity progression
        {"date": ..., "equity": 100000, "cash": 100000},
        {"date": ..., "equity": 99500, "cash": 94500},
        # ... daily progression
    ]),
    "signals": [  # All buy/sell signals
        {
            "date": datetime(...),
            "type": "BUY",
            "price": 94.78,
            "sma_short": 95.2,
            "sma_long": 105.3,
            "rsi": 32
        },
        # ... more signals
    ]
}
```

### Access in Code
```python
# Get specific metrics
print(f"Return: {results['total_return']:.2%}")
print(f"Win Rate: {results['win_rate']:.2%}")
print(f"Avg Win: ${results['avg_win']:.2f}")

# Access equity curve
equity = results['equity_curve']
print(f"Peak Equity: ${equity['equity'].max():,.2f}")
print(f"Final Equity: ${equity['equity'].iloc[-1]:,.2f}")

# Access trades
for trade in results['trades']:
    print(f"{trade['ticker']}: {trade['entry_price']:.2f} → {trade['exit_price']:.2f}")

# Access signals
for signal in results['signals']:
    print(f"{signal['date']}: {signal['type']} @ {signal['price']:.2f} (RSI={signal['rsi']:.1f})")
```

---

## Complete File Listing

### As of 2026-09-05 18:28:14 UTC

#### Backtest Results (Trades)
```
-rw-r--r--  353 bytes  backtest_results_NVDA_20260905_182750.csv
-rw-r--r--  267 bytes  backtest_results_MSFT_20260905_182802.csv
-rw-r--r--  172 bytes  backtest_results_SPY_20260905_182814.csv
(AAPL: 0 trades, no file)
```

#### Cached Data
```
~/.tradingagents/data_cache/
├── AAPL/daily_all_current.csv           (365 bars, ~24KB)
├── MSFT/daily_all_current.csv           (365 bars, ~24KB)
├── NVDA/daily_all_current.csv           (365 bars, ~24KB)
├── SPY/daily_all_current.csv            (365 bars, ~24KB)
└── cache_manifest.json                  (1.1KB metadata)
```

---

## How to Analyze Results

### Option 1: Command Line
```bash
# View trades
cat backtest_results_NVDA_*.csv

# Count trades
wc -l backtest_results_*.csv

# View only winning trades
grep -v "Stop Loss" backtest_results_NVDA_*.csv
```

### Option 2: Python
```python
import pandas as pd

# Load results
results_df = pd.read_csv("backtest_results_NVDA_20260905_182750.csv")

# Basic stats
print(f"Total Trades: {len(results_df)}")
print(f"Winners: {(results_df['pnl'] > 0).sum()}")
print(f"Losers: {(results_df['pnl'] < 0).sum()}")
print(f"Win Rate: {(results_df['pnl'] > 0).mean():.2%}")

# Profitability
print(f"\nTotal P&L: ${results_df['pnl'].sum():.2f}")
print(f"Avg Win: ${results_df[results_df['pnl'] > 0]['pnl'].mean():.2f}")
print(f"Avg Loss: ${results_df[results_df['pnl'] < 0]['pnl'].mean():.2f}")

# Best/worst trade
print(f"\nBest Trade: ${results_df['pnl'].max():.2f}")
print(f"Worst Trade: ${results_df['pnl'].min():.2f}")
```

### Option 3: Excel/Sheets
```python
# Export to Excel
results_df.to_excel("backtest_results.xlsx", index=False)

# Or to CSV for import
results_df.to_csv("backtest_results_analysis.csv", index=False)
```

---

## Auto-Cleanup

Results are NOT automatically deleted. To clean up old results:

```bash
# Delete results older than 30 days
find . -name "backtest_results_*.csv" -mtime +30 -delete

# Or manually delete specific files
rm backtest_results_NVDA_20260905_*.csv
```

To auto-cleanup cache:
```python
from tradingagents.dataflows.local_cache import LocalDataCache

cache = LocalDataCache()
# Delete data older than 30 days
deleted = cache.cleanup_old_data(older_than_days=30)
print(f"Deleted {deleted} files")
```

---

## Environment Variables

Results locations can be configured via environment:

```bash
# Set custom cache directory
TRADINGAGENTS_LOCAL_DATA_CACHE_DIR=/custom/path/to/cache

# Results always go to current working directory
# (Change with `cd` before running backtest)
```

---

## Quick Access

### Get all backtest results
```bash
ls -lh backtest_results_*.csv
```

### Get cache status
```bash
python -c "
from tradingagents.dataflows.local_cache import LocalDataCache
cache = LocalDataCache()
print(cache.status())
"
```

### Get latest results
```bash
ls -lt backtest_results_*.csv | head -1
```

### Get all tickers cached
```bash
ls ~/.tradingagents/data_cache/
```

---

## Summary

| Type | Location | Format | Lifetime |
|------|----------|--------|----------|
| **Trade Results** | `C:\Trading\TradingAgents\backtest_results_*.csv` | CSV | Persist (manual delete) |
| **Historical Data** | `~/.tradingagents/data_cache/<TICKER>/` | CSV | TTL configured (7 days default) |
| **Runtime Data** | Python memory | Dictionary | Session only |
| **Cache Metadata** | `~/.tradingagents/data_cache/cache_manifest.json` | JSON | Updated on each download |

---

**Created**: 2026-09-05  
**Files Generated**: 3 CSV files  
**Data Cached**: 1.1 MB  
**Ready to Analyze**: ✅ Yes
