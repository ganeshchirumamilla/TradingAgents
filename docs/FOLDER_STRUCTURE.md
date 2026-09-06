# Project Folder Structure

## Overview
The project is now organized with dedicated folders for reports, documentation, scripts, and data.

## Directory Layout

```
C:\Trading\TradingAgents/
├── reports/                          # All backtest results, reports, CSVs, JSONs, logs
│   ├── backtest_all_strategies_results.csv    # Detailed results for all strategy combinations
│   ├── backtest_strategy_summary.csv           # Summary by strategy
│   ├── backtest_ticker_summary.csv             # Summary by ticker
│   ├── backtest_timeframe_summary.csv          # Summary by timeframe
│   ├── backtest_all_strategies_report.json     # Detailed JSON report
│   ├── backtest_results_report.html            # Interactive HTML report
│   ├── backtest_all_strategies.log             # Console output log
│   └── [other historical results and reports]
│
├── docs/                             # All documentation and markdown files
│   ├── FOLDER_STRUCTURE.md          # This file
│   ├── BACKTEST_SETUP_COMPLETE.md
│   ├── DEPLOYMENT_CHECKLIST.md
│   ├── DAILY_PIPELINE_GUIDE.md
│   ├── TECHNICAL_FLOW.md
│   └── [other documentation files]
│
├── scripts/                          # All Python scripts
│   ├── backtest_all_strategies.py              # Multi-strategy parallel backtest
│   ├── backtest_mean_reversion_direct.py       # Mean reversion strategy backtest
│   ├── download_ibkr_multibar_data.py          # Download data from IBKR
│   ├── probe_data_availability.py              # Probe IBKR for available data
│   ├── load_data_to_redis.py                   # Load data into Redis
│   └── [other scripts]
│
├── backtest_config.py                # Central configuration for all backtest scripts
├── create_reports.py                 # Script to convert JSON reports to CSV
├── cli/                              # CLI tools
├── tradingagents/                    # Main trading agents package
├── tests/                            # Test files
└── README.md                         # Main project documentation
```

## File Organization Rules

### Reports Folder (`reports/`)
Stores all backtest results, analysis outputs, and logs:
- **CSV Files**: Detailed backtest results and summaries
- **JSON Files**: Structured data for further analysis
- **HTML Files**: Interactive reports for visualization
- **Log Files**: Console output and execution logs

### Docs Folder (`docs/`)
Stores all documentation and guides:
- **Markdown Files**: Technical documentation, guides, setup instructions
- **PDF Files**: Long-form documentation (future)
- **Configuration Guides**: Setup and deployment guides

### Scripts Folder (`scripts/`)
Stores all Python scripts:
- **Backtest Scripts**: Strategy backtesting engines
- **Data Scripts**: Data download and processing
- **Utility Scripts**: Helper and utility functions

## Backtest Output Convention

All backtest scripts now follow this naming convention for output files:

```
backtest_[name]_results.csv           # Detailed CSV results
backtest_[name]_report.json           # Structured JSON report
backtest_[name]_summary.csv           # Summary statistics
backtest_[name].log                   # Execution log
backtest_[name]_report.html           # Interactive HTML report
```

### Examples:
- `backtest_all_strategies_results.csv`
- `backtest_mean_reversion_report.json`
- `backtest_multi_timeframe.log`

## Configuration

All backtest scripts use `backtest_config.py` for:
- Default paths (reports, docs, scripts directories)
- Database credentials
- Default parameters (commission, capital, tickers, timeframes)
- Ticker and timeframe lists

### Usage in Scripts:
```python
from backtest_config import get_report_path, get_doc_path, REPORTS_DIR, DOCS_DIR

# Save report
report_path = get_report_path('my_backtest_report.csv')
df.to_csv(report_path)

# Save documentation
doc_path = get_doc_path('my_analysis.md')
with open(doc_path, 'w') as f:
    f.write("# Analysis\n...")
```

## Latest Backtest Results

### Multi-Strategy Parallel Backtest (Sept 6, 2026)
**Files Location**: `reports/`
- `backtest_all_strategies_results.csv` - 252 strategy/ticker/timeframe combinations
- `backtest_all_strategies_report.json` - Detailed results
- `backtest_all_strategies.log` - Execution log
- `backtest_strategy_summary.csv` - Performance by strategy
- `backtest_ticker_summary.csv` - Performance by ticker
- `backtest_timeframe_summary.csv` - Performance by timeframe

**Key Results**:
- 7 strategies tested
- 15 tickers analyzed
- 4 timeframes (1-min, 5-min, 1-hour, 1-day)
- 246 profitable combinations (97.6% success rate)
- Commission: 0.001% per trade

## Best Practices

1. **Always save reports to `reports/` folder**
   ```python
   from backtest_config import get_report_path
   path = get_report_path('my_results.csv')
   ```

2. **Always save documentation to `docs/` folder**
   ```python
   from backtest_config import get_doc_path
   path = get_doc_path('my_guide.md')
   ```

3. **Use centralized configuration**
   ```python
   from backtest_config import DEFAULT_COMMISSION, TICKERS, TIMEFRAMES
   ```

4. **Follow naming conventions**
   - CSV: `backtest_[name]_results.csv`
   - JSON: `backtest_[name]_report.json`
   - Logs: `backtest_[name].log`
   - HTML: `backtest_[name]_report.html`

## Future Improvements

- [ ] Add automatic report generation and archiving
- [ ] Create report comparison tools
- [ ] Add automated backup of reports to cloud storage
- [ ] Implement report versioning and history tracking
- [ ] Create visualization dashboard for historical results
