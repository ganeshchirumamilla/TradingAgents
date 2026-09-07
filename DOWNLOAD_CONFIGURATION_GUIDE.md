# Advanced Download Configuration Guide

**Date**: 2026-09-06  
**Version**: 1.0

---

## Overview

This guide explains the new parameterized download infrastructure that supports:

✅ **Configuration-driven downloads** - All settings in YAML  
✅ **Resumable downloads** - Savepoint tracking per ticker/timeframe  
✅ **Parallel execution** - Multiple tickers downloading concurrently  
✅ **File persistence** - Data saved to Parquet (efficient) or CSV  
✅ **Database persistence** - Auto-insert to PostgreSQL  
✅ **Status tracking** - Resume from last failed point  

---

## Architecture

### Components

```
1. download_config.yaml
   └─ Central configuration for all downloads
   
2. DownloadSavepoint (download_savepoint.py)
   └─ Tracks per-ticker, per-timeframe download status
   
3. ConfiguredDataDownloader (download_with_config.py)
   └─ Single-threaded downloader using config + savepoint
   
4. ParallelOrchestrator (download_parallel_orchestrator.py)
   └─ Spawns workers, coordinates parallel downloads
```

### Data Flow

```
Config (YAML)
    ↓
ParallelOrchestrator
    ↓ (spawns N workers)
Worker 1 → ConfiguredDataDownloader → Download Data
Worker 2 → ConfiguredDataDownloader → Download Data  
Worker 3 → ConfiguredDataDownloader → Download Data
    ↓
Savepoint (JSON)  ← Updated by each worker
    ↓
Files (Parquet/CSV)
    ↓
PostgreSQL Database
```

---

## Configuration (download_config.yaml)

### 1. Download Settings

```yaml
download:
  format: "parquet"  # Options: parquet, csv
  save_files: true
  file_path_template: "~/.tradingagents/data_downloads/{ticker}/{timeframe}/data_{start_date}.{format}"
  compression: "snappy"  # snappy, gzip, brotli, none
```

**Parameters**:
- `{ticker}` → AAPL, MSFT, etc.
- `{timeframe}` → 1min, 5min, hourly, daily
- `{start_date}` → YYYYMMDD format
- `{format}` → parquet or csv

### 2. Tickers Configuration

```yaml
tickers:
  AAPL:
    name: "Apple Inc."
    enabled: true
  MSFT:
    name: "Microsoft"
    enabled: true
  # ... more tickers
```

**Usage**:
- Set `enabled: false` to skip a ticker
- Add new tickers easily without code changes

### 3. Timeframe Configuration

```yaml
timeframes:
  1min:
    bar_size: "1 min"
    table_name: "historical_data_1min"
    historical_start_date: null  # null = use default_days
    default_days: 90
    description: "1-minute bars"
    
  daily:
    bar_size: "1 day"
    table_name: "historical_data_daily"
    default_days: 7300  # 20 years
```

**Customization**:
- Change `default_days` to download different date ranges
- Each timeframe has its own table in PostgreSQL
- Add new timeframes by following the same pattern

### 4. Database Configuration

```yaml
database:
  host: "localhost"
  port: 5432
  name: "postgres"
  user: "postgres"
  password: "admin"
  conflict_strategy: "DO_NOTHING"  # Or "DO_UPDATE" to replace
  batch_size: 1000  # Records per batch
```

### 5. IBKR Connection

```yaml
ibkr:
  host: "127.0.0.1"
  port: 4002
  client_id: 1
  connection_timeout: 30
  request_timeout: 60
  what_to_show: "TRADES"  # Real volume data!
  use_rth: true  # Regular Trading Hours
```

### 6. Savepoint Configuration

```yaml
savepoint:
  file_path: "~/.tradingagents/download_status.json"
  save_interval: 1  # Save after each ticker
  keep_history: true
  history_path: "~/.tradingagents/download_history/"
```

### 7. Performance Settings

```yaml
performance:
  parallel_workers: 3  # 1-5 recommended
  max_parallel_tickers: 5
  rate_limit_ms: 1000  # Delay between IBKR requests
```

---

## Usage

### Basic Usage (Single-Threaded)

```bash
# Download with default config
python scripts/download_with_config.py

# Download with specific config
python scripts/download_with_config.py --config my_config.yaml

# Resume from last savepoint
python scripts/download_with_config.py --resume

# Start fresh (ignore savepoint)
python scripts/download_with_config.py --fresh
```

### Parallel Download (Recommended)

```bash
# Download with 3 parallel workers
python scripts/download_parallel_orchestrator.py

# Download with custom config
python scripts/download_parallel_orchestrator.py --config my_config.yaml

# Download with 5 parallel workers
python scripts/download_parallel_orchestrator.py --workers 5

# Start fresh (don't resume)
python scripts/download_parallel_orchestrator.py --fresh
```

### Partial Downloads

```bash
# Edit download_config.yaml to enable only certain tickers:
tickers:
  AAPL:
    enabled: true
  MSFT:
    enabled: true
  NVDA:
    enabled: false  # Skip this one

# Then run
python scripts/download_parallel_orchestrator.py
```

### Custom Date Ranges

```yaml
# Edit download_config.yaml timeframes:
timeframes:
  daily:
    default_days: 1825  # 5 years instead of 20
  5min:
    default_days: 180   # 6 months instead of 1 year
```

---

## Savepoint Management

### Savepoint Format

The savepoint JSON tracks status for each ticker/timeframe:

```json
{
  "created_at": "2026-09-06T12:00:00",
  "last_updated": "2026-09-06T13:45:00",
  "session_id": "20260906_120000",
  "tickers": {
    "AAPL": {
      "status": "completed",
      "started_at": "2026-09-06T12:00:00",
      "completed_at": "2026-09-06T12:15:00",
      "timeframes": {
        "1min": {
          "status": "completed",
          "started_at": "2026-09-06T12:00:00",
          "completed_at": "2026-09-06T12:03:00",
          "records": 1950,
          "bytes": 140000,
          "error": null,
          "retry_count": 0
        },
        "daily": {
          "status": "completed",
          "records": 63,
          "bytes": 4000
        }
      }
    }
  }
}
```

### Resuming from Interruption

```bash
# If download fails halfway:
# 1. Fix the issue (IBKR connection, etc.)
# 2. Run again - it auto-resumes from last savepoint

python scripts/download_parallel_orchestrator.py --resume

# Shows:
# [RESUME] Resuming from savepoint
# Pending tickers: 7  (3 already completed)
# Completed timeframes skipped, only pending ones downloaded
```

### Checking Download Status

```bash
# View savepoint file
cat ~/.tradingagents/download_status.json

# Shows:
# - Total tickers: 15
# - Completed: 8
# - Failed: 1
# - Pending: 6
# - Total records: 50,000
# - Total size: 45 MB
```

---

## File Format Selection

### Parquet (Recommended)

**Advantages**:
- 60-70% smaller file size vs CSV
- Columnar format = faster queries
- Type preservation (dates, decimals)
- Compression built-in
- Better for time-series data

**File size (1-day AAPL, 63 bars)**:
- CSV: 4.1 KB
- Parquet (snappy): ~2.5 KB

**Example**:
```
~/.tradingagents/data_downloads/AAPL/daily/data_20260906.parquet
```

### CSV

**Advantages**:
- Human-readable
- Compatible with Excel
- No special libraries needed to read

**Example**:
```
~/.tradingagents/data_downloads/AAPL/daily/data_20260906.csv
```

### Configuration

```yaml
download:
  format: "parquet"      # Use Parquet for efficiency
  compression: "snappy"  # Or "gzip" for better compression
```

---

## Database Persistence

### Auto-Created Tables

The downloader automatically creates tables based on configuration:

```sql
-- historical_data_1min (auto-created)
CREATE TABLE historical_data_1min (
    id UUID PRIMARY KEY,
    ticker VARCHAR(20),
    date TIMESTAMP,
    open DECIMAL(10,4),
    high DECIMAL(10,4),
    low DECIMAL(10,4),
    close DECIMAL(10,4),
    volume BIGINT,
    created_at TIMESTAMP,
    data_source VARCHAR(50),
    UNIQUE(ticker, date)
);

-- Same for: historical_data_5min, historical_data_hourly, historical_data_daily
```

### Conflict Handling

```yaml
database:
  conflict_strategy: "DO_NOTHING"  # Skip duplicates (safe)
  # OR
  conflict_strategy: "DO_UPDATE"   # Replace old data (risky)
```

---

## Parallel Execution Strategy

### How It Works

1. **Main Process**: ParallelOrchestrator
   - Reads config
   - Loads savepoint
   - Spawns N worker processes

2. **Worker Processes** (1 per ticker):
   - Download all timeframes for ticker
   - Save to files
   - Insert to database
   - Update savepoint

3. **Shared State**: Savepoint JSON
   - Workers write independently
   - Last-write-wins for conflicts (safe)
   - Used for resumption

### Recommended Settings

```yaml
performance:
  parallel_workers: 3      # Safe default
  # For faster machines:
  parallel_workers: 5      # Max recommended
  
  # For slower connections:
  parallel_workers: 1      # Sequential (safest)
  
  rate_limit_ms: 1000      # 1 second between IBKR requests
```

### Monitoring Parallel Downloads

```
[START] AAPL   - Starting download
[START] MSFT   - Starting download
[START] NVDA   - Starting download
[OK]    NVDA   - Completed (45.2s)
[OK]    AAPL   - Completed (52.1s)
[OK]    MSFT   - Completed (48.7s)
[START] AMZN   - Starting download
...
```

---

## Advanced Usage

### Custom Date Range per Ticker

Create separate config files:

```yaml
# config_2024.yaml
timeframes:
  daily:
    default_days: 365  # 2024 only

# config_historical.yaml
timeframes:
  daily:
    default_days: 7300  # 20 years
```

Then run separately:

```bash
python scripts/download_parallel_orchestrator.py --config config_2024.yaml
python scripts/download_parallel_orchestrator.py --config config_historical.yaml
```

### Resume Failed Ticker

```bash
# Edit savepoint to mark ticker as failed:
# "AAPL": { "status": "failed" }

# Then re-run - will retry AAPL:
python scripts/download_parallel_orchestrator.py
```

### Export Savepoint Data

```python
from scripts.download_savepoint import DownloadSavepoint

sp = DownloadSavepoint("~/.tradingagents/download_status.json")
summary = sp.get_summary()
print(summary)

# Output:
# {
#   'total_tickers': 15,
#   'completed_tickers': 8,
#   'failed_tickers': 1,
#   'pending_tickers': 6,
#   'total_records': 50000,
#   'total_bytes': 47185920
# }
```

---

## Troubleshooting

### Issue: "Config file not found"
```bash
# Make sure config is in project root
ls -la download_config.yaml

# Or specify full path
python scripts/download_parallel_orchestrator.py --config /path/to/download_config.yaml
```

### Issue: "Connection timeout"
```bash
# Check IBKR is running
ps aux | grep Gateway  # or TWS

# Verify host/port in config
ibkr:
  host: "127.0.0.1"
  port: 4002
```

### Issue: "PostgreSQL permission denied"
```bash
# Verify credentials in config
database:
  user: "postgres"
  password: "admin"

# Test connection
psql -U postgres -h localhost -d postgres
```

### Issue: Downloads stop/hang
```bash
# Check savepoint for failed tickers
cat ~/.tradingagents/download_status.json | grep "failed"

# Fix the issue, then resume
python scripts/download_parallel_orchestrator.py --resume
```

---

## Performance Tips

1. **Use Parquet format** → 60% smaller files
2. **Increase workers** → Faster overall (but more IBKR load)
3. **Batch larger inserts** → Faster DB writes
4. **Skip unnecessary timeframes** → Less data to download
5. **Run overnight** → Less network interference

---

## Next Steps

1. **Review configuration**: Edit `download_config.yaml` for your needs
2. **Test single ticker**: `python scripts/download_with_config.py --ticker AAPL`
3. **Run parallel**: `python scripts/download_parallel_orchestrator.py`
4. **Monitor progress**: Watch the output, check savepoint
5. **Resume if needed**: Same command auto-resumes from last point

---

## Summary

| Feature | Benefit |
|---------|---------|
| Configuration-driven | No code changes needed |
| Resumable | Restart from last failed point |
| Parallel | 3-5x faster downloads |
| File-based | Parquet = 60% smaller |
| Status tracking | JSON savepoint |
| Database auto-insert | Direct to PostgreSQL |

**Result**: Production-grade download infrastructure that is configurable, reliable, and efficient.

