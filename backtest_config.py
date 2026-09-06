"""
Backtest Configuration
Centralized settings for all backtest scripts
"""

import os
from pathlib import Path

# Base directories
BASE_DIR = Path(__file__).parent
REPORTS_DIR = BASE_DIR / "reports"
DOCS_DIR = BASE_DIR / "docs"
SCRIPTS_DIR = BASE_DIR / "scripts"

# Create directories if they don't exist
REPORTS_DIR.mkdir(exist_ok=True)
DOCS_DIR.mkdir(exist_ok=True)

# Report naming convention
BACKTEST_REPORT_PREFIX = "backtest"
BACKTEST_CSV_SUFFIX = "_results.csv"
BACKTEST_JSON_SUFFIX = "_report.json"
BACKTEST_LOG_SUFFIX = ".log"

# Default settings
DEFAULT_COMMISSION = 0.001 / 100  # 0.001%
DEFAULT_INITIAL_CAPITAL = 10000
DEFAULT_RISK_PER_TRADE = 0.01  # 1%

# Database configuration
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "postgres")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "admin")

# Tickers to backtest
TICKERS = ["AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "TSLA", "AMD", "AVGO", "JPM", "GS", "SPY", "QQQ", "IWM", "DIA"]

# Timeframes
TIMEFRAMES = ["1min", "5min", "1h", "1d"]

def get_report_path(filename: str) -> str:
    """Get full path for a report file."""
    return str(REPORTS_DIR / filename)

def get_doc_path(filename: str) -> str:
    """Get full path for a documentation file."""
    return str(DOCS_DIR / filename)

def get_script_path(filename: str) -> str:
    """Get full path for a script file."""
    return str(SCRIPTS_DIR / filename)

if __name__ == "__main__":
    print(f"Reports Directory: {REPORTS_DIR}")
    print(f"Docs Directory: {DOCS_DIR}")
    print(f"Scripts Directory: {SCRIPTS_DIR}")
    print(f"\nConfiguration loaded successfully!")
