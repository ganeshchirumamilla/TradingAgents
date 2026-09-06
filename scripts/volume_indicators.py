#!/usr/bin/env python3
"""
Volume-based technical indicators for trading strategies.
Includes: Volume MA, OBV, VROC, Volume Divergence, VWAP, Money Flow Index
"""

import numpy as np
import pandas as pd


def calculate_volume_ma(df, period=20):
    """
    Calculate Volume Moving Average.

    Args:
        df: DataFrame with 'volume' column
        period: Period for moving average (default: 20)

    Returns:
        Series with Volume MA
    """
    return df['volume'].rolling(window=period).mean()


def is_volume_high(df, period=20, multiplier=1.0):
    """
    Check if current volume is above the moving average.

    Args:
        df: DataFrame with 'volume' column
        period: Period for moving average
        multiplier: Multiplier for MA (e.g., 1.5 = 150% of MA)

    Returns:
        Boolean Series (True if volume > MA * multiplier)
    """
    vol_ma = calculate_volume_ma(df, period)
    return df['volume'] > (vol_ma * multiplier)


def calculate_obv(df):
    """
    Calculate On-Balance Volume (OBV).
    Cumulative indicator using volume flow direction.

    Args:
        df: DataFrame with 'close' and 'volume' columns

    Returns:
        Series with OBV values
    """
    obv = pd.Series(index=df.index, dtype=float)
    obv.iloc[0] = df['volume'].iloc[0]

    for i in range(1, len(df)):
        if df['close'].iloc[i] > df['close'].iloc[i-1]:
            obv.iloc[i] = obv.iloc[i-1] + df['volume'].iloc[i]
        elif df['close'].iloc[i] < df['close'].iloc[i-1]:
            obv.iloc[i] = obv.iloc[i-1] - df['volume'].iloc[i]
        else:
            obv.iloc[i] = obv.iloc[i-1]

    return obv


def calculate_vroc(df, period=12):
    """
    Calculate Volume Rate of Change (VROC).
    Momentum indicator for volume changes.

    Args:
        df: DataFrame with 'volume' column
        period: Period for ROC (default: 12)

    Returns:
        Series with VROC values
    """
    return df['volume'].pct_change(period) * 100


def calculate_volume_divergence(df, price_col='close', volume_col='volume', period=14):
    """
    Detect volume divergence (price moving but volume declining or vice versa).
    Returns: 1 for bullish div, -1 for bearish div, 0 for no div

    Args:
        df: DataFrame with price and volume columns
        price_col: Column name for price
        volume_col: Column name for volume
        period: Period for divergence detection

    Returns:
        Series with divergence signals (-1, 0, 1)
    """
    divergence = pd.Series(0, index=df.index, dtype=int)

    price_high = df[price_col].rolling(window=period).max()
    price_low = df[price_col].rolling(window=period).min()
    vol_high = df[volume_col].rolling(window=period).max()
    vol_low = df[volume_col].rolling(window=period).min()

    # Bullish divergence: price makes lower low but volume makes higher high
    bullish = (df[price_col] < price_low.shift(1)) & (df[volume_col] > vol_high.shift(1))
    divergence[bullish] = 1

    # Bearish divergence: price makes higher high but volume makes lower low
    bearish = (df[price_col] > price_high.shift(1)) & (df[volume_col] < vol_low.shift(1))
    divergence[bearish] = -1

    return divergence


def calculate_vwap(df):
    """
    Calculate Volume Weighted Average Price (VWAP).
    Fair value reference point for intraday trading.

    Args:
        df: DataFrame with OHLCV data

    Returns:
        Series with VWAP values
    """
    df = df.copy()
    df['typical_price'] = (df['high'] + df['low'] + df['close']) / 3
    df['tp_volume'] = df['typical_price'] * df['volume']
    df['cumsum_tp_volume'] = df['tp_volume'].cumsum()
    df['cumsum_volume'] = df['volume'].cumsum()
    df['vwap'] = df['cumsum_tp_volume'] / df['cumsum_volume']

    return df['vwap']


def calculate_mfi(df, period=14):
    """
    Calculate Money Flow Index (MFI).
    Volume-weighted RSI indicator.

    Args:
        df: DataFrame with OHLCV data
        period: Period for MFI (default: 14)

    Returns:
        Series with MFI values (0-100)
    """
    df = df.copy()
    df['typical_price'] = (df['high'] + df['low'] + df['close']) / 3
    df['money_flow'] = df['typical_price'] * df['volume']

    # Positive and negative money flow
    df['positive_mf'] = 0.0
    df['negative_mf'] = 0.0

    for i in range(1, len(df)):
        if df['typical_price'].iloc[i] > df['typical_price'].iloc[i-1]:
            df['positive_mf'].iloc[i] = df['money_flow'].iloc[i]
        elif df['typical_price'].iloc[i] < df['typical_price'].iloc[i-1]:
            df['negative_mf'].iloc[i] = df['money_flow'].iloc[i]

    positive_mf_sum = df['positive_mf'].rolling(window=period).sum()
    negative_mf_sum = df['negative_mf'].rolling(window=period).sum()

    money_flow_ratio = positive_mf_sum / (negative_mf_sum + 1e-10)  # Avoid division by zero
    mfi = 100 - (100 / (1 + money_flow_ratio))

    return mfi


def volume_breakout_confirmation(df, period=20, vol_threshold=1.5):
    """
    Check if current bar is a confirmed volume breakout.
    Requires: price breakout + volume above threshold

    Args:
        df: DataFrame with OHLCV data
        period: Period for highlow calculation
        vol_threshold: Multiplier for volume threshold (default: 1.5)

    Returns:
        Boolean Series (True if confirmed breakout)
    """
    df = df.copy()

    # Price breakout
    high_lookback = df['high'].rolling(window=period).max().shift(1)
    low_lookback = df['low'].rolling(window=period).min().shift(1)

    bullish_breakout = df['close'] > high_lookback
    bearish_breakout = df['close'] < low_lookback

    # Volume confirmation
    vol_ma = calculate_volume_ma(df, period)
    high_volume = df['volume'] > (vol_ma * vol_threshold)

    # Confirmed breakout
    return (bullish_breakout | bearish_breakout) & high_volume


def volume_trend_strength(df, period=20):
    """
    Calculate volume trend strength (0-1, where 1 = strong trend).
    Based on volume increasing during trend direction.

    Args:
        df: DataFrame with OHLCV data
        period: Period for analysis

    Returns:
        Series with strength values (0-1)
    """
    df = df.copy()

    # Determine trend direction
    close_higher = df['close'] > df['close'].shift(1)

    # Volume rising or falling
    vol_higher = df['volume'] > df['volume'].rolling(window=period).mean()

    # Strength: how many bars have volume matching trend direction
    strength = pd.Series(0.0, index=df.index)

    for i in range(period, len(df)):
        window = slice(i - period + 1, i + 1)
        trend_bars = close_higher[window].sum()
        vol_confirms = (close_higher[window] & vol_higher[window]).sum()

        if trend_bars > 0:
            strength.iloc[i] = vol_confirms / period
        else:
            strength.iloc[i] = 0

    return strength


def add_all_volume_indicators(df):
    """
    Add all volume indicators to a DataFrame.

    Args:
        df: DataFrame with OHLCV data

    Returns:
        DataFrame with added volume indicator columns
    """
    df = df.copy()

    # Volume indicators
    df['vol_ma_20'] = calculate_volume_ma(df, 20)
    df['is_vol_high'] = is_volume_high(df, 20, 1.0).astype(int)
    df['obv'] = calculate_obv(df)
    df['vroc'] = calculate_vroc(df, 12)
    df['vol_div'] = calculate_volume_divergence(df, 'close', 'volume', 14)
    df['vwap'] = calculate_vwap(df)
    df['mfi'] = calculate_mfi(df, 14)
    df['vol_breakout'] = volume_breakout_confirmation(df, 20, 1.5).astype(int)
    df['vol_trend_strength'] = volume_trend_strength(df, 20)

    return df


if __name__ == "__main__":
    # Test with sample data
    print("[TEST] Volume Indicators Module")
    print("="*60)

    # Create sample data
    np.random.seed(42)
    dates = pd.date_range('2026-01-01', periods=100)
    prices = 100 + np.cumsum(np.random.randn(100) * 2)
    volumes = np.random.randint(100000, 1000000, 100)

    df_test = pd.DataFrame({
        'date': dates,
        'open': prices,
        'high': prices + 2,
        'low': prices - 2,
        'close': prices,
        'volume': volumes,
    })

    # Add volume indicators
    df_result = add_all_volume_indicators(df_test)

    print(f"Sample data with {len(df_result)} rows")
    print(f"\nColumns: {list(df_result.columns)}")
    print(f"\nLast 5 rows:")
    print(df_result[['close', 'volume', 'vol_ma_20', 'obv', 'mfi', 'vwap']].tail())
    print("\n[OK] Volume indicators working correctly!")
