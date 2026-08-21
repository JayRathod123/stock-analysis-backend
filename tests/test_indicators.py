from datetime import datetime, timedelta
import numpy as np
import pandas as pd
import pytest
from app.analysis.indicators.calculations import (
    calculate_sma,
    calculate_ema,
    calculate_atr,
    calculate_rsi,
    calculate_vwap,
    calculate_relative_volume,
)


@pytest.fixture
def sample_data() -> pd.DataFrame:
    """Generates 30 periods of synthetic stock candles."""
    np.random.seed(42)
    start_time = datetime(2026, 8, 20, 9, 30, 0)
    timestamps = [start_time + timedelta(minutes=15 * i) for i in range(30)]

    close = 100.0 + np.cumsum(np.random.normal(0, 1.0, 30))
    open_p = close - np.random.normal(0, 0.5, 30)
    high = np.maximum(open_p, close) + np.random.uniform(0.1, 1.0, 30)
    low = np.minimum(open_p, close) - np.random.uniform(0.1, 1.0, 30)
    volume = np.random.uniform(100, 1000, 30)

    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "symbol": ["TEST"] * 30,
            "exchange": ["NSE"] * 30,
            "open": open_p,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        }
    )


def test_sma_calculation(sample_data):
    close = sample_data["close"]
    sma_5 = calculate_sma(close, 5)
    assert len(sma_5) == 30
    assert pd.isna(sma_5.iloc[3])
    assert not pd.isna(sma_5.iloc[4])
    expected_sma_4 = close.iloc[0:5].mean()
    assert np.isclose(sma_5.iloc[4], expected_sma_4)


def test_ema_calculation(sample_data):
    close = sample_data["close"]
    ema_5 = calculate_ema(close, 5)
    assert len(ema_5) == 30
    assert pd.isna(ema_5.iloc[3])
    assert not pd.isna(ema_5.iloc[4])


def test_atr_calculation(sample_data):
    high = sample_data["high"]
    low = sample_data["low"]
    close = sample_data["close"]
    atr_14 = calculate_atr(high, low, close, 14)
    assert len(atr_14) == 30
    assert pd.isna(atr_14.iloc[12])
    assert not pd.isna(atr_14.iloc[13])
    assert (atr_14.dropna() > 0).all()


def test_rsi_calculation(sample_data):
    close = sample_data["close"]
    rsi_14 = calculate_rsi(close, 14)
    assert len(rsi_14) == 30
    assert (rsi_14.dropna() >= 0).all()
    assert (rsi_14.dropna() <= 100).all()


def test_vwap_calculation(sample_data):
    vwap = calculate_vwap(sample_data)
    assert len(vwap) == 30
    # VWAP of the first candle (where reset occurs) should be within its High/Low boundaries
    assert vwap.iloc[0] >= sample_data["low"].iloc[0]
    assert vwap.iloc[0] <= sample_data["high"].iloc[0]
    assert not vwap.isna().any()


def test_relative_volume(sample_data):
    rvol = calculate_relative_volume(sample_data["volume"], 20)
    assert len(rvol) == 30
    # Relative volume defaults to 1.0 for the initialization period when SMA is NaN
    assert rvol.iloc[18] == 1.0
    assert not rvol.isna().any()
    assert np.isclose(rvol.iloc[19], sample_data["volume"].iloc[19] / sample_data["volume"].iloc[0:20].mean())


def test_look_ahead_bias_protection(sample_data):
    """
    Assert that modifying a value at time T does not impact calculations
    for periods strictly before T.
    """
    close_original = sample_data["close"].copy()
    rsi_orig = calculate_rsi(close_original, 14)

    # Modify future value at index 25
    close_modified = close_original.copy()
    close_modified.iloc[25] = 999.9

    rsi_mod = calculate_rsi(close_modified, 14)

    # Verify indicators for indexes < 25 are identical
    pd.testing.assert_series_equal(rsi_orig.iloc[:25], rsi_mod.iloc[:25])
