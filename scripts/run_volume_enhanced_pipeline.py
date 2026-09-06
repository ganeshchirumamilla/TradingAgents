#!/usr/bin/env python3
"""
Master orchestration script for volume-enhanced trading pipeline.
Coordinates: parallel downloads -> enhanced backtests -> report generation
"""

import subprocess
import sys
import os
from pathlib import Path
from datetime import datetime
import json
import time


def print_header(title):
    """Print formatted header."""
    print("\n" + "="*70)
    print(f"[STAGE] {title}")
    print("="*70 + "\n")


def run_command(cmd, timeout=None):
    """Run a command and return success status."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=False,
            text=True,
            timeout=timeout
        )
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print(f"[TIMEOUT] Command timed out after {timeout} seconds")
        return False
    except Exception as e:
        print(f"[ERROR] {str(e)}")
        return False


def main():
    """Main orchestration function."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Volume-Enhanced Trading Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run complete pipeline
  python run_volume_enhanced_pipeline.py

  # Run specific stages
  python run_volume_enhanced_pipeline.py --stages download,backtest

  # Download only with custom settings
  python run_volume_enhanced_pipeline.py --stages download --days 30 --intervals "1 min,5 mins"
        """
    )

    parser.add_argument(
        "--stages",
        type=str,
        default="download,backtest,reports",
        help="Stages to run: download, backtest, reports (default: all)"
    )

    parser.add_argument(
        "--intervals",
        type=str,
        default="1 min,5 mins,1 hour,1 day",
        help="Bar intervals for download"
    )

    parser.add_argument(
        "--days",
        type=int,
        default=90,
        help="Days to download (default: 90)"
    )

    parser.add_argument(
        "--workers",
        type=int,
        default=3,
        help="Parallel workers for download and backtest"
    )

    parser.add_argument(
        "--skip-confirm",
        action="store_true",
        help="Skip confirmation prompts"
    )

    args = parser.parse_args()

    stages = [s.strip() for s in args.stages.split(",")]
    scripts_dir = Path(__file__).parent
    start_time = time.time()

    print("\n" + "="*70)
    print("VOLUME-ENHANCED TRADING PIPELINE")
    print("="*70)
    print(f"Stages: {', '.join(stages)}")
    print(f"Download intervals: {args.intervals}")
    print(f"Download days: {args.days}")
    print(f"Parallel workers: {args.workers}")
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)

    if not args.skip_confirm:
        response = input("\nProceed? (yes/no): ").strip().lower()
        if response != "yes":
            print("Aborted.")
            return 1

    results = {}

    # Stage 1: Parallel Data Download
    if "download" in stages:
        print_header("STAGE 1: Parallel Data Download with Volume")

        cmd = [
            sys.executable,
            str(scripts_dir / "download_parallel.py"),
            "--intervals", args.intervals,
            "--days", str(args.days),
            "--workers", str(args.workers),
        ]

        print("[INFO] Running parallel downloader...")
        print(f"[INFO] Command: {' '.join(cmd)}\n")

        download_start = time.time()
        success = run_command(cmd, timeout=1800)  # 30 min timeout
        download_time = time.time() - download_start

        results['download'] = {
            'success': success,
            'time': download_time,
            'stages_run': 1
        }

        if success:
            print(f"\n[SUCCESS] Download completed in {download_time/60:.1f} minutes")
        else:
            print(f"\n[FAILED] Download failed after {download_time/60:.1f} minutes")
            print("[WARNING] Continuing to backtest with existing data...")

    # Stage 2: Volume-Enhanced Backtests
    if "backtest" in stages:
        print_header("STAGE 2: Volume-Enhanced Strategy Backtests")

        cmd = [
            sys.executable,
            str(scripts_dir / "backtest_volume_enhanced.py"),
            "--workers", str(args.workers),
        ]

        print("[INFO] Running backtests with volume indicators...")
        print(f"[INFO] Command: {' '.join(cmd)}\n")

        backtest_start = time.time()
        success = run_command(cmd, timeout=3600)  # 60 min timeout
        backtest_time = time.time() - backtest_start

        results['backtest'] = {
            'success': success,
            'time': backtest_time,
            'strategies': 7,
            'tickers': 15,
            'timeframes': 4
        }

        if success:
            print(f"\n[SUCCESS] Backtests completed in {backtest_time/60:.1f} minutes")
        else:
            print(f"\n[FAILED] Backtests failed after {backtest_time/60:.1f} minutes")

    # Stage 3: Report Generation
    if "reports" in stages:
        print_header("STAGE 3: Report Generation")

        # Load backtest results
        reports_dir = scripts_dir.parent / "reports"
        report_file = reports_dir / "backtest_volume_enhanced_report.json"

        if report_file.exists():
            with open(report_file, 'r') as f:
                backtest_data = json.load(f)

            print(f"[INFO] Loaded backtest results from {report_file}")
            print(f"[INFO] Strategies: {len(backtest_data)}")

            total_results = sum(len(v) for v in backtest_data.values())
            print(f"[INFO] Total results: {total_results}")

            # Generate summary CSV
            import pandas as pd

            all_results = []
            for strategy, combinations in backtest_data.items():
                for combo_key, metrics in combinations.items():
                    parts = combo_key.split('_')
                    all_results.append({
                        'Strategy': strategy,
                        'Ticker': parts[-2],
                        'Timeframe': parts[-1],
                        'Trades': metrics.get('total_trades', 0),
                        'Wins': metrics.get('wins', 0),
                        'Losses': metrics.get('losses', 0),
                        'Win Rate': metrics.get('win_rate', '0%'),
                        'Avg Win': metrics.get('avg_win', '$0'),
                        'Avg Loss': metrics.get('avg_loss', '$0'),
                        'Profit Factor': metrics.get('profit_factor', 'N/A'),
                        'Total P&L': metrics.get('total_pnl', '$0'),
                        'Return': metrics.get('return', '+0%')
                    })

            if all_results:
                df = pd.DataFrame(all_results)

                # Save CSV
                csv_file = reports_dir / "backtest_volume_enhanced_results.csv"
                df.to_csv(csv_file, index=False)
                print(f"[OK] Saved CSV: {csv_file}")

                # Save HTML
                html_file = reports_dir / "backtest_volume_enhanced_results.html"
                html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Volume-Enhanced Backtest Results</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
        .container {{ background: white; padding: 20px; border-radius: 8px; }}
        h1 {{ color: #2563eb; }}
        table {{ border-collapse: collapse; width: 100%; margin-top: 20px; }}
        th {{ background: #2563eb; color: white; padding: 12px; text-align: left; }}
        td {{ padding: 10px; border-bottom: 1px solid #ddd; }}
        tr:hover {{ background: #f9f9f9; }}
        .positive {{ color: green; font-weight: bold; }}
        .negative {{ color: red; font-weight: bold; }}
        .footer {{ margin-top: 20px; font-size: 0.9em; color: #666; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Volume-Enhanced Strategy Backtests</h1>
        <p>Report generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        <p>Strategies tested: {len(backtest_data)} | Total results: {total_results}</p>

        <table>
            <tr>
                <th>Strategy</th>
                <th>Ticker</th>
                <th>Timeframe</th>
                <th>Trades</th>
                <th>Wins</th>
                <th>Losses</th>
                <th>Win Rate</th>
                <th>Avg Win</th>
                <th>Avg Loss</th>
                <th>Profit Factor</th>
                <th>Total P&L</th>
                <th>Return</th>
            </tr>
"""

                for _, row in df.iterrows():
                    html_content += f"<tr>"
                    html_content += f"<td>{row['Strategy']}</td>"
                    html_content += f"<td>{row['Ticker']}</td>"
                    html_content += f"<td>{row['Timeframe']}</td>"
                    html_content += f"<td>{row['Trades']}</td>"
                    html_content += f"<td>{row['Wins']}</td>"
                    html_content += f"<td>{row['Losses']}</td>"
                    html_content += f"<td>{row['Win Rate']}</td>"
                    html_content += f"<td>{row['Avg Win']}</td>"
                    html_content += f"<td>{row['Avg Loss']}</td>"
                    html_content += f"<td>{row['Profit Factor']}</td>"
                    pnl_class = "positive" if "-" not in str(row['Total P&L']) else "negative"
                    html_content += f"<td class='{pnl_class}'>{row['Total P&L']}</td>"
                    ret_class = "positive" if "-" not in str(row['Return']) else "negative"
                    html_content += f"<td class='{ret_class}'>{row['Return']}</td>"
                    html_content += f"</tr>"

                html_content += """
        </table>

        <div class="footer">
            <p>Commission: 0.001% per trade | Initial capital: $10,000</p>
            <p>Data source: IBKR (TRADES)</p>
        </div>
    </div>
</body>
</html>
"""

                with open(html_file, 'w') as f:
                    f.write(html_content)
                print(f"[OK] Saved HTML: {html_file}")

            results['reports'] = {
                'success': True,
                'csv_file': str(csv_file),
                'html_file': str(html_file),
                'total_results': total_results
            }
        else:
            print(f"[WARNING] Backtest report not found: {report_file}")
            results['reports'] = {'success': False, 'reason': 'No backtest data'}

    # Final Summary
    total_time = time.time() - start_time

    print_header("PIPELINE SUMMARY")

    print("Stage Results:")
    for stage, result in results.items():
        status = "[OK]" if result.get('success', False) else "[SKIP]"
        print(f"  {status} {stage:15s} - {result}")

    print(f"\nTotal execution time: {total_time/60:.1f} minutes")
    print(f"Pipeline completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    print("\n" + "="*70)
    print("NEXT STEPS:")
    print("  1. Review volume-enhanced backtest results in reports/")
    print("  2. Open backtest_volume_enhanced_results.html in browser")
    print("  3. Compare with original (MIDPOINT) results")
    print("  4. Select top strategies for live testing")
    print("="*70 + "\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
