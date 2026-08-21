import numpy as np
import pandas as pd


def calculate_sma(series: pd.Series, period: int) -> pd.Series:
    """Calculates Simple Moving Average."""
    return series.rolling(window=period, min_periods=period).mean()


def calculate_ema(series: pd.Series, period: int) -> pd.Series:
    """Calculates Exponential Moving Average."""
    return series.ewm(span=period, adjust=False, min_periods=period).mean()


def calculate_atr(
    high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14
) -> pd.Series:
    """Calculates Average True Range."""
    # True Range calculation
    high_low = high - low
    high_close_prev = (high - close.shift(1)).abs()
    low_close_prev = (low - close.shift(1)).abs()

    tr = pd.concat([high_low, high_close_prev, low_close_prev], axis=1).max(axis=1)

    # First ATR value is the average of first 14 TR values
    # Wilder's smoothing technique for ATR:
    atr = tr.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    return atr


def calculate_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Calculates Relative Strength Index."""
    delta = close.diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    # Wilder's moving average smoothing
    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)  # Neutral fallback for zero division


def calculate_vwap(df: pd.DataFrame) -> pd.Series:
    """
    Calculates Volume Weighted Average Price.
    For intraday timeframes, VWAP resets daily.
    """
    required_cols = ["high", "low", "close", "volume", "timestamp"]
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"Missing required column for VWAP: {col}")

    typical_price = (df["high"] + df["low"] + df["close"]) / 3.0
    pv = typical_price * df["volume"]

    # Extract date to identify daily sessions
    dates = pd.to_datetime(df["timestamp"]).dt.date

    # Group by date and calculate cumulative sums
    df_temp = pd.DataFrame(
        {"pv": pv, "volume": df["volume"], "date": dates}, index=df.index
    )

    # Calculate cumulative sums resetting daily
    cum_pv = df_temp.groupby("date")["pv"].cumsum()
    cum_vol = df_temp.groupby("date")["volume"].cumsum()

    vwap = cum_pv / cum_vol.replace(0, np.nan)
    return vwap.fillna(df["close"])  # Fallback to close price if volume is zero


def calculate_relative_volume(volume: pd.Series, period: int = 20) -> pd.Series:
    """
    Calculates Relative Volume.
    Ratio of current volume to its simple moving average over the specified period.
    """
    vol_sma = calculate_sma(volume, period)
    relative_vol = volume / vol_sma.replace(0, np.nan)
    return relative_vol.fillna(1.0)
