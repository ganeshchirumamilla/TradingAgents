# TradingAgents Backtest & Analysis Skill

**Purpose:** Run strategy backtests and analyze results with minimal output  
**Tokens Saved:** ~60% vs detailed reporting  
**Execution Time:** 5-15 minutes

---

## Quick Execution

### Step 1: Verify Prerequisites (1 min)

```bash
cd C:\Trading\TradingAgents

# Check Redis cache populated
redis-cli -h localhost -p 6379 DBSIZE
# Must be > 30000

# Check PostgreSQL has data
psql -h localhost -p 5433 -U postgres -d postgres -c "SELECT count(*) FROM historical_data_daily"
# Must be > 100
```

### Step 2: Run All Backtests (5-15 min)

```bash
python scripts/backtest_all_strategies.py
```

**Monitor progress:**
- Watch for: "Completed: X/28 backtests"
- Terminal shows live progress
- Don't interrupt (let complete)

### Step 3: Extract Results (1 min)

```bash
# View top performers
python << 'EOF'
import json

with open('reports/backtest_all_strategies_report.json', 'r') as f:
    report = json.load(f)

print("\n=== TOP 5 STRATEGIES ===\n")
for i, result in enumerate(report['top_results'][:5], 1):
    print(f"{i}. {result['strategy']:30} {result['ticker']:12} | "
          f"Trades: {result['trades']:4} | "
          f"Win%: {result['win_rate']:6.2f}% | "
          f"P&L: ${result['pnl']:7.2f} | "
          f"Return: {result['return']:+6.2f}%\n")

print(f"Total Combinations: {report['total_combinations']}")
print(f"Profitable: {report['profitable_combinations']}/{report['total_combinations']}")
EOF
```

### Step 4: Save Results

```bash
# Results already saved to:
# - reports/backtest_all_strategies_report.json (full data)
# - reports/backtest_results.csv (spreadsheet)
# - reports/backtest_results.html (visual)

echo "Results saved to reports/ folder"
ls -la reports/backtest*.* | tail -5
```

---

## Common Scenarios

### Scenario 1: Get Top Performer

```bash
python << 'EOF'
import json

with open('reports/backtest_all_strategies_report.json', 'r') as f:
    data = json.load(f)

top = data['top_results'][0]
print(f"\nBEST STRATEGY: {top['strategy']}")
print(f"Ticker/Timeframe: {top['ticker']}")
print(f"Win Rate: {top['win_rate']:.2f}%")
print(f"P&L: ${top['pnl']:.2f}")
print(f"Return: {top['return']:+.2f}%")
print(f"Trades: {top['trades']}")
EOF
```

### Scenario 2: Compare Strategy Performance

```bash
python << 'EOF'
import json
import pandas as pd

with open('reports/backtest_all_strategies_report.json', 'r') as f:
    data = json.load(f)

# Load all results
results = pd.DataFrame(data['results'])

# Group by strategy
strategy_summary = results.groupby('strategy').agg({
    'pnl': ['mean', 'max', 'min'],
    'return': 'mean',
    'win_rate': 'mean',
    'trades': 'sum'
}).round(2)

print("\n=== STRATEGY SUMMARY ===\n")
print(strategy_summary)
EOF
```

### Scenario 3: Filter by Profitability

```bash
python << 'EOF'
import json
import pandas as pd

with open('reports/backtest_all_strategies_report.json', 'r') as f:
    data = json.load(f)

results = pd.DataFrame(data['results'])

# Show only profitable combinations
profitable = results[results['pnl'] > 0].sort_values('pnl', ascending=False)

print(f"\n=== PROFITABLE COMBINATIONS ({len(profitable)}) ===\n")
print(profitable[['strategy', 'ticker', 'pnl', 'return', 'win_rate']].head(10).to_string())

print(f"\nAverage P&L: ${profitable['pnl'].mean():.2f}")
print(f"Total Profit: ${profitable['pnl'].sum():.2f}")
EOF
```

---

## Performance Metrics

| Metric | Value | Notes |
|--------|-------|-------|
| Execution Time | 5-15 min | Depends on data size |
| Strategies Tested | 7 | Momentum, RSI, MACD, etc |
| Ticker×Timeframe Combos | 28 | 7 strategies × 4 timeframes |
| Success Rate | ~100% | All combinations complete |
| Profitability Rate | 100% | All combinations are positive |

---

## Output Locations

```
reports/
├── backtest_all_strategies_report.json  (Full results, detailed)
├── backtest_results.csv                 (Spreadsheet format)
└── backtest_results.html               (Interactive HTML)
```

**Key fields in JSON:**
```json
{
  "results": [
    {
      "strategy": "MeanReversionRSI",
      "ticker": "AAPL_5min",
      "trades": 15,
      "win_rate": 100.0,
      "pnl": 105.92,
      "return": 1.06
    }
  ],
  "top_results": [...top 10...],
  "total_combinations": 28,
  "profitable_combinations": 28
}
```

---

## Token-Efficient Responses

### For Minimal Output (2-3 tokens):

```bash
# Just show top performer
python -c "import json; d=json.load(open('reports/backtest_all_strategies_report.json')); print(d['top_results'][0]['strategy'], d['top_results'][0]['pnl'])"
```

### For Brief Summary (10-15 tokens):

```bash
# Count results only
python -c "import json; d=json.load(open('reports/backtest_all_strategies_report.json')); print(f\"Results: {d['total_combinations']} tests, {d['profitable_combinations']} profitable\")"
```

### For Detailed Analysis (50-100 tokens):

```bash
# Full comparison table
python << 'EOF'
import json
import pandas as pd

with open('reports/backtest_all_strategies_report.json', 'r') as f:
    data = json.load(f)

results = pd.DataFrame(data['results'])
by_strategy = results.groupby('strategy')['pnl'].agg(['mean', 'count'])
print(by_strategy.sort_values('mean', ascending=False))
EOF
```

---

## When to Use

✅ **Use this skill when:**
- Running scheduled backtests
- Comparing multiple strategies
- Evaluating performance
- Generating reports
- Making strategy decisions

❌ **Don't use when:**
- Tweaking strategy parameters
- Debugging algorithm issues
- Single strategy deep-dive

---

## Quick Checklist

```
Before Running:
☐ PostgreSQL running (5433)
☐ Redis cache populated (>30K keys)
☐ reports/ folder exists
☐ IB Gateway not needed

During Run:
☐ Don't interrupt (let complete)
☐ Monitor progress output
☐ Check for errors in log

After Run:
☐ Check results saved to reports/
☐ Extract top performers
☐ Document decisions made
```

---

**Use this skill for regular backtesting cycles and performance analysis.**
