"""WebSocket handler for real-time updates."""
import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, Set, Any, Optional
from dataclasses import dataclass, field

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


@dataclass
class WebSocketClient:
    """Connected WebSocket client."""

    websocket: WebSocket
    subscribed_channels: Set[str] = field(default_factory=set)
    connected_at: datetime = field(default_factory=datetime.utcnow)


class WebSocketManager:
    """Manage WebSocket connections and message broadcasting."""

    def __init__(self):
        self.active_connections: Dict[str, WebSocketClient] = {}
        self._connection_counter = 0

    async def connect(self, websocket: WebSocket) -> str:
        """Accept a new WebSocket connection."""
        await websocket.accept()
        self._connection_counter += 1
        client_id = f"client_{self._connection_counter}"

        self.active_connections[client_id] = WebSocketClient(
            websocket=websocket,
            subscribed_channels={"all"},  # Default to all channels
        )

        logger.info(f"WebSocket client connected: {client_id}")
        return client_id

    def disconnect(self, client_id: str) -> None:
        """Remove a disconnected client."""
        if client_id in self.active_connections:
            del self.active_connections[client_id]
            logger.info(f"WebSocket client disconnected: {client_id}")

    async def subscribe(self, client_id: str, channels: list) -> None:
        """Subscribe a client to specific channels."""
        if client_id in self.active_connections:
            self.active_connections[client_id].subscribed_channels.update(channels)
            logger.debug(f"Client {client_id} subscribed to: {channels}")

    async def unsubscribe(self, client_id: str, channels: list) -> None:
        """Unsubscribe a client from specific channels."""
        if client_id in self.active_connections:
            self.active_connections[client_id].subscribed_channels -= set(channels)
            logger.debug(f"Client {client_id} unsubscribed from: {channels}")

    async def send_to_client(self, client_id: str, message: dict) -> bool:
        """Send a message to a specific client."""
        if client_id not in self.active_connections:
            return False

        try:
            await self.active_connections[client_id].websocket.send_json(message)
            return True
        except Exception as e:
            logger.error(f"Error sending to client {client_id}: {e}")
            self.disconnect(client_id)
            return False

    async def broadcast(self, message: dict, channel: str = "all") -> int:
        """Broadcast a message to all clients subscribed to a channel."""
        message_with_meta = {
            "type": message.get("type", "update"),
            "timestamp": datetime.utcnow().isoformat(),
            "channel": channel,
            "data": message.get("data", message),
        }

        sent_count = 0
        disconnected = []

        for client_id, client in self.active_connections.items():
            # Check if client is subscribed to this channel or "all"
            if channel in client.subscribed_channels or "all" in client.subscribed_channels:
                try:
                    await client.websocket.send_json(message_with_meta)
                    sent_count += 1
                except Exception as e:
                    logger.error(f"Error broadcasting to {client_id}: {e}")
                    disconnected.append(client_id)

        # Clean up disconnected clients
        for client_id in disconnected:
            self.disconnect(client_id)

        return sent_count

    async def broadcast_price_update(
        self,
        market_id: str,
        token_id: str,
        price: float,
        side: str,
    ) -> None:
        """Broadcast a price update."""
        await self.broadcast(
            {
                "type": "price_update",
                "data": {
                    "market_id": market_id,
                    "token_id": token_id,
                    "price": price,
                    "side": side,
                },
            },
            channel="prices",
        )

    async def broadcast_position_update(
        self,
        position_id: str,
        current_price: float,
        unrealized_pnl: float,
    ) -> None:
        """Broadcast a position P&L update."""
        await self.broadcast(
            {
                "type": "position_update",
                "data": {
                    "position_id": position_id,
                    "current_price": current_price,
                    "unrealized_pnl": unrealized_pnl,
                },
            },
            channel="positions",
        )

    async def broadcast_trade_executed(
        self,
        trade_id: str,
        market: str,
        side: str,
        size: float,
        price: float,
    ) -> None:
        """Broadcast a trade execution."""
        await self.broadcast(
            {
                "type": "trade_executed",
                "data": {
                    "trade_id": trade_id,
                    "market": market,
                    "side": side,
                    "size": size,
                    "price": price,
                },
            },
            channel="trades",
        )

    async def broadcast_trade_resolved(
        self,
        trade_id: str,
        result: str,
        pnl: float,
    ) -> None:
        """Broadcast a trade resolution."""
        await self.broadcast(
            {
                "type": "trade_resolved",
                "data": {
                    "trade_id": trade_id,
                    "result": result,
                    "pnl": pnl,
                },
            },
            channel="trades",
        )

    async def broadcast_edge_alert(
        self,
        market_id: str,
        edge: float,
        forecast_prob: float,
        market_prob: float,
    ) -> None:
        """Broadcast a new opportunity alert."""
        await self.broadcast(
            {
                "type": "edge_alert",
                "data": {
                    "market_id": market_id,
                    "edge": edge,
                    "forecast_probability": forecast_prob,
                    "market_probability": market_prob,
                },
            },
            channel="alerts",
        )

    async def broadcast_risk_alert(
        self,
        alert_type: str,
        current_value: float,
        limit_value: float,
    ) -> None:
        """Broadcast a risk warning."""
        await self.broadcast(
            {
                "type": "risk_alert",
                "data": {
                    "alert_type": alert_type,
                    "current_value": current_value,
                    "limit_value": limit_value,
                },
            },
            channel="alerts",
        )

    async def broadcast_system_status(self, status: str, message: str) -> None:
        """Broadcast a system status change."""
        await self.broadcast(
            {
                "type": "system_status",
                "data": {
                    "status": status,
                    "message": message,
                },
            },
            channel="system",
        )

    async def broadcast_halt_triggered(
        self,
        reason: str,
        can_auto_recover: bool,
    ) -> None:
        """Broadcast a trading halt."""
        await self.broadcast(
            {
                "type": "halt_triggered",
                "data": {
                    "reason": reason,
                    "can_auto_recover": can_auto_recover,
                },
            },
            channel="system",
        )

    @property
    def connection_count(self) -> int:
        """Get number of active connections."""
        return len(self.active_connections)


# Global WebSocket manager instance
ws_manager = WebSocketManager()


async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint handler."""
    client_id = await ws_manager.connect(websocket)

    try:
        # Send initial connection confirmation
        await websocket.send_json({
            "type": "connected",
            "timestamp": datetime.utcnow().isoformat(),
            "client_id": client_id,
        })

        while True:
            # Receive and process messages
            data = await websocket.receive_text()

            try:
                message = json.loads(data)
                msg_type = message.get("type", "")

                if msg_type == "subscribe":
                    channels = message.get("channels", [])
                    await ws_manager.subscribe(client_id, channels)
                    await websocket.send_json({
                        "type": "subscribed",
                        "channels": channels,
                    })

                elif msg_type == "unsubscribe":
                    channels = message.get("channels", [])
                    await ws_manager.unsubscribe(client_id, channels)
                    await websocket.send_json({
                        "type": "unsubscribed",
                        "channels": channels,
                    })

                elif msg_type == "ping":
                    await websocket.send_json({
                        "type": "pong",
                        "timestamp": datetime.utcnow().isoformat(),
                    })

            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "message": "Invalid JSON",
                })

    except WebSocketDisconnect:
        ws_manager.disconnect(client_id)
