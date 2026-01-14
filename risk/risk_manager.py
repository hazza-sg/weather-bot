"""Risk manager for enforcing trading limits and halt conditions."""
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple, List
from enum import Enum

from app.config import RISK_LIMITS

logger = logging.getLogger(__name__)


class HaltCondition(Enum):
    """Reasons for trading halts."""
    NONE = "none"
    DAILY_LOSS = "daily_loss"
    WEEKLY_LOSS = "weekly_loss"
    MONTHLY_LOSS = "monthly_loss"
    MANUAL = "manual"
    SYSTEM_ERROR = "system_error"
    API_DISCONNECTED = "api_disconnected"


@dataclass
class RiskState:
    """Current risk state snapshot."""

    # P&L tracking
    daily_pnl: float = 0.0
    weekly_pnl: float = 0.0
    monthly_pnl: float = 0.0
    total_pnl: float = 0.0

    # Period tracking
    daily_start: datetime = field(default_factory=datetime.utcnow)
    weekly_start: datetime = field(default_factory=datetime.utcnow)
    monthly_start: datetime = field(default_factory=datetime.utcnow)

    # Halt state
    is_halted: bool = False
    halt_condition: HaltCondition = HaltCondition.NONE
    halt_reason: Optional[str] = None
    halt_time: Optional[datetime] = None

    # Loss tracking
    last_loss_time: Optional[datetime] = None
    consecutive_losses: int = 0

    # Trade counts
    daily_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0


@dataclass
class TradeValidation:
    """Result of trade validation."""
    is_valid: bool
    reason: str
    adjusted_size: Optional[float] = None


class RiskManager:
    """
    Manages trading risk limits and halt conditions.

    Responsibilities:
    - Track P&L at daily, weekly, monthly levels
    - Enforce drawdown limits
    - Implement cooldown periods after losses
    - Handle trading halts and recovery
    """

    def __init__(
        self,
        initial_bankroll: float,
        config: Optional[Dict] = None,
    ):
        self.initial_bankroll = initial_bankroll
        self.config = config or RISK_LIMITS
        self.state = RiskState()

        # Initialize period starts
        now = datetime.utcnow()
        self.state.daily_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        self.state.weekly_start = now - timedelta(days=now.weekday())
        self.state.weekly_start = self.state.weekly_start.replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        self.state.monthly_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    def update_pnl(
        self,
        realized_pnl: float,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """
        Update P&L trackers when a position closes.

        Args:
            realized_pnl: The realized P&L from the closed position
            timestamp: When the P&L was realized (default: now)
        """
        timestamp = timestamp or datetime.utcnow()

        # Check for period rollovers first
        self._check_period_rollovers(timestamp)

        # Update P&L
        self.state.daily_pnl += realized_pnl
        self.state.weekly_pnl += realized_pnl
        self.state.monthly_pnl += realized_pnl
        self.state.total_pnl += realized_pnl

        # Update trade counts
        self.state.daily_trades += 1
        if realized_pnl >= 0:
            self.state.winning_trades += 1
            self.state.consecutive_losses = 0
        else:
            self.state.losing_trades += 1
            self.state.last_loss_time = timestamp
            self.state.consecutive_losses += 1

        # Check halt conditions
        self._check_halt_conditions()

        logger.info(
            f"P&L updated: {realized_pnl:+.2f} | "
            f"Daily: {self.state.daily_pnl:+.2f} | "
            f"Weekly: {self.state.weekly_pnl:+.2f} | "
            f"Monthly: {self.state.monthly_pnl:+.2f}"
        )

    def _check_period_rollovers(self, timestamp: datetime) -> None:
        """Check and handle period rollovers."""
        # Daily rollover
        today_start = timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
        if today_start > self.state.daily_start:
            logger.info(f"Daily rollover: resetting daily P&L from {self.state.daily_pnl:.2f}")
            self.state.daily_pnl = 0.0
            self.state.daily_trades = 0
            self.state.daily_start = today_start

            # Clear daily halt if applicable
            if self.state.halt_condition == HaltCondition.DAILY_LOSS:
                self._clear_halt("Daily period rollover")

        # Weekly rollover (Monday)
        week_start = timestamp - timedelta(days=timestamp.weekday())
        week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
        if week_start > self.state.weekly_start:
            logger.info(f"Weekly rollover: resetting weekly P&L from {self.state.weekly_pnl:.2f}")
            self.state.weekly_pnl = 0.0
            self.state.weekly_start = week_start

            # Clear weekly halt if applicable
            if self.state.halt_condition == HaltCondition.WEEKLY_LOSS:
                self._clear_halt("Weekly period rollover")

        # Monthly rollover
        month_start = timestamp.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if month_start > self.state.monthly_start:
            logger.info(f"Monthly rollover: resetting monthly P&L from {self.state.monthly_pnl:.2f}")
            self.state.monthly_pnl = 0.0
            self.state.monthly_start = month_start

            # Monthly halts require manual clearing
            if self.state.halt_condition == HaltCondition.MONTHLY_LOSS:
                logger.warning("Monthly halt still active - requires manual clear")

    def _check_halt_conditions(self) -> None:
        """Check if any halt condition is triggered."""
        if self.state.is_halted:
            return  # Already halted

        max_daily = self.initial_bankroll * self.config["max_daily_loss_pct"]
        max_weekly = self.initial_bankroll * self.config["max_weekly_loss_pct"]
        max_monthly = self.initial_bankroll * self.config["max_monthly_loss_pct"]

        if self.state.daily_pnl <= -max_daily:
            self._trigger_halt(
                HaltCondition.DAILY_LOSS,
                f"Daily loss limit breached: {self.state.daily_pnl:.2f} (limit: -{max_daily:.2f})"
            )

        elif self.state.weekly_pnl <= -max_weekly:
            self._trigger_halt(
                HaltCondition.WEEKLY_LOSS,
                f"Weekly loss limit breached: {self.state.weekly_pnl:.2f} (limit: -{max_weekly:.2f})"
            )

        elif self.state.monthly_pnl <= -max_monthly:
            self._trigger_halt(
                HaltCondition.MONTHLY_LOSS,
                f"Monthly loss limit breached: {self.state.monthly_pnl:.2f} (limit: -{max_monthly:.2f})"
            )

    def _trigger_halt(self, condition: HaltCondition, reason: str) -> None:
        """Trigger a trading halt."""
        self.state.is_halted = True
        self.state.halt_condition = condition
        self.state.halt_reason = reason
        self.state.halt_time = datetime.utcnow()

        logger.warning(f"TRADING HALTED: {reason}")

    def _clear_halt(self, reason: str) -> None:
        """Clear a trading halt."""
        logger.info(f"Clearing halt: {reason}")
        self.state.is_halted = False
        self.state.halt_condition = HaltCondition.NONE
        self.state.halt_reason = None
        self.state.halt_time = None

    def can_trade(self, current_time: Optional[datetime] = None) -> Tuple[bool, str]:
        """
        Check if trading is currently allowed.

        Args:
            current_time: Current timestamp (default: now)

        Returns:
            Tuple of (can_trade: bool, reason: str)
        """
        current_time = current_time or datetime.utcnow()

        # Check period rollovers (may clear halts)
        self._check_period_rollovers(current_time)

        if self.state.is_halted:
            return False, self.state.halt_reason or "Trading halted"

        # Check cooldown after loss
        cooldown_minutes = self.config.get("cooldown_after_loss_minutes", 0)
        if cooldown_minutes > 0 and self.state.last_loss_time:
            cooldown_end = self.state.last_loss_time + timedelta(minutes=cooldown_minutes)
            if current_time < cooldown_end:
                remaining = (cooldown_end - current_time).total_seconds() / 60
                return False, f"In cooldown period ({remaining:.1f} min remaining)"

        return True, "Trading allowed"

    def validate_trade(
        self,
        size: float,
        resolution_date: datetime,
        current_time: Optional[datetime] = None,
    ) -> TradeValidation:
        """
        Validate a specific trade against risk rules.

        Args:
            size: Proposed trade size
            resolution_date: When the market resolves
            current_time: Current timestamp

        Returns:
            TradeValidation result
        """
        current_time = current_time or datetime.utcnow()

        # Check if trading is allowed
        can_trade, reason = self.can_trade(current_time)
        if not can_trade:
            return TradeValidation(is_valid=False, reason=reason)

        # Check size limits
        max_trade = self.config["max_single_trade"]
        min_trade = self.config["min_single_trade"]

        if size > max_trade:
            return TradeValidation(
                is_valid=False,
                reason=f"Trade size ${size:.2f} exceeds max ${max_trade:.2f}",
                adjusted_size=max_trade,
            )

        if size < min_trade:
            return TradeValidation(
                is_valid=False,
                reason=f"Trade size ${size:.2f} below min ${min_trade:.2f}",
            )

        # Check time to resolution
        hours_to_resolution = (resolution_date - current_time).total_seconds() / 3600
        min_hours = self.config["min_hours_before_resolution"]

        if hours_to_resolution < min_hours:
            return TradeValidation(
                is_valid=False,
                reason=f"Only {hours_to_resolution:.1f} hours to resolution (min: {min_hours})",
            )

        return TradeValidation(is_valid=True, reason="Trade validated")

    def trigger_manual_halt(self, reason: str = "Manual halt") -> None:
        """Manually halt trading."""
        self._trigger_halt(HaltCondition.MANUAL, reason)

    def clear_halt(self, force: bool = False) -> Tuple[bool, str]:
        """
        Attempt to clear a trading halt.

        Args:
            force: Force clear even monthly halts

        Returns:
            Tuple of (success: bool, message: str)
        """
        if not self.state.is_halted:
            return True, "No halt to clear"

        # Monthly halts require force or manual intervention
        if self.state.halt_condition == HaltCondition.MONTHLY_LOSS and not force:
            return False, "Monthly halt requires manual review (use force=True to override)"

        self._clear_halt("Manual clear")
        return True, "Halt cleared"

    def reset_daily_pnl(self) -> None:
        """Manually reset daily P&L counter."""
        self.state.daily_pnl = 0.0
        self.state.daily_trades = 0
        self.state.daily_start = datetime.utcnow().replace(
            hour=0, minute=0, second=0, microsecond=0
        )

        # Clear daily halt if applicable
        if self.state.halt_condition == HaltCondition.DAILY_LOSS:
            self._clear_halt("Manual daily reset")

        logger.info("Daily P&L manually reset")

    def get_risk_metrics(self) -> Dict:
        """Get current risk metrics."""
        max_daily = self.initial_bankroll * self.config["max_daily_loss_pct"]
        max_weekly = self.initial_bankroll * self.config["max_weekly_loss_pct"]
        max_monthly = self.initial_bankroll * self.config["max_monthly_loss_pct"]

        return {
            "daily_pnl": self.state.daily_pnl,
            "daily_limit": -max_daily,
            "daily_buffer": max_daily + self.state.daily_pnl,
            "daily_pct_used": abs(self.state.daily_pnl) / max_daily if max_daily > 0 else 0,

            "weekly_pnl": self.state.weekly_pnl,
            "weekly_limit": -max_weekly,
            "weekly_buffer": max_weekly + self.state.weekly_pnl,
            "weekly_pct_used": abs(self.state.weekly_pnl) / max_weekly if max_weekly > 0 else 0,

            "monthly_pnl": self.state.monthly_pnl,
            "monthly_limit": -max_monthly,
            "monthly_buffer": max_monthly + self.state.monthly_pnl,
            "monthly_pct_used": abs(self.state.monthly_pnl) / max_monthly if max_monthly > 0 else 0,

            "total_pnl": self.state.total_pnl,
            "is_halted": self.state.is_halted,
            "halt_condition": self.state.halt_condition.value,
            "halt_reason": self.state.halt_reason,

            "daily_trades": self.state.daily_trades,
            "winning_trades": self.state.winning_trades,
            "losing_trades": self.state.losing_trades,
            "consecutive_losses": self.state.consecutive_losses,
            "win_rate": (
                self.state.winning_trades / (self.state.winning_trades + self.state.losing_trades)
                if (self.state.winning_trades + self.state.losing_trades) > 0
                else 0
            ),
        }

    def get_halt_conditions_status(self) -> Dict[str, Dict]:
        """Get status of all halt conditions."""
        max_daily = self.initial_bankroll * self.config["max_daily_loss_pct"]
        max_weekly = self.initial_bankroll * self.config["max_weekly_loss_pct"]
        max_monthly = self.initial_bankroll * self.config["max_monthly_loss_pct"]

        return {
            "daily_loss_limit": {
                "triggered": self.state.halt_condition == HaltCondition.DAILY_LOSS,
                "current": self.state.daily_pnl,
                "limit": -max_daily,
                "message": "Daily loss limit" if self.state.daily_pnl <= -max_daily else "Not triggered",
            },
            "weekly_loss_limit": {
                "triggered": self.state.halt_condition == HaltCondition.WEEKLY_LOSS,
                "current": self.state.weekly_pnl,
                "limit": -max_weekly,
                "message": "Weekly loss limit" if self.state.weekly_pnl <= -max_weekly else "Not triggered",
            },
            "monthly_loss_limit": {
                "triggered": self.state.halt_condition == HaltCondition.MONTHLY_LOSS,
                "current": self.state.monthly_pnl,
                "limit": -max_monthly,
                "message": "Monthly loss limit" if self.state.monthly_pnl <= -max_monthly else "Not triggered",
            },
            "manual_halt": {
                "triggered": self.state.halt_condition == HaltCondition.MANUAL,
                "message": self.state.halt_reason if self.state.halt_condition == HaltCondition.MANUAL else "Not triggered",
            },
            "system_operational": {
                "triggered": self.state.halt_condition == HaltCondition.SYSTEM_ERROR,
                "message": "System error" if self.state.halt_condition == HaltCondition.SYSTEM_ERROR else "All services running",
            },
        }
