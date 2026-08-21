class StockAnalysisException(Exception):
    """Base exception for all application errors."""
    pass


class DataQualityException(StockAnalysisException):
    """Raised when ingested candles fail validation checks."""
    pass


class DatabaseException(StockAnalysisException):
    """Raised when database interactions fail."""
    pass


class AnalysisException(StockAnalysisException):
    """Raised when an error occurs during the indicator or zone calculation."""
    pass


class AIException(StockAnalysisException):
    """Raised when AI explanations fail."""
    pass
