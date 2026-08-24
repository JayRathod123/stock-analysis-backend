from datetime import datetime
from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship


class Stock(SQLModel, table=True):
    __tablename__ = "stock"

    id: Optional[int] = Field(default=None, primary_key=True)
    symbol: str = Field(index=True, unique=True, nullable=False)
    name: str = Field(nullable=False)
    exchange: str = Field(default="NSE", index=True)
    is_active: bool = Field(default=True)

    # Relationships
    candles: List["Candle"] = Relationship(back_populates="stock", cascade_delete=True)
    zones: List["Zone"] = Relationship(back_populates="stock", cascade_delete=True)


class Candle(SQLModel, table=True):
    __tablename__ = "candle"

    id: Optional[int] = Field(default=None, primary_key=True)
    stock_id: int = Field(foreign_key="stock.id", index=True, nullable=False)
    timestamp: datetime = Field(index=True, nullable=False)
    timeframe: str = Field(index=True, nullable=False)
    open: float = Field(nullable=False)
    high: float = Field(nullable=False)
    low: float = Field(nullable=False)
    close: float = Field(nullable=False)
    volume: float = Field(nullable=False)

    # Relationships
    stock: Stock = Relationship(back_populates="candles")


class Zone(SQLModel, table=True):
    __tablename__ = "zone"

    id: Optional[int] = Field(default=None, primary_key=True)
    stock_id: int = Field(foreign_key="stock.id", index=True, nullable=False)
    zone_type: str = Field(index=True, nullable=False)  # DEMAND, SUPPLY
    pattern: str = Field(nullable=False)  # DBR, RBR, RBD, DBD
    timeframe: str = Field(index=True, nullable=False)
    proximal_boundary: float = Field(nullable=False)
    distal_boundary: float = Field(nullable=False)
    base_start_idx: int = Field(nullable=False)
    base_end_idx: int = Field(nullable=False)
    status: str = Field(default="FRESH", index=True, nullable=False)  # FRESH, FIRST_RETEST, SECOND_RETEST, CONSUMED, INVALIDATED
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)

    # Relationships
    stock: Stock = Relationship(back_populates="zones")
    scores: Optional["ZoneScore"] = Relationship(back_populates="zone", cascade_delete=True)
    tests: List["ZoneTest"] = Relationship(back_populates="zone", cascade_delete=True)
    setups: List["TradeSetup"] = Relationship(back_populates="zone", cascade_delete=True)


class ZoneTest(SQLModel, table=True):
    __tablename__ = "zone_test"

    id: Optional[int] = Field(default=None, primary_key=True)
    zone_id: int = Field(foreign_key="zone.id", index=True, nullable=False)
    test_candle_timestamp: datetime = Field(nullable=False)
    penetration_depth: float = Field(nullable=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    zone: Zone = Relationship(back_populates="tests")


class ZoneScore(SQLModel, table=True):
    __tablename__ = "zone_score"

    id: Optional[int] = Field(default=None, primary_key=True)
    zone_id: int = Field(foreign_key="zone.id", index=True, nullable=False)
    base_quality: float = Field(default=0.0)
    departure: float = Field(default=0.0)
    freshness: float = Field(default=0.0)
    authentication: float = Field(default=0.0)
    participation: float = Field(default=0.0)
    structure: float = Field(default=0.0)
    trend_alignment: float = Field(default=0.0)
    ma_vwap_context: float = Field(default=0.0)
    risk_reward: float = Field(default=0.0)
    final_score: float = Field(default=0.0)
    rating_class: str = Field(default="Watch")  # A+, Strong, Watch, Reject

    # Relationships
    zone: Zone = Relationship(back_populates="scores")


class TradeSetup(SQLModel, table=True):
    __tablename__ = "trade_setup"

    id: Optional[int] = Field(default=None, primary_key=True)
    zone_id: int = Field(foreign_key="zone.id", index=True, nullable=False)
    entry_price: float = Field(nullable=False)
    stop_loss: float = Field(nullable=False)
    target_1: float = Field(nullable=False)
    target_2: float = Field(nullable=False)
    rr_ratio: float = Field(nullable=False)
    status: str = Field(default="PENDING", index=True)  # PENDING, ACTIVE, TARGET_1_HIT, TARGET_2_HIT, STOP_LOSS_HIT, CANCELLED
    setup_type: str = Field(index=True)  # INTRADAY, SWING
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    zone: Zone = Relationship(back_populates="setups")


class Backtest(SQLModel, table=True):
    __tablename__ = "backtest"

    id: Optional[int] = Field(default=None, primary_key=True)
    symbol: str = Field(index=True, nullable=False)
    timeframe: str = Field(nullable=False)
    start_date: datetime = Field(nullable=False)
    end_date: datetime = Field(nullable=False)
    total_trades: int = Field(default=0)
    win_rate: float = Field(default=0.0)
    profit_factor: float = Field(default=0.0)
    expectancy: float = Field(default=0.0)
    max_drawdown: float = Field(default=0.0)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)

    trades: List["BacktestTrade"] = Relationship(back_populates="backtest", cascade_delete=True)


class BacktestTrade(SQLModel, table=True):
    __tablename__ = "backtest_trade"

    id: Optional[int] = Field(default=None, primary_key=True)
    backtest_id: int = Field(foreign_key="backtest.id", index=True, nullable=False)
    symbol: str = Field(nullable=False)
    direction: str = Field(nullable=False)  # LONG, SHORT
    entry_time: datetime = Field(nullable=False)
    entry_price: float = Field(nullable=False)
    exit_time: Optional[datetime] = Field(default=None)
    exit_price: Optional[float] = Field(default=None)
    result_r: float = Field(default=0.0)
    outcome: str = Field(nullable=False)  # WIN, LOSS, PENDING

    # Relationships
    backtest: Backtest = Relationship(back_populates="trades")


class AnalysisRun(SQLModel, table=True):
    __tablename__ = "analysis_run"

    id: Optional[int] = Field(default=None, primary_key=True)
    symbol: str = Field(index=True, nullable=False)
    current_price: float = Field(nullable=False)
    market_bias: str = Field(nullable=False)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)

class DailyScan(SQLModel, table=True):
    __tablename__ = "daily_scans"

    id: Optional[int] = Field(default=None, primary_key=True)
    scan_date: datetime = Field(default_factory=datetime.utcnow, index=True)
    symbol: str = Field(index=True)
    name: str = Field(default="")
    setup_type: str = Field(default="") # INTRADAY or SWING
    entry_price: float = Field(default=0.0)
    stop_loss: float = Field(default=0.0)
    target_price: float = Field(default=0.0)
    score: str = Field(default="")
    ai_summary: Optional[str] = Field(default=None)
