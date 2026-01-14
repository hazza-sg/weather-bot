"""Diversification filter for portfolio risk management."""
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Set

from app.config import DIVERSIFICATION_CONFIG, GEOGRAPHIC_CLUSTERS

logger = logging.getLogger(__name__)


@dataclass
class Position:
    """Represents an open position."""
    position_id: str
    market_id: str
    location: str
    cluster: Optional[str]
    size: float
    resolution_date: datetime
    side: str


@dataclass
class PortfolioState:
    """Current state of the portfolio for diversification checks."""

    total_exposure: float = 0.0
    positions: List[Position] = field(default_factory=list)
    cluster_exposure: Dict[str, float] = field(default_factory=dict)
    resolution_date_exposure: Dict[str, float] = field(default_factory=dict)

    def add_position(self, position: Position) -> None:
        """Add a position to the portfolio state."""
        self.positions.append(position)
        self.total_exposure += position.size

        # Update cluster exposure
        if position.cluster:
            self.cluster_exposure[position.cluster] = (
                self.cluster_exposure.get(position.cluster, 0) + position.size
            )

        # Update resolution date exposure
        date_key = position.resolution_date.strftime("%Y-%m-%d")
        self.resolution_date_exposure[date_key] = (
            self.resolution_date_exposure.get(date_key, 0) + position.size
        )

    def get_unique_clusters(self) -> Set[str]:
        """Get set of unique clusters in portfolio."""
        return set(
            p.cluster for p in self.positions
            if p.cluster is not None
        )


@dataclass
class TradeCandidate:
    """A potential trade to evaluate for diversification."""
    market_id: str
    location: str
    cluster: Optional[str]
    proposed_size: float
    resolution_date: datetime
    side: str


@dataclass
class DiversificationResult:
    """Result of diversification check."""

    allowed: bool
    reason: str
    max_allowed_size: float
    constraints_applied: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "max_allowed_size": self.max_allowed_size,
            "constraints_applied": self.constraints_applied,
        }


class DiversificationFilter:
    """
    Filter trades based on diversification rules.

    Enforces:
    - Maximum total exposure
    - Maximum exposure per geographic cluster
    - Maximum exposure to same-day resolutions
    - Minimum cluster count for high deployment
    """

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or DIVERSIFICATION_CONFIG
        self.clusters = GEOGRAPHIC_CLUSTERS

    def get_cluster_for_location(self, location: str) -> Optional[str]:
        """Get the geographic cluster for a location."""
        for cluster_name, cluster_data in self.clusters.items():
            if location in cluster_data.get("cities", []):
                return cluster_name
        return None

    def check_diversification_limits(
        self,
        trade: TradeCandidate,
        portfolio: PortfolioState,
        bankroll: float,
    ) -> DiversificationResult:
        """
        Check if adding a trade would violate diversification limits.

        Args:
            trade: The proposed trade
            portfolio: Current portfolio state
            bankroll: Total bankroll

        Returns:
            DiversificationResult with allowed status and constraints
        """
        constraints_applied = []
        max_allowed = trade.proposed_size

        # Calculate limits
        max_total = bankroll * self.config["max_total_exposure_pct"]

        # Check 1: Total exposure limit
        if portfolio.total_exposure >= max_total:
            return DiversificationResult(
                allowed=False,
                reason="Maximum total exposure reached",
                max_allowed_size=0,
                constraints_applied=["total_exposure"],
            )

        remaining_capacity = max_total - portfolio.total_exposure
        if max_allowed > remaining_capacity:
            max_allowed = remaining_capacity
            constraints_applied.append("total_exposure")

        # Check 2: Geographic cluster limit
        cluster = trade.cluster or self.get_cluster_for_location(trade.location)

        if cluster and portfolio.total_exposure > 0:
            cluster_limit = portfolio.total_exposure * self.config["max_cluster_exposure_pct"]
            current_cluster_exposure = portfolio.cluster_exposure.get(cluster, 0)
            cluster_remaining = cluster_limit - current_cluster_exposure

            if cluster_remaining <= 0:
                return DiversificationResult(
                    allowed=False,
                    reason=f"Cluster {cluster} at maximum exposure",
                    max_allowed_size=0,
                    constraints_applied=["cluster_limit"],
                )

            if max_allowed > cluster_remaining:
                max_allowed = cluster_remaining
                constraints_applied.append("cluster_limit")

        # Check 3: Same-day resolution limit
        resolution_date = trade.resolution_date.strftime("%Y-%m-%d")

        if portfolio.total_exposure > 0:
            same_day_limit = portfolio.total_exposure * self.config["max_same_day_resolution_pct"]
            current_same_day = portfolio.resolution_date_exposure.get(resolution_date, 0)
            same_day_remaining = same_day_limit - current_same_day

            if same_day_remaining <= 0:
                return DiversificationResult(
                    allowed=False,
                    reason=f"Same-day resolution limit reached for {resolution_date}",
                    max_allowed_size=0,
                    constraints_applied=["same_day_limit"],
                )

            if max_allowed > same_day_remaining:
                max_allowed = same_day_remaining
                constraints_applied.append("same_day_limit")

        # Check 4: Minimum cluster count for deployment levels
        result = self._check_cluster_diversity(
            trade=trade,
            portfolio=portfolio,
            max_total=max_total,
            current_max_allowed=max_allowed,
        )

        if result is not None:
            if not result.allowed:
                return result
            if result.max_allowed_size < max_allowed:
                max_allowed = result.max_allowed_size
                constraints_applied.extend(result.constraints_applied)

        # Check minimum size
        if max_allowed < 1.0:  # Minimum position size
            return DiversificationResult(
                allowed=False,
                reason="Remaining capacity below minimum position size",
                max_allowed_size=0,
                constraints_applied=constraints_applied,
            )

        return DiversificationResult(
            allowed=True,
            reason="Diversification check passed",
            max_allowed_size=max_allowed,
            constraints_applied=constraints_applied,
        )

    def _check_cluster_diversity(
        self,
        trade: TradeCandidate,
        portfolio: PortfolioState,
        max_total: float,
        current_max_allowed: float,
    ) -> Optional[DiversificationResult]:
        """Check minimum cluster diversity requirements."""

        current_clusters = portfolio.get_unique_clusters()
        n_clusters = len(current_clusters)

        # Check if trade adds a new cluster
        trade_cluster = trade.cluster or self.get_cluster_for_location(trade.location)
        adds_new_cluster = trade_cluster and trade_cluster not in current_clusters

        # New exposure after trade
        new_exposure = portfolio.total_exposure + current_max_allowed
        new_exposure_pct = new_exposure / max_total if max_total > 0 else 0

        # Check 50% deployment requirement
        min_for_50 = self.config["min_positions_for_50_pct"]
        if new_exposure_pct > 0.50 and n_clusters < min_for_50:
            if not adds_new_cluster:
                # Cap at 50% until more clusters added
                cap = max_total * 0.50 - portfolio.total_exposure
                if cap <= 0:
                    return DiversificationResult(
                        allowed=False,
                        reason=f"Need positions in {min_for_50} clusters before exceeding 50% deployment",
                        max_allowed_size=0,
                        constraints_applied=["cluster_diversity_50"],
                    )
                return DiversificationResult(
                    allowed=True,
                    reason="Capped at 50% deployment",
                    max_allowed_size=cap,
                    constraints_applied=["cluster_diversity_50"],
                )

        # Check 75% deployment requirement
        min_for_75 = self.config["min_positions_for_75_pct"]
        if new_exposure_pct > 0.75 and n_clusters < min_for_75:
            # Cap at 75% until more clusters added
            cap = max_total * 0.75 - portfolio.total_exposure
            if cap <= 0:
                return DiversificationResult(
                    allowed=False,
                    reason=f"Need positions in {min_for_75} clusters for full deployment",
                    max_allowed_size=0,
                    constraints_applied=["cluster_diversity_75"],
                )
            return DiversificationResult(
                allowed=True,
                reason="Capped at 75% deployment",
                max_allowed_size=cap,
                constraints_applied=["cluster_diversity_75"],
            )

        return None

    def get_exposure_summary(
        self,
        portfolio: PortfolioState,
        bankroll: float,
    ) -> Dict:
        """Get a summary of current exposure vs limits."""
        max_total = bankroll * self.config["max_total_exposure_pct"]

        summary = {
            "total_exposure": portfolio.total_exposure,
            "max_exposure": max_total,
            "exposure_pct": portfolio.total_exposure / max_total if max_total > 0 else 0,
            "cluster_exposure": {},
            "same_day_exposure": {},
            "unique_clusters": len(portfolio.get_unique_clusters()),
        }

        # Cluster breakdown
        for cluster, exposure in portfolio.cluster_exposure.items():
            limit = portfolio.total_exposure * self.config["max_cluster_exposure_pct"]
            summary["cluster_exposure"][cluster] = {
                "current": exposure,
                "limit": limit,
                "pct": exposure / limit if limit > 0 else 0,
            }

        # Same-day breakdown
        for date, exposure in portfolio.resolution_date_exposure.items():
            limit = portfolio.total_exposure * self.config["max_same_day_resolution_pct"]
            summary["same_day_exposure"][date] = {
                "current": exposure,
                "limit": limit,
                "pct": exposure / limit if limit > 0 else 0,
            }

        return summary
