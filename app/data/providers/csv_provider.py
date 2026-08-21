import os
from datetime import datetime
from typing import List, Dict, Any
import pandas as pd
from app.data.providers.base import MarketDataProvider


class CSVMarketDataProvider(MarketDataProvider):
    """Local CSV-based market data provider for offline testing and backtesting."""

    def __init__(self, data_directory: str = "data/raw"):
        self.data_directory = data_directory
        # Ensure directory exists
        os.makedirs(self.data_directory, exist_ok=True)

    def _get_filename(self, symbol: str, timeframe: str) -> str:
        return os.path.join(self.data_directory, f"{symbol.upper()}_{timeframe}.csv")

    def get_historical_candles(
        self,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime,
    ) -> pd.DataFrame:
        """
        Reads candle data from '{symbol}_{timeframe}.csv'.
        Expected CSV headers: timestamp, open, high, low, close, volume (exchange/symbol optional)
        """
        filepath = self._get_filename(symbol, timeframe)
        if not os.path.exists(filepath):
            # Return empty DataFrame conforming to the schema
            return pd.DataFrame(
                columns=[
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
            )

        df = pd.read_csv(filepath)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df[(df["timestamp"] >= pd.to_datetime(start_date)) & (df["timestamp"] <= pd.to_datetime(end_date))]

        # Ensure all standard columns are present
        if "symbol" not in df.columns:
            df["symbol"] = symbol.upper()
        if "exchange" not in df.columns:
            df["exchange"] = "NSE"
        if "timeframe" not in df.columns:
            df["timeframe"] = timeframe

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
        return df[standard_cols].sort_values("timestamp").reset_index(drop=True)

    def search_symbols(self, query: str) -> List[Dict[str, Any]]:
        """Scans the data directory and returns symbols match."""
        symbols = set()
        if not os.path.exists(self.data_directory):
            return []

        for filename in os.listdir(self.data_directory):
            if filename.endswith(".csv"):
                # Expecting symbol_timeframe.csv
                parts = filename.split("_")
                if parts:
                    symbol = parts[0]
                    if query.upper() in symbol.upper():
                        symbols.add(symbol.upper())

        return [{"symbol": sym, "exchange": "NSE", "name": f"{sym} Stock"} for sym in sorted(symbols)]

    def get_supported_timeframes(self) -> List[str]:
        return ["5m", "15m", "30m", "1h", "4h", "daily", "weekly"]
