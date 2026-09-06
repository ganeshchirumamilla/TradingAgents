"""Local data cache for historical market data and offline analysis.

Provides persistent storage for IBKR historical bars, fundamentals,
and other market data to enable offline analysis and fast backtesting.
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

import pandas as pd

logger = logging.getLogger(__name__)


class LocalDataCache:
    """Manages local caching of historical market data."""

    def __init__(self, cache_dir: str | Path = None):
        """Initialize cache manager.

        Args:
            cache_dir: Directory to store cached data. Defaults to
                      ~/.tradingagents/data_cache
        """
        if cache_dir is None:
            cache_dir = Path.home() / ".tradingagents" / "data_cache"
        else:
            cache_dir = Path(cache_dir).expanduser()

        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._manifest_file = self.cache_dir / "cache_manifest.json"
        self._manifest = self._load_manifest()

    def _load_manifest(self) -> dict:
        """Load or initialize cache manifest."""
        if self._manifest_file.exists():
            with open(self._manifest_file) as f:
                return json.load(f)
        return {"tickers": {}, "last_updated": None}

    def _save_manifest(self):
        """Save manifest to disk."""
        with open(self._manifest_file, "w") as f:
            json.dump(self._manifest, f, indent=2)

    def store_historical_data(
        self,
        ticker: str,
        data,
        data_type: str = "daily",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> bool:
        """Store historical bars data in cache.

        Args:
            ticker: Stock ticker symbol
            data: DataFrame or list of bar objects with OHLCV
            data_type: Type of data (daily, hourly, minute)
            start_date: YYYY-MM-DD format
            end_date: YYYY-MM-DD format

        Returns:
            True if storage successful
        """
        try:
            ticker = ticker.upper()
            ticker_dir = self.cache_dir / ticker
            ticker_dir.mkdir(exist_ok=True)

            # Convert to DataFrame if needed
            df = self._bars_to_dataframe(data)
            if df.empty:
                logger.warning(f"No data to cache for {ticker}")
                return False

            # Generate filename with date range
            date_range = f"{start_date or 'all'}_{end_date or 'current'}"
            filename = f"{data_type}_{date_range}.csv"
            filepath = ticker_dir / filename

            # Store CSV
            df.to_csv(filepath, index=False)
            logger.info(f"Cached {len(df)} {data_type} bars for {ticker} → {filepath}")

            # Update manifest
            if ticker not in self._manifest["tickers"]:
                self._manifest["tickers"][ticker] = {}

            self._manifest["tickers"][ticker][data_type] = {
                "filename": str(filename),
                "rows": len(df),
                "start_date": str(df.iloc[0]["date"]) if "date" in df.columns else None,
                "end_date": str(df.iloc[-1]["date"]) if "date" in df.columns else None,
                "cached_at": datetime.now().isoformat(),
            }
            self._manifest["last_updated"] = datetime.now().isoformat()
            self._save_manifest()

            return True

        except Exception as e:
            logger.error(f"Error caching data for {ticker}: {e}")
            return False

    def get_historical_data(
        self,
        ticker: str,
        data_type: str = "daily",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Optional[pd.DataFrame]:
        """Retrieve cached historical data.

        Args:
            ticker: Stock ticker symbol
            data_type: Type of data (daily, hourly, minute)
            start_date: YYYY-MM-DD format (inclusive)
            end_date: YYYY-MM-DD format (inclusive)

        Returns:
            DataFrame with cached data, or None if not found
        """
        ticker = ticker.upper()
        ticker_dir = self.cache_dir / ticker

        if not ticker_dir.exists():
            logger.debug(f"No cache directory for {ticker}")
            return None

        # Find matching cache file
        matching_files = list(ticker_dir.glob(f"{data_type}_*.csv"))
        if not matching_files:
            logger.debug(f"No {data_type} cache for {ticker}")
            return None

        try:
            # Use most recent cache file
            filepath = sorted(matching_files)[-1]
            df = pd.read_csv(filepath)

            # Filter by date range if provided
            if start_date or end_date:
                if "date" in df.columns:
                    df["date"] = pd.to_datetime(df["date"])
                    if start_date:
                        df = df[df["date"] >= start_date]
                    if end_date:
                        df = df[df["date"] <= end_date]

            logger.debug(f"Retrieved {len(df)} cached {data_type} bars for {ticker}")
            return df if not df.empty else None

        except Exception as e:
            logger.error(f"Error reading cache for {ticker}: {e}")
            return None

    def is_cache_fresh(
        self,
        ticker: str,
        data_type: str = "daily",
        max_age_days: int = 7,
    ) -> bool:
        """Check if cached data is fresh enough.

        Args:
            ticker: Stock ticker symbol
            data_type: Type of data (daily, hourly, minute)
            max_age_days: Maximum age in days to consider fresh

        Returns:
            True if cache exists and is fresh
        """
        ticker = ticker.upper()

        if ticker not in self._manifest["tickers"]:
            return False

        ticker_info = self._manifest["tickers"][ticker]
        if data_type not in ticker_info:
            return False

        cached_at = datetime.fromisoformat(ticker_info[data_type]["cached_at"])
        age = datetime.now() - cached_at
        is_fresh = age < timedelta(days=max_age_days)

        logger.debug(
            f"{ticker} cache is {age.days}d old, "
            f"fresh={is_fresh} (max {max_age_days}d)"
        )
        return is_fresh

    def cleanup_old_data(self, older_than_days: int = 30) -> int:
        """Delete cached data older than specified days.

        Args:
            older_than_days: Delete caches older than this many days

        Returns:
            Number of files deleted
        """
        cutoff = datetime.now() - timedelta(days=older_than_days)
        deleted_count = 0

        for ticker_dir in self.cache_dir.glob("*/"):
            if ticker_dir.name == "cache_manifest.json":
                continue

            for cache_file in ticker_dir.glob("*.csv"):
                mtime = datetime.fromtimestamp(cache_file.stat().st_mtime)
                if mtime < cutoff:
                    cache_file.unlink()
                    logger.info(f"Deleted old cache: {cache_file}")
                    deleted_count += 1

        return deleted_count

    def clear_ticker_cache(self, ticker: str) -> bool:
        """Clear all cached data for a ticker.

        Args:
            ticker: Stock ticker symbol

        Returns:
            True if successful
        """
        ticker = ticker.upper()
        ticker_dir = self.cache_dir / ticker

        try:
            if ticker_dir.exists():
                for f in ticker_dir.glob("*"):
                    f.unlink()
                ticker_dir.rmdir()
                logger.info(f"Cleared cache for {ticker}")

                # Update manifest
                if ticker in self._manifest["tickers"]:
                    del self._manifest["tickers"][ticker]
                    self._save_manifest()

            return True
        except Exception as e:
            logger.error(f"Error clearing cache for {ticker}: {e}")
            return False

    def get_cached_tickers(self) -> list[str]:
        """Return list of tickers with cached data.

        Returns:
            List of ticker symbols
        """
        return list(self._manifest["tickers"].keys())

    def get_cache_stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dict with cache statistics
        """
        stats = {
            "total_tickers": len(self._manifest["tickers"]),
            "total_size_mb": 0,
            "last_updated": self._manifest.get("last_updated"),
            "tickers": {},
        }

        for ticker_dir in self.cache_dir.glob("*/"):
            if ticker_dir.name == "cache_manifest.json":
                continue

            size = sum(f.stat().st_size for f in ticker_dir.glob("*.csv"))
            stats["total_size_mb"] += size / 1024 / 1024

            ticker = ticker_dir.name
            stats["tickers"][ticker] = {
                "size_mb": size / 1024 / 1024,
                "files": len(list(ticker_dir.glob("*.csv"))),
            }

        return stats

    def status(self) -> str:
        """Print human-readable cache status."""
        stats = self.get_cache_stats()
        msg = f"""
Cache Status:
- Location: {self.cache_dir}
- Total Tickers: {stats['total_tickers']}
- Total Size: {stats['total_size_mb']:.1f} MB
- Last Updated: {stats['last_updated']}

Cached Tickers:
"""
        for ticker, info in sorted(stats["tickers"].items()):
            msg += f"  {ticker}: {info['size_mb']:.1f} MB ({info['files']} files)\n"

        return msg

    @staticmethod
    def _bars_to_dataframe(data) -> pd.DataFrame:
        """Convert IBKR bars or list to DataFrame.

        Handles ib_async Bar objects and raw list data.
        """
        if isinstance(data, pd.DataFrame):
            return data

        if not data:
            return pd.DataFrame()

        # Convert list of Bar objects or dicts to DataFrame
        records = []
        for bar in data:
            if hasattr(bar, "__dict__"):
                records.append(bar.__dict__)
            elif isinstance(bar, dict):
                records.append(bar)
            else:
                # Try to extract OHLCV
                records.append(
                    {
                        "date": getattr(bar, "date", None),
                        "open": getattr(bar, "open", None),
                        "high": getattr(bar, "high", None),
                        "low": getattr(bar, "low", None),
                        "close": getattr(bar, "close", None),
                        "volume": getattr(bar, "volume", None),
                    }
                )

        return pd.DataFrame(records)
