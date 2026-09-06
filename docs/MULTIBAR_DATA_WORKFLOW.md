# Multi-Bar Historical Data Workflow

## Overview

Complete workflow for downloading, managing, and querying multi-timeframe market data (1-min, 5-min, hourly, daily) stored in separate PostgreSQL tables.

---

## Architecture

### Separate Tables Design

```
┌─────────────────────────────────────────────────┐
│         PostgreSQL Database                      │
├─────────────────────────────────────────────────┤
│                                                  │
│  ┌─────────────────────────────────────────┐   │
│  │ historical_data_daily                   │   │
│  │ (2017-present, 2,268 bars/ticker)      │   │
│  │ Size: ~7 MB                             │   │
│  └─────────────────────────────────────────┘   │
│                                                  │
│  ┌─────────────────────────────────────────┐   │
│  │ historical_data_hourly                  │   │
│  │ (2017-present, 14,742 bars/ticker)     │   │
│  │ Size: ~45 MB                            │   │
│  └─────────────────────────────────────────┘   │
│                                                  │
│  ┌─────────────────────────────────────────┐   │
│  │ historical_data_5min                    │   │
│  │ (2017-present, 177,408 bars/ticker)    │   │
│  │ Size: ~549 MB                           │   │
│  └─────────────────────────────────────────┘   │
│                                                  │
│  ┌─────────────────────────────────────────┐   │
│  │ historical_data_1min                    │   │
│  │ (Last 3 years, 294,840 bars/ticker)    │   │
│  │ Size: ~913 MB (auto-cleanup to 90 days)│   │
│  └─────────────────────────────────────────┘   │
│                                                  │
│  ┌─────────────────────────────────────────┐   │
│  │ VIEWS (unified access):                 │   │
│  │ - v_historical_data_all                 │   │
│  │ - v_latest_data                         │   │
│  │ - v_data_completeness                   │   │
│  └─────────────────────────────────────────┘   │
│                                                  │
└─────────────────────────────────────────────────┘
```

### Why Separate Tables?

| Aspect | Benefit |
|--------|---------|
| Query Performance | Smaller tables = faster scans |
| Retention Policy | Keep 1-min for 90 days, daily forever |
| Archiving | Archive/delete per interval independently |
| Indexing | Optimize indexes per access pattern |
| Maintenance | Partition large tables by year |
| Clarity | Clear data model for application code |

---

## Workflow Steps

### Phase 1: Create Schema (One-time)

**Run this FIRST to create tables and indexes:**

```powershell
python scripts/create_multibar_schema.py
```

**What it does:**
- ✅ Creates 4 tables (daily, hourly, 5min, 1min)
- ✅ Creates indexes for performance
- ✅ Creates 3 views for unified querying
- ✅ Shows table statistics

**Output:**
```
✅ Created table: historical_data_daily
   ✅ Index: idx_historical_data_daily_ticker
   ✅ Index: idx_historical_data_daily_date
   ✅ Index: idx_historical_data_daily_ticker_date
   ✅ Index: idx_historical_data_daily_created_at

[... same for hourly, 5min, 1min ...]

✅ Created view: v_historical_data_all
✅ Created view: v_latest_data
✅ Created view: v_data_completeness

📊 Table Statistics:
historical_data_daily:
  Records: 0
  Total Size: 8192 bytes
  Table Size: 0 bytes
  Indexes Size: 16 KB
```

---

### Phase 2: Download Data (One-time, ~1-2 hours)

**Run this SECOND to download and insert data:**

```powershell
python scripts/download_ibkr_multibar_data.py
```

**What it does:**
- ✅ Connects to IBKR
- ✅ Downloads data for all 15 tickers
- ✅ Downloads all 4 bar intervals
- ✅ Saves to local cache (CSV)
- ✅ Inserts into PostgreSQL
- ✅ Creates indexes
- ✅ Reports progress

**Prerequisites:**
- IBKR TWS/Gateway running with API enabled
- PostgreSQL running with schema created
- 3 GB free disk space
- ~1-2 hours of time

**Duration:**
- Download from IBKR: 30-60 minutes
- Insert into PostgreSQL: 10-20 minutes
- Create indexes: 2-5 minutes
- **Total: 40-90 minutes**

**Final Output:**
```
✅ DOWNLOAD COMPLETE!

Records inserted by interval:
   daily     : 34,020 records
   hourly    : 221,130 records
   5min      : 2,661,120 records
   1min      : 4,422,600 records

   TOTAL     : 7,338,870 records

Data saved to:
  ~/.tradingagents/data_cache_multibar/
```

---

### Phase 3: Manage & Monitor (Ongoing)

**Check data status:**

```powershell
# Full report
python scripts/multibar_data_manager.py --report

# Just statistics
python scripts/multibar_data_manager.py --stats

# Data completeness by ticker/interval
python scripts/multibar_data_manager.py --completeness

# Latest bars
python scripts/multibar_data_manager.py --latest

# Latest bars for specific ticker
python scripts/multibar_data_manager.py --latest-ticker AAPL
```

**Export data to CSV:**

```powershell
# Export AAPL daily data
python scripts/multibar_data_manager.py --export AAPL daily

# Export NVDA 5-minute data
python scripts/multibar_data_manager.py --export NVDA 5min

# Outputs: AAPL_daily_20260905.csv
```

**Analyze ticker performance:**

```powershell
python scripts/multibar_data_manager.py --analyze AAPL daily
python scripts/multibar_data_manager.py --analyze NVDA hourly
python scripts/multibar_data_manager.py --analyze SPY 5min
```

**Output example:**
```
📈 PERFORMANCE ANALYSIS: AAPL (daily)
============================================================
  Period: 2017-01-01 to 2026-09-05
  Bar Count: 2,268
  Price Range: $95.00 - $238.50
  Average Close: $165.35
  Volatility (Std Dev): $42.15
  Total Volume: 15,234,567,890
============================================================
```

**Clean up old 1-minute data (monthly):**

```powershell
# Keep only last 90 days of 1-minute data
python scripts/multibar_data_manager.py --cleanup 90

# Output:
# ✅ Deleted 1,234,567 1-minute bars older than 90 days
# Cutoff date: 2026-06-07
```

---

## Quick Start Commands

### One-Time Setup (Day 1)

```powershell
# Step 1: Create schema
python scripts/create_multibar_schema.py

# Step 2: Download data (takes 1-2 hours, get coffee ☕)
python scripts/download_ibkr_multibar_data.py

# Step 3: Verify
python scripts/multibar_data_manager.py --report
```

### Daily Operations

```powershell
# Check data status
python scripts/multibar_data_manager.py --stats

# Export data for analysis
python scripts/multibar_data_manager.py --export AAPL daily > aapl_data.csv

# Query via SQL
# SELECT * FROM historical_data_daily WHERE ticker='AAPL' ORDER BY date DESC LIMIT 10;
```

### Monthly Maintenance

```powershell
# Clean up old 1-minute bars (keep 90 days)
python scripts/multibar_data_manager.py --cleanup 90

# Generate report
python scripts/multibar_data_manager.py --report

# Backup database
docker exec tagent pg_dump -U postgres -d tradingagents -Fc > backup_$(date +%Y%m%d).dump
```

---

## Direct SQL Queries

### Common Queries

**Get all daily bars for a ticker:**
```sql
SELECT date, open, high, low, close, volume
FROM historical_data_daily
WHERE ticker = 'AAPL'
ORDER BY date DESC
LIMIT 10;
```

**Get hourly data for specific date range:**
```sql
SELECT date, open, high, low, close, volume
FROM historical_data_hourly
WHERE ticker = 'NVDA'
  AND date >= '2026-01-01'
  AND date < '2026-09-01'
ORDER BY date;
```

**Get 5-minute bars for last trading day:**
```sql
SELECT date, open, high, low, close, volume
FROM historical_data_5min
WHERE ticker = 'SPY'
  AND date::date = CURRENT_DATE - INTERVAL '1 day'
ORDER BY date;
```

**Get latest bar from all intervals:**
```sql
SELECT * FROM v_latest_data
WHERE ticker = 'AAPL'
ORDER BY bar_interval, date DESC;
```

**Check data completeness:**
```sql
SELECT interval, ticker, total_bars, completeness
FROM v_data_completeness
WHERE ticker IN ('AAPL', 'MSFT', 'NVDA')
ORDER BY interval, ticker;
```

**Compare prices across intervals:**
```sql
SELECT
  'daily' as interval, date::date, close
FROM historical_data_daily WHERE ticker = 'AAPL'
UNION ALL
SELECT
  'hourly', date::date, close
FROM historical_data_hourly WHERE ticker = 'AAPL'
ORDER BY date DESC
LIMIT 20;
```

---

## Data Retention Policy

### Daily Data
- **Retention**: Keep forever
- **Recommended Action**: Full backups quarterly
- **Use Case**: Long-term trend analysis, strategy backtesting

### Hourly Data
- **Retention**: Keep forever
- **Recommended Action**: Archive to S3 yearly
- **Use Case**: Medium-term analysis, intraday patterns

### 5-Minute Data
- **Retention**: Keep for 2+ years (space permitting)
- **Recommended Action**: Archive to S3 yearly
- **Use Case**: Intraday trading, scalping strategies

### 1-Minute Data
- **Retention**: 90 days (auto-cleanup)
- **Recommended Action**: Cleanup monthly
- **Use Case**: Real-time trading, scalping, market micro-structure

---

## Performance Tuning

### Query Performance by Interval

| Interval | Typical Query | Time |
|----------|--------------|------|
| Daily | Get all 2,268 bars | <50ms |
| Hourly | Get all 14,742 bars | <100ms |
| 5-min | Get 1 day (78 bars) | <200ms |
| 1-min | Get 1 hour (60 bars) | <500ms |

### Index Strategy

Each table has 4 indexes optimized for common queries:

1. **ticker index** - Find all bars for a ticker
2. **date index** - Find latest bars (DESC)
3. **ticker + date composite** - Get ticker's recent bars (most common)
4. **created_at index** - Track data import time

### Optimization for Your Queries

```python
# Python: Get AAPL daily data efficiently
import psycopg2

conn = psycopg2.connect("dbname=tradingagents user=postgres")
cursor = conn.cursor()

# This uses composite index (very fast)
cursor.execute("""
    SELECT date, open, high, low, close, volume
    FROM historical_data_daily
    WHERE ticker = %s
    ORDER BY date DESC
    LIMIT 252
""", ('AAPL',))

data = cursor.fetchall()
conn.close()
```

---

## Troubleshooting

### Schema Creation Issues

**Error: "Table already exists"**
```powershell
# Tables are already created, which is fine
# To reset:
docker exec tagent psql -U postgres -d tradingagents -c "DROP TABLE historical_data_daily CASCADE;"

# Then re-run
python scripts/create_multibar_schema.py
```

### Download Issues

**Error: "Connection to IBKR failed"**
```
✓ Make sure TWS or IB Gateway is running
✓ Make sure API is enabled in settings
✓ Check TRADINGAGENTS_IBKR_HOST and PORT in .env
✓ Try: docker exec tagent ping 127.0.0.1
```

**Error: "No data available for this contract"**
```
✓ IBKR may not have historical data
✓ Some tickers have limited data availability
✓ Try another ticker: AAPL, MSFT, NVDA usually have full history
```

### Query Issues

**Error: "relation does not exist"**
```sql
-- Make sure tables exist
SELECT tablename FROM pg_tables WHERE schemaname = 'public';

-- Should show:
-- historical_data_daily
-- historical_data_hourly
-- historical_data_5min
-- historical_data_1min
```

**Slow queries**
```sql
-- Check index usage
EXPLAIN ANALYZE
SELECT * FROM historical_data_daily
WHERE ticker = 'AAPL'
ORDER BY date DESC
LIMIT 100;

-- Should show "Index Scan" (not "Seq Scan")
```

---

## Integration with Application Code

### Get Recent Daily Bars for Backtest

```python
from sqlalchemy import create_engine, text
import os

# Connect to database
engine = create_engine(os.getenv("DATABASE_URL"))

# Get recent daily bars
with engine.connect() as conn:
    query = text("""
        SELECT date, open, high, low, close, volume
        FROM historical_data_daily
        WHERE ticker = :ticker
        ORDER BY date DESC
        LIMIT 252
    """)
    
    result = conn.execute(query, {"ticker": "AAPL"})
    data = result.fetchall()

# Convert to DataFrame
import pandas as pd
df = pd.DataFrame(data, columns=['date', 'open', 'high', 'low', 'close', 'volume'])
```

### Get Intraday 5-Min Bars for Strategy

```python
from sqlalchemy import create_engine, text
from datetime import datetime, timedelta

engine = create_engine(os.getenv("DATABASE_URL"))

# Get today's 5-min bars
today = datetime.now().date()

with engine.connect() as conn:
    query = text("""
        SELECT date, open, high, low, close, volume
        FROM historical_data_5min
        WHERE ticker = :ticker
          AND date::date = :date
        ORDER BY date
    """)
    
    result = conn.execute(query, {
        "ticker": "AAPL",
        "date": today
    })
    
    data = result.fetchall()

# Process for intraday trading
```

---

## Maintenance Schedule

### Daily
- ✅ Monitor data freshness (if doing real-time updates)

### Weekly
- ✅ Check data completeness: `python scripts/multibar_data_manager.py --completeness`
- ✅ Verify table sizes: `python scripts/multibar_data_manager.py --stats`

### Monthly
- ✅ Clean old 1-minute data: `python scripts/multibar_data_manager.py --cleanup 90`
- ✅ Generate report: `python scripts/multibar_data_manager.py --report`
- ✅ Backup database: `docker exec tagent pg_dump -U postgres tradingagents | gzip > backup_$(date +%Y%m).sql.gz`

### Quarterly
- ✅ Archive hourly/5-min data to S3
- ✅ Verify backup restoration
- ✅ Review disk usage

### Annually
- ✅ Full audit of data completeness
- ✅ Archive old data (1+ years)
- ✅ Update retention policies as needed

---

## Summary

| Step | Command | Time | One-time? |
|------|---------|------|-----------|
| Create Schema | `create_multibar_schema.py` | 2 min | ✅ Yes |
| Download Data | `download_ibkr_multibar_data.py` | 45-90 min | ✅ Yes |
| Check Status | `multibar_data_manager.py --report` | 1 min | ❌ Recurring |
| Export Data | `multibar_data_manager.py --export AAPL daily` | 1 min | ❌ Recurring |
| Cleanup Old | `multibar_data_manager.py --cleanup 90` | 1 min | ❌ Monthly |

---

**Status**: Workflow Complete ✅  
**Total Setup Time**: ~45-90 minutes (mostly download)  
**Data Size**: ~1.5 GB  
**Tickers**: 15  
**Intervals**: 4 (daily, hourly, 5-min, 1-min)  
**Ready to Use**: Yes! 🚀
