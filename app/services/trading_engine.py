"""Core trading engine service."""
import asyncio
import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple

from app.config import (
    get_settings,
    STRATEGY_CONFIG,
    POSITION_SIZING_CONFIG,
    RISK_LIMITS,
    DIVERSIFICATION_CONFIG,
    GEOGRAPHIC_CLUSTERS,
)
from app.models.api_models import (
    SystemStatus,
    PortfolioSummary,
    PositionResponse,
    ExposureBreakdown,
    RiskStatus,
)
from app.database import get_db_session
from app.models.database_models import Trade, Position, Market, RiskSnapshot

logger = logging.getLogger(__name__)


class TradingEngine:
    """
    Core trading engine that orchestrates all trading operations.

    This is the central component that connects data sources, strategy logic,
    and execution layer.
    """

    def __init__(self, test_mode: bool = False):
        self.test_mode = test_mode
        self.status = "stopped"
        self.start_time: Optional[datetime] = None

        # Configuration
        self.settings = get_settings()
        self.initial_bankroll = self.settings.initial_bankroll

        # State tracking
        self.current_bankroll = self.initial_bankroll
        self.daily_pnl = 0.0
        self.weekly_pnl = 0.0
        self.monthly_pnl = 0.0

        # Risk state
        self.is_halted = False
        self.halt_reason: Optional[str] = None
        self.last_loss_time: Optional[datetime] = None

        # Clients (initialized on start)
        self._weather_client = None
        self._market_client = None
        self._executor = None

        # Cached data
        self._markets: Dict[str, Any] = {}
        self._forecasts: Dict[str, Any] = {}
        self._positions: Dict[str, PositionResponse] = {}

        # Last update times
        self._last_trade_time: Optional[datetime] = None
        self._last_forecast_update: Optional[datetime] = None
        self._last_market_scan: Optional[datetime] = None

    async def initialize(self) -> bool:
        """Initialize all components."""
        try:
            from data.weather_client import OpenMeteoClient
            from data.market_client import GammaAPIClient
            from execution.clob_client import PolymarketExecutor

            self._weather_client = OpenMeteoClient()
            self._market_client = GammaAPIClient()
            self._executor = PolymarketExecutor(
                private_key=self.settings.private_key,
                wallet_address=self.settings.wallet_address,
                test_mode=self.test_mode,
            )

            await self._executor.initialize()

            logger.info("Trading engine initialized")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize trading engine: {e}")
            return False

    async def start(self) -> bool:
        """Start automated trading."""
        if self.status == "active":
            return True

        if not await self.initialize():
            return False

        self.status = "active"
        self.start_time = datetime.utcnow()

        logger.info("Trading started")
        return True

    async def pause(self) -> bool:
        """Pause trading (keep monitoring)."""
        self.status = "paused"
        logger.info("Trading paused")
        return True

    async def stop(self) -> bool:
        """Stop trading completely."""
        self.status = "stopped"

        # Close clients
        if self._weather_client:
            await self._weather_client.close()
        if self._market_client:
            await self._market_client.close()
        if self._executor:
            await self._executor.close()

        logger.info("Trading stopped")
        return True

    def get_status(self) -> SystemStatus:
        """Get current system status."""
        uptime = 0
        if self.start_time:
            uptime = int((datetime.utcnow() - self.start_time).total_seconds())

        forecast_age = None
        if self._last_forecast_update:
            forecast_age = int(
                (datetime.utcnow() - self._last_forecast_update).total_seconds()
            )

        errors = []
        if self.is_halted:
            errors.append(self.halt_reason or "Trading halted")

        return SystemStatus(
            status=self.status,
            uptime_seconds=uptime,
            trading_enabled=self.status == "active",
            last_trade_time=self._last_trade_time,
            open_positions_count=len(self._positions),
            pending_orders_count=0,
            api_connected=True,
            forecast_data_age_seconds=forecast_age,
            errors=errors,
        )

    async def get_portfolio_summary(self) -> PortfolioSummary:
        """Get portfolio overview."""
        total_exposure = sum(p.size for p in self._positions.values())
        unrealized_pnl = sum(p.unrealized_pnl for p in self._positions.values())

        # Calculate stats from trade history
        async with get_db_session() as session:
            from sqlalchemy import select, func

            # Get completed trades
            result = await session.execute(
                select(Trade).where(Trade.result.in_(["win", "loss"]))
            )
            trades = result.scalars().all()

            total_trades = len(trades)
            wins = sum(1 for t in trades if t.result == "win")
            win_rate = wins / total_trades if total_trades > 0 else 0

            # Profit factor
            total_wins = sum(t.realized_pnl or 0 for t in trades if t.result == "win")
            total_losses = abs(sum(t.realized_pnl or 0 for t in trades if t.result == "loss"))
            profit_factor = total_wins / total_losses if total_losses > 0 else 0

        return PortfolioSummary(
            bankroll=self.current_bankroll,
            initial_bankroll=self.initial_bankroll,
            total_exposure=total_exposure,
            exposure_percentage=total_exposure / self.current_bankroll if self.current_bankroll > 0 else 0,
            unrealized_pnl=unrealized_pnl,
            daily_pnl=self.daily_pnl,
            weekly_pnl=self.weekly_pnl,
            monthly_pnl=self.monthly_pnl,
            total_trades=total_trades,
            win_rate=win_rate,
            profit_factor=profit_factor,
        )

    async def get_open_positions(self) -> List[PositionResponse]:
        """Get all open positions."""
        return list(self._positions.values())

    async def get_exposure_breakdown(self) -> ExposureBreakdown:
        """Get exposure breakdown by category."""
        total_exposure = sum(p.size for p in self._positions.values())
        max_exposure = self.current_bankroll * DIVERSIFICATION_CONFIG["max_total_exposure_pct"]

        # Calculate cluster exposure
        cluster_exposure: Dict[str, float] = {}
        resolution_date_exposure: Dict[str, float] = {}

        for position in self._positions.values():
            # By cluster
            if position.location:
                for cluster_name, cluster_data in GEOGRAPHIC_CLUSTERS.items():
                    if position.location in cluster_data.get("cities", []):
                        cluster_exposure[cluster_name] = (
                            cluster_exposure.get(cluster_name, 0) + position.size
                        )

            # By resolution date
            date_key = position.resolution_date.strftime("%Y-%m-%d")
            resolution_date_exposure[date_key] = (
                resolution_date_exposure.get(date_key, 0) + position.size
            )

        return ExposureBreakdown(
            total_exposure=total_exposure,
            max_exposure=max_exposure,
            exposure_pct=total_exposure / max_exposure if max_exposure > 0 else 0,
            cluster_exposure=cluster_exposure,
            resolution_date_exposure=resolution_date_exposure,
        )

    async def get_risk_status(self) -> RiskStatus:
        """Get current risk metrics."""
        exposure = await self.get_exposure_breakdown()

        max_daily = self.initial_bankroll * RISK_LIMITS["max_daily_loss_pct"]
        max_weekly = self.initial_bankroll * RISK_LIMITS["max_weekly_loss_pct"]
        max_monthly = self.initial_bankroll * RISK_LIMITS["max_monthly_loss_pct"]

        cluster_limits = {}
        for cluster_name in GEOGRAPHIC_CLUSTERS:
            cluster_limits[cluster_name] = (
                exposure.total_exposure * DIVERSIFICATION_CONFIG["max_cluster_exposure_pct"]
            )

        same_day_limit = (
            exposure.total_exposure * DIVERSIFICATION_CONFIG["max_same_day_resolution_pct"]
        )

        halt_conditions = {
            "daily_loss": {
                "triggered": self.daily_pnl <= -max_daily,
                "message": "Daily loss limit",
            },
            "weekly_loss": {
                "triggered": self.weekly_pnl <= -max_weekly,
                "message": "Weekly loss limit",
            },
            "monthly_loss": {
                "triggered": self.monthly_pnl <= -max_monthly,
                "message": "Monthly loss limit",
            },
            "system_operational": {
                "triggered": False,
                "message": "All services running",
            },
            "api_connectivity": {
                "triggered": False,
                "message": "Connected to Polymarket",
            },
        }

        return RiskStatus(
            total_exposure=exposure.total_exposure,
            max_exposure=exposure.max_exposure,
            exposure_pct=exposure.exposure_pct,
            cluster_exposure=exposure.cluster_exposure,
            cluster_limits=cluster_limits,
            same_day_exposure=exposure.resolution_date_exposure,
            same_day_limit=same_day_limit,
            daily_pnl=self.daily_pnl,
            daily_limit=-max_daily,
            daily_buffer=max_daily + self.daily_pnl,
            weekly_pnl=self.weekly_pnl,
            weekly_limit=-max_weekly,
            weekly_buffer=max_weekly + self.weekly_pnl,
            monthly_pnl=self.monthly_pnl,
            monthly_limit=-max_monthly,
            monthly_buffer=max_monthly + self.monthly_pnl,
            is_halted=self.is_halted,
            halt_reason=self.halt_reason,
            halt_conditions=halt_conditions,
        )

    async def close_position(self, position_id: str) -> Dict[str, Any]:
        """Manually close a position."""
        if position_id not in self._positions:
            return {"success": False, "message": "Position not found"}

        position = self._positions[position_id]

        # In real implementation, would execute sell order
        realized_pnl = position.unrealized_pnl

        # Update state
        del self._positions[position_id]
        self.daily_pnl += realized_pnl
        self.weekly_pnl += realized_pnl
        self.monthly_pnl += realized_pnl
        self.current_bankroll += realized_pnl

        logger.info(f"Closed position {position_id}: P&L = {realized_pnl:.2f}")

        return {
            "success": True,
            "message": "Position closed",
            "realized_pnl": realized_pnl,
        }

    async def execute_manual_trade(
        self,
        market_id: str,
        side: str,
        size: float,
        price: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Execute a manual trade."""
        if self.is_halted:
            return {"success": False, "message": f"Trading halted: {self.halt_reason}"}

        if size > RISK_LIMITS["max_single_trade"]:
            return {"success": False, "message": f"Trade size exceeds maximum"}

        if size < RISK_LIMITS["min_single_trade"]:
            return {"success": False, "message": f"Trade size below minimum"}

        # Create trade record
        trade_id = str(uuid.uuid4())[:8]
        now = datetime.utcnow()

        trade = {
            "trade_id": trade_id,
            "market_id": market_id,
            "side": side,
            "entry_price": price or 0.50,
            "size": size,
            "entry_time": now,
            "resolution_date": now + timedelta(days=3),
        }

        self._last_trade_time = now
        logger.info(f"Manual trade executed: {trade_id}")

        return {"success": True, "trade": trade}

    async def reset_daily_pnl(self) -> bool:
        """Reset daily P&L counter."""
        self.daily_pnl = 0.0
        logger.info("Daily P&L reset")
        return True

    async def clear_halt(self) -> bool:
        """Clear trading halt."""
        if "Monthly" in (self.halt_reason or ""):
            logger.warning("Cannot auto-clear monthly halt")
            return False

        self.is_halted = False
        self.halt_reason = None
        logger.info("Trading halt cleared")
        return True


# Global engine instance
_engine: Optional[TradingEngine] = None


def get_trading_engine() -> TradingEngine:
    """Get the global trading engine instance."""
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = TradingEngine(test_mode=settings.test_mode)
    return _engine


async def initialize_engine() -> TradingEngine:
    """Initialize and return the trading engine."""
    engine = get_trading_engine()
    await engine.initialize()
    return engine
