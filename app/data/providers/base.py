from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Dict, Any, Optional
import pandas as pd


class MarketDataProvider(ABC):
    """Abstract Base Class for historical stock market data retrieval."""

    @abstractmethod
    def get_historical_candles(
        self,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime,
    ) -> pd.DataFrame:
        """
        Fetch historical candle data for a given symbol, timeframe, and date range.
        Returns a pandas DataFrame with columns:
        ['timestamp', 'symbol', 'exchange', 'timeframe', 'open', 'high', 'low', 'close', 'volume']
        """
        pass

    @abstractmethod
    def search_symbols(self, query: str) -> List[Dict[str, Any]]:
        """
        Search for ticker symbols matching a string.
        Returns a list of dictionaries with stock metadata.
        """
        pass

    @abstractmethod
    def get_supported_timeframes(self) -> List[str]:
        """
        Returns a list of timeframe keys supported natively by the provider.
        """
        pass
