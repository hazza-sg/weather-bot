"""SQLAlchemy database models."""
from datetime import datetime
from typing import Optional
from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Boolean,
    DateTime,
    Text,
    JSON,
    ForeignKey,
    Index,
)
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()


class Trade(Base):
    """Trade history model."""

    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, autoincrement=True)
    trade_id = Column(String(64), unique=True, nullable=False, index=True)
    market_id = Column(String(128), nullable=False, index=True)
    token_id = Column(String(128), nullable=False)

    # Trade details
    side = Column(String(3), nullable=False)  # YES or NO
    entry_price = Column(Float, nullable=False)
    exit_price = Column(Float, nullable=True)
    size = Column(Float, nullable=False)

    # Timing
    entry_time = Column(DateTime, nullable=False, default=datetime.utcnow)
    exit_time = Column(DateTime, nullable=True)
    resolution_date = Column(DateTime, nullable=False)

    # P&L
    realized_pnl = Column(Float, nullable=True)
    result = Column(String(10), nullable=True)  # win, loss, pending

    # Strategy metadata
    forecast_probability = Column(Float, nullable=True)
    market_probability = Column(Float, nullable=True)
    edge_at_entry = Column(Float, nullable=True)
    model_agreement = Column(Float, nullable=True)

    # Market info
    location = Column(String(64), nullable=True)
    market_type = Column(String(32), nullable=True)  # temperature, precipitation, etc.
    description = Column(Text, nullable=True)

    # Order tracking
    order_id = Column(String(128), nullable=True)
    order_status = Column(String(20), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_trades_entry_time", "entry_time"),
        Index("ix_trades_result", "result"),
    )


class Position(Base):
    """Open position tracking model."""

    __tablename__ = "positions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    position_id = Column(String(64), unique=True, nullable=False, index=True)
    trade_id = Column(String(64), ForeignKey("trades.trade_id"), nullable=False)

    market_id = Column(String(128), nullable=False, index=True)
    token_id = Column(String(128), nullable=False)

    side = Column(String(3), nullable=False)
    entry_price = Column(Float, nullable=False)
    current_price = Column(Float, nullable=True)
    size = Column(Float, nullable=False)
    quantity = Column(Float, nullable=False)

    unrealized_pnl = Column(Float, default=0.0)
    unrealized_pnl_pct = Column(Float, default=0.0)

    resolution_date = Column(DateTime, nullable=False)
    location = Column(String(64), nullable=True)
    cluster = Column(String(32), nullable=True)
    description = Column(Text, nullable=True)

    is_open = Column(Boolean, default=True)
    opened_at = Column(DateTime, default=datetime.utcnow)
    closed_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (Index("ix_positions_is_open", "is_open"),)


class Market(Base):
    """Monitored market model."""

    __tablename__ = "markets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    market_id = Column(String(128), unique=True, nullable=False, index=True)
    condition_id = Column(String(128), nullable=True)
    token_id_yes = Column(String(128), nullable=True)
    token_id_no = Column(String(128), nullable=True)

    # Market details
    question = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    outcomes = Column(JSON, nullable=True)

    # Parsed criteria
    location = Column(String(64), nullable=True)
    station_id = Column(String(16), nullable=True)
    resolution_date = Column(DateTime, nullable=True)
    variable = Column(String(32), nullable=True)  # temperature_max, precipitation, etc.
    threshold = Column(Float, nullable=True)
    comparison = Column(String(4), nullable=True)  # >=, >, <=, <
    unit = Column(String(16), nullable=True)

    # Market state
    current_price_yes = Column(Float, nullable=True)
    current_price_no = Column(Float, nullable=True)
    liquidity = Column(Float, nullable=True)
    volume = Column(Float, nullable=True)

    # Forecast data
    forecast_probability = Column(Float, nullable=True)
    model_agreement = Column(Float, nullable=True)
    edge = Column(Float, nullable=True)

    # Status
    is_active = Column(Boolean, default=True)
    is_tradeable = Column(Boolean, default=False)
    has_position = Column(Boolean, default=False)
    status = Column(String(20), default="watching")  # watching, opportunity, position_open

    last_price_update = Column(DateTime, nullable=True)
    last_forecast_update = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_markets_is_active", "is_active"),
        Index("ix_markets_resolution_date", "resolution_date"),
    )


class Forecast(Base):
    """Weather forecast cache model."""

    __tablename__ = "forecasts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    market_id = Column(String(128), ForeignKey("markets.market_id"), nullable=False, index=True)

    # Location
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    target_date = Column(DateTime, nullable=False)

    # Forecast data
    model_name = Column(String(32), nullable=False)
    ensemble_values = Column(JSON, nullable=True)  # List of ensemble member values
    probability = Column(Float, nullable=True)

    # Aggregated values
    mean_value = Column(Float, nullable=True)
    median_value = Column(Float, nullable=True)
    std_value = Column(Float, nullable=True)
    min_value = Column(Float, nullable=True)
    max_value = Column(Float, nullable=True)

    # Metadata
    variable = Column(String(32), nullable=True)
    unit = Column(String(16), nullable=True)
    forecast_run_time = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_forecasts_target_date", "target_date"),
        Index("ix_forecasts_model", "model_name"),
    )


class RiskSnapshot(Base):
    """Risk metrics snapshot model."""

    __tablename__ = "risk_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # P&L tracking
    daily_pnl = Column(Float, default=0.0)
    weekly_pnl = Column(Float, default=0.0)
    monthly_pnl = Column(Float, default=0.0)
    total_pnl = Column(Float, default=0.0)

    # Exposure
    total_exposure = Column(Float, default=0.0)
    exposure_pct = Column(Float, default=0.0)
    cluster_exposure = Column(JSON, nullable=True)  # Dict of cluster -> exposure
    same_day_exposure = Column(JSON, nullable=True)  # Dict of date -> exposure

    # Bankroll
    current_bankroll = Column(Float, nullable=True)
    initial_bankroll = Column(Float, nullable=True)

    # Status
    is_halted = Column(Boolean, default=False)
    halt_reason = Column(String(256), nullable=True)
    last_loss_time = Column(DateTime, nullable=True)

    # Timestamps
    snapshot_time = Column(DateTime, default=datetime.utcnow, index=True)
    period_start = Column(DateTime, nullable=True)  # Start of current period (day/week/month)

    created_at = Column(DateTime, default=datetime.utcnow)


class ConfigSetting(Base):
    """User configuration settings model."""

    __tablename__ = "config_settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(64), unique=True, nullable=False, index=True)
    value = Column(JSON, nullable=True)
    category = Column(String(32), nullable=True)
    description = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ActivityLog(Base):
    """Activity log for UI display."""

    __tablename__ = "activity_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    level = Column(String(10), nullable=False)  # ERROR, WARN, INFO, DEBUG
    message = Column(Text, nullable=False)
    category = Column(String(32), nullable=True)  # trade, forecast, risk, system
    details = Column(JSON, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (Index("ix_activity_logs_level", "level"),)
