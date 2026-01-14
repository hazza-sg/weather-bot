"""Alert management system for notifications and activity logging."""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from enum import Enum
import json

from app.api.websocket import broadcast_message

logger = logging.getLogger(__name__)


class AlertLevel(Enum):
    """Alert severity levels."""
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertCategory(Enum):
    """Alert categories for filtering."""
    TRADE = "trade"
    RISK = "risk"
    SYSTEM = "system"
    MARKET = "market"
    POSITION = "position"
    FORECAST = "forecast"


@dataclass
class Alert:
    """An alert/notification."""
    id: str
    level: AlertLevel
    category: AlertCategory
    title: str
    message: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    data: Optional[Dict[str, Any]] = None
    read: bool = False
    dismissed: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "level": self.level.value,
            "category": self.category.value,
            "title": self.title,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
            "read": self.read,
            "dismissed": self.dismissed,
        }


@dataclass
class ActivityLogEntry:
    """An entry in the activity log."""
    id: str
    action: str
    description: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    category: str = "system"
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "action": self.action,
            "description": self.description,
            "timestamp": self.timestamp.isoformat(),
            "category": self.category,
            "metadata": self.metadata,
        }


@dataclass
class AlertPreferences:
    """User preferences for alerts."""
    enabled: bool = True
    desktop_notifications: bool = True
    sound_enabled: bool = False

    # Category preferences
    trade_alerts: bool = True
    risk_alerts: bool = True
    system_alerts: bool = True
    market_alerts: bool = True
    position_alerts: bool = True

    # Thresholds
    min_edge_for_alert: float = 0.10  # Alert when edge >= 10%
    pnl_alert_threshold: float = 50.0  # Alert on P&L changes >= $50
    position_alert_threshold: float = 100.0  # Alert on positions >= $100

    def to_dict(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "desktop_notifications": self.desktop_notifications,
            "sound_enabled": self.sound_enabled,
            "trade_alerts": self.trade_alerts,
            "risk_alerts": self.risk_alerts,
            "system_alerts": self.system_alerts,
            "market_alerts": self.market_alerts,
            "position_alerts": self.position_alerts,
            "min_edge_for_alert": self.min_edge_for_alert,
            "pnl_alert_threshold": self.pnl_alert_threshold,
            "position_alert_threshold": self.position_alert_threshold,
        }


class AlertManager:
    """
    Manages alerts, notifications, and activity logging.

    Responsibilities:
    - Generate alerts for various events
    - Manage user alert preferences
    - Maintain activity log
    - Broadcast alerts via WebSocket
    """

    def __init__(self, max_alerts: int = 100, max_activity_log: int = 500):
        self.max_alerts = max_alerts
        self.max_activity_log = max_activity_log

        self._alerts: List[Alert] = []
        self._activity_log: List[ActivityLogEntry] = []
        self._preferences = AlertPreferences()
        self._alert_counter = 0

        # Callbacks
        self._on_alert: Optional[Callable[[Alert], Any]] = None

    def on_alert(self, callback: Callable[[Alert], Any]) -> None:
        """Register callback for new alerts."""
        self._on_alert = callback

    def get_preferences(self) -> AlertPreferences:
        """Get current alert preferences."""
        return self._preferences

    def update_preferences(self, updates: Dict[str, Any]) -> None:
        """Update alert preferences."""
        for key, value in updates.items():
            if hasattr(self._preferences, key):
                setattr(self._preferences, key, value)

        logger.info(f"Alert preferences updated: {updates}")

    async def create_alert(
        self,
        level: AlertLevel,
        category: AlertCategory,
        title: str,
        message: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> Optional[Alert]:
        """Create and broadcast a new alert."""
        # Check if alerts are enabled for this category
        if not self._preferences.enabled:
            return None

        category_enabled = {
            AlertCategory.TRADE: self._preferences.trade_alerts,
            AlertCategory.RISK: self._preferences.risk_alerts,
            AlertCategory.SYSTEM: self._preferences.system_alerts,
            AlertCategory.MARKET: self._preferences.market_alerts,
            AlertCategory.POSITION: self._preferences.position_alerts,
            AlertCategory.FORECAST: self._preferences.market_alerts,
        }

        if not category_enabled.get(category, True):
            return None

        # Create alert
        self._alert_counter += 1
        alert = Alert(
            id=f"alert-{self._alert_counter}",
            level=level,
            category=category,
            title=title,
            message=message,
            data=data,
        )

        # Add to list
        self._alerts.insert(0, alert)

        # Trim old alerts
        if len(self._alerts) > self.max_alerts:
            self._alerts = self._alerts[:self.max_alerts]

        # Broadcast via WebSocket
        await broadcast_message({
            "type": "alert",
            "alert": alert.to_dict(),
        })

        # Call callback
        if self._on_alert:
            try:
                if asyncio.iscoroutinefunction(self._on_alert):
                    await self._on_alert(alert)
                else:
                    self._on_alert(alert)
            except Exception as e:
                logger.error(f"Error in alert callback: {e}")

        logger.info(f"Alert created: [{level.value}] {title}")

        return alert

    def log_activity(
        self,
        action: str,
        description: str,
        category: str = "system",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ActivityLogEntry:
        """Log an activity."""
        entry = ActivityLogEntry(
            id=f"activity-{len(self._activity_log) + 1}",
            action=action,
            description=description,
            category=category,
            metadata=metadata,
        )

        self._activity_log.insert(0, entry)

        # Trim old entries
        if len(self._activity_log) > self.max_activity_log:
            self._activity_log = self._activity_log[:self.max_activity_log]

        return entry

    def get_alerts(
        self,
        limit: int = 50,
        unread_only: bool = False,
        category: Optional[AlertCategory] = None,
        level: Optional[AlertLevel] = None,
    ) -> List[Alert]:
        """Get alerts with optional filtering."""
        alerts = self._alerts

        if unread_only:
            alerts = [a for a in alerts if not a.read]

        if category:
            alerts = [a for a in alerts if a.category == category]

        if level:
            alerts = [a for a in alerts if a.level == level]

        return alerts[:limit]

    def get_unread_count(self) -> int:
        """Get count of unread alerts."""
        return sum(1 for a in self._alerts if not a.read and not a.dismissed)

    def mark_read(self, alert_id: str) -> bool:
        """Mark an alert as read."""
        for alert in self._alerts:
            if alert.id == alert_id:
                alert.read = True
                return True
        return False

    def mark_all_read(self) -> int:
        """Mark all alerts as read."""
        count = 0
        for alert in self._alerts:
            if not alert.read:
                alert.read = True
                count += 1
        return count

    def dismiss_alert(self, alert_id: str) -> bool:
        """Dismiss an alert."""
        for alert in self._alerts:
            if alert.id == alert_id:
                alert.dismissed = True
                return True
        return False

    def clear_alerts(self, older_than_hours: int = 0) -> int:
        """Clear alerts, optionally older than specified hours."""
        if older_than_hours > 0:
            cutoff = datetime.utcnow() - timedelta(hours=older_than_hours)
            old_count = len(self._alerts)
            self._alerts = [a for a in self._alerts if a.timestamp > cutoff]
            return old_count - len(self._alerts)
        else:
            count = len(self._alerts)
            self._alerts.clear()
            return count

    def get_activity_log(
        self,
        limit: int = 100,
        category: Optional[str] = None,
    ) -> List[ActivityLogEntry]:
        """Get activity log entries."""
        entries = self._activity_log

        if category:
            entries = [e for e in entries if e.category == category]

        return entries[:limit]

    def clear_activity_log(self) -> int:
        """Clear activity log."""
        count = len(self._activity_log)
        self._activity_log.clear()
        return count

    # ========== Convenience Methods for Common Alerts ==========

    async def alert_trade_executed(
        self,
        trade_id: str,
        market_id: str,
        side: str,
        size: float,
        price: float,
        edge: float,
    ) -> None:
        """Alert for trade execution."""
        if size < self._preferences.position_alert_threshold:
            return

        await self.create_alert(
            level=AlertLevel.SUCCESS,
            category=AlertCategory.TRADE,
            title="Trade Executed",
            message=f"{side} ${size:.2f} at {price:.2%} (edge: {edge:.1%})",
            data={
                "trade_id": trade_id,
                "market_id": market_id,
                "side": side,
                "size": size,
                "price": price,
                "edge": edge,
            },
        )

        self.log_activity(
            action="trade_executed",
            description=f"Executed {side} trade for ${size:.2f}",
            category="trade",
            metadata={"trade_id": trade_id, "market_id": market_id},
        )

    async def alert_position_closed(
        self,
        position_id: str,
        realized_pnl: float,
        side: str,
    ) -> None:
        """Alert for position closure."""
        if abs(realized_pnl) < self._preferences.pnl_alert_threshold:
            return

        level = AlertLevel.SUCCESS if realized_pnl > 0 else AlertLevel.WARNING

        await self.create_alert(
            level=level,
            category=AlertCategory.POSITION,
            title="Position Closed",
            message=f"{side} position closed: P&L ${realized_pnl:+.2f}",
            data={
                "position_id": position_id,
                "realized_pnl": realized_pnl,
            },
        )

    async def alert_risk_warning(self, message: str, metrics: Dict[str, Any]) -> None:
        """Alert for risk warnings."""
        await self.create_alert(
            level=AlertLevel.WARNING,
            category=AlertCategory.RISK,
            title="Risk Warning",
            message=message,
            data=metrics,
        )

    async def alert_trading_halted(self, reason: str) -> None:
        """Alert for trading halt."""
        await self.create_alert(
            level=AlertLevel.CRITICAL,
            category=AlertCategory.RISK,
            title="Trading Halted",
            message=reason,
        )

        self.log_activity(
            action="trading_halted",
            description=f"Trading halted: {reason}",
            category="risk",
        )

    async def alert_opportunity_found(
        self,
        market_id: str,
        question: str,
        edge: float,
        side: str,
    ) -> None:
        """Alert for high-edge opportunity."""
        if edge < self._preferences.min_edge_for_alert:
            return

        await self.create_alert(
            level=AlertLevel.INFO,
            category=AlertCategory.MARKET,
            title="Opportunity Found",
            message=f"{edge:.1%} edge on {side}: {question[:50]}...",
            data={
                "market_id": market_id,
                "question": question,
                "edge": edge,
                "side": side,
            },
        )

    async def alert_system_error(self, error: str, component: str) -> None:
        """Alert for system errors."""
        await self.create_alert(
            level=AlertLevel.ERROR,
            category=AlertCategory.SYSTEM,
            title=f"System Error: {component}",
            message=error,
        )

        self.log_activity(
            action="system_error",
            description=f"Error in {component}: {error}",
            category="system",
        )

    async def alert_forecast_update(self, markets_updated: int) -> None:
        """Alert for forecast updates."""
        await self.create_alert(
            level=AlertLevel.INFO,
            category=AlertCategory.FORECAST,
            title="Forecasts Updated",
            message=f"Updated forecasts for {markets_updated} markets",
        )


# Global alert manager instance
_alert_manager: Optional[AlertManager] = None


def get_alert_manager() -> AlertManager:
    """Get the global alert manager instance."""
    global _alert_manager
    if _alert_manager is None:
        _alert_manager = AlertManager()
    return _alert_manager
