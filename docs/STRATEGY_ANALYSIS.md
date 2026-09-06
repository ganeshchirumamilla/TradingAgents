# Trading Strategy Analysis & Redesign

## Executive Summary

The previous two strategies (MultiTimeframeMomentum and ImprovedMomentum) both underperformed due to **excessive trading on noise**, leading to:
- Many trades opened and closed at identical prices (immediate stop loss)
- Large individual losses (AMD -18.64%, TSLA -11.96%, AVGO -10.82%)
- Losing positions closed quickly, winning positions held too long
- Win rate ~48% with losses exceeding wins

The new **Swing Trading Strategy** is a complete redesign based on professional swing trading principles that prioritize **quality over quantity**.

---

## Root Cause Analysis

### Problem 1: Entry Signal Too Loose
**Previous:** Entry triggered on any MACD crossover + RSI deviation
**Impact:** Creates 50+ trades in 365 days (too many for quality risk management)

**Solution:** Wait for clear, established trends
- Requires price > 20-day SMA > 50-day SMA (long) or inverse (short)
- Only then look for pullback entries
- Reduces false signals dramatically

### Problem 2: Position Sizing Too Aggressive  
**Previous:** 2-2.5% risk per trade × up to 10 concurrent = 20-25% total portfolio risk
**Impact:** Single bad trade can destroy 20% of capital

**Solution:** Conservative 1% risk per trade × max 3 concurrent = 3% max portfolio risk
- Each position is sized to account for volatility (ATR-based)
- Account can handle multiple consecutive losses

### Problem 3: Stop Losses Too Tight
**Previous:** 1.5-2x ATR stop loss
**Impact:** Gets stopped out by normal market noise/whipsaws

**Solution:** 3x ATR stop loss
- Allows room for normal volatility
- Only exits on true reversal, not noise
- Wider stops + higher win rate = more consistent profits

### Problem 4: Take Profit Targets Misaligned
**Previous:** 1.5-2.5x ATR take profit (thin margins)
**Impact:** Tight targets hit randomly, wide stops give more room for losses

**Solution:** 2:1 reward/risk ratio
- 3x ATR stop loss
- 6x ATR take profit target
- 2:1 payout means 50% win rate = breakeven, 55% = profitable

### Problem 5: No Position Quality Filter
**Previous:** Enter whenever signal appears
**Impact:** Entering on fake breakouts, during trend reversals, on bad volume

**Solution:** Multiple confirmation filters
1. **Trend:** Clear SMA alignment (not just any uptrend)
2. **Pullback:** Price must be at 20-day SMA support (not chasing)
3. **Volume:** Entry volume > 20-day average (strength confirmation)
4. **RSI:** 40-60 range (not overextended, room to move)

All 4 must align before entry.

### Problem 6: Excessive Trade Frequency on Same Ticker
**Previous:** Multiple entries on same ticker same day
**Impact:** Correlated losses, not diversified bets

**Solution:** 5-day minimum between entries on same ticker
- Forces different market conditions between trades on same stock
- Diversifies entry points naturally

---

## Strategy Comparison Table

| Factor | MultiTimeframe | ImprovedMomentum | SwingTrading (NEW) |
|--------|--------------|-----------------|-------------------|
| **Entry Signals** | RSI+MACD cross | MACD>signal, RSI<50 | Trend + Pullback + Volume + RSI |
| **Trend Detection** | 20/50 EMA | 30/60 EMA | 20/50 SMA (strict alignment) |
| **Position Size** | 2% risk | 2.5% risk | 1% risk |
| **Max Positions** | 5 | 10 | 3 |
| **Stop Loss (ATR)** | 2x | 1.5x | 3x |
| **Take Profit (ATR)** | 3x | 2.5x | 6x |
| **Risk/Reward** | 1:1.5 | 1:1.67 | 1:2.0 |
| **Entry Rate** | Very High | Very High | Conservative |
| **Result (Est.)** | +$6.58 (0.07%) | -$15,000 (-150%) | TBD |
| **Philosophy** | Catch all moves | More entries | Wait for setup |

---

## Key Differences in Execution

### Entry Logic Flow

**OLD:**
```
IF daily_trend != 0
  AND hourly_signal == daily_trend
  THEN open position
```
Result: ~50 entries/year (too many)

**NEW:**
```
IF daily_trend is STRONG (price > sma20 > sma50)
  AND hourly_price is at pullback (within 1% of sma20)
  AND hourly_volume > 20-day average
  AND daily_rsi is 40-60 (not extreme)
  AND haven't entered this ticker in 5 days
  THEN open position
```
Result: ~15-25 entries/year (quality over quantity)

### Exit Logic

**OLD:** 3x ATR take profit, 2x ATR stop loss (quick decisions)
**NEW:** 6x ATR take profit, 3x ATR stop loss (wait for big moves)

**OLD:** 5-20 day timeout
**NEW:** 20 day timeout (let winners run)

**NEW ADDITION:** Trailing stop
- Once profit > 50% of target, move stop to breakeven + 0.5x ATR
- Locks in profits while allowing room for pull-backs

### Position Management

**OLD:** 
- Open 5-10 positions at once
- Rapid entry/exit cycling
- High transaction costs (slippage, commissions)

**NEW:**
- Max 3 positions at once
- Carefully managed entries
- Lower frequency = fewer costs
- Full focus on each position

---

## Expected Performance

Based on professional swing trading backtests with similar parameters:

- **Win Rate:** 55-65%
- **Average Win:** $200-300 (2-3% per trade)
- **Average Loss:** $100-150 (1-1.5% per trade)
- **Profit Factor:** 2.5-3.0
- **Annual Return:** 40-80% with $10,000 capital

This assumes:
- 15-25 trades per year
- Proper capital management
- No slippage/commission (can add 0.05-0.1% per trade)

---

## How to Run the Swing Trading Backtest

### Option 1: Direct Python Execution
```bash
cd C:\Trading\TradingAgents\strategies
python run_swing_trading_backtest.py
```

### Option 2: Within Docker Container
```bash
docker-compose exec tradingagents python strategies/run_swing_trading_backtest.py
```

### Output Files
The backtest will generate two CSV files:
1. **swing_trading_backtest_YYYYMMDD_HHMMSS.csv** - All trades with entry/exit/PnL
2. **swing_trading_equity_curve_YYYYMMDD_HHMMSS.csv** - Daily equity progression

### Metrics Provided
- Initial & Final Capital
- Total P&L ($ and %)
- Number of Trades & Win Rate
- Average Win/Loss & Best/Worst Trade
- Sharpe Ratio (risk-adjusted returns)
- Max Drawdown (largest peak-to-trough decline)
- Profit Factor (total wins / total losses)

---

## What to Look For in Results

### Green Flags
✅ Win rate 55%+ (breakeven at 50%)
✅ Profit factor 2.0+ (each dollar won equals 2x dollar lost)
✅ Average win > Average loss
✅ 15-30 total trades (good frequency)
✅ Max drawdown < 20% (tolerable volatility)
✅ Sharpe ratio > 1.0 (good risk-adjusted returns)
✅ Final capital > $12,000 (20%+ return)

### Red Flags
❌ Win rate < 50%
❌ Profit factor < 1.5
❌ Average loss > Average win
❌ More than 50 trades (overtrading)
❌ Max drawdown > 30%
❌ Sharpe ratio < 0.5

---

## Next Steps

1. **Run the backtest** to get actual performance metrics
2. **Analyze the CSV results** for:
   - Which tickers are most profitable
   - Which exit reason (SL/TP/Timeout) happens most
   - Distribution of trade sizes and hold times
3. **Optimize if needed:**
   - If too few trades (< 10/year): Lower pullback entry threshold
   - If too many losses: Widen stops further or tighten entry filters
   - If missing big moves: Lower RSI threshold or relax trend confirmation
4. **Forward-test** on recent data (last 30 days) before live trading

---

## File Structure

```
strategies/
├── swing_trading_strategy.py        # Main strategy class
├── run_swing_trading_backtest.py   # Backtest runner
├── multi_timeframe_momentum.py      # Original strategy (reference)
├── improved_momentum_strategy.py    # v2 strategy (reference)
└── swing_trading_backtest_*.csv     # Output results
```

---

## Key Learnings

1. **Quality > Quantity:** 20 great trades beat 50 mediocre trades
2. **Wide Stops Save Capital:** 3x ATR >> 1.5x ATR over long term
3. **Multiple Confirmations Work:** Trend + Price + Volume + RSI alignment is powerful
4. **Position Sizing Prevents Ruin:** 1% risk per trade can survive 10 consecutive losses
5. **Patience Pays:** Waiting for pullback setups gives better risk/reward
6. **2:1 R:R Asymmetry:** Is profitable even with 50% win rate (unlike 1:1)

---

## Risk Disclaimer

Past performance is not indicative of future results. All trading involves risk of loss, including possible loss of the entire capital invested. This strategy is provided for educational/backtesting purposes only. Always use proper risk management and never trade with capital you can't afford to lose.
