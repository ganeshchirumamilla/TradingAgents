#!/usr/bin/env python3
import json
import pandas as pd
import os

print("[CREATE REPORTS] Converting JSON to CSV and creating summaries...")

# Load JSON
with open('backtest_all_strategies_report.json', 'r') as f:
    data = json.load(f)

rows = []
for strategy, combinations in data.items():
    for combo, metrics in combinations.items():
        if metrics:
            parts = combo.rsplit('_', 1)
            ticker = parts[0]
            timeframe = parts[1] if len(parts) > 1 else 'unknown'

            row = {
                'Strategy': strategy,
                'Ticker': ticker,
                'Timeframe': timeframe,
                'Trades': int(metrics.get('total_trades', 0)),
                'Wins': int(metrics.get('wins', 0)),
                'Losses': int(metrics.get('losses', 0)),
                'Win_Rate': metrics.get('win_rate', '0%'),
                'Avg_Win': metrics.get('avg_win', '$0'),
                'Avg_Loss': metrics.get('avg_loss', '$0'),
                'Profit_Factor': metrics.get('profit_factor', 'N/A'),
                'Total_PnL': metrics.get('total_pnl', '$0'),
                'Final_Equity': metrics.get('final_equity', '$10000'),
                'Return': metrics.get('return', '+0%')
            }
            rows.append(row)

df = pd.DataFrame(rows)

# Extract return percent for sorting
df['Return_Num'] = df['Return'].str.replace('%', '').str.replace('+', '').astype(float)
df_sorted = df.sort_values('Return_Num', ascending=False)

# Save detailed CSV
df_sorted.to_csv('backtest_all_strategies_results.csv', index=False)
print("[OK] backtest_all_strategies_results.csv ({} rows)".format(len(df_sorted)))

# Summary by Strategy
strategy_summary = df_sorted.groupby('Strategy').agg({
    'Trades': 'sum',
    'Wins': 'sum',
    'Losses': 'sum',
    'Return_Num': 'mean'
}).round(2)
strategy_summary['Avg_Return'] = strategy_summary['Return_Num'].apply(lambda x: "{:+.2f}%".format(x))
strategy_summary = strategy_summary[['Trades', 'Wins', 'Losses', 'Avg_Return']]
strategy_summary.to_csv('backtest_strategy_summary.csv')
print("[OK] backtest_strategy_summary.csv")

# Summary by Ticker
ticker_summary = df_sorted.groupby('Ticker').agg({
    'Trades': 'sum',
    'Wins': 'sum',
    'Losses': 'sum',
    'Return_Num': 'mean'
}).round(2)
ticker_summary['Avg_Return'] = ticker_summary['Return_Num'].apply(lambda x: "{:+.2f}%".format(x))
ticker_summary = ticker_summary[['Trades', 'Wins', 'Losses', 'Avg_Return']]
ticker_summary.to_csv('backtest_ticker_summary.csv')
print("[OK] backtest_ticker_summary.csv")

# Summary by Timeframe
timeframe_summary = df_sorted.groupby('Timeframe').agg({
    'Trades': 'sum',
    'Wins': 'sum',
    'Losses': 'sum',
    'Return_Num': 'mean'
}).round(2)
timeframe_summary['Avg_Return'] = timeframe_summary['Return_Num'].apply(lambda x: "{:+.2f}%".format(x))
timeframe_summary = timeframe_summary[['Trades', 'Wins', 'Losses', 'Avg_Return']]
timeframe_summary.to_csv('backtest_timeframe_summary.csv')
print("[OK] backtest_timeframe_summary.csv")

print("\n[SUCCESS] All CSVs created!")
print("Total combinations analyzed: {}".format(len(df_sorted)))
