#!/usr/bin/env python3
"""
Generate individual HTML and CSV reports for each strategy/ticker/timeframe combination
"""

import json
import pandas as pd
import os
from pathlib import Path
from datetime import datetime

print("[GENERATE] Creating individual reports for each strategy/ticker/timeframe combination...")

# Create subdirectories
reports_base = Path("reports")
detailed_dir = reports_base / "detailed_results"
by_strategy_dir = detailed_dir / "by_strategy"
by_ticker_dir = detailed_dir / "by_ticker"
by_timeframe_dir = detailed_dir / "by_timeframe"

for d in [detailed_dir, by_strategy_dir, by_ticker_dir, by_timeframe_dir]:
    d.mkdir(parents=True, exist_ok=True)

# Load JSON report
with open(reports_base / "backtest_all_strategies_report.json", 'r') as f:
    data = json.load(f)

# Track statistics
total_combinations = 0
csv_created = 0
html_created = 0
strategies_list = set()
tickers_list = set()
timeframes_list = set()

# Generate reports for each combination
for strategy, combinations in data.items():
    strategies_list.add(strategy)

    # Create strategy folder
    strategy_dir = by_strategy_dir / strategy
    strategy_dir.mkdir(exist_ok=True)

    for combo, metrics in combinations.items():
        if metrics:
            total_combinations += 1

            # Parse combo name
            parts = combo.rsplit('_', 1)
            ticker = parts[0]
            timeframe = parts[1] if len(parts) > 1 else 'unknown'

            tickers_list.add(ticker)
            timeframes_list.add(timeframe)

            # Prepare data
            filename_base = f"{strategy}_{ticker}_{timeframe}"
            csv_path = strategy_dir / f"{filename_base}.csv"
            html_path = strategy_dir / f"{filename_base}.html"

            # Create CSV
            csv_data = {
                'Metric': [
                    'Strategy', 'Ticker', 'Timeframe', 'Total Trades', 'Winning Trades',
                    'Losing Trades', 'Win Rate', 'Average Win', 'Average Loss',
                    'Profit Factor', 'Total P&L', 'Final Equity', 'Return'
                ],
                'Value': [
                    strategy, ticker, timeframe, metrics.get('total_trades', 0),
                    metrics.get('wins', 0), metrics.get('losses', 0),
                    metrics.get('win_rate', '0%'), metrics.get('avg_win', '$0'),
                    metrics.get('avg_loss', '$0'), metrics.get('profit_factor', 'N/A'),
                    metrics.get('total_pnl', '$0'), metrics.get('final_equity', '$10000'),
                    metrics.get('return', '+0%')
                ]
            }

            df_csv = pd.DataFrame(csv_data)
            df_csv.to_csv(csv_path, index=False)
            csv_created += 1

            # Create HTML
            html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{strategy} - {ticker} - {timeframe}</title>
    <style>
        :root {{
            --primary: #2563eb;
            --success: #10b981;
            --danger: #ef4444;
            --bg: #f9fafb;
            --text: #1f2937;
            --border: #e5e7eb;
        }}

        @media (prefers-color-scheme: dark) {{
            :root {{
                --bg: #111827;
                --text: #f3f4f6;
                --border: #374151;
            }}
        }}

        body {{
            background: var(--bg);
            color: var(--text);
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            padding: 20px;
            margin: 0;
        }}

        .container {{
            max-width: 900px;
            margin: 0 auto;
            background: white;
            border-radius: 8px;
            padding: 30px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }}

        @media (prefers-color-scheme: dark) {{
            .container {{
                background: #1f2937;
            }}
        }}

        h1 {{
            color: var(--primary);
            margin: 0 0 10px 0;
            font-size: 2em;
        }}

        .subtitle {{
            color: var(--text);
            opacity: 0.7;
            margin-bottom: 30px;
            font-size: 1.1em;
        }}

        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}

        .metric-card {{
            background: var(--bg);
            border: 1px solid var(--border);
            border-radius: 6px;
            padding: 15px;
        }}

        .metric-label {{
            font-size: 0.9em;
            color: var(--text);
            opacity: 0.7;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 8px;
        }}

        .metric-value {{
            font-size: 1.5em;
            font-weight: bold;
            color: var(--primary);
        }}

        .positive {{
            color: var(--success) !important;
        }}

        .negative {{
            color: var(--danger) !important;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }}

        th {{
            background: var(--primary);
            color: white;
            padding: 12px;
            text-align: left;
            font-weight: 600;
        }}

        td {{
            padding: 12px;
            border-bottom: 1px solid var(--border);
        }}

        tr:hover {{
            background: var(--bg);
        }}

        .footer {{
            text-align: center;
            color: var(--text);
            opacity: 0.6;
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid var(--border);
            font-size: 0.9em;
        }}

        .badge {{
            display: inline-block;
            padding: 4px 12px;
            border-radius: 20px;
            background: var(--primary);
            color: white;
            font-size: 0.85em;
            margin-right: 8px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>{strategy}</h1>
        <p class="subtitle">
            <span class="badge">{ticker}</span>
            <span class="badge">{timeframe}</span>
        </p>

        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-label">Total Trades</div>
                <div class="metric-value">{metrics.get('total_trades', 0)}</div>
            </div>

            <div class="metric-card">
                <div class="metric-label">Win Rate</div>
                <div class="metric-value">{metrics.get('win_rate', '0%')}</div>
            </div>

            <div class="metric-card">
                <div class="metric-label">Winning Trades</div>
                <div class="metric-value positive">{metrics.get('wins', 0)}</div>
            </div>

            <div class="metric-card">
                <div class="metric-label">Losing Trades</div>
                <div class="metric-value negative">{metrics.get('losses', 0)}</div>
            </div>

            <div class="metric-card">
                <div class="metric-label">Average Win</div>
                <div class="metric-value positive">{metrics.get('avg_win', '$0')}</div>
            </div>

            <div class="metric-card">
                <div class="metric-label">Average Loss</div>
                <div class="metric-value negative">{metrics.get('avg_loss', '$0')}</div>
            </div>

            <div class="metric-card">
                <div class="metric-label">Profit Factor</div>
                <div class="metric-value">{metrics.get('profit_factor', 'N/A')}</div>
            </div>

            <div class="metric-card">
                <div class="metric-label">Total P&L</div>
                <div class="metric-value {'positive' if '+' in metrics.get('total_pnl', '$0') else 'negative'}">{metrics.get('total_pnl', '$0')}</div>
            </div>

            <div class="metric-card">
                <div class="metric-label">Final Equity</div>
                <div class="metric-value">{metrics.get('final_equity', '$10000')}</div>
            </div>

            <div class="metric-card">
                <div class="metric-label">Return</div>
                <div class="metric-value {'positive' if '+' in metrics.get('return', '+0%') else 'negative'}">{metrics.get('return', '+0%')}</div>
            </div>
        </div>

        <table>
            <tr>
                <th>Metric</th>
                <th>Value</th>
            </tr>
            <tr>
                <td>Strategy</td>
                <td>{strategy}</td>
            </tr>
            <tr>
                <td>Ticker</td>
                <td>{ticker}</td>
            </tr>
            <tr>
                <td>Timeframe</td>
                <td>{timeframe}</td>
            </tr>
            <tr>
                <td>Total Trades</td>
                <td>{metrics.get('total_trades', 0)}</td>
            </tr>
            <tr>
                <td>Winning Trades</td>
                <td class="positive">{metrics.get('wins', 0)}</td>
            </tr>
            <tr>
                <td>Losing Trades</td>
                <td class="negative">{metrics.get('losses', 0)}</td>
            </tr>
            <tr>
                <td>Win Rate</td>
                <td>{metrics.get('win_rate', '0%')}</td>
            </tr>
            <tr>
                <td>Average Win</td>
                <td class="positive">{metrics.get('avg_win', '$0')}</td>
            </tr>
            <tr>
                <td>Average Loss</td>
                <td class="negative">{metrics.get('avg_loss', '$0')}</td>
            </tr>
            <tr>
                <td>Profit Factor</td>
                <td>{metrics.get('profit_factor', 'N/A')}</td>
            </tr>
            <tr>
                <td>Total P&L</td>
                <td class="{'positive' if '+' in metrics.get('total_pnl', '$0') else 'negative'}">{metrics.get('total_pnl', '$0')}</td>
            </tr>
            <tr>
                <td>Final Equity</td>
                <td>{metrics.get('final_equity', '$10000')}</td>
            </tr>
            <tr>
                <td>Return</td>
                <td class="{'positive' if '+' in metrics.get('return', '+0%') else 'negative'}">{metrics.get('return', '+0%')}</td>
            </tr>
        </table>

        <div class="footer">
            <p>Backtest Results Report | Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            <p>Commission: 0.001% per trade | Initial Capital: $10,000</p>
        </div>
    </div>
</body>
</html>"""

            with open(html_path, 'w') as f:
                f.write(html_content)
            html_created += 1

# Create index files
print("\n[INDEX] Creating navigation index files...")

# Index by Strategy
index_html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Detailed Backtest Results - By Strategy</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; padding: 20px; background: #f9fafb; }
        .container { max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; }
        h1 { color: #2563eb; margin-bottom: 30px; }
        .strategy-section { margin-bottom: 40px; }
        .strategy-title { font-size: 1.3em; font-weight: bold; color: #2563eb; margin: 20px 0 10px 0; padding-bottom: 10px; border-bottom: 2px solid #2563eb; }
        .results-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 15px; }
        .result-card { background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 6px; padding: 15px; text-decoration: none; color: inherit; transition: all 0.2s; }
        .result-card:hover { background: #2563eb; color: white; }
        .result-card-title { font-weight: bold; margin-bottom: 8px; }
        .result-card-meta { font-size: 0.9em; opacity: 0.7; }
        .back-link { margin-bottom: 20px; }
        .back-link a { color: #2563eb; text-decoration: none; }
        .back-link a:hover { text-decoration: underline; }
    </style>
</head>
<body>
    <div class="container">
        <div class="back-link">
            <a href="../backtest_all_strategies_results.csv">Back to Summary CSV</a> |
            <a href="../backtest_results_report.html">Back to Summary HTML</a>
        </div>

        <h1>Detailed Backtest Results - By Strategy</h1>
        <p>Click any result to view detailed performance metrics.</p>
"""

for strategy in sorted(strategies_list):
    strategy_dir = by_strategy_dir / strategy
    results = list(strategy_dir.glob("*.html"))

    if results:
        index_html += f"<div class='strategy-section'><div class='strategy-title'>{strategy}</div><div class='results-grid'>"

        for html_file in sorted(results):
            filename = html_file.stem
            parts = filename.split('_')
            ticker = parts[-2]
            timeframe = parts[-1]

            index_html += f"""
            <a href="{html_file.name}" class="result-card">
                <div class="result-card-title">{ticker} - {timeframe.upper()}</div>
                <div class="result-card-meta">View detailed results</div>
            </a>"""

        index_html += "</div></div>"

index_html += """
    </div>
</body>
</html>"""

with open(by_strategy_dir / "index.html", 'w') as f:
    f.write(index_html)

print(f"\n[SUCCESS] Report Generation Complete!")
print(f"  Total combinations: {total_combinations}")
print(f"  CSV files created: {csv_created}")
print(f"  HTML files created: {html_created}")
print(f"  Unique strategies: {len(strategies_list)}")
print(f"  Unique tickers: {len(tickers_list)}")
print(f"  Unique timeframes: {len(timeframes_list)}")
print(f"\n[LOCATION] reports/detailed_results/by_strategy/")
print(f"  Each strategy folder contains CSV and HTML for all ticker/timeframe combinations")
print(f"  Open: reports/detailed_results/by_strategy/index.html to navigate")
