# TradingAgents Operations Master Skill

**Purpose:** Quick reference for all common operations  
**Use:** When you need to run anything in TradingAgents system  
**Token Efficiency:** Map your task to the right command

---

## Task Routing

### "I need fresh data"
→ Use: `tradingagents_data_pipeline` skill  
→ Run: `python scripts/download_market_data.py AAPL`  
→ Time: 10-15 minutes

### "Run backtests"
→ Use: `tradingagents_backtest_analysis` skill  
→ Run: `python scripts/backtest_all_strategies.py`  
→ Time: 5-15 minutes

### "Check system status"
→ Use: This skill (Operations)  
→ Run: Commands below under "Health Check"

### "Database issue"
→ Use: This skill (Operations)  
→ Ref: "Troubleshooting" section below

### "First-time setup"
→ Use: SETUP_GUIDE.md (comprehensive)  
→ Quick: db/QUICK_REFERENCE.md

---

## 🏥 Health Check (30 seconds)

```bash
# Run all checks
echo "PostgreSQL..." && psql -h localhost -p 5433 -U postgres -c "SELECT 1" && \
echo "✓ PostgreSQL OK" && \
echo "" && \
echo "Redis..." && redis-cli -h localhost -p 6379 ping && \
echo "✓ Redis OK" && \
echo "" && \
echo "IB Gateway..." && nc -zv 127.0.0.1 4002 && \
echo "✓ IB Gateway OK" && \
echo "" && \
echo "Data..." && psql -h localhost -p 5433 -U postgres -d postgres -c "SELECT COUNT(*) FROM historical_data_daily" && \
echo "✓ Database populated" && \
echo "" && \
echo "Cache..." && redis-cli -h localhost -p 6379 DBSIZE && \
echo "✓ Cache populated"
```

**Expected output:**
```
✓ PostgreSQL OK
✓ Redis OK
✓ IB Gateway OK
✓ Database populated
✓ Cache populated
```

---

## 📊 Quick Status Commands

```bash
# Show data by ticker
psql -h localhost -p 5433 -U postgres -d postgres << EOF
SELECT ticker, 
       (SELECT count(*) FROM historical_data_daily WHERE ticker=t.ticker) as daily,
       (SELECT count(*) FROM historical_data_hourly WHERE ticker=t.ticker) as hourly,
       (SELECT count(*) FROM historical_data_5min WHERE ticker=t.ticker) as 5min,
       (SELECT count(*) FROM historical_data_1min WHERE ticker=t.ticker) as 1min
FROM (SELECT DISTINCT ticker FROM historical_data_daily UNION SELECT DISTINCT ticker FROM historical_data_hourly UNION SELECT DISTINCT ticker FROM historical_data_5min UNION SELECT DISTINCT ticker FROM historical_data_1min) t;
EOF

# Show cache keys
redis-cli -h localhost -p 6379 DBSIZE

# Show latest backtest
ls -lth reports/backtest*.* | head -3

# Show download logs
ls -lth ~/.tradingagents/download_logs/ | head -3
```

---

## ⚡ Quick Commands by Goal

### Download Data for Ticker
```bash
python scripts/download_market_data.py AAPL
python scripts/download_market_data.py MSFT
python scripts/download_market_data.py TSLA
```

### Update Redis Cache
```bash
redis-cli -h localhost -p 6379 --raw FLUSHDB
python scripts/load_postgres_to_redis.py
```

### Run Backtests
```bash
python scripts/backtest_all_strategies.py
```

### Clear Everything (Reset)
```bash
# Backup first!
pg_dump -h localhost -p 5433 -U postgres -d postgres > backup.sql

# Then clear
redis-cli -h localhost -p 6379 --raw FLUSHDB
psql -h localhost -p 5433 -U postgres -d postgres -c "DELETE FROM historical_data_daily; DELETE FROM historical_data_hourly; DELETE FROM historical_data_5min; DELETE FROM historical_data_1min;"
```

---

## 🔧 Troubleshooting Decision Tree

```
System not working?
│
├─ PostgreSQL error?
│  ├─ Connection refused (5433)
│  │  └─ Start: net start postgresql-x64-15
│  ├─ Password wrong
│  │  └─ Reset: ALTER USER postgres WITH PASSWORD 'admin'
│  └─ Table not found
│     └─ Create: psql -f db/01_create_tables.sql
│
├─ Redis error?
│  ├─ Connection refused
│  │  └─ Start: redis-server
│  ├─ Empty cache
│  │  └─ Load: python scripts/load_postgres_to_redis.py
│  └─ Password wrong
│     └─ Fix: AUTH admin
│
├─ IB Gateway error?
│  ├─ Connection timeout
│  │  └─ Check: IB Gateway GUI running, API enabled
│  ├─ No historical data
│  │  └─ Check: IBKR limits (1yr daily max)
│  └─ Client ID conflict
│     └─ Wait: IDs expire in ~10 min
│
├─ Download slow?
│  ├─ Check IB Gateway logs
│  ├─ Reduce date range
│  └─ Retry with V2-Sequential
│
└─ Backtest fails?
   ├─ Verify cache populated (DBSIZE > 30000)
   ├─ Verify PostgreSQL has data
   └─ Check Python packages installed
```

---

## 📈 Common Analyses

### Compare All Strategies
```bash
cd C:\Trading\TradingAgents && python << 'EOF'
import json
import pandas as pd

with open('reports/backtest_all_strategies_report.json', 'r') as f:
    data = json.load(f)

df = pd.DataFrame(data['results'])
summary = df.groupby('strategy').agg({
    'pnl': ['mean', 'max', 'count'],
    'win_rate': 'mean'
}).round(2)

print(summary.sort_values(('pnl', 'mean'), ascending=False))
EOF
```

### Find Best Ticker
```bash
cd C:\Trading\TradingAgents && python << 'EOF'
import json
import pandas as pd

with open('reports/backtest_all_strategies_report.json', 'r') as f:
    data = json.load(f)

df = pd.DataFrame(data['results'])
df['base_ticker'] = df['ticker'].str.split('_').str[0]
summary = df.groupby('base_ticker')['pnl'].agg(['mean', 'sum', 'count']).sort_values('mean', ascending=False)

print(summary)
EOF
```

### Show Profitability by Timeframe
```bash
cd C:\Trading\TradingAgents && python << 'EOF'
import json
import pandas as pd

with open('reports/backtest_all_strategies_report.json', 'r') as f:
    data = json.load(f)

df = pd.DataFrame(data['results'])
df['timeframe'] = df['ticker'].str.split('_').str[-1]
summary = df.groupby('timeframe')['pnl'].agg(['mean', 'sum', 'count']).sort_values('sum', ascending=False)

print(summary)
EOF
```

---

## 🛠️ Maintenance Tasks

### Weekly: Backup Database
```bash
pg_dump -h localhost -p 5433 -U postgres -d postgres > backup_$(date +%Y%m%d).sql
```

### Weekly: Check Disk Space
```bash
du -sh ~/.tradingagents/
du -sh C:\Trading\TradingAgents\reports\
```

### Monthly: Clean Old Logs
```bash
find ~/.tradingagents/download_logs -mtime +30 -delete
```

### Daily: Download Latest Data (Scheduled)
```bash
# Add to Windows Task Scheduler
python C:\Trading\TradingAgents\scripts\download_market_data.py AAPL
```

---

## 📚 Document Reference

| Doc | Use For | Read Time |
|-----|---------|-----------|
| SETUP_GUIDE.md | First setup, deep understanding | 30 min |
| db/QUICK_REFERENCE.md | Fast execution, commands | 5 min |
| db/01_create_tables.sql | Database schema creation | 2 min |
| This skill | Task routing, quick lookup | 2 min |

---

## 🚀 Minimum Token Workflow

When Claude asks you for details:

**Provide this info upfront:**
```
Task: [Download/Backtest/Status]
Ticker: [AAPL/MSFT/etc or N/A]
Current Status: [All services up / X service down]
Last Action: [When you last ran something]
```

**Then Claude can:**
- Route to correct skill
- Run exact command
- Report results
- Minimal back-and-forth

---

## Token Optimization Tips

### Use Skill Summary (30 tokens)
"Use tradingagents_data_pipeline skill. Status: All services up. Run download for AAPL."

### vs Manual Explanation (200+ tokens)
"I need to download data from IBKR through the TradingAgents system. I'm not sure about the steps..."

### Savings: ~85% reduction

---

## Command Cheat Sheet

```bash
# 1. Download AAPL
python scripts/download_market_data.py AAPL

# 2. Update cache
python scripts/load_postgres_to_redis.py

# 3. Backtest
python scripts/backtest_all_strategies.py

# 4. Check status
psql -h localhost -p 5433 -U postgres -c "SELECT 'OK'"
redis-cli DBSIZE

# 5. View results
ls -lth reports/
cat reports/backtest_all_strategies_report.json | head -50
```

---

## When NOT to Use This Skill

❌ **Use SETUP_GUIDE.md instead if:**
- First time setup
- Need detailed explanation
- System broken and need comprehensive guide

❌ **Use data_pipeline skill instead if:**
- Need to download new data
- Cache refresh needed

❌ **Use backtest_analysis skill instead if:**
- Running backtests
- Deep analysis of results

---

**Keep this open when running TradingAgents. Reference whenever you need to do something.**
