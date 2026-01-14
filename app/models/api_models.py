"""Pydantic models for API request/response schemas."""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


# === System Models ===


class SystemStatus(BaseModel):
    """System health and status response."""

    status: str = Field(..., description="Current system status")
    uptime_seconds: int = Field(..., description="Time since startup")
    trading_enabled: bool = Field(..., description="Whether trading is active")
    last_trade_time: Optional[datetime] = Field(None, description="Time of last trade")
    open_positions_count: int = Field(0, description="Number of open positions")
    pending_orders_count: int = Field(0, description="Number of pending orders")
    api_connected: bool = Field(True, description="Polymarket API connection status")
    forecast_data_age_seconds: Optional[int] = Field(
        None, description="Age of forecast data in seconds"
    )
    errors: List[str] = Field(default_factory=list, description="Current errors")


class ControlAction(BaseModel):
    """Control action request."""

    action: str = Field(..., description="Action to perform: start, pause, stop")


class ControlResponse(BaseModel):
    """Control action response."""

    success: bool
    message: str
    new_status: str


# === Portfolio Models ===


class PortfolioSummary(BaseModel):
    """Portfolio overview metrics."""

    bankroll: float = Field(..., description="Current wallet balance")
    initial_bankroll: float = Field(..., description="Starting bankroll")
    total_exposure: float = Field(..., description="Total capital in positions")
    exposure_percentage: float = Field(..., description="Exposure as % of bankroll")
    unrealized_pnl: float = Field(0.0, description="Unrealized P&L")
    daily_pnl: float = Field(0.0, description="Today's P&L")
    weekly_pnl: float = Field(0.0, description="This week's P&L")
    monthly_pnl: float = Field(0.0, description="This month's P&L")
    total_trades: int = Field(0, description="Total trades executed")
    win_rate: float = Field(0.0, description="Win rate (0-1)")
    profit_factor: float = Field(0.0, description="Profit factor")


class ExposureBreakdown(BaseModel):
    """Exposure breakdown by category."""

    total_exposure: float
    max_exposure: float
    exposure_pct: float
    cluster_exposure: Dict[str, float]
    resolution_date_exposure: Dict[str, float]


class PerformancePoint(BaseModel):
    """Single point in performance timeseries."""

    timestamp: datetime
    bankroll: float
    pnl: float


class PerformanceData(BaseModel):
    """Performance timeseries data."""

    points: List[PerformancePoint]
    period: str


# === Position Models ===


class PositionResponse(BaseModel):
    """Open position details."""

    position_id: str
    market_id: str
    description: str
    side: str
    entry_price: float
    current_price: Optional[float]
    size: float
    quantity: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    resolution_date: datetime
    hours_to_resolution: float
    location: Optional[str]
    forecast_probability: Optional[float]
    market_probability: Optional[float]
    edge_at_entry: Optional[float]
    opened_at: datetime


class PositionList(BaseModel):
    """List of positions response."""

    positions: List[PositionResponse]
    count: int
    total_exposure: float
    total_unrealized_pnl: float


class ClosePositionRequest(BaseModel):
    """Request to close a position."""

    position_id: str


class ClosePositionResponse(BaseModel):
    """Response after closing a position."""

    success: bool
    message: str
    realized_pnl: Optional[float]


# === Market Models ===


class MarketResponse(BaseModel):
    """Market details response."""

    id: str
    market_id: str
    description: str
    location: Optional[str]
    resolution_date: Optional[datetime]
    hours_to_resolution: Optional[float]
    variable: Optional[str]
    threshold: Optional[float]
    comparison: Optional[str]
    forecast_probability: Optional[float]
    market_price: Optional[float]
    edge: Optional[float]
    model_agreement: Optional[float]
    liquidity: Optional[float]
    volume: Optional[float]
    status: str
    position_open: bool
    is_tradeable: bool


class MarketList(BaseModel):
    """List of markets response."""

    markets: List[MarketResponse]
    count: int
    opportunities_count: int


class ForecastBreakdown(BaseModel):
    """Detailed forecast breakdown for a market."""

    market_id: str
    target_date: datetime
    models: Dict[str, Dict[str, Any]]  # model_name -> {probability, ensemble_values, etc.}
    aggregated_probability: float
    model_agreement: float


# === Trade Models ===


class TradeCreate(BaseModel):
    """Manual trade request."""

    market_id: str
    side: str = Field(..., pattern="^(YES|NO)$")
    size: float = Field(..., gt=0)
    price: Optional[float] = Field(None, description="Limit price, None for market")


class TradeResponse(BaseModel):
    """Trade details response."""

    trade_id: str
    market_id: str
    description: Optional[str]
    side: str
    entry_price: float
    exit_price: Optional[float]
    size: float
    entry_time: datetime
    exit_time: Optional[datetime]
    resolution_date: datetime
    realized_pnl: Optional[float]
    result: Optional[str]
    forecast_probability: Optional[float]
    market_probability: Optional[float]
    edge_at_entry: Optional[float]
    location: Optional[str]
    market_type: Optional[str]


class TradeList(BaseModel):
    """Paginated trade list response."""

    trades: List[TradeResponse]
    count: int
    total_count: int
    offset: int
    limit: int


class TradeStats(BaseModel):
    """Trade statistics for a period."""

    period: str
    total_trades: int
    wins: int
    losses: int
    win_rate: float
    total_pnl: float
    avg_win: float
    avg_loss: float
    profit_factor: float
    avg_edge: float
    edge_captured: float


# === Risk Models ===


class RiskStatus(BaseModel):
    """Current risk metrics."""

    # Exposure
    total_exposure: float
    max_exposure: float
    exposure_pct: float

    # Cluster exposure
    cluster_exposure: Dict[str, float]
    cluster_limits: Dict[str, float]

    # Same-day exposure
    same_day_exposure: Dict[str, float]
    same_day_limit: float

    # Drawdown status
    daily_pnl: float
    daily_limit: float
    daily_buffer: float
    weekly_pnl: float
    weekly_limit: float
    weekly_buffer: float
    monthly_pnl: float
    monthly_limit: float
    monthly_buffer: float

    # Halt conditions
    is_halted: bool
    halt_reason: Optional[str]
    halt_conditions: Dict[str, Dict[str, Any]]


class RiskLimits(BaseModel):
    """Configured risk limits."""

    max_daily_loss_pct: float
    max_weekly_loss_pct: float
    max_monthly_loss_pct: float
    max_total_exposure_pct: float
    max_cluster_exposure_pct: float
    max_same_day_resolution_pct: float
    min_hours_before_resolution: int


# === Config Models ===


class ConfigSection(BaseModel):
    """Configuration section."""

    name: str
    settings: Dict[str, Any]


class ConfigUpdate(BaseModel):
    """Configuration update request."""

    section: str
    settings: Dict[str, Any]


class ConfigResponse(BaseModel):
    """Full configuration response."""

    strategy: Dict[str, Any]
    position_sizing: Dict[str, Any]
    risk: Dict[str, Any]
    diversification: Dict[str, Any]
    system: Dict[str, Any]


# === WebSocket Models ===


class WebSocketMessage(BaseModel):
    """WebSocket message format."""

    type: str
    timestamp: datetime
    data: Dict[str, Any]


class SubscribeMessage(BaseModel):
    """WebSocket subscribe message."""

    type: str = "subscribe"
    channels: List[str]


class UnsubscribeMessage(BaseModel):
    """WebSocket unsubscribe message."""

    type: str = "unsubscribe"
    channels: List[str]


# === Error Models ===


class ErrorResponse(BaseModel):
    """Error response format."""

    error: bool = True
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None
