"""Position sizing using fractional Kelly criterion."""
import logging
from dataclasses import dataclass
from typing import Optional, Dict

from app.config import POSITION_SIZING_CONFIG, RISK_LIMITS

logger = logging.getLogger(__name__)


@dataclass
class PositionSize:
    """Result of position sizing calculation."""

    size: float  # Dollar amount to wager
    kelly_fraction_used: float  # Fraction of Kelly applied
    full_kelly_size: float  # What full Kelly would suggest
    max_allowed: float  # Maximum allowed by constraints
    constrained_by: Optional[str]  # What constraint limited the size

    def to_dict(self) -> dict:
        return {
            "size": self.size,
            "kelly_fraction_used": self.kelly_fraction_used,
            "full_kelly_size": self.full_kelly_size,
            "max_allowed": self.max_allowed,
            "constrained_by": self.constrained_by,
        }


class PositionSizer:
    """
    Calculate position sizes using fractional Kelly criterion.

    The Kelly criterion determines the optimal fraction of bankroll to wager:

    f* = (bp - q) / b

    Where:
        f* = fraction of bankroll to wager
        b = decimal odds - 1 (net profit per unit wagered)
        p = probability of winning
        q = probability of losing (1 - p)

    We use fractional Kelly (typically 25%) for more conservative sizing.
    """

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or POSITION_SIZING_CONFIG
        self.risk_config = RISK_LIMITS

    def calculate_kelly_fraction(
        self,
        probability: float,
        odds: float,
    ) -> float:
        """
        Calculate full Kelly fraction.

        Args:
            probability: Probability of winning (0-1)
            odds: Net odds (profit per unit stake if win)

        Returns:
            Kelly fraction (can be negative or > 1)
        """
        if probability <= 0 or probability >= 1:
            return 0

        if odds <= 0:
            return 0

        q = 1 - probability
        b = odds

        kelly = (b * probability - q) / b

        return kelly

    def calculate_position_size(
        self,
        bankroll: float,
        forecast_prob: float,
        market_price: float,
        side: str,
        current_exposure: float = 0,
        max_exposure_pct: Optional[float] = None,
    ) -> PositionSize:
        """
        Calculate position size using fractional Kelly criterion.

        Args:
            bankroll: Total allocated capital
            forecast_prob: Our estimated probability of YES outcome
            market_price: Current YES token price
            side: Which side to bet ("YES" or "NO")
            current_exposure: Current total exposure
            max_exposure_pct: Override max exposure percentage

        Returns:
            PositionSize with calculated size and constraints
        """
        # Get configuration
        kelly_fraction = self.config["kelly_fraction"]
        max_position_pct = self.config["max_position_pct"]
        min_position = self.config["min_position"]
        max_position = self.config["max_position"]

        # Adjust probability and price for side
        if side == "YES":
            prob = forecast_prob
            price = market_price
        else:
            prob = 1 - forecast_prob
            price = 1 - market_price

        # Validate price
        if price <= 0 or price >= 1:
            return PositionSize(
                size=0,
                kelly_fraction_used=kelly_fraction,
                full_kelly_size=0,
                max_allowed=0,
                constrained_by="invalid_price",
            )

        # Calculate net odds
        # If we pay $P for a contract worth $1 if we win:
        # profit = (1-P)/P per dollar risked
        net_odds = (1 - price) / price

        # Calculate full Kelly
        full_kelly = self.calculate_kelly_fraction(prob, net_odds)

        # If Kelly is negative or zero, don't bet
        if full_kelly <= 0:
            return PositionSize(
                size=0,
                kelly_fraction_used=kelly_fraction,
                full_kelly_size=0,
                max_allowed=max_position,
                constrained_by="negative_kelly",
            )

        # Apply Kelly fraction
        position_pct = full_kelly * kelly_fraction

        # Apply maximum position percentage constraint
        position_pct = min(position_pct, max_position_pct)

        # Calculate dollar amount
        position = bankroll * position_pct
        full_kelly_position = bankroll * full_kelly

        # Track what constrains us
        constrained_by = None

        # Apply min/max constraints
        if position < min_position:
            if full_kelly_position >= min_position:
                # Kelly suggests enough, but fraction too small
                position = min_position
                constrained_by = "min_position"
            else:
                # Not enough edge to justify minimum
                return PositionSize(
                    size=0,
                    kelly_fraction_used=kelly_fraction,
                    full_kelly_size=full_kelly_position,
                    max_allowed=max_position,
                    constrained_by="below_minimum",
                )

        if position > max_position:
            position = max_position
            constrained_by = "max_position"

        # Check exposure limits
        max_total_exposure = bankroll * (max_exposure_pct or 0.75)
        remaining_exposure = max_total_exposure - current_exposure

        if remaining_exposure <= 0:
            return PositionSize(
                size=0,
                kelly_fraction_used=kelly_fraction,
                full_kelly_size=full_kelly_position,
                max_allowed=0,
                constrained_by="exposure_limit",
            )

        if position > remaining_exposure:
            position = remaining_exposure
            constrained_by = "exposure_limit"

        # Round to 2 decimal places
        position = round(position, 2)

        return PositionSize(
            size=position,
            kelly_fraction_used=kelly_fraction,
            full_kelly_size=round(full_kelly_position, 2),
            max_allowed=min(max_position, remaining_exposure),
            constrained_by=constrained_by,
        )

    def calculate_for_edge(
        self,
        bankroll: float,
        edge_calculation,  # EdgeCalculation
        current_exposure: float = 0,
    ) -> PositionSize:
        """
        Calculate position size from an EdgeCalculation.

        Args:
            bankroll: Total allocated capital
            edge_calculation: EdgeCalculation object
            current_exposure: Current total exposure

        Returns:
            PositionSize
        """
        if not edge_calculation.recommended_side:
            return PositionSize(
                size=0,
                kelly_fraction_used=self.config["kelly_fraction"],
                full_kelly_size=0,
                max_allowed=self.config["max_position"],
                constrained_by="no_edge",
            )

        return self.calculate_position_size(
            bankroll=bankroll,
            forecast_prob=edge_calculation.forecast_probability,
            market_price=edge_calculation.market_probability,
            side=edge_calculation.recommended_side,
            current_exposure=current_exposure,
        )


def calculate_optimal_kelly(
    win_rate: float,
    avg_win: float,
    avg_loss: float,
) -> float:
    """
    Calculate Kelly fraction from historical win rate and average win/loss.

    This is useful for calibrating the Kelly fraction based on past performance.

    Args:
        win_rate: Historical win rate (0-1)
        avg_win: Average profit on winning trades
        avg_loss: Average loss on losing trades (positive number)

    Returns:
        Optimal Kelly fraction
    """
    if avg_loss <= 0 or win_rate <= 0 or win_rate >= 1:
        return 0

    # W = avg_win / avg_loss (win/loss ratio)
    # p = win_rate
    # Kelly = p - (1-p)/W = p - q/W

    w = avg_win / avg_loss
    q = 1 - win_rate

    kelly = win_rate - (q / w)

    return max(0, kelly)
