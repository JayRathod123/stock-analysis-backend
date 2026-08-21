from datetime import datetime, timedelta, timezone
import pandas as pd
import pytest
from app.data.normalization.normalization import resample_candles
from app.data.validation.validator import validate_candles


@pytest.fixture
def base_candles() -> pd.DataFrame:
    """Returns a basic list of 5 valid 15-minute candles."""
    start_time = datetime(2026, 8, 20, 9, 30, 0)
    data = []
    for i in range(5):
        data.append(
            {
                "timestamp": start_time + timedelta(minutes=15 * i),
                "symbol": "RELIANCE",
                "exchange": "NSE",
                "timeframe": "15m",
                "open": 100.0 + i,
                "high": 105.0 + i,
                "low": 98.0 + i,
                "close": 102.0 + i,
                "volume": 1000.0 + (i * 100),
            }
        )
    return pd.DataFrame(data)


def test_valid_candles(base_candles):
    report = validate_candles(base_candles)
    assert report["is_valid"] is True
    assert report["total_candles"] == 5
    assert report["duplicates_found"] == 0
    assert report["failed_ohlc_count"] == 0
    assert report["negative_prices_count"] == 0


def test_duplicate_candles(base_candles):
    # Duplicate first row
    duplicate_row = base_candles.iloc[[0]].copy()
    invalid_df = pd.concat([base_candles, duplicate_row], ignore_index=True)
    report = validate_candles(invalid_df)
    assert report["is_valid"] is False
    assert report["duplicates_found"] == 1


def test_invalid_ohlc(base_candles):
    # Edit high to be less than low
    base_candles.loc[0, "high"] = 90.0
    report = validate_candles(base_candles)
    assert report["is_valid"] is False
    assert report["failed_ohlc_count"] == 1


def test_negative_prices(base_candles):
    # Edit close to be negative
    base_candles.loc[0, "close"] = -10.0
    report = validate_candles(base_candles)
    assert report["is_valid"] is False
    assert report["negative_prices_count"] == 1


def test_resample_candles_15m_to_1h():
    start_time = datetime(2026, 8, 20, 9, 0, 0)
    # Generate 4 candles (covers 1 hour)
    data = []
    for i in range(4):
        data.append(
            {
                "timestamp": start_time + timedelta(minutes=15 * i),
                "symbol": "TCS",
                "exchange": "NSE",
                "timeframe": "15m",
                "open": 100.0 if i == 0 else 102.0,
                "high": 105.0,
                "low": 95.0,
                "close": 103.0 if i == 3 else 101.0,
                "volume": 500.0,
            }
        )
    df_15m = pd.DataFrame(data)
    df_1h = resample_candles(df_15m, "1h")

    assert len(df_1h) == 1
    candle = df_1h.iloc[0]
    assert candle["open"] == 100.0
    assert candle["high"] == 105.0
    assert candle["low"] == 95.0
    assert candle["close"] == 103.0
    assert candle["volume"] == 2000.0  # Sum of all volumes
