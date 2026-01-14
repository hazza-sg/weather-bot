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

        # Risk state (now managed by RiskManager)
        self.is_halted = False
        self.halt_reason: Optional[str] = None

        # Clients (initialized on start)
        self._weather_client = None
        self._market_client = None
        self._executor = None

        # Strategy components (initialized on start)
        self._risk_manager = None
        self._edge_calculator = None
        self._position_sizer = None
        self._diversification_filter = None
        self._market_scanner = None

        # Event loop
        self._event_loop = None

        # Cached data
        self._markets: Dict[str, Any] = {}
        self._forecasts: Dict[str, Any] = {}
        self._positions: Dict[str, PositionResponse] = {}
        self._pending_orders: Dict[str, Any] = {}

        # Last update times
        self._last_trade_time: Optional[datetime] = None
        self._last_forecast_update: Optional[datetime] = None
        self._last_market_scan: Optional[datetime] = None

    async def initialize(self) -> bool:
        """Initialize all components."""
        try:
            # Initialize data clients
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

            # Initialize strategy components
            from strategy import EdgeCalculator, PositionSizer, DiversificationFilter, MarketScanner
            from risk import RiskManager

            self._edge_calculator = EdgeCalculator()
            self._position_sizer = PositionSizer(
                initial_bankroll=self.initial_bankroll,
            )
            self._diversification_filter = DiversificationFilter(
                initial_bankroll=self.initial_bankroll,
            )
            self._market_scanner = MarketScanner()
            self._risk_manager = RiskManager(
                initial_bankroll=self.initial_bankroll,
            )

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

        # Start event loop
        from app.services.event_loop import start_event_loop
        self._event_loop = await start_event_loop(self)

        logger.info("Trading started")
        return True

    async def pause(self) -> bool:
        """Pause trading (keep monitoring)."""
        self.status = "paused"

        if self._event_loop:
            await self._event_loop.pause()

        logger.info("Trading paused")
        return True

    async def resume(self) -> bool:
        """Resume trading after pause."""
        self.status = "active"

        if self._event_loop:
            await self._event_loop.resume()

        logger.info("Trading resumed")
        return True

    async def stop(self) -> bool:
        """Stop trading completely."""
        self.status = "stopped"

        # Stop event loop
        if self._event_loop:
            await self._event_loop.stop()

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
            pending_orders_count=len(self._pending_orders),
            api_connected=True,
            forecast_data_age_seconds=forecast_age,
            errors=errors,
        )

    async def get_portfolio_summary(self) -> PortfolioSummary:
        """Get portfolio overview."""
        total_exposure = sum(p.size for p in self._positions.values())
        unrealized_pnl = sum(p.unrealized_pnl for p in self._positions.values())

        # Get P&L from risk manager
        daily_pnl = 0.0
        weekly_pnl = 0.0
        monthly_pnl = 0.0

        if self._risk_manager:
            metrics = self._risk_manager.get_risk_metrics()
            daily_pnl = metrics["daily_pnl"]
            weekly_pnl = metrics["weekly_pnl"]
            monthly_pnl = metrics["monthly_pnl"]

        # Calculate stats from trade history
        async with get_db_session() as session:
            from sqlalchemy import select

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
            daily_pnl=daily_pnl,
            weekly_pnl=weekly_pnl,
            monthly_pnl=monthly_pnl,
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
            if position.location and self._diversification_filter:
                cluster = self._diversification_filter.get_cluster_for_location(position.location)
                if cluster:
                    cluster_exposure[cluster] = cluster_exposure.get(cluster, 0) + position.size

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

        # Get metrics from risk manager
        if self._risk_manager:
            metrics = self._risk_manager.get_risk_metrics()
            halt_status = self._risk_manager.get_halt_conditions_status()

            return RiskStatus(
                total_exposure=exposure.total_exposure,
                max_exposure=exposure.max_exposure,
                exposure_pct=exposure.exposure_pct,
                cluster_exposure=exposure.cluster_exposure,
                cluster_limits={
                    cluster: exposure.total_exposure * DIVERSIFICATION_CONFIG["max_cluster_exposure_pct"]
                    for cluster in GEOGRAPHIC_CLUSTERS
                },
                same_day_exposure=exposure.resolution_date_exposure,
                same_day_limit=exposure.total_exposure * DIVERSIFICATION_CONFIG["max_same_day_resolution_pct"],
                daily_pnl=metrics["daily_pnl"],
                daily_limit=metrics["daily_limit"],
                daily_buffer=metrics["daily_buffer"],
                weekly_pnl=metrics["weekly_pnl"],
                weekly_limit=metrics["weekly_limit"],
                weekly_buffer=metrics["weekly_buffer"],
                monthly_pnl=metrics["monthly_pnl"],
                monthly_limit=metrics["monthly_limit"],
                monthly_buffer=metrics["monthly_buffer"],
                is_halted=metrics["is_halted"],
                halt_reason=metrics["halt_reason"],
                halt_conditions=halt_status,
            )

        # Fallback if risk manager not initialized
        max_daily = self.initial_bankroll * RISK_LIMITS["max_daily_loss_pct"]
        max_weekly = self.initial_bankroll * RISK_LIMITS["max_weekly_loss_pct"]
        max_monthly = self.initial_bankroll * RISK_LIMITS["max_monthly_loss_pct"]

        return RiskStatus(
            total_exposure=exposure.total_exposure,
            max_exposure=exposure.max_exposure,
            exposure_pct=exposure.exposure_pct,
            cluster_exposure=exposure.cluster_exposure,
            cluster_limits={},
            same_day_exposure=exposure.resolution_date_exposure,
            same_day_limit=0,
            daily_pnl=0,
            daily_limit=-max_daily,
            daily_buffer=max_daily,
            weekly_pnl=0,
            weekly_limit=-max_weekly,
            weekly_buffer=max_weekly,
            monthly_pnl=0,
            monthly_limit=-max_monthly,
            monthly_buffer=max_monthly,
            is_halted=self.is_halted,
            halt_reason=self.halt_reason,
            halt_conditions={},
        )

    async def evaluate_opportunity(
        self,
        market_id: str,
        market_data: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """
        Evaluate a trading opportunity.

        Args:
            market_id: The market identifier
            market_data: Market data including price, question, etc.

        Returns:
            Trade recommendation or None
        """
        if not all([self._market_scanner, self._edge_calculator, self._weather_client]):
            return None

        # Parse the market
        parsed = self._market_scanner.parse_market(market_data)
        if not parsed or parsed.market_type == "unknown":
            return None

        # Get forecast data
        try:
            forecast = await self._weather_client.get_ensemble_forecast(
                latitude=parsed.latitude or 0,
                longitude=parsed.longitude or 0,
                target_date=parsed.resolution_date,
            )
        except Exception as e:
            logger.error(f"Failed to get forecast for {market_id}: {e}")
            return None

        if not forecast:
            return None

        # Calculate edge
        market_price = market_data.get("yes_price", 0.5)
        edge_calc = self._edge_calculator.calculate_from_forecast_data(
            forecast_data=forecast,
            threshold=parsed.threshold or 0,
            comparison=parsed.comparison or ">=",
            market_price=market_price,
            unit=parsed.unit or "fahrenheit",
        )

        if not edge_calc.is_tradeable():
            return None

        return {
            "market_id": market_id,
            "edge": edge_calc.edge,
            "recommended_side": edge_calc.recommended_side,
            "forecast_probability": edge_calc.forecast_probability,
            "market_probability": edge_calc.market_probability,
            "confidence": edge_calc.confidence_level.value,
            "model_agreement": edge_calc.model_agreement,
        }

    async def calculate_position_size(
        self,
        opportunity: Dict[str, Any],
        market_data: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """
        Calculate position size for an opportunity.

        Args:
            opportunity: Output from evaluate_opportunity
            market_data: Market data

        Returns:
            Position sizing recommendation
        """
        if not self._position_sizer or not self._diversification_filter:
            return None

        market_price = market_data.get("yes_price", 0.5)
        if opportunity["recommended_side"] == "NO":
            market_price = 1 - market_price

        # Calculate Kelly-based size
        position = self._position_sizer.calculate_position_size(
            bankroll=self.current_bankroll,
            forecast_prob=opportunity["forecast_probability"],
            market_price=market_price,
            side=opportunity["recommended_side"],
            model_agreement=opportunity["model_agreement"],
        )

        if not position.is_valid:
            return None

        # Check diversification limits
        parsed = self._market_scanner.parse_market(market_data)
        trade_info = {
            "location": parsed.location if parsed else None,
            "resolution_date": parsed.resolution_date if parsed else None,
            "size": position.final_size,
        }

        # Get current portfolio for diversification check
        portfolio = list(self._positions.values())
        div_result = self._diversification_filter.check_diversification_limits(
            trade=trade_info,
            portfolio=portfolio,
            bankroll=self.current_bankroll,
        )

        if not div_result.is_allowed:
            return {
                "is_valid": False,
                "reason": div_result.rejection_reason,
            }

        final_size = min(position.final_size, div_result.max_allowed_size or position.final_size)

        return {
            "is_valid": True,
            "recommended_size": final_size,
            "kelly_fraction": position.kelly_fraction,
            "adjusted_kelly": position.adjusted_kelly,
            "expected_value": position.expected_value,
            "adjustments": position.adjustments,
        }

    async def execute_trade(
        self,
        market_id: str,
        side: str,
        size: float,
        price: Optional[float] = None,
        is_manual: bool = False,
    ) -> Dict[str, Any]:
        """
        Execute a trade.

        Args:
            market_id: Market identifier
            side: "YES" or "NO"
            size: Dollar amount to trade
            price: Limit price (None for market order)
            is_manual: Whether this is a manual trade

        Returns:
            Trade result
        """
        # Validate with risk manager
        if self._risk_manager:
            validation = self._risk_manager.validate_trade(
                size=size,
                resolution_date=datetime.utcnow() + timedelta(days=7),  # Would use actual date
            )
            if not validation.is_valid:
                return {"success": False, "message": validation.reason}

        # Check halt state
        if self.is_halted:
            return {"success": False, "message": f"Trading halted: {self.halt_reason}"}

        # Execute via CLOB
        try:
            if self._executor and not self.test_mode:
                result = await self._executor.place_order(
                    market_id=market_id,
                    side=side,
                    size=size,
                    price=price,
                )
            else:
                # Test mode - simulate execution
                result = {
                    "order_id": str(uuid.uuid4())[:8],
                    "status": "filled",
                    "filled_size": size,
                    "filled_price": price or 0.50,
                }

            # Create position record
            position_id = str(uuid.uuid4())[:8]
            now = datetime.utcnow()

            self._positions[position_id] = PositionResponse(
                id=position_id,
                market_id=market_id,
                market_question=f"Market {market_id}",
                side=side,
                size=size,
                entry_price=result.get("filled_price", 0.50),
                current_price=result.get("filled_price", 0.50),
                entry_time=now,
                resolution_date=now + timedelta(days=7),
                location=None,
                unrealized_pnl=0.0,
                edge_at_entry=0.0,
            )

            self._last_trade_time = now

            logger.info(f"Trade executed: {side} {size:.2f} on {market_id}")

            return {
                "success": True,
                "trade_id": result.get("order_id"),
                "position_id": position_id,
                "filled_price": result.get("filled_price"),
                "filled_size": result.get("filled_size"),
            }

        except Exception as e:
            logger.error(f"Trade execution failed: {e}")
            return {"success": False, "message": str(e)}

    async def close_position(self, position_id: str) -> Dict[str, Any]:
        """Manually close a position."""
        if position_id not in self._positions:
            return {"success": False, "message": "Position not found"}

        position = self._positions[position_id]

        # Calculate realized P&L
        realized_pnl = position.unrealized_pnl

        # Update risk manager
        if self._risk_manager:
            self._risk_manager.update_pnl(realized_pnl)

        # Update state
        del self._positions[position_id]
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
        return await self.execute_trade(
            market_id=market_id,
            side=side,
            size=size,
            price=price,
            is_manual=True,
        )

    async def reset_daily_pnl(self) -> bool:
        """Reset daily P&L counter."""
        if self._risk_manager:
            self._risk_manager.reset_daily_pnl()
        logger.info("Daily P&L reset")
        return True

    async def clear_halt(self, force: bool = False) -> bool:
        """Clear trading halt."""
        if self._risk_manager:
            success, message = self._risk_manager.clear_halt(force=force)
            if success:
                self.is_halted = False
                self.halt_reason = None
            logger.info(message)
            return success

        self.is_halted = False
        self.halt_reason = None
        logger.info("Trading halt cleared")
        return True

    def get_event_loop_status(self) -> Optional[Dict[str, Any]]:
        """Get event loop status."""
        if self._event_loop:
            return {
                "state": self._event_loop.get_state(),
                "tasks": self._event_loop.get_task_status(),
            }
        return None


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
