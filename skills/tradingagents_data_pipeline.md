# TradingAgents Data Pipeline Skill

**Purpose:** Efficiently download market data, cache to Redis, and load PostgreSQL  
**Tokens Saved:** ~70% vs manual prompting  
**Execution Time:** ~15-20 minutes for full pipeline

---

## Workflow

### Phase 1: Verify Services (2 min)

```bash
# Check PostgreSQL (5433)
psql -h localhost -p 5433 -U postgres -c "SELECT 'PostgreSQL OK'"

# Check Redis (6379)
redis-cli -h localhost -p 6379 ping

# Check IB Gateway (4002)
# Expected: Port accessible
```

**If any fail:** Stop and report which service is down.

### Phase 2: Download Data (3-10 min per ticker)

```bash
cd C:\Trading\TradingAgents

# For single ticker (recommended)
python scripts/download_market_data.py AAPL

# Output check:
# - Look for: "40,315 total records"
# - Files saved to: ~/.tradingagents/data_downloads/AAPL/historical/
# - Database: 365 daily, 2546 hourly, 14004 5min, 23400 1min
```

**If timeout errors:**
- Reduce date range in script
- Check IBKR server status
- Retry with V2-Sequential

### Phase 3: Verify Database (1 min)

```bash
psql -h localhost -p 5433 -U postgres -d postgres << EOF
SELECT ticker, 
       (SELECT count(*) FROM historical_data_daily WHERE ticker=t.ticker) as daily_rows,
       (SELECT count(*) FROM historical_data_hourly WHERE ticker=t.ticker) as hourly_rows,
       (SELECT count(*) FROM historical_data_5min WHERE ticker=t.ticker) as min5_rows,
       (SELECT count(*) FROM historical_data_1min WHERE ticker=t.ticker) as min1_rows
FROM (SELECT DISTINCT ticker FROM historical_data_daily UNION SELECT DISTINCT ticker FROM historical_data_hourly UNION SELECT DISTINCT ticker FROM historical_data_5min UNION SELECT DISTINCT ticker FROM historical_data_1min) t
ORDER BY ticker;
EOF
```

**Expected output:**
```
 ticker | daily_rows | hourly_rows | min5_rows | min1_rows
--------+------------+-------------+-----------+-----------
 AAPL   |        365 |        2546 |     20328 |     23400
 AMZN   |         63 |         441 |      4914 |         0
```

### Phase 4: Load Redis Cache (1-2 min)

```bash
# Clear old cache
redis-cli -h localhost -p 6379 --raw FLUSHDB

# Load new data
python scripts/load_postgres_to_redis.py

# Verify
redis-cli -h localhost -p 6379 --raw DBSIZE
# Should show: 50000+ keys
```

### Phase 5: Summary Report

```bash
# Data summary
echo "=== PostgreSQL Data Summary ===" && \
psql -h localhost -p 5433 -U postgres -d postgres -c "SELECT count(*) as total_records FROM (SELECT * FROM historical_data_daily UNION ALL SELECT * FROM historical_data_hourly UNION ALL SELECT * FROM historical_data_5min UNION ALL SELECT * FROM historical_data_1min) all_data"

echo "" && \
echo "=== Redis Cache Status ===" && \
redis-cli -h localhost -p 6379 DBSIZE

echo "" && \
echo "=== Download Complete ===" && \
echo "Ready for backtesting"
```

---

## Quick Commands

```bash
# Run entire pipeline for AAPL
cd C:\Trading\TradingAgents && \
python scripts/download_market_data.py AAPL && \
python scripts/load_postgres_to_redis.py

# Check if services running
psql -h localhost -p 5433 -U postgres -c "SELECT 1" && \
redis-cli -h localhost -p 6379 ping

# View latest download log
tail -f ~/.tradingagents/download_logs/download_*.log
```

---

## When to Use

✅ **Use this skill when:**
- Need to download fresh market data
- Cache needs refresh
- Setting up new ticker
- Daily scheduled run

❌ **Don't use when:**
- Only running backtests (data already cached)
- Troubleshooting specific error
- Analyzing existing results

---

## Expected Outputs

| Stage | Duration | Expected Output |
|-------|----------|-----------------|
| Phase 1 | 2 min | All 3 services online |
| Phase 2 | 3-10 min | 40K+ records, CSV files saved |
| Phase 3 | 1 min | Data counts verified |
| Phase 4 | 1-2 min | 50K+ Redis keys |
| Total | **7-15 min** | **Ready to backtest** |

---

## Troubleshooting Shortcuts

```bash
# Service down? Check status
service postgresql status
redis-cli ping

# Download slow? Check log
tail -f ~/.tradingagents/download_logs/download_*.log

# Cache empty? Reload
python scripts/load_postgres_to_redis.py

# Data corrupted? Restore backup
psql -h localhost -p 5433 -U postgres -d postgres < backup.sql
```

---

**Use this skill for routine data updates and refresh cycles.**
