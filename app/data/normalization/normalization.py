from typing import Dict
import pandas as pd

TIMEFRAME_MAPPING: Dict[str, str] = {
    "5m": "5min",
    "15m": "15min",
    "30m": "30min",
    "1h": "1h",
    "4h": "4h",
    "daily": "1D",
    "weekly": "W",
}


def resample_candles(df: pd.DataFrame, target_timeframe: str) -> pd.DataFrame:
    """
    Resamples candle data from a lower timeframe to a higher timeframe.
    Args:
        df: Input DataFrame with standard columns
        target_timeframe: One of ['5m', '15m', '30m', '1h', '4h', 'daily', 'weekly']
    Returns:
        Resampled DataFrame.
    """
    if df.empty:
        return df.copy()

    # Verify target timeframe is supported
    if target_timeframe not in TIMEFRAME_MAPPING:
        raise ValueError(f"Unsupported target timeframe: {target_timeframe}")

    # Set timestamp as datetime index if not already
    df_temp = df.copy()
    df_temp["timestamp"] = pd.to_datetime(df_temp["timestamp"])
    df_temp = df_temp.set_index("timestamp")

    # Group by symbol and exchange to avoid mixing them during resampling
    def resample_group(group: pd.DataFrame) -> pd.DataFrame:
        symbol, exchange = group.name
        rule = TIMEFRAME_MAPPING[target_timeframe]
        resampled = group.resample(rule, origin="start_day").agg(
            {
                "open": "first",
                "high": "max",
                "low": "min",
                "close": "last",
                "volume": "sum",
            }
        )
        # Drop intervals with no trade activity
        resampled = resampled.dropna(subset=["open"])
        resampled["symbol"] = symbol
        resampled["exchange"] = exchange
        return resampled

    # Resample
    resampled_df = (
        df_temp.groupby(["symbol", "exchange"], group_keys=False)
        .apply(resample_group)
        .reset_index()
    )

    # Add timeframe metadata back
    resampled_df["timeframe"] = target_timeframe

    standard_cols = [
        "timestamp",
        "symbol",
        "exchange",
        "timeframe",
        "open",
        "high",
        "low",
        "close",
        "volume",
    ]
    return resampled_df[standard_cols].sort_values("timestamp").reset_index(drop=True)
