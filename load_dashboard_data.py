#!/usr/bin/env python3
"""
Load actual backtest data into the interactive dashboard HTML
"""

import json
import os
from pathlib import Path

print("[LOAD] Loading backtest data into interactive dashboard...")

# Load JSON report
reports_dir = Path("reports")
json_file = reports_dir / "backtest_all_strategies_report.json"

with open(json_file, 'r') as f:
    data = json.load(f)

# Convert to array format for JavaScript
rows = []
for strategy, combinations in data.items():
    for combo, metrics in combinations.items():
        parts = combo.rsplit('_', 1)
        ticker = parts[0]
        timeframe = parts[1] if len(parts) > 1 else 'unknown'

        if metrics:
            row = {
                'strategy': strategy,
                'ticker': ticker,
                'timeframe': timeframe,
                'trades': int(metrics.get('total_trades', 0)),
                'wins': int(metrics.get('wins', 0)),
                'losses': int(metrics.get('losses', 0)),
                'win_rate': metrics.get('win_rate', '0%'),
                'avg_win': metrics.get('avg_win', '$0'),
                'avg_loss': metrics.get('avg_loss', '$0'),
                'profit_factor': metrics.get('profit_factor', 'N/A'),
                'pnl': metrics.get('total_pnl', '$0'),
                'return': metrics.get('return', '+0%')
            }
            rows.append(row)

print(f"Loaded {len(rows)} combinations")

# Read the HTML file
html_file = reports_dir / "interactive_results_dashboard.html"
with open(html_file, 'r') as f:
    html_content = f.read()

# Create JavaScript data
data_js = f"""
        // Actual backtest data - {len(rows)} combinations
        allData = {json.dumps(rows)};
        filteredData = [...allData];
"""

# Replace the sample data loading function
old_load = """        function loadFullDataset() {
            // In production, this would load from backtest_all_strategies_report.json
            // For now, we'll generate sample data representing all 252 combinations
            const strategies = ["MeanReversionRSI", "RsiDivergence", "BollingerBandMeanReversion", "VolatilityBreakout", "MacdStrategy", "MovingAverageCrossover"];
            const tickers = ["AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "TSLA", "AMD", "AVGO", "JPM", "GS", "SPY", "QQQ", "IWM", "DIA"];
            const timeframes = ["1min", "5min", "1h"];

            allData = [];
            for (let s of strategies) {
                for (let t of tickers) {
                    for (let tf of timeframes) {
                        // Generate realistic mock data
                        const trades = Math.floor(Math.random() * 200) + 10;
                        const wins = Math.floor(trades * (Math.random() * 0.5 + 0.25));
                        const losses = trades - wins;
                        const winRate = ((wins / trades) * 100).toFixed(2);
                        const returnVal = (Math.random() * 8 - 2).toFixed(2);
                        const pnl = Math.round(returnVal * 100 + 100) / 10;

                        allData.push({
                            strategy: s,
                            ticker: t,
                            timeframe: tf,
                            trades: trades,
                            wins: wins,
                            losses: losses,
                            win_rate: winRate + "%",
                            avg_win: "$" + (Math.random() * 5 + 1).toFixed(2),
                            avg_loss: "$" + (Math.random() * 3).toFixed(2),
                            profit_factor: (Math.random() * 3 + 0.5).toFixed(2),
                            pnl: (returnVal >= 0 ? "+" : "") + "$" + pnl,
                            return: (returnVal >= 0 ? "+" : "") + returnVal + "%"
                        });
                    }
                }
            }

            filteredData = [...allData];
        }"""

new_load = """        function loadFullDataset() {
            // Data already loaded from loadDataFromJSON()
        }"""

html_content = html_content.replace(old_load, new_load)

# Also update loadDataFromJSON to use actual data
old_load_json = """        function loadDataFromJSON() {
            // This will be replaced with actual data from backtest_all_strategies_report.json
            allData = [
                { strategy: "MeanReversionRSI", ticker: "AMD", timeframe: "5min", trades: 35, wins: 35, losses: 0, win_rate: "100.00%", avg_win: "$10.98", avg_loss: "$0.00", profit_factor: "N/A", pnl: "$384.31", return: "+3.84%" },
                { strategy: "RsiDivergence", ticker: "META", timeframe: "5min", trades: 88, wins: 38, losses: 50, win_rate: "43.18%", avg_win: "$4.79", avg_loss: "$0.00", profit_factor: "N/A", pnl: "$182.03", return: "+1.82%" },
                { strategy: "MeanReversionRSI", ticker: "GS", timeframe: "5min", trades: 7, wins: 7, losses: 0, win_rate: "100.00%", avg_win: "$23.02", avg_loss: "$0.00", profit_factor: "N/A", pnl: "$161.11", return: "+1.61%" },
                { strategy: "BollingerBandMeanReversion", ticker: "TSLA", timeframe: "5min", trades: 224, wins: 139, losses: 85, win_rate: "62.05%", avg_win: "$1.12", avg_loss: "$0.70", profit_factor: "2.21", pnl: "-$156.57", return: "-1.57%" },
                { strategy: "VolatilityBreakout", ticker: "AMD", timeframe: "1min", trades: 74, wins: 21, losses: 53, win_rate: "28.38%", avg_win: "$7.42", avg_loss: "$3.00", profit_factor: "0.52", pnl: "-$155.69", return: "-1.56%" }
            ];

            // Load full data (placeholder - would load from JSON in production)
            loadFullDataset();
            filteredData = [...allData];
        }"""

new_load_json = f"""        function loadDataFromJSON() {{
{data_js}
        }}"""

html_content = html_content.replace(old_load_json, new_load_json)

# Save updated HTML
with open(html_file, 'w') as f:
    f.write(html_content)

print(f"[SUCCESS] Updated interactive_results_dashboard.html with {len(rows)} actual backtest results!")
print(f"\nDashboard Features:")
print(f"  ✓ Filter by Strategy dropdown")
print(f"  ✓ Filter by Ticker dropdown")
print(f"  ✓ Filter by Timeframe dropdown")
print(f"  ✓ Global search box")
print(f"  ✓ Sortable columns (click headers)")
print(f"  ✓ Export to CSV button")
print(f"  ✓ Real-time statistics")
print(f"\nLocation: reports/interactive_results_dashboard.html")
