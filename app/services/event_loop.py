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
            from strategy import EdgeCalculator, PositionSizer, MarketScanner
            from risk import RiskManager

            self._edge_calculator = EdgeCalculator()
            self._position_sizer = PositionSizer(
                initial_bankroll=self.settings.initial_bankroll
            )
            self._market_scanner = MarketScanner()
            self._risk_manager = RiskManager(
                initial_bankroll=self.settings.initial_bankroll
            )

            # Register default tasks
            self._register_default_tasks()

            logger.info("Event loop initialized")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize event loop: {e}")
            return False

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

        try:
            await self._run_loop()
        except asyncio.CancelledError:
            logger.info("Event loop cancelled")
        except Exception as e:
            logger.error(f"Event loop error: {e}")
            logger.error(traceback.format_exc())
        finally:
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

    async def _task_price_update(self) -> None:
        """Update position prices from market."""
        if not self._trading_engine:
            return

        # Get current market prices for open positions
        positions = await self._trading_engine.get_open_positions()

        for position in positions:
            # In real implementation, fetch current price from CLOB
            # For now, simulate small price movement
            pass

        await broadcast_message({
            "type": "price_update",
            "timestamp": datetime.utcnow().isoformat(),
            "positions_updated": len(positions),
        })

    async def _task_order_monitor(self) -> None:
        """Monitor pending orders for fills."""
        if not self._trading_engine or not self._trading_engine._executor:
            return

        # Check for filled orders
        # In real implementation, would query CLOB for order status
        pass

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

        # Get markets that need forecast updates
        # In real implementation, would iterate through markets and fetch forecasts
        self._trading_engine._last_forecast_update = datetime.utcnow()

        await broadcast_message({
            "type": "forecast_update",
            "timestamp": datetime.utcnow().isoformat(),
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

        # In real implementation:
        # 1. Get markets with forecasts
        # 2. Calculate edge for each
        # 3. Filter by diversification rules
        # 4. Size positions with Kelly
        # 5. Execute trades

        await broadcast_message({
            "type": "trading_cycle",
            "timestamp": datetime.utcnow().isoformat(),
            "status": "completed",
        })

    async def _task_status_broadcast(self) -> None:
        """Broadcast system status to connected clients."""
        if not self._trading_engine:
            return

        status = self._trading_engine.get_status()

        await broadcast_message({
            "type": "status",
            "data": {
                "status": status.status,
                "uptime": status.uptime_seconds,
                "trading_enabled": status.trading_enabled,
                "open_positions": status.open_positions_count,
                "api_connected": status.api_connected,
            },
            "timestamp": datetime.utcnow().isoformat(),
        })

    async def _task_metrics_log(self) -> None:
        """Log performance metrics."""
        if not self._trading_engine:
            return

        portfolio = await self._trading_engine.get_portfolio_summary()

        logger.info(
            f"Metrics | Bankroll: ${portfolio.bankroll:.2f} | "
            f"Daily P&L: ${portfolio.daily_pnl:+.2f} | "
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
