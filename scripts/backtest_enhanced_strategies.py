#!/usr/bin/env python3
"""
Enhanced trading strategies using volume indicators.
Improves on original strategies with volume confirmation and divergence detection.
"""

import numpy as np
import pandas as pd
from volume_indicators import (
    calculate_volume_ma, is_volume_high, calculate_obv,
    calculate_vroc, calculate_volume_divergence, calculate_vwap,
    calculate_mfi, volume_breakout_confirmation
)


class EnhancedMeanReversionRSI:
    """Mean reversion strategy with volume divergence confirmation."""

    def __init__(self, rsi_period=14, rsi_oversold=30, vol_period=20, vol_threshold=1.0):
        self.rsi_period = rsi_period
        self.rsi_oversold = rsi_oversold
        self.vol_period = vol_period
        self.vol_threshold = vol_threshold

    def calculate_rsi(self, prices, period=14):
        deltas = np.diff(prices)
        seed = deltas[:period+1]
        up = seed[seed >= 0].sum() / period
        down = -seed[seed < 0].sum() / period
        rs = up / (down + 1e-10)

        rsi = np.zeros_like(prices)
        rsi[:period] = 100. - 100. / (1. + rs)

        for i in range(period, len(prices)):
            delta = deltas[i-1]
            if delta > 0:
                upval = delta
                downval = 0.
            else:
                upval = 0.
                downval = -delta

            up = (up * (period - 1) + upval) / period
            down = (down * (period - 1) + downval) / period
            rs = up / (down + 1e-10)
            rsi[i] = 100. - 100. / (1. + rs)

        return rsi

    def calculate_atr(self, df, period=14):
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())

        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = np.max(ranges, axis=1)
        return true_range.rolling(period).mean()

    def generate_signals(self, df):
        """Generate buy/sell signals with volume confirmation."""
        df = df.copy()

        # Calculate indicators
        df['rsi'] = self.calculate_rsi(df['close'].values, self.rsi_period)
        df['atr'] = self.calculate_atr(df)
        df['vol_ma'] = calculate_volume_ma(df, self.vol_period)
        df['vol_div'] = calculate_volume_divergence(df, 'close', 'volume')

        # Buy signal: RSI oversold + high volume (capitulation)
        df['buy'] = (df['rsi'] < self.rsi_oversold) & \
                    (df['volume'] > df['vol_ma'] * self.vol_threshold) & \
                    (df['vol_div'] == 1)  # Bullish divergence

        # Sell signal: RSI recovery + high volume
        df['sell'] = (df['rsi'] > 70) & (df['volume'] > df['vol_ma'] * self.vol_threshold)

        return df


class EnhancedBreakoutStrategy:
    """Breakout strategy with volume confirmation (most improved)."""

    def __init__(self, lookback=20, vol_threshold=1.5):
        self.lookback = lookback
        self.vol_threshold = vol_threshold

    def generate_signals(self, df):
        """Generate breakout signals with HIGH VOLUME confirmation."""
        df = df.copy()

        # Calculate volume moving average
        df['vol_ma'] = calculate_volume_ma(df, self.lookback)

        # Determine resistance/support
        df['resistance'] = df['high'].rolling(window=self.lookback).max().shift(1)
        df['support'] = df['low'].rolling(window=self.lookback).min().shift(1)

        # Volume confirmation: CRITICAL for breakouts
        df['high_volume'] = df['volume'] > (df['vol_ma'] * self.vol_threshold)

        # Buy: Price breaks above resistance on high volume
        df['buy'] = (df['close'] > df['resistance']) & df['high_volume']

        # Sell: Price breaks below support on high volume
        df['sell'] = (df['close'] < df['support']) & df['high_volume']

        return df


class EnhancedBollingerBandMeanReversion:
    """Bollinger Band strategy with volume and MFI confirmation."""

    def __init__(self, period=20, num_std=2, mfi_period=14):
        self.period = period
        self.num_std = num_std
        self.mfi_period = mfi_period

    def generate_signals(self, df):
        """Generate mean reversion signals with volume confirmation."""
        df = df.copy()

        # Bollinger Bands
        df['sma'] = df['close'].rolling(window=self.period).mean()
        df['std'] = df['close'].rolling(window=self.period).std()
        df['upper_band'] = df['sma'] + (df['std'] * self.num_std)
        df['lower_band'] = df['sma'] - (df['std'] * self.num_std)

        # Volume and MFI confirmation
        df['vol_ma'] = calculate_volume_ma(df, self.period)
        df['high_volume'] = df['volume'] > df['vol_ma']
        df['mfi'] = calculate_mfi(df, self.mfi_period)

        # Buy: Price at lower band + high volume + MFI oversold
        df['buy'] = (df['close'] < df['lower_band']) & \
                    df['high_volume'] & \
                    (df['mfi'] < 30)

        # Sell: Price at upper band + MFI overbought
        df['sell'] = (df['close'] > df['upper_band']) & (df['mfi'] > 70)

        return df


class EnhancedMACDStrategy:
    """MACD strategy with volume divergence detection."""

    def __init__(self, fast=12, slow=26, signal=9):
        self.fast = fast
        self.slow = slow
        self.signal = signal

    def calculate_macd(self, prices):
        ema_fast = pd.Series(prices).ewm(span=self.fast).mean()
        ema_slow = pd.Series(prices).ewm(span=self.slow).mean()
        macd = ema_fast - ema_slow
        signal_line = macd.ewm(span=self.signal).mean()
        histogram = macd - signal_line
        return macd.values, signal_line.values, histogram.values

    def generate_signals(self, df):
        """Generate MACD signals with volume divergence check."""
        df = df.copy()

        macd, signal, histogram = self.calculate_macd(df['close'].values)
        df['macd'] = macd
        df['signal'] = signal
        df['histogram'] = histogram

        # Volume divergence
        df['vol_div'] = calculate_volume_divergence(df, 'close', 'volume', 14)

        # Buy: MACD crosses above signal line + bullish divergence
        df['buy'] = (df['histogram'] > 0) & (df['histogram'].shift(1) <= 0) & \
                    (df['vol_div'] >= 0)  # No bearish divergence

        # Sell: MACD crosses below signal line
        df['sell'] = (df['histogram'] < 0) & (df['histogram'].shift(1) >= 0)

        return df


class EnhancedMovingAverageCrossover:
    """Moving average crossover with volume confirmation."""

    def __init__(self, fast=50, slow=200, vol_threshold=1.0):
        self.fast = fast
        self.slow = slow
        self.vol_threshold = vol_threshold

    def generate_signals(self, df):
        """Generate MA crossover signals with volume filter."""
        df = df.copy()

        df['sma_fast'] = df['close'].rolling(window=self.fast).mean()
        df['sma_slow'] = df['close'].rolling(window=self.slow).mean()

        # Volume filter
        df['vol_ma'] = calculate_volume_ma(df, 20)
        df['adequate_volume'] = df['volume'] > (df['vol_ma'] * self.vol_threshold)

        # Buy: Fast MA crosses above slow MA on volume
        df['buy'] = (df['sma_fast'] > df['sma_slow']) & \
                    (df['sma_fast'].shift(1) <= df['sma_slow'].shift(1)) & \
                    df['adequate_volume']

        # Sell: Fast MA crosses below slow MA
        df['sell'] = (df['sma_fast'] < df['sma_slow']) & \
                     (df['sma_fast'].shift(1) >= df['sma_slow'].shift(1))

        return df


class EnhancedVolatilityBreakout:
    """Volatility breakout strategy with volume confirmation."""

    def __init__(self, atr_period=14, atr_multiplier=2.0):
        self.atr_period = atr_period
        self.atr_multiplier = atr_multiplier

    def calculate_atr(self, df, period=14):
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())

        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = np.max(ranges, axis=1)
        return true_range.rolling(period).mean()

    def generate_signals(self, df):
        """Generate volatility breakout signals with volume."""
        df = df.copy()

        df['atr'] = self.calculate_atr(df, self.atr_period)
        df['vol_ma'] = calculate_volume_ma(df, 20)

        # Determine support/resistance with ATR
        df['resistance'] = df['close'].shift(1) + (df['atr'] * self.atr_multiplier)
        df['support'] = df['close'].shift(1) - (df['atr'] * self.atr_multiplier)

        # Volume confirmation
        df['high_volume'] = df['volume'] > df['vol_ma']

        # Buy: Price breaks resistance on volume
        df['buy'] = (df['close'] > df['resistance']) & df['high_volume']

        # Sell: Price breaks support
        df['sell'] = (df['close'] < df['support']) & df['high_volume']

        return df


class EnhancedRSIDivergence:
    """RSI divergence strategy with volume confirmation."""

    def __init__(self, rsi_period=14):
        self.rsi_period = rsi_period

    def calculate_rsi(self, prices, period=14):
        deltas = np.diff(prices)
        seed = deltas[:period+1]
        up = seed[seed >= 0].sum() / period
        down = -seed[seed < 0].sum() / period
        rs = up / (down + 1e-10)

        rsi = np.zeros_like(prices)
        rsi[:period] = 100. - 100. / (1. + rs)

        for i in range(period, len(prices)):
            delta = deltas[i-1]
            if delta > 0:
                upval = delta
                downval = 0.
            else:
                upval = 0.
                downval = -delta

            up = (up * (period - 1) + upval) / period
            down = (down * (period - 1) + downval) / period
            rs = up / (down + 1e-10)
            rsi[i] = 100. - 100. / (1. + rs)

        return rsi

    def generate_signals(self, df):
        """Generate RSI divergence signals with volume confirmation."""
        df = df.copy()

        df['rsi'] = self.calculate_rsi(df['close'].values, self.rsi_period)
        df['vol_div'] = calculate_volume_divergence(df, 'close', 'volume', 14)
        df['vol_ma'] = calculate_volume_ma(df, 20)

        # Buy: Bullish divergence (lower low, higher RSI) + volume confirmation
        df['buy'] = (df['vol_div'] == 1) & \
                    (df['rsi'] > 40) & \
                    (df['volume'] > df['vol_ma'])

        # Sell: Bearish divergence (higher high, lower RSI)
        df['sell'] = (df['vol_div'] == -1) & (df['rsi'] < 60)

        return df


# Dictionary mapping strategy names to classes
ENHANCED_STRATEGIES = {
    'EnhancedMeanReversionRSI': EnhancedMeanReversionRSI,
    'EnhancedBreakoutStrategy': EnhancedBreakoutStrategy,
    'EnhancedBollingerBandMeanReversion': EnhancedBollingerBandMeanReversion,
    'EnhancedMACDStrategy': EnhancedMACDStrategy,
    'EnhancedMovingAverageCrossover': EnhancedMovingAverageCrossover,
    'EnhancedVolatilityBreakout': EnhancedVolatilityBreakout,
    'EnhancedRSIDivergence': EnhancedRSIDivergence,
}

if __name__ == "__main__":
    print("[OK] Enhanced strategies module loaded")
    print(f"Available strategies: {list(ENHANCED_STRATEGIES.keys())}")
