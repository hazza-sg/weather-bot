"""System status endpoints."""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends

from app.models.api_models import SystemStatus, ControlAction, ControlResponse
from app.services.trading_engine import TradingEngine, get_trading_engine

router = APIRouter()


@router.get("", response_model=SystemStatus)
async def get_status(
    engine: TradingEngine = Depends(get_trading_engine),
) -> SystemStatus:
    """Get current system status."""
    return engine.get_status()


@router.post("/control/start", response_model=ControlResponse)
async def start_trading(
    engine: TradingEngine = Depends(get_trading_engine),
) -> ControlResponse:
    """Start automated trading."""
    success = await engine.start()
    return ControlResponse(
        success=success,
        message="Trading started" if success else "Failed to start trading",
        new_status=engine.status,
    )


@router.post("/control/pause", response_model=ControlResponse)
async def pause_trading(
    engine: TradingEngine = Depends(get_trading_engine),
) -> ControlResponse:
    """Pause automated trading."""
    success = await engine.pause()
    return ControlResponse(
        success=success,
        message="Trading paused" if success else "Failed to pause trading",
        new_status=engine.status,
    )


@router.post("/control/stop", response_model=ControlResponse)
async def stop_trading(
    engine: TradingEngine = Depends(get_trading_engine),
) -> ControlResponse:
    """Emergency stop - halt all trading immediately."""
    success = await engine.stop()
    return ControlResponse(
        success=success,
        message="Trading stopped" if success else "Failed to stop trading",
        new_status=engine.status,
    )
