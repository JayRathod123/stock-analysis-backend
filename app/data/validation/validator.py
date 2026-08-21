from datetime import datetime, timezone
from typing import Dict, Any, List
import numpy as np
import pandas as pd


def validate_candles(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Validates candle records for data integrity.
    Returns a dictionary quality report.
    """
    report: Dict[str, Any] = {
        "total_candles": len(df),
        "duplicates_found": 0,
        "gaps_found": 0,
        "failed_ohlc_count": 0,
        "negative_prices_count": 0,
        "warnings": [],
        "is_valid": True,
    }

    if df.empty:
        report["warnings"].append("Input candles DataFrame is empty.")
        return report

    # 1. Duplicate check
    duplicates = df.duplicated(subset=["timestamp", "symbol", "timeframe"], keep="first").sum()
    report["duplicates_found"] = int(duplicates)

    # 2. Zero/negative check
    negative_prices = (
        (df["open"] <= 0) | (df["high"] <= 0) | (df["low"] <= 0) | (df["close"] <= 0)
    ).sum()
    negative_volume = (df["volume"] < 0).sum()
    report["negative_prices_count"] = int(negative_prices + negative_volume)

    # 3. Physical boundaries (OHLC relationship validation)
    failed_ohlc = (
        (df["high"] < df["low"])
        | (df["high"] < df["open"])
        | (df["high"] < df["close"])
        | (df["low"] > df["open"])
        | (df["low"] > df["close"])
    ).sum()
    report["failed_ohlc_count"] = int(failed_ohlc)

    # 4. Check for future timestamps
    now = datetime.now(timezone.utc)
    future_timestamps = (pd.to_datetime(df["timestamp"]).dt.tz_localize(None) > now.replace(tzinfo=None)).sum()
    if future_timestamps > 0:
        report["warnings"].append(f"Found {future_timestamps} candles with timestamps in the future.")

    # 5. Gap checks (Check differences in consecutive candles)
    # We sort by timestamp first to measure sequential steps
    sorted_df = df.sort_values("timestamp").reset_index(drop=True)
    timestamps = pd.to_datetime(sorted_df["timestamp"])
    diffs = timestamps.diff().dropna()
    
    if len(diffs) > 0:
        # Determine the most common/expected interval mode (in minutes/seconds)
        mode_diff = diffs.mode()
        if not mode_diff.empty:
            expected_diff = mode_diff[0]
            # Gaps are diffs that are larger than the expected mode
            # We filter out gaps that could be standard session boundaries (e.g., overnight/weekend gap)
            # A gap is defined as any sequence missing more than 1 period within session hours
            # For simplicity, we flag diffs > 3x the expected timeframe duration
            gaps = (diffs > expected_diff * 3).sum()
            report["gaps_found"] = int(gaps)
            if gaps > 0:
                report["warnings"].append(f"Detected {gaps} unexpected gaps in the timestamp sequence.")

    # 6. Abnormal volume checks
    if len(df) >= 20:
        rolling_mean = df["volume"].rolling(20, min_periods=1).mean()
        rolling_std = df["volume"].rolling(20, min_periods=1).std().fillna(0)
        outlier_volume = (df["volume"] > (rolling_mean + 5 * rolling_std)).sum()
        if outlier_volume > 0:
            report["warnings"].append(
                f"Flagged {outlier_volume} candles with abnormally high volume (> 5x rolling std dev)."
            )

    # Compile validation state
    if (
        report["duplicates_found"] > 0
        or report["failed_ohlc_count"] > 0
        or report["negative_prices_count"] > 0
        or future_timestamps > 0
    ):
        report["is_valid"] = False

    return report
