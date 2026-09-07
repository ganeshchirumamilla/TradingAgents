# TradingAgents - Quick Reference Card

**For rapid setup on a new computer**

---

## 1. Service Startup Commands

### Start All Services

```bash
# Terminal 1: PostgreSQL
psql -h localhost -p 5433 -U postgres

# Terminal 2: Redis
redis-server

# Terminal 3: IB Gateway
# Start IB Gateway GUI application (manual)
```

### Verify Services Running

```bash
# PostgreSQL
psql -h localhost -p 5433 -U postgres -c "SELECT version();"

# Redis
redis-cli -h localhost -p 6379 ping
# Should return: PONG

# IB Gateway
# Check: http://localhost:7497 or port 4002 accessible
```

---

## 2. Database Setup (One-Time)

### Create Tables

```bash
cd C:\Trading\TradingAgents
psql -h localhost -p 5433 -U postgres -d postgres -f db/01_create_tables.sql
```

### Verify Tables

```bash
psql -h localhost -p 5433 -U postgres -d postgres -c "\dt"
```

### Check Current Data

```bash
psql -h localhost -p 5433 -U postgres -d postgres << EOF
SELECT ticker, count(*) as rows, min(date), max(date)
FROM historical_data_daily
GROUP BY ticker
ORDER BY ticker;
EOF
```

---

## 3. Data Download Workflow

### Quick Download (1 ticker, all timeframes)

```bash
cd C:\Trading\TradingAgents
python scripts/download_market_data.py AAPL
# Output: 40,315 records in ~3 minutes
```

### Advanced Download (chunked, incremental)

```bash
python scripts/download_market_data_v2_sequential.py AAPL
# Features: Database-aware, retries, chunked
```

### Supported Tickers

```
Primary: AAPL, AMZN
Configured: MSFT, GOOGL, TSLA, META, NVDA, etc.
Add new: Modify scripts/backtest_all_strategies.py tickers list
```

### Data Retention Limits

```
Daily:   365 days (1 year)
Hourly:  365 days (1 year)
5-Min:   180 days (6 months)
1-Min:   60 days (2 months)
```

---

## 4. Redis Cache Management

### Load Cache from PostgreSQL

```bash
cd C:\Trading\TradingAgents
python scripts/load_postgres_to_redis.py
# Output: ~52,000 records cached
```

### Clear Cache

```bash
redis-cli -h localhost -p 6379 --raw FLUSHDB
```

### Verify Cache

```bash
redis-cli -h localhost -p 6379
> AUTH admin
> KEYS market_data:*
> GET market_data:AAPL:daily
> DBSIZE  # Shows total keys
```

---

## 5. Backtesting & Strategies

### Run All Backtests

```bash
cd C:\Trading\TradingAgents
python scripts/backtest_all_strategies.py
# Runtime: 5-10 minutes
# Output: Top 10 strategies with P&L
```

### Expected Results

```
MeanReversionRSI on AAPL 5min: 
  Win Rate: 100%
  P&L: +$105.92
  Return: +1.06%
```

### Results Location

```
reports/
├── backtest_all_strategies_report.json
├── backtest_results.csv
└── backtest_results.html
```

---

## 6. Connection Strings Reference

### PostgreSQL

```
Host:     localhost
Port:     5433
Database: postgres
User:     postgres
Password: admin

Connection URL:
postgresql://postgres:admin@localhost:5433/postgres
```

### Redis

```
Host:     localhost
Port:     6379
Password: admin

Connection:
redis-cli -h localhost -p 6379 -a admin
```

### IB Gateway

```
Host:     127.0.0.1
Port:     4002
Protocol: TCP/IP
```

---

## 7. Configuration Quick Reference

### V1 Downloader (download_market_data.py)

```python
# Edit: scripts/download_market_data.py

# Database (line ~45)
DB_HOST = "localhost"
DB_PORT = 5433
DB_NAME = "postgres"
DB_USER = "postgres"
DB_PASS = "admin"

# IBKR (line ~60)
IBKR_HOST = "127.0.0.1"
IBKR_PORT = 4002

# Download ranges (built-in)
DAILY:   365 days
HOURLY:  365 days
5MIN:    180 days
1MIN:    60 days
```

### V2-Sequential (download_market_data_v2_sequential.py)

```python
# Edit: scripts/download_market_data_v2_sequential.py

# Lookback periods (line ~55)
self.lookback = {
    'daily': timedelta(days=365),
    'hourly': timedelta(days=365),
    '5min': timedelta(days=180),
    '1min': timedelta(days=60),
}

# Chunk sizes (line ~47)
self.chunk_sizes = {
    'daily': timedelta(days=365),    # 1-year chunks
    'hourly': timedelta(days=30),    # 1-month chunks
    '5min': timedelta(days=5),       # 5-day chunks
    '1min': timedelta(days=1),       # 1-day chunks
}

# Retries (line ~306)
max_retries = 3  # With exponential backoff
```

### Redis Loader (load_postgres_to_redis.py)

```python
# Edit: scripts/load_postgres_to_redis.py

# TTL settings (line ~46)
self.ttl = {
    'daily': 30 * 86400,      # 30 days
    'hourly': 7 * 86400,      # 7 days
    '5min': 2 * 86400,        # 2 days
    '1min': 1 * 86400,        # 1 day
}

# Database (line ~56)
PostgreSQL: localhost:5433
Redis: localhost:6379
```

---

## 8. Troubleshooting Checklist

### Download Fails

```
☐ IB Gateway running and API enabled?
☐ Port 4002 accessible?
☐ IBKR account active and has funds?
☐ Date range within IBKR limits (1 year daily)?
☐ PostgreSQL running on 5433?
→ Check: scripts/download_*.py log output
```

### Cache Issues

```
☐ Redis running on 6379?
☐ PostgreSQL has data (>0 rows)?
☐ Password correct (admin)?
→ Command: redis-cli -h localhost -p 6379 ping
→ Command: redis-cli DBSIZE
```

### Backtest Fails

```
☐ Redis cache populated?
☐ PostgreSQL has data?
☐ Python packages installed (pandas, psycopg2, etc)?
☐ Reports/ folder exists?
→ Run: python -m pip install -r requirements.txt
```

---

## 9. Typical Workflow

```
Day 1: Initial Setup
├─ Install PostgreSQL (port 5433)
├─ Install Redis
├─ Setup IB Gateway
├─ Create database schema
└─ Run first download

Day 2: Data & Analysis
├─ Download data for required tickers
├─ Load to Redis cache
├─ Run backtests
└─ Review results

Ongoing: Maintenance
├─ Daily downloads (after market close)
├─ Weekly backtests
├─ Monthly PostgreSQL backups
└─ Monitor cache hit rates
```

---

## 10. Performance Baseline

### Download Performance

```
V1 Downloader (40K records):
  Time:    2-3 minutes
  CPU:     Low
  Network: Stable
  Result:  100% reliable

V2-Sequential (50K records):
  Time:    10-15 minutes (more data)
  CPU:     Low
  Network: Stable if configured correctly
  Result:  ~100% (when tuned)
```

### Cache Performance

```
Loading 52K records to Redis:
  Time:    <1 second
  Network: Localhost only
  Result:  All 4 tickers cached
```

### Backtest Performance

```
All strategies (AAPL + AMZN, 4 timeframes):
  Time:    5-10 minutes
  CPU:     Medium-High (parallel)
  Memory:  ~2GB
  Result:  19 combinations tested
```

---

## 11. Backup & Restore

### Backup PostgreSQL

```bash
pg_dump -h localhost -p 5433 -U postgres -d postgres > backup_$(date +%Y%m%d).sql

# Backup size: ~5-10 MB for 52K records
```

### Restore PostgreSQL

```bash
psql -h localhost -p 5433 -U postgres -d postgres < backup_20260906.sql
```

### Backup Redis

```bash
redis-cli -h localhost -p 6379 --rdb dump.rdb

# Or via config: Automatic BGSAVE
```

---

## 12. Environment Variables (Optional)

```bash
# Windows (set in terminal)
set DB_HOST=localhost
set DB_PORT=5433
set REDIS_HOST=localhost
set IBKR_HOST=127.0.0.1
set IBKR_PORT=4002
```

---

## Quick Commands Reference

```bash
# List all files (project structure)
tree C:\Trading\TradingAgents -L 2

# Download AAPL data
python scripts/download_market_data.py AAPL

# Load to Redis
python scripts/load_postgres_to_redis.py

# Run backtests
python scripts/backtest_all_strategies.py

# Check PostgreSQL data
psql -h localhost -p 5433 -U postgres -d postgres -c "SELECT COUNT(*) FROM historical_data_daily"

# Check Redis keys
redis-cli DBSIZE

# View latest log
tail -f ~/.tradingagents/download_logs/download_*.log

# View backtest results
type reports\backtest_all_strategies_report.json
```

---

**Keep this file handy for rapid deployment on new systems!**

**Generated:** 2026-09-06  
**Version:** 1.0
