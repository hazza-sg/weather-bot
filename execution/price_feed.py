"""WebSocket price feed for real-time market data."""
import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Callable, Any, Set
from dataclasses import dataclass, field
from enum import Enum

import websockets
from websockets.client import WebSocketClientProtocol

logger = logging.getLogger(__name__)


class FeedStatus(Enum):
    """Price feed connection status."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    ERROR = "error"


@dataclass
class PriceUpdate:
    """A price update from the feed."""
    token_id: str
    market_id: str
    bid: float
    ask: float
    mid: float
    last_trade_price: Optional[float]
    last_trade_size: Optional[float]
    timestamp: datetime
    volume_24h: float = 0.0


@dataclass
class OrderBookUpdate:
    """Order book update from the feed."""
    token_id: str
    bids: List[Dict[str, float]]  # [{"price": 0.55, "size": 100}, ...]
    asks: List[Dict[str, float]]
    timestamp: datetime


class PriceFeed:
    """
    WebSocket connection to Polymarket price feed.

    Provides real-time price updates for subscribed markets.
    """

    WS_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"

    def __init__(
        self,
        reconnect_delay: float = 5.0,
        max_reconnect_attempts: int = 10,
        heartbeat_interval: float = 30.0,
    ):
        self.reconnect_delay = reconnect_delay
        self.max_reconnect_attempts = max_reconnect_attempts
        self.heartbeat_interval = heartbeat_interval

        # Connection state
        self.status = FeedStatus.DISCONNECTED
        self._ws: Optional[WebSocketClientProtocol] = None
        self._reconnect_count = 0

        # Subscriptions
        self._subscribed_tokens: Set[str] = set()
        self._token_to_market: Dict[str, str] = {}

        # Cached prices
        self._prices: Dict[str, PriceUpdate] = {}
        self._order_books: Dict[str, OrderBookUpdate] = {}

        # Callbacks
        self._on_price: Optional[Callable[[PriceUpdate], Any]] = None
        self._on_orderbook: Optional[Callable[[OrderBookUpdate], Any]] = None
        self._on_connect: Optional[Callable[[], Any]] = None
        self._on_disconnect: Optional[Callable[[str], Any]] = None

        # Tasks
        self._receive_task: Optional[asyncio.Task] = None
        self._heartbeat_task: Optional[asyncio.Task] = None

    def on_price(self, callback: Callable[[PriceUpdate], Any]) -> None:
        """Register callback for price updates."""
        self._on_price = callback

    def on_orderbook(self, callback: Callable[[OrderBookUpdate], Any]) -> None:
        """Register callback for order book updates."""
        self._on_orderbook = callback

    def on_connect(self, callback: Callable[[], Any]) -> None:
        """Register callback for connection."""
        self._on_connect = callback

    def on_disconnect(self, callback: Callable[[str], Any]) -> None:
        """Register callback for disconnection."""
        self._on_disconnect = callback

    async def connect(self) -> bool:
        """Connect to the price feed."""
        if self.status == FeedStatus.CONNECTED:
            return True

        self.status = FeedStatus.CONNECTING
        logger.info("Connecting to price feed...")

        try:
            self._ws = await websockets.connect(
                self.WS_URL,
                ping_interval=20,
                ping_timeout=10,
            )

            self.status = FeedStatus.CONNECTED
            self._reconnect_count = 0

            # Start receive loop
            self._receive_task = asyncio.create_task(self._receive_loop())
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

            logger.info("Connected to price feed")

            # Resubscribe to any previous subscriptions
            if self._subscribed_tokens:
                await self._resubscribe()

            # Call connect callback
            if self._on_connect:
                try:
                    if asyncio.iscoroutinefunction(self._on_connect):
                        await self._on_connect()
                    else:
                        self._on_connect()
                except Exception as e:
                    logger.error(f"Error in connect callback: {e}")

            return True

        except Exception as e:
            logger.error(f"Failed to connect to price feed: {e}")
            self.status = FeedStatus.ERROR
            return False

    async def disconnect(self) -> None:
        """Disconnect from the price feed."""
        logger.info("Disconnecting from price feed...")

        # Cancel tasks
        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass

        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

        # Close connection
        if self._ws:
            await self._ws.close()
            self._ws = None

        self.status = FeedStatus.DISCONNECTED
        logger.info("Disconnected from price feed")

    async def subscribe(self, token_id: str, market_id: str = "") -> bool:
        """Subscribe to price updates for a token."""
        self._subscribed_tokens.add(token_id)
        self._token_to_market[token_id] = market_id

        if self.status != FeedStatus.CONNECTED or not self._ws:
            return False

        try:
            message = {
                "type": "subscribe",
                "channel": "price",
                "market": token_id,
            }
            await self._ws.send(json.dumps(message))

            logger.debug(f"Subscribed to {token_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to subscribe to {token_id}: {e}")
            return False

    async def unsubscribe(self, token_id: str) -> bool:
        """Unsubscribe from price updates for a token."""
        self._subscribed_tokens.discard(token_id)

        if token_id in self._token_to_market:
            del self._token_to_market[token_id]

        if self.status != FeedStatus.CONNECTED or not self._ws:
            return False

        try:
            message = {
                "type": "unsubscribe",
                "channel": "price",
                "market": token_id,
            }
            await self._ws.send(json.dumps(message))

            logger.debug(f"Unsubscribed from {token_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to unsubscribe from {token_id}: {e}")
            return False

    async def _resubscribe(self) -> None:
        """Resubscribe to all tokens after reconnection."""
        for token_id in self._subscribed_tokens:
            market_id = self._token_to_market.get(token_id, "")
            await self.subscribe(token_id, market_id)

    async def _receive_loop(self) -> None:
        """Main receive loop for WebSocket messages."""
        while self.status == FeedStatus.CONNECTED and self._ws:
            try:
                message = await self._ws.recv()
                await self._handle_message(message)

            except websockets.ConnectionClosed as e:
                logger.warning(f"WebSocket connection closed: {e}")
                await self._handle_disconnect("Connection closed")
                break

            except Exception as e:
                logger.error(f"Error receiving message: {e}")
                continue

    async def _heartbeat_loop(self) -> None:
        """Send periodic heartbeats."""
        while self.status == FeedStatus.CONNECTED and self._ws:
            try:
                await asyncio.sleep(self.heartbeat_interval)

                if self._ws:
                    await self._ws.send(json.dumps({"type": "ping"}))

            except Exception as e:
                logger.error(f"Heartbeat error: {e}")
                break

    async def _handle_message(self, raw_message: str) -> None:
        """Handle an incoming WebSocket message."""
        try:
            data = json.loads(raw_message)
            msg_type = data.get("type", "")

            if msg_type == "price":
                await self._handle_price_update(data)
            elif msg_type == "book":
                await self._handle_orderbook_update(data)
            elif msg_type == "pong":
                pass  # Heartbeat response
            elif msg_type == "error":
                logger.error(f"Feed error: {data.get('message', 'Unknown error')}")
            else:
                logger.debug(f"Unknown message type: {msg_type}")

        except json.JSONDecodeError:
            logger.error(f"Invalid JSON message: {raw_message[:100]}")

    async def _handle_price_update(self, data: Dict[str, Any]) -> None:
        """Handle a price update message."""
        token_id = data.get("market", data.get("token_id", ""))
        if not token_id:
            return

        update = PriceUpdate(
            token_id=token_id,
            market_id=self._token_to_market.get(token_id, ""),
            bid=float(data.get("bid", 0)),
            ask=float(data.get("ask", 0)),
            mid=float(data.get("mid", 0)),
            last_trade_price=data.get("last_trade_price"),
            last_trade_size=data.get("last_trade_size"),
            timestamp=datetime.utcnow(),
            volume_24h=float(data.get("volume_24h", 0)),
        )

        self._prices[token_id] = update

        # Call callback
        if self._on_price:
            try:
                if asyncio.iscoroutinefunction(self._on_price):
                    await self._on_price(update)
                else:
                    self._on_price(update)
            except Exception as e:
                logger.error(f"Error in price callback: {e}")

    async def _handle_orderbook_update(self, data: Dict[str, Any]) -> None:
        """Handle an order book update message."""
        token_id = data.get("market", data.get("token_id", ""))
        if not token_id:
            return

        update = OrderBookUpdate(
            token_id=token_id,
            bids=data.get("bids", []),
            asks=data.get("asks", []),
            timestamp=datetime.utcnow(),
        )

        self._order_books[token_id] = update

        # Call callback
        if self._on_orderbook:
            try:
                if asyncio.iscoroutinefunction(self._on_orderbook):
                    await self._on_orderbook(update)
                else:
                    self._on_orderbook(update)
            except Exception as e:
                logger.error(f"Error in orderbook callback: {e}")

    async def _handle_disconnect(self, reason: str) -> None:
        """Handle disconnection and attempt reconnection."""
        old_status = self.status
        self.status = FeedStatus.DISCONNECTED

        # Call disconnect callback
        if self._on_disconnect:
            try:
                if asyncio.iscoroutinefunction(self._on_disconnect):
                    await self._on_disconnect(reason)
                else:
                    self._on_disconnect(reason)
            except Exception as e:
                logger.error(f"Error in disconnect callback: {e}")

        # Attempt reconnection
        if old_status == FeedStatus.CONNECTED:
            await self._attempt_reconnect()

    async def _attempt_reconnect(self) -> None:
        """Attempt to reconnect to the price feed."""
        while self._reconnect_count < self.max_reconnect_attempts:
            self._reconnect_count += 1
            self.status = FeedStatus.RECONNECTING

            logger.info(
                f"Attempting reconnection ({self._reconnect_count}/{self.max_reconnect_attempts})..."
            )

            # Exponential backoff
            delay = self.reconnect_delay * (2 ** (self._reconnect_count - 1))
            delay = min(delay, 60)  # Cap at 60 seconds
            await asyncio.sleep(delay)

            if await self.connect():
                logger.info("Reconnected to price feed")
                return

        logger.error("Max reconnection attempts reached")
        self.status = FeedStatus.ERROR

    def get_price(self, token_id: str) -> Optional[PriceUpdate]:
        """Get cached price for a token."""
        return self._prices.get(token_id)

    def get_midpoint(self, token_id: str) -> Optional[float]:
        """Get midpoint price for a token."""
        price = self._prices.get(token_id)
        return price.mid if price else None

    def get_orderbook(self, token_id: str) -> Optional[OrderBookUpdate]:
        """Get cached order book for a token."""
        return self._order_books.get(token_id)

    def get_all_prices(self) -> Dict[str, PriceUpdate]:
        """Get all cached prices."""
        return self._prices.copy()

    def get_status(self) -> Dict[str, Any]:
        """Get feed status."""
        return {
            "status": self.status.value,
            "subscribed_tokens": len(self._subscribed_tokens),
            "cached_prices": len(self._prices),
            "reconnect_count": self._reconnect_count,
        }


class SimulatedPriceFeed:
    """
    Simulated price feed for testing.

    Generates random price movements for subscribed tokens.
    """

    def __init__(self, update_interval: float = 5.0):
        self.update_interval = update_interval
        self.status = FeedStatus.DISCONNECTED

        self._subscribed_tokens: Set[str] = set()
        self._prices: Dict[str, PriceUpdate] = {}

        self._on_price: Optional[Callable[[PriceUpdate], Any]] = None
        self._update_task: Optional[asyncio.Task] = None

    def on_price(self, callback: Callable[[PriceUpdate], Any]) -> None:
        """Register callback for price updates."""
        self._on_price = callback

    async def connect(self) -> bool:
        """Start the simulated feed."""
        self.status = FeedStatus.CONNECTED
        self._update_task = asyncio.create_task(self._simulation_loop())
        logger.info("Simulated price feed started")
        return True

    async def disconnect(self) -> None:
        """Stop the simulated feed."""
        if self._update_task:
            self._update_task.cancel()
            try:
                await self._update_task
            except asyncio.CancelledError:
                pass

        self.status = FeedStatus.DISCONNECTED
        logger.info("Simulated price feed stopped")

    async def subscribe(self, token_id: str, market_id: str = "") -> bool:
        """Add token to simulation."""
        import random

        self._subscribed_tokens.add(token_id)

        # Initialize with random price
        mid = random.uniform(0.3, 0.7)
        spread = random.uniform(0.01, 0.03)

        self._prices[token_id] = PriceUpdate(
            token_id=token_id,
            market_id=market_id,
            bid=mid - spread / 2,
            ask=mid + spread / 2,
            mid=mid,
            last_trade_price=mid,
            last_trade_size=random.uniform(10, 100),
            timestamp=datetime.utcnow(),
        )

        return True

    async def unsubscribe(self, token_id: str) -> bool:
        """Remove token from simulation."""
        self._subscribed_tokens.discard(token_id)
        if token_id in self._prices:
            del self._prices[token_id]
        return True

    async def _simulation_loop(self) -> None:
        """Generate simulated price updates."""
        import random

        while self.status == FeedStatus.CONNECTED:
            for token_id in list(self._subscribed_tokens):
                price = self._prices.get(token_id)
                if not price:
                    continue

                # Random price movement
                change = random.gauss(0, 0.005)
                new_mid = max(0.01, min(0.99, price.mid + change))
                spread = random.uniform(0.01, 0.03)

                update = PriceUpdate(
                    token_id=token_id,
                    market_id=price.market_id,
                    bid=max(0.01, new_mid - spread / 2),
                    ask=min(0.99, new_mid + spread / 2),
                    mid=new_mid,
                    last_trade_price=new_mid,
                    last_trade_size=random.uniform(10, 100),
                    timestamp=datetime.utcnow(),
                )

                self._prices[token_id] = update

                if self._on_price:
                    try:
                        if asyncio.iscoroutinefunction(self._on_price):
                            await self._on_price(update)
                        else:
                            self._on_price(update)
                    except Exception as e:
                        logger.error(f"Error in price callback: {e}")

            await asyncio.sleep(self.update_interval)

    def get_price(self, token_id: str) -> Optional[PriceUpdate]:
        """Get cached price."""
        return self._prices.get(token_id)

    def get_midpoint(self, token_id: str) -> Optional[float]:
        """Get midpoint price."""
        price = self._prices.get(token_id)
        return price.mid if price else None
