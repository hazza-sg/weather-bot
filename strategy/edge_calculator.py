"""Edge calculation module for comparing forecast probabilities to market prices."""
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from enum import Enum

from data.weather_client import (
    calculate_exceedance_probability,
    aggregate_model_probabilities,
    celsius_to_fahrenheit,
)
from app.config import STRATEGY_CONFIG

logger = logging.getLogger(__name__)


class ConfidenceLevel(Enum):
    """Confidence level for trading signals."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


@dataclass
class EdgeCalculation:
    """Result of edge calculation."""

    forecast_probability: float
    market_probability: float
    edge: float  # Percentage edge (positive = favorable)
    expected_value: float  # EV per dollar wagered
    model_agreement: float  # 0-1 confidence score
    recommended_side: Optional[str]  # "YES" or "NO" or None
    confidence_level: ConfidenceLevel

    # Detailed breakdown
    model_probabilities: Dict[str, float]  # Per-model probabilities
    edge_yes: float  # Edge on YES side
    edge_no: float  # Edge on NO side

    def is_tradeable(self) -> bool:
        """Check if this edge meets minimum criteria."""
        return (
            self.recommended_side is not None
            and self.edge >= STRATEGY_CONFIG["min_edge"]
            and self.edge <= STRATEGY_CONFIG["max_edge"]
            and self.model_agreement >= STRATEGY_CONFIG["min_model_agreement"]
        )

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "forecast_probability": self.forecast_probability,
            "market_probability": self.market_probability,
            "edge": self.edge,
            "expected_value": self.expected_value,
            "model_agreement": self.model_agreement,
            "recommended_side": self.recommended_side,
            "confidence_level": self.confidence_level.value,
            "model_probabilities": self.model_probabilities,
            "edge_yes": self.edge_yes,
            "edge_no": self.edge_no,
            "is_tradeable": self.is_tradeable(),
        }


class EdgeCalculator:
    """
    Calculate trading edge by comparing forecast probabilities to market prices.

    Edge = (Forecast Probability / Market Probability) - 1

    Positive edge on YES: forecast_prob > market_price (buy YES)
    Positive edge on NO: forecast_prob < market_price (buy NO)
    """

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or STRATEGY_CONFIG

    def calculate_forecast_probability(
        self,
        ensemble_data: Dict[str, Dict],
        threshold: float,
        comparison: str,
        unit: str = "fahrenheit",
        model_weights: Optional[Dict[str, float]] = None,
    ) -> Tuple[float, float, Dict[str, float]]:
        """
        Calculate aggregated forecast probability from ensemble data.

        Args:
            ensemble_data: Dict of model_name -> {ensemble_values, mean, std, ...}
            threshold: The threshold value for comparison
            comparison: Comparison operator (>=, >, <=, <)
            unit: Unit of threshold (fahrenheit, celsius, mm, inches)
            model_weights: Optional weights for each model

        Returns:
            Tuple of (aggregated_probability, model_agreement, per_model_probs)
        """
        model_probabilities = {}

        for model_name, model_data in ensemble_data.items():
            ensemble_values = model_data.get("ensemble_values", [])

            if not ensemble_values:
                continue

            # Convert threshold to match ensemble units if needed
            adjusted_threshold = threshold
            if unit == "fahrenheit" and "temperature" in model_name.lower():
                # Open-Meteo returns Celsius, convert threshold
                adjusted_threshold = (threshold - 32) * 5 / 9

            # Calculate exceedance probability for this model
            prob = calculate_exceedance_probability(
                ensemble_values=ensemble_values,
                threshold=adjusted_threshold,
                comparison=comparison,
                apply_smoothing=True,
            )

            model_probabilities[model_name] = prob

        if not model_probabilities:
            return 0.5, 0.0, {}

        # Aggregate across models
        aggregated_prob, agreement = aggregate_model_probabilities(
            model_probabilities=model_probabilities,
            model_weights=model_weights,
        )

        return aggregated_prob, agreement, model_probabilities

    def calculate_edge(
        self,
        forecast_prob: float,
        market_price: float,
        model_agreement: float,
        model_probabilities: Optional[Dict[str, float]] = None,
    ) -> EdgeCalculation:
        """
        Calculate trading edge and expected value.

        Args:
            forecast_prob: Our estimated probability of YES outcome
            market_price: Current YES token price (0-1)
            model_agreement: Model consensus score (0-1)
            model_probabilities: Optional per-model breakdown

        Returns:
            EdgeCalculation with full analysis
        """
        # Ensure valid inputs
        market_price = max(0.01, min(0.99, market_price))
        forecast_prob = max(0.01, min(0.99, forecast_prob))

        # Calculate edge on YES side
        # Edge = (true_prob / market_prob) - 1
        edge_yes = (forecast_prob / market_price) - 1

        # Calculate edge on NO side
        no_market_price = 1 - market_price
        no_forecast_prob = 1 - forecast_prob
        edge_no = (no_forecast_prob / no_market_price) - 1

        # Determine recommended side and edge
        if edge_yes > edge_no and edge_yes > 0:
            recommended_side = "YES"
            edge = edge_yes

            # Expected value per $1 wagered
            # EV = P(win) * profit_if_win - P(lose) * stake
            # For buying YES at price P: profit_if_win = (1-P)/P per dollar of stake
            decimal_odds = 1 / market_price
            ev = forecast_prob * decimal_odds - 1

        elif edge_no > 0:
            recommended_side = "NO"
            edge = edge_no

            decimal_odds = 1 / no_market_price
            ev = no_forecast_prob * decimal_odds - 1
        else:
            recommended_side = None
            edge = max(edge_yes, edge_no)
            ev = 0

        # Determine confidence level
        confidence = self._calculate_confidence(edge, model_agreement)

        return EdgeCalculation(
            forecast_probability=forecast_prob,
            market_probability=market_price,
            edge=edge,
            expected_value=ev,
            model_agreement=model_agreement,
            recommended_side=recommended_side,
            confidence_level=confidence,
            model_probabilities=model_probabilities or {},
            edge_yes=edge_yes,
            edge_no=edge_no,
        )

    def _calculate_confidence(
        self,
        edge: float,
        model_agreement: float,
    ) -> ConfidenceLevel:
        """Determine confidence level based on edge and model agreement."""
        if model_agreement >= 0.8 and edge >= 0.15:
            return ConfidenceLevel.HIGH
        elif model_agreement >= 0.6 and edge >= 0.08:
            return ConfidenceLevel.MEDIUM
        else:
            return ConfidenceLevel.LOW

    def calculate_from_forecast_data(
        self,
        forecast_data,  # ForecastData from weather_client
        threshold: float,
        comparison: str,
        market_price: float,
        unit: str = "fahrenheit",
    ) -> EdgeCalculation:
        """
        Convenience method to calculate edge directly from ForecastData.

        Args:
            forecast_data: ForecastData object from weather client
            threshold: Threshold value for comparison
            comparison: Comparison operator
            market_price: Current market price for YES
            unit: Unit of threshold

        Returns:
            EdgeCalculation
        """
        # Extract ensemble data from forecast
        ensemble_data = forecast_data.models

        # Calculate forecast probability
        forecast_prob, agreement, model_probs = self.calculate_forecast_probability(
            ensemble_data=ensemble_data,
            threshold=threshold,
            comparison=comparison,
            unit=unit,
        )

        # Calculate edge
        return self.calculate_edge(
            forecast_prob=forecast_prob,
            market_price=market_price,
            model_agreement=agreement,
            model_probabilities=model_probs,
        )


def calculate_bracket_probability(
    ensemble_values: List[float],
    lower_bound: float,
    upper_bound: float,
    inclusive_lower: bool = True,
    inclusive_upper: bool = False,
) -> float:
    """
    Calculate probability of value falling within a bracket.

    Standard bracket convention: [lower, upper) - inclusive lower, exclusive upper

    Args:
        ensemble_values: List of ensemble member values
        lower_bound: Lower bound of bracket
        upper_bound: Upper bound of bracket
        inclusive_lower: Include lower bound
        inclusive_upper: Include upper bound

    Returns:
        Probability (0-1) with Laplace smoothing
    """
    if not ensemble_values:
        return 0.5

    n_members = len(ensemble_values)

    if inclusive_lower and inclusive_upper:
        n_in_bracket = sum(1 for v in ensemble_values if lower_bound <= v <= upper_bound)
    elif inclusive_lower and not inclusive_upper:
        n_in_bracket = sum(1 for v in ensemble_values if lower_bound <= v < upper_bound)
    elif not inclusive_lower and inclusive_upper:
        n_in_bracket = sum(1 for v in ensemble_values if lower_bound < v <= upper_bound)
    else:
        n_in_bracket = sum(1 for v in ensemble_values if lower_bound < v < upper_bound)

    # Laplace smoothing
    return (n_in_bracket + 1) / (n_members + 2)
