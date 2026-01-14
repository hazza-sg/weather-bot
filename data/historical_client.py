"""Historical climate data client for baseline calculations."""
import logging
from datetime import datetime, date
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import statistics

import httpx

logger = logging.getLogger(__name__)


@dataclass
class ClimatologyData:
    """Historical climatology statistics for a location and date."""

    latitude: float
    longitude: float
    target_day: int  # Day of year (1-366)
    target_month: int
    target_date: int

    # Temperature stats (Celsius)
    temp_max_mean: float
    temp_max_std: float
    temp_max_p10: float
    temp_max_p90: float
    temp_min_mean: float
    temp_min_std: float

    # Precipitation stats
    precip_mean: float
    precip_days_pct: float  # Percentage of days with measurable precip

    # Sample size
    years_of_data: int


class HistoricalClient:
    """Client for Open-Meteo Historical API."""

    BASE_URL = "https://archive-api.open-meteo.com/v1/archive"

    def __init__(self, timeout: float = 60.0):
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
        self._cache: Dict[str, ClimatologyData] = {}

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create async HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    def _cache_key(self, lat: float, lon: float, month: int, day: int) -> str:
        """Generate cache key for climatology data."""
        return f"{lat:.2f}_{lon:.2f}_{month}_{day}"

    async def get_climatology(
        self,
        latitude: float,
        longitude: float,
        target_date: date,
        years_back: int = 30,
    ) -> ClimatologyData:
        """
        Get climatological statistics for a location and date.

        Args:
            latitude: Location latitude
            longitude: Location longitude
            target_date: Target date for climatology
            years_back: Number of years of historical data to use

        Returns:
            ClimatologyData with temperature and precipitation statistics
        """
        cache_key = self._cache_key(
            latitude, longitude, target_date.month, target_date.day
        )
        if cache_key in self._cache:
            return self._cache[cache_key]

        client = await self._get_client()

        # Calculate date range (same day across multiple years)
        current_year = datetime.utcnow().year
        start_year = current_year - years_back
        end_year = current_year - 1  # Don't include current year

        # Fetch historical data
        temp_maxes = []
        temp_mins = []
        precip_values = []

        # We'll fetch year by year for the specific date
        for year in range(start_year, end_year + 1):
            try:
                hist_date = date(year, target_date.month, target_date.day)
            except ValueError:
                # Handle Feb 29 in non-leap years
                continue

            params = {
                "latitude": latitude,
                "longitude": longitude,
                "start_date": hist_date.isoformat(),
                "end_date": hist_date.isoformat(),
                "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
            }

            try:
                response = await client.get(self.BASE_URL, params=params)
                response.raise_for_status()
                data = response.json()

                daily = data.get("daily", {})
                if daily.get("temperature_2m_max"):
                    val = daily["temperature_2m_max"][0]
                    if val is not None:
                        temp_maxes.append(val)

                if daily.get("temperature_2m_min"):
                    val = daily["temperature_2m_min"][0]
                    if val is not None:
                        temp_mins.append(val)

                if daily.get("precipitation_sum"):
                    val = daily["precipitation_sum"][0]
                    if val is not None:
                        precip_values.append(val)

            except httpx.HTTPError as e:
                logger.warning(f"Error fetching historical data for {year}: {e}")
                continue

        # Calculate statistics
        if not temp_maxes:
            raise ValueError("No historical data available")

        result = ClimatologyData(
            latitude=latitude,
            longitude=longitude,
            target_day=target_date.timetuple().tm_yday,
            target_month=target_date.month,
            target_date=target_date.day,
            temp_max_mean=statistics.mean(temp_maxes),
            temp_max_std=statistics.stdev(temp_maxes) if len(temp_maxes) > 1 else 0,
            temp_max_p10=sorted(temp_maxes)[int(len(temp_maxes) * 0.1)] if temp_maxes else 0,
            temp_max_p90=sorted(temp_maxes)[int(len(temp_maxes) * 0.9)] if temp_maxes else 0,
            temp_min_mean=statistics.mean(temp_mins) if temp_mins else 0,
            temp_min_std=statistics.stdev(temp_mins) if len(temp_mins) > 1 else 0,
            precip_mean=statistics.mean(precip_values) if precip_values else 0,
            precip_days_pct=sum(1 for p in precip_values if p > 0.1) / len(precip_values) if precip_values else 0,
            years_of_data=len(temp_maxes),
        )

        self._cache[cache_key] = result
        return result

    async def get_climatological_probability(
        self,
        latitude: float,
        longitude: float,
        target_date: date,
        threshold: float,
        comparison: str,
        variable: str = "temperature_max",
    ) -> float:
        """
        Calculate climatological probability of threshold exceedance.

        Args:
            latitude: Location latitude
            longitude: Location longitude
            target_date: Target date
            threshold: Threshold value (in Celsius for temperature)
            comparison: Comparison operator
            variable: Weather variable

        Returns:
            Historical probability of threshold exceedance
        """
        climatology = await self.get_climatology(latitude, longitude, target_date)

        if variable == "temperature_max":
            mean = climatology.temp_max_mean
            std = climatology.temp_max_std
        elif variable == "temperature_min":
            mean = climatology.temp_min_mean
            std = climatology.temp_min_std
        else:
            # For precipitation, return historical frequency
            if comparison in (">=", ">"):
                return climatology.precip_days_pct
            else:
                return 1 - climatology.precip_days_pct

        if std == 0:
            # No variability - deterministic
            if comparison == ">=":
                return 1.0 if mean >= threshold else 0.0
            elif comparison == ">":
                return 1.0 if mean > threshold else 0.0
            elif comparison == "<=":
                return 1.0 if mean <= threshold else 0.0
            else:
                return 1.0 if mean < threshold else 0.0

        # Use normal distribution approximation
        from math import erf, sqrt

        z = (threshold - mean) / std

        # CDF of standard normal
        def norm_cdf(x: float) -> float:
            return 0.5 * (1 + erf(x / sqrt(2)))

        if comparison in (">=", ">"):
            return 1 - norm_cdf(z)
        else:
            return norm_cdf(z)
