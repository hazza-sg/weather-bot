"""Risk management endpoints."""
from typing import Dict, Any

from fastapi import APIRouter, HTTPException, Depends

from app.models.api_models import RiskStatus, RiskLimits
from app.services.trading_engine import TradingEngine, get_trading_engine
from app.config import RISK_LIMITS, DIVERSIFICATION_CONFIG

router = APIRouter()


@router.get("/status", response_model=RiskStatus)
async def get_risk_status(
    engine: TradingEngine = Depends(get_trading_engine),
) -> RiskStatus:
    """Get current risk metrics."""
    return await engine.get_risk_status()


@router.get("/limits", response_model=RiskLimits)
async def get_risk_limits() -> RiskLimits:
    """Get configured risk limits."""
    return RiskLimits(
        max_daily_loss_pct=RISK_LIMITS["max_daily_loss_pct"],
        max_weekly_loss_pct=RISK_LIMITS["max_weekly_loss_pct"],
        max_monthly_loss_pct=RISK_LIMITS["max_monthly_loss_pct"],
        max_total_exposure_pct=DIVERSIFICATION_CONFIG["max_total_exposure_pct"],
        max_cluster_exposure_pct=DIVERSIFICATION_CONFIG["max_cluster_exposure_pct"],
        max_same_day_resolution_pct=DIVERSIFICATION_CONFIG["max_same_day_resolution_pct"],
        min_hours_before_resolution=RISK_LIMITS["min_hours_before_resolution"],
    )


@router.post("/reset-daily")
async def reset_daily_pnl(
    engine: TradingEngine = Depends(get_trading_engine),
) -> Dict[str, Any]:
    """Reset daily P&L counter."""
    success = await engine.reset_daily_pnl()
    return {
        "success": success,
        "message": "Daily P&L reset" if success else "Failed to reset",
    }


@router.post("/clear-halt")
async def clear_halt(
    engine: TradingEngine = Depends(get_trading_engine),
) -> Dict[str, Any]:
    """Manually clear halt condition."""
    success = await engine.clear_halt()
    return {
        "success": success,
        "message": "Halt cleared" if success else "Failed to clear halt",
    }
