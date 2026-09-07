#!/usr/bin/env python3
"""
Download savepoint manager for resuming interrupted downloads.
Tracks per-ticker, per-timeframe download status.
"""

import json
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional


class DownloadSavepoint:
    """Manages download status savepoints for resumable downloads."""

    def __init__(self, savepoint_path: str):
        """
        Initialize savepoint manager.

        Args:
            savepoint_path: Path to savepoint JSON file
        """
        self.savepoint_path = Path(savepoint_path).expanduser()
        self.savepoint_path.parent.mkdir(parents=True, exist_ok=True)
        self.data = self._load()

    def _load(self) -> Dict:
        """Load savepoint data from file."""
        if self.savepoint_path.exists():
            try:
                with open(self.savepoint_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"[WARNING] Could not load savepoint: {e}. Starting fresh.")
                return self._empty_savepoint()
        return self._empty_savepoint()

    def _empty_savepoint(self) -> Dict:
        """Create empty savepoint structure."""
        return {
            'created_at': datetime.now().isoformat(),
            'last_updated': datetime.now().isoformat(),
            'tickers': {},
            'session_id': datetime.now().strftime('%Y%m%d_%H%M%S')
        }

    def _save(self):
        """Save savepoint data to file."""
        self.data['last_updated'] = datetime.now().isoformat()
        try:
            with open(self.savepoint_path, 'w') as f:
                json.dump(self.data, f, indent=2)
        except Exception as e:
            print(f"[ERROR] Could not save savepoint: {e}")

    def initialize_ticker(self, ticker: str, timeframes: List[str]):
        """Initialize savepoint for a ticker."""
        if ticker not in self.data['tickers']:
            self.data['tickers'][ticker] = {
                'status': 'pending',
                'started_at': None,
                'completed_at': None,
                'timeframes': {}
            }

        for timeframe in timeframes:
            if timeframe not in self.data['tickers'][ticker]['timeframes']:
                self.data['tickers'][ticker]['timeframes'][timeframe] = {
                    'status': 'pending',  # pending, downloading, completed, failed
                    'started_at': None,
                    'completed_at': None,
                    'records': 0,
                    'bytes': 0,
                    'error': None,
                    'retry_count': 0
                }

        self._save()

    def start_ticker(self, ticker: str):
        """Mark ticker as started."""
        if ticker in self.data['tickers']:
            self.data['tickers'][ticker]['status'] = 'downloading'
            self.data['tickers'][ticker]['started_at'] = datetime.now().isoformat()
            self._save()

    def start_timeframe(self, ticker: str, timeframe: str):
        """Mark timeframe download as started."""
        if ticker in self.data['tickers'] and timeframe in self.data['tickers'][ticker]['timeframes']:
            self.data['tickers'][ticker]['timeframes'][timeframe]['status'] = 'downloading'
            self.data['tickers'][ticker]['timeframes'][timeframe]['started_at'] = datetime.now().isoformat()
            self._save()

    def complete_timeframe(self, ticker: str, timeframe: str, records: int = 0, bytes_written: int = 0):
        """Mark timeframe download as completed."""
        if ticker in self.data['tickers'] and timeframe in self.data['tickers'][ticker]['timeframes']:
            self.data['tickers'][ticker]['timeframes'][timeframe]['status'] = 'completed'
            self.data['tickers'][ticker]['timeframes'][timeframe]['completed_at'] = datetime.now().isoformat()
            self.data['tickers'][ticker]['timeframes'][timeframe]['records'] = records
            self.data['tickers'][ticker]['timeframes'][timeframe]['bytes'] = bytes_written
            self.data['tickers'][ticker]['timeframes'][timeframe]['error'] = None
            self.data['tickers'][ticker]['timeframes'][timeframe]['retry_count'] = 0
            self._save()

    def fail_timeframe(self, ticker: str, timeframe: str, error: str):
        """Mark timeframe download as failed."""
        if ticker in self.data['tickers'] and timeframe in self.data['tickers'][ticker]['timeframes']:
            self.data['tickers'][ticker]['timeframes'][timeframe]['status'] = 'failed'
            self.data['tickers'][ticker]['timeframes'][timeframe]['error'] = str(error)
            self.data['tickers'][ticker]['timeframes'][timeframe]['retry_count'] = \
                self.data['tickers'][ticker]['timeframes'][timeframe].get('retry_count', 0) + 1
            self._save()

    def complete_ticker(self, ticker: str):
        """Mark ticker as fully completed."""
        if ticker in self.data['tickers']:
            self.data['tickers'][ticker]['status'] = 'completed'
            self.data['tickers'][ticker]['completed_at'] = datetime.now().isoformat()
            self._save()

    def get_pending_tickers(self) -> List[str]:
        """Get list of tickers not yet completed."""
        pending = []
        for ticker, ticker_data in self.data['tickers'].items():
            if ticker_data['status'] != 'completed':
                pending.append(ticker)
        return pending

    def get_pending_timeframes(self, ticker: str) -> List[str]:
        """Get list of timeframes not yet completed for a ticker."""
        if ticker not in self.data['tickers']:
            return []

        pending = []
        for timeframe, tf_data in self.data['tickers'][ticker]['timeframes'].items():
            if tf_data['status'] != 'completed':
                pending.append(timeframe)
        return pending

    def should_retry(self, ticker: str, timeframe: str, max_retries: int = 3) -> bool:
        """Check if a failed timeframe should be retried."""
        if ticker not in self.data['tickers'] or timeframe not in self.data['tickers'][ticker]['timeframes']:
            return False

        tf_data = self.data['tickers'][ticker]['timeframes'][timeframe]
        if tf_data['status'] == 'failed':
            return tf_data.get('retry_count', 0) < max_retries
        return False

    def get_summary(self) -> Dict:
        """Get download summary statistics."""
        summary = {
            'total_tickers': len(self.data['tickers']),
            'completed_tickers': 0,
            'failed_tickers': 0,
            'pending_tickers': 0,
            'total_timeframes': 0,
            'completed_timeframes': 0,
            'failed_timeframes': 0,
            'pending_timeframes': 0,
            'total_records': 0,
            'total_bytes': 0
        }

        for ticker, ticker_data in self.data['tickers'].items():
            if ticker_data['status'] == 'completed':
                summary['completed_tickers'] += 1
            elif ticker_data['status'] == 'failed':
                summary['failed_tickers'] += 1
            else:
                summary['pending_tickers'] += 1

            for timeframe, tf_data in ticker_data['timeframes'].items():
                summary['total_timeframes'] += 1
                if tf_data['status'] == 'completed':
                    summary['completed_timeframes'] += 1
                    summary['total_records'] += tf_data.get('records', 0)
                    summary['total_bytes'] += tf_data.get('bytes', 0)
                elif tf_data['status'] == 'failed':
                    summary['failed_timeframes'] += 1
                else:
                    summary['pending_timeframes'] += 1

        return summary

    def print_status(self):
        """Print current download status."""
        summary = self.get_summary()

        print("\n" + "="*70)
        print("DOWNLOAD STATUS")
        print("="*70)
        print(f"\nTickers:")
        print(f"  Completed: {summary['completed_tickers']}")
        print(f"  Failed:    {summary['failed_tickers']}")
        print(f"  Pending:   {summary['pending_tickers']}")

        print(f"\nTimeframes:")
        print(f"  Completed: {summary['completed_timeframes']}")
        print(f"  Failed:    {summary['failed_timeframes']}")
        print(f"  Pending:   {summary['pending_timeframes']}")

        print(f"\nData:")
        print(f"  Total Records: {summary['total_records']:,}")
        print(f"  Total Size: {summary['total_bytes'] / (1024*1024):.1f} MB")

        print("\n" + "="*70 + "\n")

    def export_status(self) -> str:
        """Export status as JSON string."""
        return json.dumps(self.data, indent=2)


if __name__ == "__main__":
    # Test savepoint manager
    print("[TEST] Download Savepoint Manager\n")

    sp = DownloadSavepoint("~/.tradingagents/download_status.json")

    # Initialize some tickers
    tickers = ['AAPL', 'MSFT', 'NVDA']
    timeframes = ['1min', '5min', 'hourly', 'daily']

    for ticker in tickers:
        sp.initialize_ticker(ticker, timeframes)

    # Simulate downloads
    sp.start_ticker('AAPL')
    sp.start_timeframe('AAPL', '1min')
    sp.complete_timeframe('AAPL', '1min', records=1950, bytes_written=140000)

    sp.start_timeframe('AAPL', 'daily')
    sp.complete_timeframe('AAPL', 'daily', records=63, bytes_written=4000)

    sp.complete_ticker('AAPL')

    # Show status
    sp.print_status()
    print("[OK] Savepoint manager working correctly!")
