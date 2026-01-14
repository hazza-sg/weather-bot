"""Order monitoring service for tracking fills and managing pending orders."""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class OrderStatus(Enum):
    """Order status values."""
    PENDING = "pending"       # Submitted but not yet acknowledged
    OPEN = "open"             # Active on the order book
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    REJECTED = "rejected"


class OrderType(Enum):
    """Order type values."""
    LIMIT = "limit"
    MARKET = "market"
    LIMIT_IOC = "limit_ioc"  # Immediate or cancel


@dataclass
class Order:
    """Represents a trading order."""
    order_id: str
    market_id: str
    token_id: str
    side: str               # "BUY" or "SELL"
    order_type: OrderType
    price: float
    size: float             # Total size in dollars
    quantity: float         # Number of tokens

    status: OrderStatus = OrderStatus.PENDING
    filled_size: float = 0.0
    filled_quantity: float = 0.0
    average_fill_price: float = 0.0

    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None

    # Tracking
    fill_events: List[Dict[str, Any]] = field(default_factory=list)
    error_message: Optional[str] = None

    # Trade metadata
    edge_at_entry: float = 0.0
    forecast_probability: float = 0.0
    is_manual: bool = False

    def remaining_size(self) -> float:
        """Get unfilled size."""
        return self.size - self.filled_size

    def fill_percentage(self) -> float:
        """Get fill percentage."""
        return (self.filled_size / self.size) if self.size > 0 else 0

    def is_complete(self) -> bool:
        """Check if order is complete (filled/cancelled/rejected)."""
        return self.status in [
            OrderStatus.FILLED,
            OrderStatus.CANCELLED,
            OrderStatus.EXPIRED,
            OrderStatus.REJECTED,
        ]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "order_id": self.order_id,
            "market_id": self.market_id,
            "token_id": self.token_id,
            "side": self.side,
            "order_type": self.order_type.value,
            "price": self.price,
            "size": self.size,
            "quantity": self.quantity,
            "status": self.status.value,
            "filled_size": self.filled_size,
            "filled_quantity": self.filled_quantity,
            "average_fill_price": self.average_fill_price,
            "fill_percentage": self.fill_percentage(),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "is_manual": self.is_manual,
        }


@dataclass
class FillEvent:
    """Represents a fill event for an order."""
    order_id: str
    fill_id: str
    price: float
    quantity: float
    size: float  # Dollar amount
    timestamp: datetime
    maker_address: Optional[str] = None
    taker_address: Optional[str] = None


class OrderMonitor:
    """
    Monitor and manage trading orders.

    Responsibilities:
    - Track pending and open orders
    - Process fill events
    - Handle order timeouts and expirations
    - Notify on order state changes
    """

    def __init__(
        self,
        executor = None,
        poll_interval: float = 5.0,
        order_timeout_minutes: int = 60,
    ):
        self.executor = executor
        self.poll_interval = poll_interval
        self.order_timeout = timedelta(minutes=order_timeout_minutes)

        # Order tracking
        self._orders: Dict[str, Order] = {}
        self._orders_by_market: Dict[str, List[str]] = {}

        # Callbacks
        self._on_fill: Optional[Callable[[Order, FillEvent], Any]] = None
        self._on_complete: Optional[Callable[[Order], Any]] = None
        self._on_timeout: Optional[Callable[[Order], Any]] = None

        # Monitoring state
        self._is_running = False
        self._monitor_task: Optional[asyncio.Task] = None

    def set_executor(self, executor) -> None:
        """Set the execution client."""
        self.executor = executor

    def on_fill(self, callback: Callable[[Order, FillEvent], Any]) -> None:
        """Register callback for fill events."""
        self._on_fill = callback

    def on_complete(self, callback: Callable[[Order], Any]) -> None:
        """Register callback for order completion."""
        self._on_complete = callback

    def on_timeout(self, callback: Callable[[Order], Any]) -> None:
        """Register callback for order timeout."""
        self._on_timeout = callback

    def add_order(self, order: Order) -> None:
        """Add an order to be monitored."""
        self._orders[order.order_id] = order

        if order.market_id not in self._orders_by_market:
            self._orders_by_market[order.market_id] = []
        self._orders_by_market[order.market_id].append(order.order_id)

        logger.info(f"Monitoring order {order.order_id}: {order.side} {order.size:.2f} @ {order.price:.4f}")

    def get_order(self, order_id: str) -> Optional[Order]:
        """Get an order by ID."""
        return self._orders.get(order_id)

    def get_open_orders(self) -> List[Order]:
        """Get all open (non-complete) orders."""
        return [o for o in self._orders.values() if not o.is_complete()]

    def get_orders_for_market(self, market_id: str) -> List[Order]:
        """Get all orders for a market."""
        order_ids = self._orders_by_market.get(market_id, [])
        return [self._orders[oid] for oid in order_ids if oid in self._orders]

    def get_pending_size(self, market_id: str) -> float:
        """Get total pending order size for a market."""
        orders = self.get_orders_for_market(market_id)
        return sum(o.remaining_size() for o in orders if not o.is_complete())

    async def start_monitoring(self) -> None:
        """Start the order monitoring loop."""
        if self._is_running:
            return

        self._is_running = True
        self._monitor_task = asyncio.create_task(self._monitoring_loop())
        logger.info("Order monitoring started")

    async def stop_monitoring(self) -> None:
        """Stop the order monitoring loop."""
        self._is_running = False

        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass

        logger.info("Order monitoring stopped")

    async def _monitoring_loop(self) -> None:
        """Main monitoring loop."""
        while self._is_running:
            try:
                await self._check_orders()
                await self._check_timeouts()
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")

            await asyncio.sleep(self.poll_interval)

    async def _check_orders(self) -> None:
        """Check status of all open orders."""
        if not self.executor:
            return

        open_orders = self.get_open_orders()
        if not open_orders:
            return

        # In production, would query the CLOB for order status
        # For now, check against simulated state
        for order in open_orders:
            await self._check_order_status(order)

    async def _check_order_status(self, order: Order) -> None:
        """Check and update status of a single order."""
        # In production, query CLOB API:
        # response = await self.executor.get_order(order.order_id)

        # For simulation/test mode, check executor's internal state
        if hasattr(self.executor, '_simulated_orders'):
            sim_order = self.executor._simulated_orders.get(order.order_id)
            if sim_order:
                await self._process_order_update(order, sim_order)

    async def _process_order_update(self, order: Order, update: Dict[str, Any]) -> None:
        """Process an order status update."""
        old_status = order.status
        new_status_str = update.get("status", "").lower()

        # Map status strings to enum
        status_map = {
            "open": OrderStatus.OPEN,
            "pending": OrderStatus.PENDING,
            "filled": OrderStatus.FILLED,
            "partially_filled": OrderStatus.PARTIALLY_FILLED,
            "cancelled": OrderStatus.CANCELLED,
            "expired": OrderStatus.EXPIRED,
            "rejected": OrderStatus.REJECTED,
        }

        new_status = status_map.get(new_status_str, order.status)

        # Check for fills
        filled_size = update.get("filled_size", update.get("size", 0))
        if isinstance(filled_size, float) and filled_size > order.filled_size:
            # Process fill
            fill_amount = filled_size - order.filled_size
            fill_price = update.get("price", order.price)

            fill_event = FillEvent(
                order_id=order.order_id,
                fill_id=f"{order.order_id}-{len(order.fill_events) + 1}",
                price=fill_price,
                quantity=fill_amount / fill_price,
                size=fill_amount,
                timestamp=datetime.utcnow(),
            )

            order.fill_events.append(fill_event.__dict__)
            order.filled_size = filled_size
            order.filled_quantity += fill_event.quantity

            # Recalculate average fill price
            if order.filled_quantity > 0:
                order.average_fill_price = order.filled_size / order.filled_quantity

            # Call fill callback
            if self._on_fill:
                try:
                    await self._on_fill(order, fill_event) if asyncio.iscoroutinefunction(self._on_fill) else self._on_fill(order, fill_event)
                except Exception as e:
                    logger.error(f"Error in fill callback: {e}")

            logger.info(f"Order {order.order_id} fill: {fill_amount:.2f} @ {fill_price:.4f}")

        # Update status
        if new_status != old_status:
            order.status = new_status
            order.updated_at = datetime.utcnow()

            logger.info(f"Order {order.order_id} status: {old_status.value} -> {new_status.value}")

            # Check if complete
            if order.is_complete() and self._on_complete:
                try:
                    await self._on_complete(order) if asyncio.iscoroutinefunction(self._on_complete) else self._on_complete(order)
                except Exception as e:
                    logger.error(f"Error in complete callback: {e}")

    async def _check_timeouts(self) -> None:
        """Check for timed out orders."""
        now = datetime.utcnow()

        for order in self.get_open_orders():
            # Check expiration
            if order.expires_at and now > order.expires_at:
                await self._handle_timeout(order, "Order expired")
                continue

            # Check default timeout
            if now - order.created_at > self.order_timeout:
                await self._handle_timeout(order, "Order timed out")

    async def _handle_timeout(self, order: Order, reason: str) -> None:
        """Handle an order timeout."""
        order.status = OrderStatus.EXPIRED
        order.error_message = reason
        order.updated_at = datetime.utcnow()

        logger.warning(f"Order {order.order_id} timeout: {reason}")

        # Attempt to cancel on exchange
        if self.executor:
            try:
                await self.executor.cancel_order(order.order_id)
            except Exception as e:
                logger.error(f"Failed to cancel timed out order: {e}")

        # Call timeout callback
        if self._on_timeout:
            try:
                await self._on_timeout(order) if asyncio.iscoroutinefunction(self._on_timeout) else self._on_timeout(order)
            except Exception as e:
                logger.error(f"Error in timeout callback: {e}")

    async def cancel_order(self, order_id: str, reason: str = "User cancelled") -> bool:
        """Cancel an order."""
        order = self._orders.get(order_id)
        if not order:
            return False

        if order.is_complete():
            return False

        # Cancel on exchange
        if self.executor:
            success = await self.executor.cancel_order(order_id)
            if not success:
                logger.warning(f"Failed to cancel order {order_id} on exchange")

        order.status = OrderStatus.CANCELLED
        order.error_message = reason
        order.updated_at = datetime.utcnow()

        logger.info(f"Order {order_id} cancelled: {reason}")

        if self._on_complete:
            try:
                await self._on_complete(order) if asyncio.iscoroutinefunction(self._on_complete) else self._on_complete(order)
            except Exception as e:
                logger.error(f"Error in complete callback: {e}")

        return True

    async def cancel_all_orders(self, market_id: Optional[str] = None) -> int:
        """Cancel all open orders, optionally filtered by market."""
        cancelled = 0

        orders = self.get_orders_for_market(market_id) if market_id else self.get_open_orders()

        for order in orders:
            if not order.is_complete():
                if await self.cancel_order(order.order_id, "Bulk cancellation"):
                    cancelled += 1

        return cancelled

    def get_statistics(self) -> Dict[str, Any]:
        """Get order monitoring statistics."""
        all_orders = list(self._orders.values())
        open_orders = self.get_open_orders()

        filled_orders = [o for o in all_orders if o.status == OrderStatus.FILLED]
        cancelled_orders = [o for o in all_orders if o.status == OrderStatus.CANCELLED]

        total_filled_size = sum(o.filled_size for o in filled_orders)

        return {
            "total_orders": len(all_orders),
            "open_orders": len(open_orders),
            "filled_orders": len(filled_orders),
            "cancelled_orders": len(cancelled_orders),
            "total_filled_size": total_filled_size,
            "pending_size": sum(o.remaining_size() for o in open_orders),
            "fill_rate": len(filled_orders) / len(all_orders) if all_orders else 0,
        }

    def clear_completed_orders(self, older_than_hours: int = 24) -> int:
        """Remove completed orders older than specified hours."""
        cutoff = datetime.utcnow() - timedelta(hours=older_than_hours)
        to_remove = []

        for order_id, order in self._orders.items():
            if order.is_complete() and order.updated_at < cutoff:
                to_remove.append(order_id)

        for order_id in to_remove:
            order = self._orders[order_id]
            del self._orders[order_id]

            if order.market_id in self._orders_by_market:
                if order_id in self._orders_by_market[order.market_id]:
                    self._orders_by_market[order.market_id].remove(order_id)

        return len(to_remove)
