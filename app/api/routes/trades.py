"""Trade endpoints."""
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from app.database import get_session
from app.models.database_models import Trade
from app.models.api_models import (
    TradeCreate,
    TradeResponse,
    TradeList,
    TradeStats,
)
from app.services.trading_engine import TradingEngine, get_trading_engine

router = APIRouter()


@router.get("", response_model=TradeList)
async def get_trades(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    result: Optional[str] = Query(None, pattern="^(win|loss|pending)$"),
    market_type: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_session),
) -> TradeList:
    """Get trade history (paginated)."""
    query = select(Trade)

    # Apply filters
    conditions = []
    if start_date:
        conditions.append(Trade.entry_time >= start_date)
    if end_date:
        conditions.append(Trade.entry_time <= end_date)
    if result:
        conditions.append(Trade.result == result)
    if market_type:
        conditions.append(Trade.market_type == market_type)

    if conditions:
        query = query.where(and_(*conditions))

    # Get total count
    count_query = select(func.count(Trade.id))
    if conditions:
        count_query = count_query.where(and_(*conditions))
    total_result = await session.execute(count_query)
    total_count = total_result.scalar() or 0

    # Apply pagination and ordering
    query = query.order_by(Trade.entry_time.desc()).offset(offset).limit(limit)

    result = await session.execute(query)
    trades = result.scalars().all()

    trade_responses = [
        TradeResponse(
            trade_id=trade.trade_id,
            market_id=trade.market_id,
            description=trade.description,
            side=trade.side,
            entry_price=trade.entry_price,
            exit_price=trade.exit_price,
            size=trade.size,
            entry_time=trade.entry_time,
            exit_time=trade.exit_time,
            resolution_date=trade.resolution_date,
            realized_pnl=trade.realized_pnl,
            result=trade.result,
            forecast_probability=trade.forecast_probability,
            market_probability=trade.market_probability,
            edge_at_entry=trade.edge_at_entry,
            location=trade.location,
            market_type=trade.market_type,
        )
        for trade in trades
    ]

    return TradeList(
        trades=trade_responses,
        count=len(trade_responses),
        total_count=total_count,
        offset=offset,
        limit=limit,
    )


@router.get("/stats", response_model=TradeStats)
async def get_trade_stats(
    period: str = Query("month", pattern="^(day|week|month|all)$"),
    session: AsyncSession = Depends(get_session),
) -> TradeStats:
    """Get trade statistics for a period."""
    now = datetime.utcnow()

    if period == "day":
        start_date = now - timedelta(days=1)
    elif period == "week":
        start_date = now - timedelta(weeks=1)
    elif period == "month":
        start_date = now - timedelta(days=30)
    else:
        start_date = datetime(2020, 1, 1)

    # Query completed trades
    result = await session.execute(
        select(Trade)
        .where(Trade.entry_time >= start_date)
        .where(Trade.result.in_(["win", "loss"]))
    )
    trades = result.scalars().all()

    if not trades:
        return TradeStats(
            period=period,
            total_trades=0,
            wins=0,
            losses=0,
            win_rate=0.0,
            total_pnl=0.0,
            avg_win=0.0,
            avg_loss=0.0,
            profit_factor=0.0,
            avg_edge=0.0,
            edge_captured=0.0,
        )

    wins = [t for t in trades if t.result == "win"]
    losses = [t for t in trades if t.result == "loss"]

    total_wins = sum(t.realized_pnl or 0 for t in wins)
    total_losses = abs(sum(t.realized_pnl or 0 for t in losses))

    avg_win = total_wins / len(wins) if wins else 0
    avg_loss = total_losses / len(losses) if losses else 0

    profit_factor = total_wins / total_losses if total_losses > 0 else float("inf")

    edges = [t.edge_at_entry for t in trades if t.edge_at_entry]
    avg_edge = sum(edges) / len(edges) if edges else 0

    # Edge captured = actual return vs expected
    total_pnl = total_wins - total_losses
    total_size = sum(t.size for t in trades)
    edge_captured = total_pnl / total_size if total_size > 0 else 0

    return TradeStats(
        period=period,
        total_trades=len(trades),
        wins=len(wins),
        losses=len(losses),
        win_rate=len(wins) / len(trades) if trades else 0,
        total_pnl=total_pnl,
        avg_win=avg_win,
        avg_loss=avg_loss,
        profit_factor=profit_factor,
        avg_edge=avg_edge,
        edge_captured=edge_captured,
    )


@router.get("/{trade_id}", response_model=TradeResponse)
async def get_trade(
    trade_id: str,
    session: AsyncSession = Depends(get_session),
) -> TradeResponse:
    """Get single trade details."""
    result = await session.execute(
        select(Trade).where(Trade.trade_id == trade_id)
    )
    trade = result.scalar_one_or_none()

    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")

    return TradeResponse(
        trade_id=trade.trade_id,
        market_id=trade.market_id,
        description=trade.description,
        side=trade.side,
        entry_price=trade.entry_price,
        exit_price=trade.exit_price,
        size=trade.size,
        entry_time=trade.entry_time,
        exit_time=trade.exit_time,
        resolution_date=trade.resolution_date,
        realized_pnl=trade.realized_pnl,
        result=trade.result,
        forecast_probability=trade.forecast_probability,
        market_probability=trade.market_probability,
        edge_at_entry=trade.edge_at_entry,
        location=trade.location,
        market_type=trade.market_type,
    )


@router.post("", response_model=TradeResponse)
async def create_trade(
    trade: TradeCreate,
    engine: TradingEngine = Depends(get_trading_engine),
) -> TradeResponse:
    """Execute a manual trade."""
    result = await engine.execute_manual_trade(
        market_id=trade.market_id,
        side=trade.side,
        size=trade.size,
        price=trade.price,
    )

    if not result.get("success"):
        raise HTTPException(
            status_code=400,
            detail=result.get("message", "Trade execution failed"),
        )

    return TradeResponse(**result["trade"])
