"""API route handlers."""
from fastapi import APIRouter

from app.api.routes import status, portfolio, markets, trades, risk, config, alerts

api_router = APIRouter()

api_router.include_router(status.router, prefix="/status", tags=["status"])
api_router.include_router(portfolio.router, prefix="/portfolio", tags=["portfolio"])
api_router.include_router(markets.router, prefix="/markets", tags=["markets"])
api_router.include_router(trades.router, prefix="/trades", tags=["trades"])
api_router.include_router(risk.router, prefix="/risk", tags=["risk"])
api_router.include_router(config.router, prefix="/config", tags=["config"])
api_router.include_router(alerts.router, prefix="/alerts", tags=["alerts"])
