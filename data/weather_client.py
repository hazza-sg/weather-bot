"""Open-Meteo Ensemble API client for weather forecast data."""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
import statistics

import httpx

logger = logging.getLogger(__name__)

# Available ensemble models
ENSEMBLE_MODELS = {
    "gfs_seamless": {"members": 31, "update_freq": 4, "horizon_days": 16},
    "ecmwf_ifs025": {"members": 51, "update_freq": 2, "horizon_days": 15},
    "icon_seamless": {"members": 40, "update_freq": 4, "horizon_days": 7},
    "gem_global_ensemble": {"members": 21, "update_freq": 2, "horizon_days": 16},
}


@dataclass
class ForecastData:
    """Container for ensemble forecast data."""

    latitude: float
    longitude: float
    target_date: datetime
    variable: str
    unit: str
    models: Dict[str, Dict[str, Any]]  # model_name -> {values, probability, stats}
    aggregated_probability: Optional[float] = None
    model_agreement: Optional[float] = None


class OpenMeteoClient:
    """Client for Open-Meteo Ensemble API."""

    BASE_URL = "https://api.open-meteo.com/v1/ensemble"
    HISTORICAL_URL = "https://archive-api.open-meteo.com/v1/archive"

    def __init__(self, timeout: float = 30.0):
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create async HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def get_ensemble_forecast(
        self,
        latitude: float,
        longitude: float,
        target_date: datetime,
        variable: str = "temperature_2m",
        models: Optional[List[str]] = None,
    ) -> ForecastData:
        """
        Fetch ensemble forecast for a specific location and date.

        Args:
            latitude: Location latitude
            longitude: Location longitude
            target_date: Target forecast date
            variable: Weather variable (temperature_2m, precipitation, etc.)
            models: List of models to use (default: all available)

        Returns:
            ForecastData with ensemble values and probabilities
        """
        if models is None:
            models = ["gfs_seamless", "ecmwf_ifs025", "icon_seamless"]

        client = await self._get_client()

        # Calculate forecast days needed
        days_ahead = (target_date.date() - datetime.utcnow().date()).days
        forecast_days = max(1, min(days_ahead + 1, 16))

        params = {
            "latitude": latitude,
            "longitude": longitude,
            "hourly": variable,
            "models": ",".join(models),
            "forecast_days": forecast_days,
        }

        try:
            response = await client.get(self.BASE_URL, params=params)
            response.raise_for_status()
            data = response.json()

            return self._parse_ensemble_response(
                data, target_date, variable, models
            )

        except httpx.HTTPError as e:
            logger.error(f"Error fetching ensemble forecast: {e}")
            raise

    def _parse_ensemble_response(
        self,
        data: Dict[str, Any],
        target_date: datetime,
        variable: str,
        models: List[str],
    ) -> ForecastData:
        """Parse Open-Meteo ensemble response into ForecastData."""
        hourly = data.get("hourly", {})
        times = hourly.get("time", [])

        # Find indices for target date
        target_date_str = target_date.strftime("%Y-%m-%d")
        target_indices = [
            i for i, t in enumerate(times) if t.startswith(target_date_str)
        ]

        model_data = {}

        for model in models:
            ensemble_values = []

            # Collect all ensemble member values for the target date
            for key, values in hourly.items():
                if key.startswith(f"{variable}_{model}_member"):
                    if target_indices:
                        # Get values for target date
                        day_values = [values[i] for i in target_indices if i < len(values)]
                        if day_values:
                            # For temperature, get daily max
                            if "temperature" in variable:
                                ensemble_values.append(max(day_values))
                            else:
                                # For precipitation, sum daily
                                ensemble_values.append(sum(day_values))

            if ensemble_values:
                model_data[model] = {
                    "ensemble_values": ensemble_values,
                    "mean": statistics.mean(ensemble_values),
                    "median": statistics.median(ensemble_values),
                    "std": statistics.stdev(ensemble_values) if len(ensemble_values) > 1 else 0,
                    "min": min(ensemble_values),
                    "max": max(ensemble_values),
                    "count": len(ensemble_values),
                }

        # Determine unit
        unit = "celsius" if "temperature" in variable else "mm"

        return ForecastData(
            latitude=data.get("latitude", 0),
            longitude=data.get("longitude", 0),
            target_date=target_date,
            variable=variable,
            unit=unit,
            models=model_data,
        )

    async def get_daily_max_temperature(
        self,
        latitude: float,
        longitude: float,
        target_date: datetime,
        models: Optional[List[str]] = None,
    ) -> ForecastData:
        """Get ensemble forecast for daily maximum temperature."""
        return await self.get_ensemble_forecast(
            latitude=latitude,
            longitude=longitude,
            target_date=target_date,
            variable="temperature_2m",
            models=models,
        )

    async def get_precipitation_forecast(
        self,
        latitude: float,
        longitude: float,
        target_date: datetime,
        models: Optional[List[str]] = None,
    ) -> ForecastData:
        """Get ensemble forecast for daily precipitation."""
        return await self.get_ensemble_forecast(
            latitude=latitude,
            longitude=longitude,
            target_date=target_date,
            variable="precipitation",
            models=models,
        )


def celsius_to_fahrenheit(celsius: float) -> float:
    """Convert Celsius to Fahrenheit."""
    return celsius * 9 / 5 + 32


def fahrenheit_to_celsius(fahrenheit: float) -> float:
    """Convert Fahrenheit to Celsius."""
    return (fahrenheit - 32) * 5 / 9


def calculate_exceedance_probability(
    ensemble_values: List[float],
    threshold: float,
    comparison: str,
    apply_smoothing: bool = True,
) -> float:
    """
    Calculate probability of threshold exceedance from ensemble members.

    Args:
        ensemble_values: List of forecast values from all ensemble members
        threshold: The threshold value
        comparison: One of ">=", ">", "<=", "<"
        apply_smoothing: Apply Laplace smoothing to avoid 0% or 100%

    Returns:
        Probability between 0 and 1
    """
    if not ensemble_values:
        return 0.5  # Return neutral if no data

    n_members = len(ensemble_values)

    if comparison == ">=":
        n_exceed = sum(1 for v in ensemble_values if v >= threshold)
    elif comparison == ">":
        n_exceed = sum(1 for v in ensemble_values if v > threshold)
    elif comparison == "<=":
        n_exceed = sum(1 for v in ensemble_values if v <= threshold)
    elif comparison == "<":
        n_exceed = sum(1 for v in ensemble_values if v < threshold)
    else:
        raise ValueError(f"Unknown comparison operator: {comparison}")

    if apply_smoothing:
        # Laplace smoothing to avoid 0% or 100% extremes
        return (n_exceed + 1) / (n_members + 2)
    else:
        return n_exceed / n_members


def aggregate_model_probabilities(
    model_probabilities: Dict[str, float],
    model_weights: Optional[Dict[str, float]] = None,
) -> Tuple[float, float]:
    """
    Aggregate probabilities from multiple models.

    Args:
        model_probabilities: Dict mapping model name to probability
        model_weights: Optional weights (default: equal weighting)

    Returns:
        Tuple of (weighted mean probability, model agreement score)
    """
    if not model_probabilities:
        return 0.5, 0.0

    if model_weights is None:
        model_weights = {m: 1.0 for m in model_probabilities}

    # Normalize weights
    total_weight = sum(model_weights.get(m, 1.0) for m in model_probabilities)

    # Weighted mean
    weighted_sum = sum(
        model_probabilities[m] * model_weights.get(m, 1.0)
        for m in model_probabilities
    )
    mean_prob = weighted_sum / total_weight if total_weight > 0 else 0.5

    # Model agreement score (1 - normalized standard deviation)
    probs = list(model_probabilities.values())
    if len(probs) > 1:
        std_dev = statistics.stdev(probs)
        # Normalize: 0 std = 1.0 agreement, 0.5 std = 0 agreement
        agreement = max(0, 1 - 2 * std_dev)
    else:
        agreement = 1.0

    return mean_prob, agreement
