"""Portfolio endpoints."""
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_session
from app.models.database_models import Trade, Position
from app.models.api_models import (
    PortfolioSummary,
    PositionResponse,
    PositionList,
    ExposureBreakdown,
    PerformanceData,
    PerformancePoint,
    ClosePositionRequest,
    ClosePositionResponse,
)
from app.services.trading_engine import TradingEngine, get_trading_engine

router = APIRouter()


@router.get("/summary", response_model=PortfolioSummary)
async def get_portfolio_summary(
    engine: TradingEngine = Depends(get_trading_engine),
) -> PortfolioSummary:
    """Get portfolio overview metrics."""
    return await engine.get_portfolio_summary()


@router.get("/positions", response_model=PositionList)
async def get_positions(
    engine: TradingEngine = Depends(get_trading_engine),
) -> PositionList:
    """Get all open positions."""
    positions = await engine.get_open_positions()

    total_exposure = sum(p.size for p in positions)
    total_unrealized = sum(p.unrealized_pnl for p in positions)

    return PositionList(
        positions=positions,
        count=len(positions),
        total_exposure=total_exposure,
        total_unrealized_pnl=total_unrealized,
    )


@router.get("/exposure", response_model=ExposureBreakdown)
async def get_exposure_breakdown(
    engine: TradingEngine = Depends(get_trading_engine),
) -> ExposureBreakdown:
    """Get exposure breakdown by category."""
    return await engine.get_exposure_breakdown()


@router.get("/performance", response_model=PerformanceData)
async def get_performance(
    period: str = Query("week", pattern="^(day|week|month|all)$"),
    session: AsyncSession = Depends(get_session),
) -> PerformanceData:
    """Get performance timeseries data."""
    # Calculate date range
    now = datetime.utcnow()
    if period == "day":
        start_date = now - timedelta(days=1)
    elif period == "week":
        start_date = now - timedelta(weeks=1)
    elif period == "month":
        start_date = now - timedelta(days=30)
    else:
        start_date = datetime(2020, 1, 1)

    # Query trades in period
    result = await session.execute(
        select(Trade)
        .where(Trade.entry_time >= start_date)
        .where(Trade.exit_time.isnot(None))
        .order_by(Trade.exit_time)
    )
    trades = result.scalars().all()

    # Build performance points
    points = []
    cumulative_pnl = 0.0

    for trade in trades:
        if trade.realized_pnl is not None:
            cumulative_pnl += trade.realized_pnl
            points.append(
                PerformancePoint(
                    timestamp=trade.exit_time,
                    bankroll=100 + cumulative_pnl,  # Assuming $100 start
                    pnl=cumulative_pnl,
                )
            )

    return PerformanceData(points=points, period=period)


@router.delete("/positions/{position_id}", response_model=ClosePositionResponse)
async def close_position(
    position_id: str,
    engine: TradingEngine = Depends(get_trading_engine),
) -> ClosePositionResponse:
    """Manually close a position."""
    result = await engine.close_position(position_id)
    return ClosePositionResponse(
        success=result.get("success", False),
        message=result.get("message", ""),
        realized_pnl=result.get("realized_pnl"),
    )
