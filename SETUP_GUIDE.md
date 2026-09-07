# TradingAgents System Setup Guide

**Last Updated:** 2026-09-06  
**System Version:** 1.0

---

## Table of Contents

1. [System Architecture](#system-architecture)
2. [Prerequisites](#prerequisites)
3. [Installation Steps](#installation-steps)
4. [Database Setup](#database-setup)
5. [Data Download & Caching](#data-download--caching)
6. [Strategies & Backtesting](#strategies--backtesting)
7. [Key Learnings & Limitations](#key-learnings--limitations)

---

## System Architecture

### Components

```
┌─────────────────────────────────────────────────────┐
│ TradingAgents System Architecture                    │
├─────────────────────────────────────────────────────┤
│                                                      │
│  Market Data Sources                                │
│  ├─ IBKR (Interactive Brokers) API                  │
│  │  └─ 4002 port (IB Gateway)                       │
│  │  └─ Historical data limits: 1yr daily, 6mo 5min  │
│  │                                                   │
│  Data Storage Layer                                  │
│  ├─ PostgreSQL (Port 5433)                          │
│  │  └─ 4 timeframe tables (daily, hourly, 5min, 1min)
│  │  └─ Current data: AAPL (46K records), AMZN (5.7K)
│  │                                                   │
│  ├─ Redis Cache (Port 6379)                         │
│  │  └─ 52,057 records cached                        │
│  │  └─ TTL: 30d (daily), 7d (hourly), 2d (5min), 1d
│  │                                                   │
│  Processing Layer                                    │
│  ├─ Download Scripts                                │
│  │  ├─ V1: download_market_data.py (PRODUCTION)     │
│  │  └─ V2: download_market_data_v2_sequential.py    │
│  │                                                   │
│  ├─ Redis Loader                                    │
│  │  └─ load_postgres_to_redis.py                    │
│  │                                                   │
│  Strategy & Backtesting Layer                       │
│  ├─ 7 Strategies (momentum, RSI, MACD, etc)         │
│  ├─ Parallel backtesting engine                     │
│  └─ Report generation (JSON, CSV, HTML)             │
│                                                      │
└─────────────────────────────────────────────────────┘
```

### Data Flow

```
IBKR API (IB Gateway)
    ↓
Download Scripts (V1/V2-Sequential)
    ↓
PostgreSQL (5433) [Primary Storage]
    ↓
Redis Cache (6379) [Fast Access]
    ↓
Strategy Engine
    ↓
Backtest Results (JSON/CSV/HTML)
```

---

## Prerequisites

### Software Requirements

```
✓ Python 3.8+
✓ PostgreSQL 12+
✓ Redis 6.0+
✓ IB Gateway (Interactive Brokers)
✓ Git
```

### Python Packages

```bash
pip install psycopg2-binary pandas redis ib_async
```

### Network Requirements

```
IBKR API:      127.0.0.1:4002
PostgreSQL:    localhost:5433
Redis:         localhost:6379
```

---

## Installation Steps

### Step 1: Install PostgreSQL

**Windows (Local Installation, Not Docker)**

```bash
# Download from: https://www.postgresql.org/download/windows/
# Install with:
# - Port: 5433 (not default 5432)
# - Password: admin
# - Admin user: postgres
```

**Verify Installation:**

```bash
psql -h localhost -p 5433 -U postgres -c "SELECT version();"
```

### Step 2: Install Redis

**Windows (Local Installation)**

```bash
# Download from: https://github.com/microsoftarchive/redis/releases
# Or use WSL2: wsl redis-server
```

**Verify Installation:**

```bash
redis-cli -h localhost -p 6379 ping
# Should return: PONG
```

### Step 3: Install IB Gateway

```bash
# Download from: https://www.interactivebrokers.com/en/software/tws/twslaunch.exe
# Launch and login with IBKR credentials
# Ensure API is enabled: Configure → API → Enable ActiveX and Socket Clients
```

### Step 4: Create Database Schema

```bash
# Navigate to project root
cd C:\Trading\TradingAgents

# Apply schema
psql -h localhost -p 5433 -U postgres -d postgres -f db/01_create_tables.sql

# Verify tables created
psql -h localhost -p 5433 -U postgres -d postgres -c "\dt"
```

---

## Database Setup

### Table Schema

All tables follow this structure:

```sql
CREATE TABLE historical_data_<timeframe> (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(10) NOT NULL,
    date TIMESTAMP NOT NULL,
    open DECIMAL(10,2),
    high DECIMAL(10,2),
    low DECIMAL(10,2),
    close DECIMAL(10,2),
    volume BIGINT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(ticker, date)
);
```

### Tables

| Table | Purpose | Typical Size | Default Retention |
|-------|---------|--------------|-------------------|
| `historical_data_daily` | Daily OHLCV data | 365 rows/ticker | 1 year |
| `historical_data_hourly` | Hourly OHLCV data | 2500+ rows/ticker | 1 year |
| `historical_data_5min` | 5-minute OHLCV data | 20K+ rows/ticker | 6 months |
| `historical_data_1min` | 1-minute OHLCV data | 23K+ rows/ticker | 2 months |

### Backup & Restore

```bash
# Backup from PostgreSQL
pg_dump -h localhost -p 5433 -U postgres -d postgres > backup.sql

# Restore to new instance
psql -h localhost -p 5433 -U postgres -d postgres < backup.sql
```

---

## Data Download & Caching

### Available Tickers

Current system has data for:
- **AAPL** (Apple): Complete data across all timeframes
- **AMZN** (Amazon): Partial data (no 1-minute)
- More tickers can be added via download scripts

### IBKR API Limitations

```
Important: These are hard limits from IBKR API
├─ Daily:    1 year maximum (not 10 years)
├─ Hourly:   1 year maximum
├─ 5-minute: 6 months maximum (180 days)
└─ 1-minute: 2 months safe limit (60 days)

Request larger ranges = Timeout errors
```

### Download Workflow

#### Option 1: V1 Downloader (RECOMMENDED - Production Ready)

**Best for:** Single ticker, all timeframes, simple & reliable

```bash
python scripts/download_market_data.py AAPL
```

**What it does:**
- Downloads 365d daily, 365d hourly, 180d 5min, 60d 1min
- Saves raw + processed CSV files
- Inserts to PostgreSQL
- Single threaded, no concurrency issues
- Typical runtime: 2-3 minutes

**Output:**
```
✓ 40,315 records downloaded
✓ Files saved to: ~/.tradingagents/data_downloads/AAPL/historical/
✓ Data inserted to PostgreSQL
```

#### Option 2: V2-Sequential (Advanced)

**Best for:** Multiple tickers, automatic chunk management, retry logic

```bash
python scripts/download_market_data_v2_sequential.py AAPL
```

**Features:**
- Database-aware (skips already-downloaded ranges)
- Intelligent chunking (1yr daily, 1mo hourly, 5d 5min, 1d 1min)
- 3 retries per chunk with exponential backoff
- Fully sequential (no concurrency)
- Comprehensive logging

**Configuration in code:**

```python
self.lookback = {
    'daily': timedelta(days=365),      # 1 year
    'hourly': timedelta(days=365),     # 1 year
    '5min': timedelta(days=180),       # 6 months
    '1min': timedelta(days=60),        # 60 days (safe)
}

self.chunk_sizes = {
    'daily': timedelta(days=365),      # 1-year chunks
    'hourly': timedelta(days=30),      # 1-month chunks
    '5min': timedelta(days=5),         # 5-day chunks
    '1min': timedelta(days=1),         # 1-day chunks
}
```

### Caching with Redis

#### Load Data to Cache

```bash
# Clear old cache
redis-cli -h localhost -p 6379 --raw FLUSHDB

# Load PostgreSQL to Redis
python scripts/load_postgres_to_redis.py
```

**What it does:**
- Reads all tickers from PostgreSQL
- Converts to JSON format
- Stores in Redis with TTL
- Output: 52,057 records cached

**Redis Key Pattern:**

```
market_data:<ticker>:<timeframe>
Example: market_data:AAPL:daily
```

**TTL Configuration:**

```python
self.ttl = {
    'daily': 30 * 86400,      # 30 days
    'hourly': 7 * 86400,      # 7 days
    '5min': 2 * 86400,        # 2 days
    '1min': 1 * 86400,        # 1 day
}
```

#### Verify Redis Cache

```bash
redis-cli
> AUTH admin
> INFO stats
> KEYS market_data:*
> GET market_data:AAPL:daily
```

---

## Strategies & Backtesting

### Available Strategies

| Strategy | Type | Best For | Win Rate (AAPL 5min) |
|----------|------|----------|----------------------|
| **MeanReversionRSI** | Mean Reversion | Quick reversals | 100% |
| **VolatilityBreakout** | Breakout | Trending markets | 43.56% |
| **MovingAverageCrossover** | Trend Following | Sustained moves | 40.60% |
| **MacdStrategy** | Momentum | Moderate trends | 37.12% |
| **RsiDivergence** | Divergence | Reversal points | 39.23% |
| SwingTradingStrategy | Swing | Multi-day moves | - |
| MultiTimeframeStrategy | Multi-TF | Confluence | - |

### Run Backtests

```bash
# Run all strategies (parallel execution)
python scripts/backtest_all_strategies.py

# Configuration
Initial Capital: $10,000
Commission: 0.001% per trade
Tickers: 15 configured
Timeframes: 4 (daily, hourly, 5min, 1min)
```

**Expected Output:**

```
[SUMMARY] Top 10 Best Performing Strategies
Rank  Strategy                  Combo       Trades   Win%     P&L      Return
────────────────────────────────────────────────────────────────────────────
1     MeanReversionRSI          AAPL_5min   15       100.00%  +$105.92 +1.06%
2     VolatilityBreakout        AAPL_5min   163      43.56%   +$98.12  +0.98%
3     MovingAverageCrossover    AAPL_5min   234      40.60%   +$85.27  +0.85%
...
```

### Reports Location

```
reports/
├── backtest_all_strategies_report.json
├── backtest_results.csv
└── backtest_results.html
```

---

## Key Learnings & Limitations

### What Works

✅ **V1 Downloader**
- Single threaded, proven reliable
- Downloads 40K+ records in 2-3 minutes
- No concurrency issues
- Recommended for production

✅ **Database-Aware Downloads**
- Queries min/max dates from PostgreSQL
- Only downloads missing data
- Saves API calls and time

✅ **Redis Caching**
- 52K records cached and fast accessible
- TTL-based expiration
- Reduces database load

✅ **Sequential Processing**
- V2-Sequential with no concurrency
- Intelligent chunking prevents timeouts
- Retry logic with exponential backoff

### Known Limitations

⚠️ **IBKR API Limits (Hard Constraints)**

```
Cannot be changed or worked around:
├─ Daily:    1 year max (not 10 years)
├─ Hourly:   1 year max
├─ 5-minute: 6 months max
└─ 1-minute: 2 months max
```

Solution: Request reasonable date ranges or split into multiple downloads

⚠️ **Concurrency Issues with V2 (3-layer model)**

```
3 IB Clients ÷ 12+ Concurrent Threads = Thread Starvation
Problem: ThreadPoolExecutor concurrency overwhelms IB Gateway
Solution: Use V1 or configure V2 to 1 worker per timeframe
```

⚠️ **Limited Historical Data**

```
Current system only has:
├─ AAPL: Partial (1 year daily)
├─ AMZN: Minimal (2-3 months daily)
└─ Others: None

To expand: Run downloads for each ticker
```

### Recommended Configuration

```
Production Environment Setup:
├─ Download: V1 (download_market_data.py)
├─ Frequency: Daily after market close
├─ Storage: PostgreSQL 5433
├─ Cache: Redis 6379
├─ Strategies: Top 3 (MeanReversionRSI, VolatilityBreakout, MacdStrategy)
└─ Backtesting: Weekly analysis
```

---

## Quick Start Checklist

```
System Setup:
□ PostgreSQL installed on port 5433
□ Redis installed on port 6379
□ IB Gateway running (port 4002)
□ Python packages installed
□ Database schema created (db/01_create_tables.sql)

Data Preparation:
□ Run V1 downloader for AAPL
□ Verify PostgreSQL has data
□ Load Redis cache
□ Check Redis for 50K+ records

Testing:
□ Run sample backtest
□ Verify results output to reports/
□ Check top performing strategy
□ Monitor execution time (~5-10 min)

Production Ready:
□ Configure automated downloads (daily)
□ Set up monitoring/alerts
□ Backup PostgreSQL regularly
□ Document custom tickers added
```

---

## Support & Troubleshooting

### Common Issues

**Issue: "Connection refused: port 5433"**
```
→ PostgreSQL not running
→ Start service: services.msc → PostgreSQL → Start
→ Verify: psql -h localhost -p 5433 -U postgres
```

**Issue: "Redis connection failed"**
```
→ Redis not running
→ Start service: redis-server
→ Verify: redis-cli ping
```

**Issue: "IB connection timeout"**
```
→ IB Gateway not running
→ Ensure API enabled in Configuration
→ Port 4002 accessible
→ Check IBKR account status/IP restrictions
```

**Issue: "IBKR timeout on historical data"**
```
→ Date range too large (exceeds 1 year for daily)
→ Use configured limits (see Data Download section)
→ Check IBKR server status
```

---

## Files & Directories

```
TradingAgents/
├── db/
│   └── 01_create_tables.sql          [Database schema]
│
├── scripts/
│   ├── download_market_data.py        [V1 Downloader - PRODUCTION]
│   ├── download_market_data_v2_sequential.py  [V2 Sequential]
│   ├── load_postgres_to_redis.py      [Cache Loader]
│   └── backtest_all_strategies.py     [Backtesting Engine]
│
├── strategies/
│   ├── improved_momentum_strategy.py
│   ├── ma_rsi_strategy.py
│   ├── swing_trading_strategy.py
│   └── ... (more strategies)
│
├── reports/                           [Output: Results & Analysis]
│   ├── backtest_all_strategies_report.json
│   ├── backtest_results.csv
│   └── backtest_results.html
│
├── ~/.tradingagents/
│   ├── data_downloads/                [CSV Files]
│   │   └── AAPL/historical/
│   │       ├── marketdata_AAPL_daily_*.csv
│   │       ├── marketdata_AAPL_hourly_*.csv
│   │       ├── marketdata_AAPL_5min_*.csv
│   │       └── marketdata_AAPL_1min_*.csv
│   │
│   └── download_logs/                 [Execution Logs]
│       └── download_20260906_*.log
│
└── SETUP_GUIDE.md                     [This file]
```

---

## Next Steps

1. **Set up local PostgreSQL on port 5433**
2. **Create database tables from db/01_create_tables.sql**
3. **Run V1 downloader for AAPL**
4. **Load data to Redis cache**
5. **Run backtests and verify results**
6. **Configure automated downloads**

---

**Generated:** 2026-09-06  
**Author:** TradingAgents Development Team  
**Version:** 1.0
