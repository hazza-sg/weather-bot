"""Main event loop for automated trading operations."""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any
from enum import Enum, auto
from dataclasses import dataclass, field
import traceback

from app.config import (
    get_settings,
    STRATEGY_CONFIG,
    RISK_LIMITS,
)
from app.api.websocket import broadcast_message

logger = logging.getLogger(__name__)


class TaskPriority(Enum):
    """Priority levels for scheduled tasks."""
    CRITICAL = auto()  # Risk checks, halt conditions
    HIGH = auto()      # Price updates, order monitoring
    NORMAL = auto()    # Market scanning, forecasts
    LOW = auto()       # Analytics, logging


@dataclass
class ScheduledTask:
    """A task scheduled to run at intervals."""
    name: str
    coroutine: Callable
    interval_seconds: int
    priority: TaskPriority = TaskPriority.NORMAL
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    run_count: int = 0
    error_count: int = 0
    last_error: Optional[str] = None
    enabled: bool = True
    max_retries: int = 3
    retry_delay_seconds: int = 5


@dataclass
class EventLoopState:
    """Current state of the event loop."""
    is_running: bool = False
    started_at: Optional[datetime] = None
    total_cycles: int = 0
    tasks_executed: int = 0
    errors_encountered: int = 0
    last_cycle_time: Optional[datetime] = None
    cycle_duration_ms: float = 0


@dataclass
class TradingOpportunity:
    """A trading opportunity identified by the system."""
    market_id: str
    token_id: str
    market_question: str
    side: str  # "YES" or "NO"
    edge: float
    forecast_probability: float
    market_probability: float
    model_agreement: float
    confidence: str
    recommended_size: float
    location: Optional[str] = None
    resolution_date: Optional[datetime] = None


class TradingEventLoop:
    """
    Main event loop that orchestrates all trading operations.

    Responsibilities:
    - Schedule and execute recurring tasks
    - Coordinate between data fetching, strategy, and execution
    - Handle errors and maintain system stability
    - Broadcast updates via WebSocket
    """

    def __init__(self):
        self.settings = get_settings()
        self.state = EventLoopState()
        self.tasks: Dict[str, ScheduledTask] = {}
        self._stop_event = asyncio.Event()
        self._pause_event = asyncio.Event()
        self._pause_event.set()  # Not paused initially

        # Components (injected on start)
        self._trading_engine = None
        self._risk_manager = None
        self._market_scanner = None
        self._edge_calculator = None
        self._position_sizer = None
        self._diversification_filter = None

        # Execution layer components
        self._order_monitor = None
        self._position_tracker = None
        self._price_feed = None

        # Cached market data
        self._active_markets: Dict[str, Dict[str, Any]] = {}
        self._market_forecasts: Dict[str, Any] = {}
        self._pending_opportunities: List[TradingOpportunity] = []

        # Tick interval (main loop frequency)
        self.tick_interval = 1.0  # seconds

    def register_task(
        self,
        name: str,
        coroutine: Callable,
        interval_seconds: int,
        priority: TaskPriority = TaskPriority.NORMAL,
        enabled: bool = True,
    ) -> None:
        """Register a recurring task."""
        now = datetime.utcnow()
        self.tasks[name] = ScheduledTask(
            name=name,
            coroutine=coroutine,
            interval_seconds=interval_seconds,
            priority=priority,
            next_run=now,
            enabled=enabled,
        )
        logger.info(f"Registered task: {name} (interval: {interval_seconds}s)")

    def unregister_task(self, name: str) -> bool:
        """Remove a task from the schedule."""
        if name in self.tasks:
            del self.tasks[name]
            logger.info(f"Unregistered task: {name}")
            return True
        return False

    def enable_task(self, name: str) -> bool:
        """Enable a disabled task."""
        if name in self.tasks:
            self.tasks[name].enabled = True
            return True
        return False

    def disable_task(self, name: str) -> bool:
        """Disable a task without removing it."""
        if name in self.tasks:
            self.tasks[name].enabled = False
            return True
        return False

    async def initialize(self, trading_engine) -> bool:
        """
        Initialize event loop with required components.

        Args:
            trading_engine: The main trading engine instance
        """
        try:
            self._trading_engine = trading_engine

            # Import and initialize strategy components
            from strategy import EdgeCalculator, PositionSizer, MarketScanner, DiversificationFilter
            from risk import RiskManager
            from execution import OrderMonitor, PositionTracker
            from execution.price_feed import SimulatedPriceFeed

            self._edge_calculator = EdgeCalculator()
            self._position_sizer = PositionSizer(
                initial_bankroll=self.settings.initial_bankroll
            )
            self._market_scanner = MarketScanner()
            self._diversification_filter = DiversificationFilter(
                initial_bankroll=self.settings.initial_bankroll
            )
            self._risk_manager = RiskManager(
                initial_bankroll=self.settings.initial_bankroll
            )

            # Initialize execution components
            self._order_monitor = OrderMonitor(
                executor=trading_engine._executor,
                poll_interval=5.0,
            )
            self._position_tracker = PositionTracker(
                executor=trading_engine._executor,
                price_update_interval=30.0,
            )

            # Use simulated price feed in test mode
            if self.settings.test_mode:
                self._price_feed = SimulatedPriceFeed(update_interval=10.0)
            else:
                from execution.price_feed import PriceFeed
                self._price_feed = PriceFeed()

            # Set up callbacks
            self._setup_callbacks()

            # Register default tasks
            self._register_default_tasks()

            logger.info("Event loop initialized")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize event loop: {e}")
            logger.error(traceback.format_exc())
            return False

    def _setup_callbacks(self) -> None:
        """Set up callbacks for execution components."""
        if self._order_monitor:
            self._order_monitor.on_fill(self._handle_order_fill)
            self._order_monitor.on_complete(self._handle_order_complete)

        if self._position_tracker:
            self._position_tracker.on_position_closed(self._handle_position_closed)
            self._position_tracker.on_resolution(self._handle_market_resolution)

        if self._price_feed:
            self._price_feed.on_price(self._handle_price_update)

    async def _handle_order_fill(self, order, fill_event) -> None:
        """Handle order fill events."""
        logger.info(f"Order {order.order_id} filled: {fill_event.size:.2f} @ {fill_event.price:.4f}")

        await broadcast_message({
            "type": "order_fill",
            "order_id": order.order_id,
            "market_id": order.market_id,
            "side": order.side,
            "fill_size": fill_event.size,
            "fill_price": fill_event.price,
            "timestamp": datetime.utcnow().isoformat(),
        })

    async def _handle_order_complete(self, order) -> None:
        """Handle order completion."""
        logger.info(f"Order {order.order_id} completed: {order.status.value}")

        if order.status.value == "filled":
            # Create position from filled order
            from execution import TrackedPosition
            import uuid

            position = TrackedPosition(
                position_id=str(uuid.uuid4())[:8],
                market_id=order.market_id,
                token_id=order.token_id,
                market_question=f"Market {order.market_id}",
                side="YES" if order.side == "BUY" else "NO",
                quantity=order.filled_quantity,
                size=order.filled_size,
                entry_price=order.average_fill_price,
                entry_time=datetime.utcnow(),
                resolution_date=datetime.utcnow() + timedelta(days=7),
                edge_at_entry=order.edge_at_entry,
                forecast_probability=order.forecast_probability,
            )

            if self._position_tracker:
                self._position_tracker.add_position(position)

    async def _handle_position_closed(self, position) -> None:
        """Handle position closure."""
        logger.info(f"Position {position.position_id} closed: P&L = {position.realized_pnl:+.2f}")

        # Update risk manager with realized P&L
        if self._risk_manager:
            self._risk_manager.update_pnl(position.realized_pnl)

        await broadcast_message({
            "type": "position_closed",
            "position_id": position.position_id,
            "realized_pnl": position.realized_pnl,
            "timestamp": datetime.utcnow().isoformat(),
        })

    async def _handle_market_resolution(self, position, outcome) -> None:
        """Handle market resolution."""
        logger.info(f"Market resolved for {position.position_id}: {outcome}, P&L = {position.realized_pnl:+.2f}")

        # Update risk manager with realized P&L
        if self._risk_manager:
            self._risk_manager.update_pnl(position.realized_pnl)

        await broadcast_message({
            "type": "market_resolution",
            "position_id": position.position_id,
            "outcome": outcome,
            "realized_pnl": position.realized_pnl,
            "timestamp": datetime.utcnow().isoformat(),
        })

    async def _handle_price_update(self, price_update) -> None:
        """Handle price feed updates."""
        # Update position tracker with new price
        if self._position_tracker:
            for position in self._position_tracker.get_open_positions():
                if position.token_id == price_update.token_id:
                    position.current_price = price_update.mid
                    position.unrealized_pnl = position.calculate_unrealized_pnl()
                    position.last_price_update = datetime.utcnow()

    def _register_default_tasks(self) -> None:
        """Register the default set of trading tasks."""

        # Critical: Risk checks (every 10 seconds)
        self.register_task(
            name="risk_check",
            coroutine=self._task_risk_check,
            interval_seconds=10,
            priority=TaskPriority.CRITICAL,
        )

        # High: Price updates (every 30 seconds)
        self.register_task(
            name="price_update",
            coroutine=self._task_price_update,
            interval_seconds=30,
            priority=TaskPriority.HIGH,
        )

        # High: Order monitoring (every 15 seconds)
        self.register_task(
            name="order_monitor",
            coroutine=self._task_order_monitor,
            interval_seconds=15,
            priority=TaskPriority.HIGH,
        )

        # Normal: Market scanning (every 5 minutes)
        self.register_task(
            name="market_scan",
            coroutine=self._task_market_scan,
            interval_seconds=300,
            priority=TaskPriority.NORMAL,
        )

        # Normal: Forecast update (every 15 minutes)
        self.register_task(
            name="forecast_update",
            coroutine=self._task_forecast_update,
            interval_seconds=900,
            priority=TaskPriority.NORMAL,
        )

        # Normal: Edge calculation and trading (every 2 minutes)
        self.register_task(
            name="trading_cycle",
            coroutine=self._task_trading_cycle,
            interval_seconds=120,
            priority=TaskPriority.NORMAL,
        )

        # Low: Status broadcast (every 5 seconds)
        self.register_task(
            name="status_broadcast",
            coroutine=self._task_status_broadcast,
            interval_seconds=5,
            priority=TaskPriority.LOW,
        )

        # Low: Metrics logging (every minute)
        self.register_task(
            name="metrics_log",
            coroutine=self._task_metrics_log,
            interval_seconds=60,
            priority=TaskPriority.LOW,
        )

    async def start(self) -> None:
        """Start the main event loop."""
        if self.state.is_running:
            logger.warning("Event loop already running")
            return

        self.state.is_running = True
        self.state.started_at = datetime.utcnow()
        self._stop_event.clear()

        logger.info("Event loop starting...")

        # Start execution components
        if self._order_monitor:
            await self._order_monitor.start_monitoring()

        if self._position_tracker:
            await self._position_tracker.start_price_updates()

        if self._price_feed:
            await self._price_feed.connect()

        try:
            await self._run_loop()
        except asyncio.CancelledError:
            logger.info("Event loop cancelled")
        except Exception as e:
            logger.error(f"Event loop error: {e}")
            logger.error(traceback.format_exc())
        finally:
            # Stop execution components
            if self._order_monitor:
                await self._order_monitor.stop_monitoring()

            if self._position_tracker:
                await self._position_tracker.stop_price_updates()

            if self._price_feed:
                await self._price_feed.disconnect()

            self.state.is_running = False
            logger.info("Event loop stopped")

    async def stop(self) -> None:
        """Stop the event loop gracefully."""
        logger.info("Stopping event loop...")
        self._stop_event.set()

    async def pause(self) -> None:
        """Pause task execution (loop continues but tasks don't run)."""
        self._pause_event.clear()
        logger.info("Event loop paused")

    async def resume(self) -> None:
        """Resume task execution."""
        self._pause_event.set()
        logger.info("Event loop resumed")

    async def _run_loop(self) -> None:
        """Main loop execution."""
        while not self._stop_event.is_set():
            cycle_start = datetime.utcnow()

            # Wait if paused
            await self._pause_event.wait()

            # Get tasks due for execution
            due_tasks = self._get_due_tasks()

            # Sort by priority
            due_tasks.sort(key=lambda t: t.priority.value)

            # Execute tasks
            for task in due_tasks:
                if self._stop_event.is_set():
                    break

                await self._execute_task(task)

            # Update cycle stats
            cycle_end = datetime.utcnow()
            self.state.total_cycles += 1
            self.state.last_cycle_time = cycle_end
            self.state.cycle_duration_ms = (cycle_end - cycle_start).total_seconds() * 1000

            # Sleep until next tick
            elapsed = (cycle_end - cycle_start).total_seconds()
            sleep_time = max(0, self.tick_interval - elapsed)
            await asyncio.sleep(sleep_time)

    def _get_due_tasks(self) -> List[ScheduledTask]:
        """Get all tasks that are due to run."""
        now = datetime.utcnow()
        due = []

        for task in self.tasks.values():
            if not task.enabled:
                continue

            if task.next_run is None or now >= task.next_run:
                due.append(task)

        return due

    async def _execute_task(self, task: ScheduledTask) -> None:
        """Execute a single task with error handling."""
        try:
            await task.coroutine()

            # Update task state on success
            now = datetime.utcnow()
            task.last_run = now
            task.next_run = now + timedelta(seconds=task.interval_seconds)
            task.run_count += 1
            self.state.tasks_executed += 1

        except Exception as e:
            task.error_count += 1
            task.last_error = str(e)
            self.state.errors_encountered += 1

            logger.error(f"Task {task.name} failed: {e}")

            # Still schedule next run to avoid blocking
            now = datetime.utcnow()
            retry_delay = task.retry_delay_seconds * min(task.error_count, task.max_retries)
            task.next_run = now + timedelta(seconds=retry_delay)

    # ========== Task Implementations ==========

    async def _task_risk_check(self) -> None:
        """Check risk conditions and halt if necessary."""
        if not self._risk_manager or not self._trading_engine:
            return

        can_trade, reason = self._risk_manager.can_trade()

        if not can_trade:
            # Update trading engine halt state
            if not self._trading_engine.is_halted:
                self._trading_engine.is_halted = True
                self._trading_engine.halt_reason = reason
                logger.warning(f"Trading halted: {reason}")

                await broadcast_message({
                    "type": "risk_alert",
                    "level": "critical",
                    "message": f"Trading halted: {reason}",
                    "timestamp": datetime.utcnow().isoformat(),
                })
        else:
            # Clear halt if conditions allow
            if self._trading_engine.is_halted:
                self._trading_engine.is_halted = False
                self._trading_engine.halt_reason = None
                logger.info("Trading halt cleared - conditions normal")

    async def _task_price_update(self) -> None:
        """Update position prices from market."""
        if not self._position_tracker:
            return

        # Trigger price update for all positions
        await self._position_tracker._update_all_prices()

        positions = self._position_tracker.get_open_positions()

        await broadcast_message({
            "type": "price_update",
            "timestamp": datetime.utcnow().isoformat(),
            "positions_updated": len(positions),
            "total_unrealized_pnl": self._position_tracker.get_total_unrealized_pnl(),
        })

    async def _task_order_monitor(self) -> None:
        """Monitor pending orders for fills."""
        if not self._order_monitor:
            return

        # Check order status
        await self._order_monitor._check_orders()

        open_orders = self._order_monitor.get_open_orders()

        if open_orders:
            logger.debug(f"Monitoring {len(open_orders)} open orders")

    async def _task_market_scan(self) -> None:
        """Scan for new weather markets."""
        if not self._market_scanner or not self._trading_engine:
            return

        if not self._trading_engine._market_client:
            return

        try:
            # Fetch weather markets
            markets = await self._trading_engine._market_client.get_weather_markets(
                limit=50
            )

            # Parse each market
            parsed_markets = []
            for market in markets:
                parsed = self._market_scanner.parse_market(market)
                if parsed and parsed.market_type != "unknown":
                    parsed_markets.append(parsed)

                    # Cache market data
                    self._active_markets[market.get("id", "")] = {
                        "raw": market,
                        "parsed": parsed,
                    }

            logger.info(f"Market scan found {len(parsed_markets)} tradeable markets")

            await broadcast_message({
                "type": "market_scan",
                "timestamp": datetime.utcnow().isoformat(),
                "markets_found": len(parsed_markets),
            })

        except Exception as e:
            logger.error(f"Market scan failed: {e}")

    async def _task_forecast_update(self) -> None:
        """Update weather forecasts for active markets."""
        if not self._trading_engine or not self._trading_engine._weather_client:
            return

        updated_count = 0

        for market_id, market_data in self._active_markets.items():
            parsed = market_data.get("parsed")
            if not parsed:
                continue

            # Only fetch forecasts for markets with valid coordinates
            if not (parsed.latitude and parsed.longitude):
                continue

            try:
                forecast = await self._trading_engine._weather_client.get_ensemble_forecast(
                    latitude=parsed.latitude,
                    longitude=parsed.longitude,
                    target_date=parsed.resolution_date,
                )

                if forecast:
                    self._market_forecasts[market_id] = forecast
                    updated_count += 1

            except Exception as e:
                logger.error(f"Failed to fetch forecast for {market_id}: {e}")

        self._trading_engine._last_forecast_update = datetime.utcnow()

        logger.info(f"Updated forecasts for {updated_count} markets")

        await broadcast_message({
            "type": "forecast_update",
            "timestamp": datetime.utcnow().isoformat(),
            "forecasts_updated": updated_count,
        })

    async def _task_trading_cycle(self) -> None:
        """Main trading cycle: calculate edges and execute trades."""
        if not self._trading_engine:
            return

        # Check if trading is allowed
        can_trade, reason = self._risk_manager.can_trade() if self._risk_manager else (True, "")
        if not can_trade:
            logger.debug(f"Trading cycle skipped: {reason}")
            return

        if self._trading_engine.status != "active":
            return

        # Clear previous opportunities
        self._pending_opportunities.clear()
        opportunities_found = 0
        trades_executed = 0

        # Step 1: Calculate edge for each market with forecast
        for market_id, forecast in self._market_forecasts.items():
            market_data = self._active_markets.get(market_id, {})
            raw_market = market_data.get("raw", {})
            parsed = market_data.get("parsed")

            if not parsed:
                continue

            # Get current market price
            market_price = raw_market.get("yes_price", raw_market.get("price", 0.5))

            # Calculate edge
            try:
                edge_calc = self._edge_calculator.calculate_from_forecast_data(
                    forecast_data=forecast,
                    threshold=parsed.threshold or 0,
                    comparison=parsed.comparison or ">=",
                    market_price=market_price,
                    unit=parsed.unit or "fahrenheit",
                )

                if edge_calc.is_tradeable():
                    opportunity = TradingOpportunity(
                        market_id=market_id,
                        token_id=raw_market.get("token_id", market_id),
                        market_question=raw_market.get("question", ""),
                        side=edge_calc.recommended_side,
                        edge=edge_calc.edge,
                        forecast_probability=edge_calc.forecast_probability,
                        market_probability=edge_calc.market_probability,
                        model_agreement=edge_calc.model_agreement,
                        confidence=edge_calc.confidence_level.value,
                        recommended_size=0,  # Will be calculated
                        location=parsed.location,
                        resolution_date=parsed.resolution_date,
                    )
                    self._pending_opportunities.append(opportunity)
                    opportunities_found += 1

            except Exception as e:
                logger.error(f"Edge calculation failed for {market_id}: {e}")

        # Step 2: Size positions and check diversification
        for opportunity in self._pending_opportunities:
            # Calculate Kelly-based position size
            effective_price = opportunity.market_probability
            if opportunity.side == "NO":
                effective_price = 1 - effective_price

            position_size = self._position_sizer.calculate_position_size(
                bankroll=self._trading_engine.current_bankroll,
                forecast_prob=opportunity.forecast_probability,
                market_price=effective_price,
                side=opportunity.side,
                model_agreement=opportunity.model_agreement,
            )

            if not position_size.is_valid:
                continue

            # Check diversification limits
            existing_positions = []
            if self._position_tracker:
                existing_positions = [
                    {
                        "location": p.location,
                        "resolution_date": p.resolution_date,
                        "size": p.size,
                    }
                    for p in self._position_tracker.get_open_positions()
                ]

            trade_info = {
                "location": opportunity.location,
                "resolution_date": opportunity.resolution_date,
                "size": position_size.final_size,
            }

            div_result = self._diversification_filter.check_diversification_limits(
                trade=trade_info,
                portfolio=existing_positions,
                bankroll=self._trading_engine.current_bankroll,
            )

            if not div_result.is_allowed:
                logger.debug(f"Trade blocked by diversification: {div_result.rejection_reason}")
                continue

            # Adjust size if needed
            final_size = min(
                position_size.final_size,
                div_result.max_allowed_size or position_size.final_size
            )

            opportunity.recommended_size = final_size

        # Step 3: Execute trades for valid opportunities
        for opportunity in self._pending_opportunities:
            if opportunity.recommended_size <= 0:
                continue

            # Execute trade
            result = await self._trading_engine.execute_trade(
                market_id=opportunity.market_id,
                side=opportunity.side,
                size=opportunity.recommended_size,
                price=opportunity.market_probability,
            )

            if result.get("success"):
                trades_executed += 1
                logger.info(
                    f"Trade executed: {opportunity.side} ${opportunity.recommended_size:.2f} "
                    f"on {opportunity.market_id} (edge: {opportunity.edge:.1%})"
                )

        await broadcast_message({
            "type": "trading_cycle",
            "timestamp": datetime.utcnow().isoformat(),
            "status": "completed",
            "opportunities_found": opportunities_found,
            "trades_executed": trades_executed,
        })

    async def _task_status_broadcast(self) -> None:
        """Broadcast system status to connected clients."""
        if not self._trading_engine:
            return

        status = self._trading_engine.get_status()

        # Add execution layer stats
        order_stats = {}
        position_stats = {}

        if self._order_monitor:
            order_stats = self._order_monitor.get_statistics()

        if self._position_tracker:
            position_stats = self._position_tracker.get_statistics()

        await broadcast_message({
            "type": "status",
            "data": {
                "status": status.status,
                "uptime": status.uptime_seconds,
                "trading_enabled": status.trading_enabled,
                "open_positions": status.open_positions_count,
                "pending_orders": order_stats.get("open_orders", 0),
                "api_connected": status.api_connected,
                "unrealized_pnl": position_stats.get("unrealized_pnl", 0),
                "realized_pnl": position_stats.get("realized_pnl", 0),
            },
            "timestamp": datetime.utcnow().isoformat(),
        })

    async def _task_metrics_log(self) -> None:
        """Log performance metrics."""
        if not self._trading_engine:
            return

        portfolio = await self._trading_engine.get_portfolio_summary()

        # Add position tracker stats
        position_stats = {}
        if self._position_tracker:
            position_stats = self._position_tracker.get_statistics()

        logger.info(
            f"Metrics | Bankroll: ${portfolio.bankroll:.2f} | "
            f"Daily P&L: ${portfolio.daily_pnl:+.2f} | "
            f"Unrealized: ${position_stats.get('unrealized_pnl', 0):+.2f} | "
            f"Win Rate: {portfolio.win_rate:.1%} | "
            f"Trades: {portfolio.total_trades}"
        )

    # ========== Status Methods ==========

    def get_state(self) -> Dict[str, Any]:
        """Get current event loop state."""
        uptime = 0
        if self.state.started_at:
            uptime = int((datetime.utcnow() - self.state.started_at).total_seconds())

        return {
            "is_running": self.state.is_running,
            "is_paused": not self._pause_event.is_set(),
            "uptime_seconds": uptime,
            "total_cycles": self.state.total_cycles,
            "tasks_executed": self.state.tasks_executed,
            "errors_encountered": self.state.errors_encountered,
            "cycle_duration_ms": self.state.cycle_duration_ms,
            "active_markets": len(self._active_markets),
            "pending_opportunities": len(self._pending_opportunities),
        }

    def get_task_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all registered tasks."""
        result = {}

        for name, task in self.tasks.items():
            result[name] = {
                "enabled": task.enabled,
                "interval_seconds": task.interval_seconds,
                "priority": task.priority.name,
                "run_count": task.run_count,
                "error_count": task.error_count,
                "last_run": task.last_run.isoformat() if task.last_run else None,
                "next_run": task.next_run.isoformat() if task.next_run else None,
                "last_error": task.last_error,
            }

        return result

    def get_opportunities(self) -> List[Dict[str, Any]]:
        """Get current trading opportunities."""
        return [
            {
                "market_id": o.market_id,
                "market_question": o.market_question,
                "side": o.side,
                "edge": o.edge,
                "forecast_probability": o.forecast_probability,
                "market_probability": o.market_probability,
                "confidence": o.confidence,
                "recommended_size": o.recommended_size,
                "location": o.location,
            }
            for o in self._pending_opportunities
        ]


# Global event loop instance
_event_loop: Optional[TradingEventLoop] = None


def get_event_loop() -> TradingEventLoop:
    """Get the global event loop instance."""
    global _event_loop
    if _event_loop is None:
        _event_loop = TradingEventLoop()
    return _event_loop


async def start_event_loop(trading_engine) -> TradingEventLoop:
    """Initialize and start the event loop."""
    loop = get_event_loop()
    await loop.initialize(trading_engine)
    asyncio.create_task(loop.start())
    return loop
