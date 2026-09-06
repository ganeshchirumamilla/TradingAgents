# PostgreSQL Storage Estimation - Multi-Bar Historical Data

## Overview

Storage requirements for downloading historical market data from IBKR for 15 tickers across 4 different bar intervals (Daily, Hourly, 5-minute, 1-minute).

---

## Data Configuration

| Parameter | Value |
|-----------|-------|
| Tickers | 15 (AAPL, MSFT, NVDA, AMZN, META, GOOGL, TSLA, AMD, AVGO, JPM, GS, SPY, QQQ, IWM, DIA) |
| Bar Intervals | 4 (Daily, Hourly, 5-min, 1-min) |
| Date Range | 2017-09-05 to 2026-09-05 (~9 years) |
| Trading Days/Year | ~252 (US market) |

---

## Storage Calculation by Interval

### 1. Daily Bars

**Data Points per Ticker:**
- Period: 2017-2026 = ~9 years
- Trading days: ~252 per year
- Daily bars per ticker: 252 × 9 = **2,268 records**

**Total Records:**
- 2,268 daily bars × 15 tickers = **34,020 daily records**

**Per-Record Size (PostgreSQL):**
```
UUID (16 bytes)
  + ticker VARCHAR(20) (20 bytes)
  + date TIMESTAMP (8 bytes)
  + open DECIMAL(10,4) (8 bytes)
  + high DECIMAL(10,4) (8 bytes)
  + low DECIMAL(10,4) (8 bytes)
  + close DECIMAL(10,4) (8 bytes)
  + volume BIGINT (8 bytes)
  + created_at TIMESTAMP (8 bytes)
  + data_source VARCHAR(50) (50 bytes)
  + Overhead/indexes (~30 bytes)
  ─────────────────────────────────
  Total per record: ~172 bytes
```

**Storage Per Ticker:**
- 2,268 records × 172 bytes = **389.8 KB**

**Total Storage (Daily):**
- 34,020 records × 172 bytes = **5.85 MB**
- Plus indexes (~20% overhead): **~7.0 MB**

---

### 2. Hourly Bars

**Data Points per Ticker:**
- Period: 2017-2026 = ~9 years
- Trading days: ~252 per year
- Trading hours per day: 6.5 (9:30 AM - 4:00 PM ET)
- Hourly bars per ticker: 252 × 9 × 6.5 = **14,742 records**

**Total Records:**
- 14,742 hourly bars × 15 tickers = **221,130 hourly records**

**Storage Per Ticker:**
- 14,742 records × 172 bytes = **2.54 MB**

**Total Storage (Hourly):**
- 221,130 records × 172 bytes = **38.04 MB**
- Plus indexes (~20% overhead): **~45.6 MB**

---

### 3. Five-Minute Bars

**Data Points per Ticker:**
- Period: 2017-2026 = ~9 years
- Trading days: ~252 per year
- 5-minute bars per trading day: 6.5 hours × 60 min/hour ÷ 5 = 78 bars
- 5-minute bars per ticker: 252 × 9 × 78 = **177,408 records**

**Total Records:**
- 177,408 5-min bars × 15 tickers = **2,661,120 5-min records**

**Storage Per Ticker:**
- 177,408 records × 172 bytes = **30.53 MB**

**Total Storage (5-minute):**
- 2,661,120 records × 172 bytes = **457.92 MB**
- Plus indexes (~20% overhead): **~549.5 MB**

---

### 4. One-Minute Bars

**Data Points per Ticker:**
- Period: Last 3 years (2023-2026)
- Trading days: ~252 per year
- 1-minute bars per trading day: 6.5 hours × 60 = 390 bars
- 1-minute bars per ticker: 252 × 3 × 390 = **294,840 records**

*Note: IBKR typically limits 1-minute data to ~3-6 months of history. We request 3 months but get what's available.*

**Total Records:**
- 294,840 1-min bars × 15 tickers = **4,422,600 1-min records**

**Storage Per Ticker:**
- 294,840 records × 172 bytes = **50.75 MB**

**Total Storage (1-minute):**
- 4,422,600 records × 172 bytes = **761.09 MB**
- Plus indexes (~20% overhead): **~913.3 MB**

---

## Total Storage Summary

| Interval | Records | Storage | + Indexes | Total |
|----------|---------|---------|-----------|-------|
| Daily | 34,020 | 5.85 MB | 1.17 MB | **7.0 MB** |
| Hourly | 221,130 | 38.04 MB | 7.61 MB | **45.6 MB** |
| 5-minute | 2,661,120 | 457.92 MB | 91.58 MB | **549.5 MB** |
| 1-minute | 4,422,600 | 761.09 MB | 152.22 MB | **913.3 MB** |
| **GRAND TOTAL** | **7,338,870** | **1,262.9 MB** | **252.6 MB** | **~1.51 GB** |

---

## Table Statistics

### By Interval

| Interval | Table Name | Rows | Avg Row Size |
|----------|-----------|------|--------------|
| Daily | historical_data_daily | 34,020 | 172 bytes |
| Hourly | historical_data_hourly | 221,130 | 172 bytes |
| 5-minute | historical_data_5min | 2,661,120 | 172 bytes |
| 1-minute | historical_data_1min | 4,422,600 | 172 bytes |

### By Ticker (All Intervals Combined)

| Ticker | Records | Storage |
|--------|---------|---------|
| AAPL | 489,252 | ~84 MB |
| MSFT | 489,252 | ~84 MB |
| NVDA | 489,252 | ~84 MB |
| AMZN | 489,252 | ~84 MB |
| META | 489,252 | ~84 MB |
| GOOGL | 489,252 | ~84 MB |
| TSLA | 489,252 | ~84 MB |
| AMD | 489,252 | ~84 MB |
| AVGO | 489,252 | ~84 MB |
| JPM | 489,252 | ~84 MB |
| GS | 489,252 | ~84 MB |
| SPY | 489,252 | ~84 MB |
| QQQ | 489,252 | ~84 MB |
| IWM | 489,252 | ~84 MB |
| DIA | 489,252 | ~84 MB |
| **TOTAL** | **7,338,870** | **~1.51 GB** |

---

## PostgreSQL Configuration Recommendations

### Minimum Requirements
- **Disk Space**: At least 2-3 GB free (for data + indexes + log files)
- **RAM**: 1-2 GB (PostgreSQL will cache frequently accessed data)
- **CPU**: 2+ cores (for concurrent queries)

### Recommended Hardware
- **Disk**: SSD with 10-20 GB free space
- **RAM**: 4-8 GB (for better performance)
- **CPU**: 4+ cores (for faster bulk inserts)

### Database Tuning for Bulk Inserts

```sql
-- Temporarily increase performance for bulk inserts
ALTER SYSTEM SET shared_buffers = '2GB';
ALTER SYSTEM SET effective_cache_size = '6GB';
ALTER SYSTEM SET work_mem = '50MB';
ALTER SYSTEM SET maintenance_work_mem = '512MB';
ALTER SYSTEM SET max_wal_size = '4GB';

-- Reload configuration
SELECT pg_reload_conf();
```

---

## Data Transfer Timeline

### Network Bandwidth Estimation
- **Total data from IBKR**: ~1.5 GB
- **Average IBKR API bandwidth**: 1-5 MB/sec
- **Estimated transfer time**: 5-25 minutes (excluding processing)

### Total Execution Time Estimate
- **Data download**: 20-60 minutes (depends on IBKR server load)
- **Data parsing**: 5-10 minutes
- **Database insertion**: 10-20 minutes
- **Index creation**: 2-5 minutes
- **Total time**: **40-90 minutes** (~1-1.5 hours)

---

## Disk Space Breakdown

| Component | Size |
|-----------|------|
| Table data (4 tables) | ~1.26 GB |
| Indexes (4 tables × 8-10 indexes) | ~252 MB |
| PostgreSQL WAL logs | ~100-200 MB |
| Temporary space during load | ~200-300 MB |
| **Buffer/Reserve (20%)** | **~300 MB** |
| **TOTAL NEEDED** | **~2.0-2.5 GB** |

---

## Scaling Considerations

### If You Add More Tickers
For each additional ticker (all 4 intervals):
- Storage increase: ~84 MB
- Insertion time: +5 minutes

### If You Extend Historical Data
- Daily bars (10 more years): +1 MB per ticker
- Hourly bars (1 more year): +3 MB per ticker
- 5-minute bars (3 more months): +6 MB per ticker
- 1-minute bars (not practical to extend beyond 3 months)

### Growth Over Time
With daily incremental updates:
- Daily bars: +1 KB per ticker per day
- Hourly bars: +6 KB per ticker per day
- 5-minute bars: +75 KB per ticker per day
- 1-minute bars: +450 KB per ticker per day
- **Total daily growth**: ~531 KB per ticker = ~8 MB for all 15 tickers

---

## Query Performance Expectations

### Typical Query Times

| Query | Time | Index Used |
|-------|------|------------|
| Get all daily bars for 1 ticker | <50ms | idx_historical_data_daily_ticker_date |
| Get hourly bars for date range | <100ms | idx_historical_data_hourly_date |
| Get 5-min bars for 1 day | <200ms | idx_historical_data_5min_ticker_date |
| Aggregation (avg price 1 year) | 500ms-2s | Depends on interval |

### Recommended Indexes

```sql
-- Already created by init_db.sql
CREATE INDEX idx_historical_data_daily_ticker ON historical_data_daily(ticker);
CREATE INDEX idx_historical_data_daily_date ON historical_data_daily(date DESC);
CREATE INDEX idx_historical_data_daily_ticker_date ON historical_data_daily(ticker, date DESC);

-- Similar for hourly, 5min, 1min tables
```

---

## Backup Strategy

### Full Backup Size
- With compression (pg_dump -Fc): ~400-500 MB
- Without compression: ~1.5 GB

### Backup Time
- Full backup: 5-10 minutes
- Incremental backup: 1-2 minutes

### Recommended Backup Schedule
- **Full backup**: Weekly (Sunday)
- **Incremental backup**: Daily (after market close)

---

## Practical Tips

### 1. Pre-Download Optimization
```sql
-- Increase synchronous_commit for faster inserts
ALTER SYSTEM SET synchronous_commit = off;
SELECT pg_reload_conf();

-- REMEMBER TO TURN IT BACK ON AFTER LOAD
ALTER SYSTEM SET synchronous_commit = on;
SELECT pg_reload_conf();
```

### 2. Monitor Progress
```sql
-- Check table size during load
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

### 3. Verify Data Completeness
```sql
-- Check record count by interval
SELECT 'daily' as interval, COUNT(*) as count FROM historical_data_daily
UNION ALL
SELECT 'hourly', COUNT(*) FROM historical_data_hourly
UNION ALL
SELECT '5min', COUNT(*) FROM historical_data_5min
UNION ALL
SELECT '1min', COUNT(*) FROM historical_data_1min;

-- Check records per ticker
SELECT ticker, COUNT(*) as total_records
FROM (
    SELECT ticker FROM historical_data_daily
    UNION ALL
    SELECT ticker FROM historical_data_hourly
    UNION ALL
    SELECT ticker FROM historical_data_5min
    UNION ALL
    SELECT ticker FROM historical_data_1min
) t
GROUP BY ticker
ORDER BY total_records DESC;
```

---

## Storage Comparison

### Local CSV Files vs. PostgreSQL

| Aspect | CSV Files | PostgreSQL |
|--------|-----------|-----------|
| Storage Size | ~800 MB | ~1.5 GB (with indexes) |
| Query Speed | Slow (full scan) | Fast (indexed) |
| Compression | Easy | Built-in |
| Backup | Manual | Automated |
| Concurrent Access | Limited | Excellent |
| Data Integrity | No ACID | Full ACID |
| Recommended For | Archival | Production |

---

## Final Summary

| Metric | Value |
|--------|-------|
| **Total Records** | ~7.3 million |
| **Total Storage** | ~1.5 GB (in PostgreSQL) |
| **Disk Space Needed** | 2-3 GB free |
| **Estimated Load Time** | 40-90 minutes |
| **Daily Growth** | ~8 MB |
| **Backup Size** | ~400-500 MB |
| **Query Performance** | <200ms typical |

---

## When Ready to Download

Run this command:
```powershell
python scripts/download_ibkr_multibar_data.py
```

This will:
1. ✅ Connect to IBKR and download data
2. ✅ Save to local cache (~800 MB on disk)
3. ✅ Insert into PostgreSQL (~1.5 GB)
4. ✅ Create indexes for fast queries
5. ✅ Provide summary statistics

---

**Status**: Ready to download (once you confirm)  
**Created**: 2026-09-05  
**Script**: `scripts/download_ibkr_multibar_data.py`  
**Database Tables**: 4 (daily, hourly, 5min, 1min)  
**Tickers**: 15  
**Expected Completion**: 40-90 minutes
