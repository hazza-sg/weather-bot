"""Position tracking service with price updates and P&L calculation."""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class PositionStatus(Enum):
    """Position status values."""
    OPEN = "open"
    CLOSING = "closing"     # Close order pending
    CLOSED = "closed"
    EXPIRED = "expired"     # Market resolved


@dataclass
class TrackedPosition:
    """A tracked trading position."""
    position_id: str
    market_id: str
    token_id: str
    market_question: str

    # Position details
    side: str               # "YES" or "NO"
    quantity: float         # Number of tokens held
    size: float             # Dollar cost basis
    entry_price: float      # Average entry price
    entry_time: datetime

    # Market info
    resolution_date: datetime
    location: Optional[str] = None
    market_type: str = "unknown"

    # Current state
    status: PositionStatus = PositionStatus.OPEN
    current_price: float = 0.0
    last_price_update: Optional[datetime] = None

    # P&L tracking
    unrealized_pnl: float = 0.0
    unrealized_pnl_pct: float = 0.0
    realized_pnl: float = 0.0

    # Trading metadata
    edge_at_entry: float = 0.0
    forecast_probability: float = 0.0
    model_agreement: float = 0.0

    # Resolution
    resolution_outcome: Optional[str] = None  # "YES", "NO", or None
    resolution_time: Optional[datetime] = None

    def calculate_unrealized_pnl(self) -> float:
        """Calculate unrealized P&L based on current price."""
        if self.current_price <= 0 or self.entry_price <= 0:
            return 0.0

        # P&L = (current_price - entry_price) * quantity
        # For YES positions: profit if price goes up
        # For NO positions: profit if underlying YES price goes down

        if self.side == "YES":
            pnl = (self.current_price - self.entry_price) * self.quantity
        else:
            # NO position profits when YES price falls
            # Entry was at (1 - entry_yes_price), current at (1 - current_yes_price)
            pnl = (self.entry_price - self.current_price) * self.quantity

        return pnl

    def calculate_pnl_percentage(self) -> float:
        """Calculate P&L as percentage of cost basis."""
        if self.size <= 0:
            return 0.0
        return (self.unrealized_pnl / self.size) * 100

    def market_value(self) -> float:
        """Get current market value of position."""
        return self.current_price * self.quantity

    def time_to_resolution(self) -> timedelta:
        """Get time until market resolution."""
        return self.resolution_date - datetime.utcnow()

    def hours_to_resolution(self) -> float:
        """Get hours until resolution."""
        return self.time_to_resolution().total_seconds() / 3600

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "position_id": self.position_id,
            "market_id": self.market_id,
            "token_id": self.token_id,
            "market_question": self.market_question,
            "side": self.side,
            "quantity": self.quantity,
            "size": self.size,
            "entry_price": self.entry_price,
            "entry_time": self.entry_time.isoformat(),
            "resolution_date": self.resolution_date.isoformat(),
            "location": self.location,
            "market_type": self.market_type,
            "status": self.status.value,
            "current_price": self.current_price,
            "unrealized_pnl": self.unrealized_pnl,
            "unrealized_pnl_pct": self.unrealized_pnl_pct,
            "realized_pnl": self.realized_pnl,
            "edge_at_entry": self.edge_at_entry,
            "market_value": self.market_value(),
            "hours_to_resolution": self.hours_to_resolution(),
        }


class PositionTracker:
    """
    Track and manage trading positions.

    Responsibilities:
    - Maintain position inventory
    - Update prices and calculate P&L
    - Track position lifecycle
    - Handle market resolutions
    """

    def __init__(
        self,
        executor = None,
        price_update_interval: float = 30.0,
    ):
        self.executor = executor
        self.price_update_interval = price_update_interval

        # Position tracking
        self._positions: Dict[str, TrackedPosition] = {}
        self._positions_by_market: Dict[str, List[str]] = {}
        self._closed_positions: List[TrackedPosition] = []

        # Callbacks
        self._on_price_update: Optional[Callable[[TrackedPosition], Any]] = None
        self._on_position_closed: Optional[Callable[[TrackedPosition], Any]] = None
        self._on_resolution: Optional[Callable[[TrackedPosition, str], Any]] = None

        # Price update state
        self._is_running = False
        self._update_task: Optional[asyncio.Task] = None

        # Statistics
        self._total_realized_pnl = 0.0

    def set_executor(self, executor) -> None:
        """Set the execution client for price lookups."""
        self.executor = executor

    def on_price_update(self, callback: Callable[[TrackedPosition], Any]) -> None:
        """Register callback for price updates."""
        self._on_price_update = callback

    def on_position_closed(self, callback: Callable[[TrackedPosition], Any]) -> None:
        """Register callback for position closures."""
        self._on_position_closed = callback

    def on_resolution(self, callback: Callable[[TrackedPosition, str], Any]) -> None:
        """Register callback for market resolutions."""
        self._on_resolution = callback

    def add_position(self, position: TrackedPosition) -> None:
        """Add a position to track."""
        self._positions[position.position_id] = position

        if position.market_id not in self._positions_by_market:
            self._positions_by_market[position.market_id] = []
        self._positions_by_market[position.market_id].append(position.position_id)

        # Initialize current price to entry
        if position.current_price == 0:
            position.current_price = position.entry_price

        logger.info(
            f"Tracking position {position.position_id}: "
            f"{position.side} {position.quantity:.4f} @ {position.entry_price:.4f}"
        )

    def get_position(self, position_id: str) -> Optional[TrackedPosition]:
        """Get a position by ID."""
        return self._positions.get(position_id)

    def get_open_positions(self) -> List[TrackedPosition]:
        """Get all open positions."""
        return [p for p in self._positions.values() if p.status == PositionStatus.OPEN]

    def get_positions_for_market(self, market_id: str) -> List[TrackedPosition]:
        """Get all positions for a market."""
        position_ids = self._positions_by_market.get(market_id, [])
        return [self._positions[pid] for pid in position_ids if pid in self._positions]

    def get_total_exposure(self) -> float:
        """Get total dollar exposure across all positions."""
        return sum(p.size for p in self.get_open_positions())

    def get_total_unrealized_pnl(self) -> float:
        """Get total unrealized P&L."""
        return sum(p.unrealized_pnl for p in self.get_open_positions())

    def get_total_market_value(self) -> float:
        """Get total current market value."""
        return sum(p.market_value() for p in self.get_open_positions())

    async def start_price_updates(self) -> None:
        """Start automatic price updates."""
        if self._is_running:
            return

        self._is_running = True
        self._update_task = asyncio.create_task(self._price_update_loop())
        logger.info("Position price updates started")

    async def stop_price_updates(self) -> None:
        """Stop automatic price updates."""
        self._is_running = False

        if self._update_task:
            self._update_task.cancel()
            try:
                await self._update_task
            except asyncio.CancelledError:
                pass

        logger.info("Position price updates stopped")

    async def _price_update_loop(self) -> None:
        """Main price update loop."""
        while self._is_running:
            try:
                await self._update_all_prices()
                await self._check_resolutions()
            except Exception as e:
                logger.error(f"Error in price update loop: {e}")

            await asyncio.sleep(self.price_update_interval)

    async def _update_all_prices(self) -> None:
        """Update prices for all open positions."""
        if not self.executor:
            return

        for position in self.get_open_positions():
            try:
                await self._update_position_price(position)
            except Exception as e:
                logger.error(f"Error updating price for {position.position_id}: {e}")

    async def _update_position_price(self, position: TrackedPosition) -> None:
        """Update price for a single position."""
        # Get current price from executor
        price = await self.executor.get_midpoint(position.token_id)

        if price is None:
            return

        old_price = position.current_price
        position.current_price = price
        position.last_price_update = datetime.utcnow()

        # Recalculate P&L
        position.unrealized_pnl = position.calculate_unrealized_pnl()
        position.unrealized_pnl_pct = position.calculate_pnl_percentage()

        # Log significant price changes
        if abs(price - old_price) / old_price > 0.05 and old_price > 0:
            logger.info(
                f"Position {position.position_id} price: "
                f"{old_price:.4f} -> {price:.4f} (P&L: {position.unrealized_pnl:+.2f})"
            )

        # Call callback
        if self._on_price_update:
            try:
                if asyncio.iscoroutinefunction(self._on_price_update):
                    await self._on_price_update(position)
                else:
                    self._on_price_update(position)
            except Exception as e:
                logger.error(f"Error in price update callback: {e}")

    async def _check_resolutions(self) -> None:
        """Check for resolved markets."""
        now = datetime.utcnow()

        for position in self.get_open_positions():
            if now >= position.resolution_date:
                # Market should be resolved - check outcome
                await self._check_market_resolution(position)

    async def _check_market_resolution(self, position: TrackedPosition) -> None:
        """Check if a market has resolved and process outcome."""
        # In production, would query market API for resolution
        # For now, simulate based on final price

        if position.current_price >= 0.95:
            outcome = "YES"
        elif position.current_price <= 0.05:
            outcome = "NO"
        else:
            # Not yet resolved
            return

        await self._handle_resolution(position, outcome)

    async def _handle_resolution(self, position: TrackedPosition, outcome: str) -> None:
        """Handle market resolution for a position."""
        position.status = PositionStatus.EXPIRED
        position.resolution_outcome = outcome
        position.resolution_time = datetime.utcnow()

        # Calculate final P&L
        if position.side == outcome:
            # Won - receive $1 per token
            position.realized_pnl = (1.0 - position.entry_price) * position.quantity
        else:
            # Lost - lose cost basis
            position.realized_pnl = -position.size

        position.unrealized_pnl = 0
        self._total_realized_pnl += position.realized_pnl

        logger.info(
            f"Position {position.position_id} resolved: "
            f"Outcome={outcome}, Side={position.side}, P&L={position.realized_pnl:+.2f}"
        )

        # Move to closed positions
        self._closed_positions.append(position)

        # Call callback
        if self._on_resolution:
            try:
                if asyncio.iscoroutinefunction(self._on_resolution):
                    await self._on_resolution(position, outcome)
                else:
                    self._on_resolution(position, outcome)
            except Exception as e:
                logger.error(f"Error in resolution callback: {e}")

    async def close_position(
        self,
        position_id: str,
        exit_price: Optional[float] = None,
        reason: str = "Manual close",
    ) -> Optional[float]:
        """
        Close a position.

        Returns realized P&L or None if position not found.
        """
        position = self._positions.get(position_id)
        if not position:
            return None

        if position.status != PositionStatus.OPEN:
            return None

        # Use current price if exit price not specified
        exit_price = exit_price or position.current_price

        # Calculate realized P&L
        if position.side == "YES":
            realized_pnl = (exit_price - position.entry_price) * position.quantity
        else:
            realized_pnl = (position.entry_price - exit_price) * position.quantity

        position.status = PositionStatus.CLOSED
        position.realized_pnl = realized_pnl
        position.unrealized_pnl = 0

        self._total_realized_pnl += realized_pnl
        self._closed_positions.append(position)

        logger.info(f"Closed position {position_id}: P&L = {realized_pnl:+.2f} ({reason})")

        # Call callback
        if self._on_position_closed:
            try:
                if asyncio.iscoroutinefunction(self._on_position_closed):
                    await self._on_position_closed(position)
                else:
                    self._on_position_closed(position)
            except Exception as e:
                logger.error(f"Error in position closed callback: {e}")

        return realized_pnl

    def update_position_from_fill(
        self,
        position_id: str,
        fill_quantity: float,
        fill_price: float,
        is_add: bool = True,
    ) -> bool:
        """
        Update position from a fill event.

        Args:
            position_id: Position to update
            fill_quantity: Quantity filled
            fill_price: Price of fill
            is_add: True if adding to position, False if reducing
        """
        position = self._positions.get(position_id)
        if not position:
            return False

        if is_add:
            # Adding to position - update average entry
            total_quantity = position.quantity + fill_quantity
            total_cost = position.size + (fill_quantity * fill_price)

            position.quantity = total_quantity
            position.size = total_cost
            position.entry_price = total_cost / total_quantity if total_quantity > 0 else 0
        else:
            # Reducing position
            position.quantity -= fill_quantity
            position.size -= fill_quantity * position.entry_price

            if position.quantity <= 0:
                position.status = PositionStatus.CLOSED

        # Recalculate P&L
        position.unrealized_pnl = position.calculate_unrealized_pnl()
        position.unrealized_pnl_pct = position.calculate_pnl_percentage()

        return True

    def get_positions_by_location(self) -> Dict[str, List[TrackedPosition]]:
        """Get positions grouped by location."""
        result: Dict[str, List[TrackedPosition]] = {}

        for position in self.get_open_positions():
            location = position.location or "Unknown"
            if location not in result:
                result[location] = []
            result[location].append(position)

        return result

    def get_positions_by_resolution_date(self) -> Dict[str, List[TrackedPosition]]:
        """Get positions grouped by resolution date."""
        result: Dict[str, List[TrackedPosition]] = {}

        for position in self.get_open_positions():
            date_key = position.resolution_date.strftime("%Y-%m-%d")
            if date_key not in result:
                result[date_key] = []
            result[date_key].append(position)

        return result

    def get_statistics(self) -> Dict[str, Any]:
        """Get position tracking statistics."""
        open_positions = self.get_open_positions()

        winning = [p for p in open_positions if p.unrealized_pnl > 0]
        losing = [p for p in open_positions if p.unrealized_pnl < 0]

        return {
            "open_positions": len(open_positions),
            "closed_positions": len(self._closed_positions),
            "total_exposure": self.get_total_exposure(),
            "total_market_value": self.get_total_market_value(),
            "unrealized_pnl": self.get_total_unrealized_pnl(),
            "realized_pnl": self._total_realized_pnl,
            "total_pnl": self.get_total_unrealized_pnl() + self._total_realized_pnl,
            "winning_positions": len(winning),
            "losing_positions": len(losing),
            "avg_unrealized_pnl": (
                self.get_total_unrealized_pnl() / len(open_positions)
                if open_positions else 0
            ),
        }

    def remove_closed_positions(self, older_than_hours: int = 24) -> int:
        """Remove closed positions from tracking."""
        cutoff = datetime.utcnow() - timedelta(hours=older_than_hours)

        # Remove from closed list
        old_count = len(self._closed_positions)
        self._closed_positions = [
            p for p in self._closed_positions
            if p.resolution_time and p.resolution_time > cutoff
        ]

        # Remove from main dict
        to_remove = [
            pid for pid, pos in self._positions.items()
            if pos.status in [PositionStatus.CLOSED, PositionStatus.EXPIRED]
        ]

        for pid in to_remove:
            pos = self._positions[pid]
            del self._positions[pid]

            if pos.market_id in self._positions_by_market:
                if pid in self._positions_by_market[pos.market_id]:
                    self._positions_by_market[pos.market_id].remove(pid)

        return old_count - len(self._closed_positions) + len(to_remove)
