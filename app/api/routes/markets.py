"""Market endpoints."""
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_session
from app.models.database_models import Market, Forecast
from app.models.api_models import MarketResponse, MarketList, ForecastBreakdown
from app.services.trading_engine import TradingEngine, get_trading_engine

router = APIRouter()


@router.get("", response_model=MarketList)
async def get_markets(
    status_filter: Optional[str] = Query(None, alias="status"),
    location: Optional[str] = Query(None),
    tradeable_only: bool = Query(False),
    engine: TradingEngine = Depends(get_trading_engine),
    session: AsyncSession = Depends(get_session),
) -> MarketList:
    """Get all monitored markets."""
    query = select(Market).where(Market.is_active == True)

    if status_filter:
        query = query.where(Market.status == status_filter)

    if location:
        query = query.where(Market.location == location)

    if tradeable_only:
        query = query.where(Market.is_tradeable == True)

    result = await session.execute(query.order_by(Market.resolution_date))
    markets = result.scalars().all()

    now = datetime.utcnow()
    market_responses = []
    opportunities_count = 0

    for market in markets:
        hours_to_resolution = None
        if market.resolution_date:
            delta = market.resolution_date - now
            hours_to_resolution = delta.total_seconds() / 3600

        is_opportunity = market.status == "opportunity"
        if is_opportunity:
            opportunities_count += 1

        market_responses.append(
            MarketResponse(
                id=str(market.id),
                market_id=market.market_id,
                description=market.question or "",
                location=market.location,
                resolution_date=market.resolution_date,
                hours_to_resolution=hours_to_resolution,
                variable=market.variable,
                threshold=market.threshold,
                comparison=market.comparison,
                forecast_probability=market.forecast_probability,
                market_price=market.current_price_yes,
                edge=market.edge,
                model_agreement=market.model_agreement,
                liquidity=market.liquidity,
                volume=market.volume,
                status=market.status or "watching",
                position_open=market.has_position or False,
                is_tradeable=market.is_tradeable or False,
            )
        )

    return MarketList(
        markets=market_responses,
        count=len(market_responses),
        opportunities_count=opportunities_count,
    )


@router.get("/opportunities", response_model=MarketList)
async def get_opportunities(
    engine: TradingEngine = Depends(get_trading_engine),
    session: AsyncSession = Depends(get_session),
) -> MarketList:
    """Get markets meeting entry criteria."""
    return await get_markets(
        status_filter="opportunity",
        tradeable_only=True,
        engine=engine,
        session=session,
    )


@router.get("/{market_id}", response_model=MarketResponse)
async def get_market(
    market_id: str,
    session: AsyncSession = Depends(get_session),
) -> MarketResponse:
    """Get single market details."""
    result = await session.execute(
        select(Market).where(Market.market_id == market_id)
    )
    market = result.scalar_one_or_none()

    if not market:
        raise HTTPException(status_code=404, detail="Market not found")

    now = datetime.utcnow()
    hours_to_resolution = None
    if market.resolution_date:
        delta = market.resolution_date - now
        hours_to_resolution = delta.total_seconds() / 3600

    return MarketResponse(
        id=str(market.id),
        market_id=market.market_id,
        description=market.question or "",
        location=market.location,
        resolution_date=market.resolution_date,
        hours_to_resolution=hours_to_resolution,
        variable=market.variable,
        threshold=market.threshold,
        comparison=market.comparison,
        forecast_probability=market.forecast_probability,
        market_price=market.current_price_yes,
        edge=market.edge,
        model_agreement=market.model_agreement,
        liquidity=market.liquidity,
        volume=market.volume,
        status=market.status or "watching",
        position_open=market.has_position or False,
        is_tradeable=market.is_tradeable or False,
    )


@router.get("/{market_id}/forecast", response_model=ForecastBreakdown)
async def get_market_forecast(
    market_id: str,
    session: AsyncSession = Depends(get_session),
) -> ForecastBreakdown:
    """Get detailed forecast breakdown for a market."""
    # Get market
    result = await session.execute(
        select(Market).where(Market.market_id == market_id)
    )
    market = result.scalar_one_or_none()

    if not market:
        raise HTTPException(status_code=404, detail="Market not found")

    # Get forecasts
    result = await session.execute(
        select(Forecast)
        .where(Forecast.market_id == market_id)
        .order_by(Forecast.created_at.desc())
    )
    forecasts = result.scalars().all()

    models = {}
    for forecast in forecasts:
        models[forecast.model_name] = {
            "probability": forecast.probability,
            "ensemble_values": forecast.ensemble_values,
            "mean": forecast.mean_value,
            "median": forecast.median_value,
            "std": forecast.std_value,
            "min": forecast.min_value,
            "max": forecast.max_value,
        }

    return ForecastBreakdown(
        market_id=market_id,
        target_date=market.resolution_date or datetime.utcnow(),
        models=models,
        aggregated_probability=market.forecast_probability or 0.5,
        model_agreement=market.model_agreement or 0.0,
    )
