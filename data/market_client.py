"""Polymarket Gamma API client for market discovery."""
import logging
import re
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

import httpx

from app.config import WEATHER_STATIONS, CITY_ALIASES

logger = logging.getLogger(__name__)


@dataclass
class WeatherStation:
    """Weather station information."""

    station_id: str
    name: str
    latitude: float
    longitude: float
    elevation_m: int
    timezone: str
    resolution_source: str
    cluster: str


@dataclass
class WeatherMarketCriteria:
    """Parsed weather market resolution criteria."""

    market_id: str
    condition_id: str
    token_id_yes: str
    token_id_no: str
    question: str
    description: str
    location: str
    station: Optional[WeatherStation]
    resolution_date: datetime
    variable: str  # temperature_max, temperature_min, precipitation
    threshold: float
    comparison: str  # >=, >, <=, <
    unit: str  # fahrenheit, celsius, inches, mm
    resolution_source: str
    current_price_yes: Optional[float]
    current_price_no: Optional[float]
    liquidity: float
    volume: float
    outcomes: List[str]


class GammaAPIClient:
    """Client for Polymarket Gamma API (market discovery)."""

    BASE_URL = "https://gamma-api.polymarket.com"

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

    async def get_active_markets(
        self,
        tag: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Fetch active markets from Gamma API.

        Args:
            tag: Optional tag filter (e.g., 'climate-science')
            limit: Maximum number of markets to return

        Returns:
            List of market dictionaries
        """
        client = await self._get_client()

        params = {
            "active": "true",
            "limit": limit,
        }
        if tag:
            params["tag"] = tag

        try:
            response = await client.get(f"{self.BASE_URL}/markets", params=params)
            response.raise_for_status()
            return response.json()

        except httpx.HTTPError as e:
            logger.error(f"Error fetching markets: {e}")
            return []

    async def get_market(self, condition_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a single market by condition ID."""
        client = await self._get_client()

        try:
            response = await client.get(f"{self.BASE_URL}/markets/{condition_id}")
            response.raise_for_status()
            return response.json()

        except httpx.HTTPError as e:
            logger.error(f"Error fetching market {condition_id}: {e}")
            return None

    async def get_event(self, event_slug: str) -> Optional[Dict[str, Any]]:
        """Fetch an event with all its markets."""
        client = await self._get_client()

        try:
            response = await client.get(f"{self.BASE_URL}/events/{event_slug}")
            response.raise_for_status()
            return response.json()

        except httpx.HTTPError as e:
            logger.error(f"Error fetching event {event_slug}: {e}")
            return None

    async def discover_weather_markets(
        self,
        max_days_ahead: int = 7,
        min_liquidity: float = 1000,
    ) -> List[WeatherMarketCriteria]:
        """
        Discover and parse active weather markets.

        Args:
            max_days_ahead: Maximum days until resolution
            min_liquidity: Minimum market liquidity

        Returns:
            List of parsed WeatherMarketCriteria
        """
        raw_markets = await self.get_active_markets(tag="climate-science")
        weather_markets = []

        for market in raw_markets:
            parsed = parse_market_criteria(market)
            if parsed is None:
                continue

            # Filter by resolution date
            days_to_resolution = (
                parsed.resolution_date - datetime.utcnow()
            ).total_seconds() / 86400
            if days_to_resolution < 0 or days_to_resolution > max_days_ahead:
                continue

            # Filter by liquidity
            if parsed.liquidity < min_liquidity:
                continue

            weather_markets.append(parsed)

        logger.info(f"Discovered {len(weather_markets)} tradeable weather markets")
        return weather_markets


# Parsing patterns for market questions
TEMPERATURE_PATTERNS = [
    # "Highest temperature in NYC on January 20?"
    r"[Hh]ighest temperature in (?P<city>[\w\s]+) on (?P<date>[\w\s\d,]+)\??",
    # "Will the high in London exceed 50°F on Feb 5?"
    r"[Hh]igh in (?P<city>[\w\s]+) (?:exceed|above) (?P<threshold>\d+)°[FfCc] on (?P<date>[\w\s\d,]+)",
    # "NYC temperature on January 20"
    r"(?P<city>[\w\s]+) temperature on (?P<date>[\w\s\d,]+)",
    # "Temperature in New York on Jan 20"
    r"[Tt]emperature in (?P<city>[\w\s]+) on (?P<date>[\w\s\d,]+)",
]

OUTCOME_PATTERNS = [
    # "85°F or higher"
    (r"(?P<threshold>\d+)°[Ff]\s+or\s+higher", ">="),
    # "84°F or lower"
    (r"(?P<threshold>\d+)°[Ff]\s+or\s+lower", "<="),
    # "Above 85°F"
    (r"[Aa]bove\s+(?P<threshold>\d+)°[Ff]", ">"),
    # "Below 85°F"
    (r"[Bb]elow\s+(?P<threshold>\d+)°[Ff]", "<"),
    # "85-86°F" (bracket)
    (r"(?P<low>\d+)-(?P<high>\d+)°[Ff]", "bracket"),
]

PRECIPITATION_PATTERNS = [
    # "Will it rain in NYC on January 20?"
    r"[Ww]ill it rain in (?P<city>[\w\s]+) on (?P<date>[\w\s\d,]+)",
    # "Precipitation in London on Feb 5"
    r"[Pp]recipitation in (?P<city>[\w\s]+) on (?P<date>[\w\s\d,]+)",
    # "Any rain in Miami on Jan 21"
    r"[Aa]ny rain in (?P<city>[\w\s]+) on (?P<date>[\w\s\d,]+)",
]


def standardize_city_name(raw_city: str) -> Optional[str]:
    """Map raw city string to canonical station key."""
    normalized = raw_city.strip().title()

    # Check direct alias match
    if normalized in CITY_ALIASES:
        return CITY_ALIASES[normalized]

    # Check uppercase
    upper = raw_city.upper().strip()
    if upper in CITY_ALIASES:
        return CITY_ALIASES[upper]

    # Check if it matches a station key directly
    key = normalized.upper().replace(" ", "_")
    if key in WEATHER_STATIONS:
        return key

    return None


def parse_date(date_str: str) -> Optional[datetime]:
    """Parse date string to datetime."""
    date_str = date_str.strip()

    # Common formats
    formats = [
        "%B %d, %Y",  # January 20, 2026
        "%B %d %Y",   # January 20 2026
        "%b %d, %Y",  # Jan 20, 2026
        "%b %d %Y",   # Jan 20 2026
        "%B %d",      # January 20
        "%b %d",      # Jan 20
        "%m/%d/%Y",   # 01/20/2026
        "%Y-%m-%d",   # 2026-01-20
    ]

    current_year = datetime.utcnow().year

    for fmt in formats:
        try:
            parsed = datetime.strptime(date_str, fmt)
            # If year not specified, use current year
            if parsed.year == 1900:
                parsed = parsed.replace(year=current_year)
            return parsed
        except ValueError:
            continue

    return None


def extract_threshold_from_outcomes(outcomes: List[str]) -> Optional[tuple]:
    """Extract threshold and comparison from outcome strings."""
    for outcome in outcomes:
        for pattern, comparison in OUTCOME_PATTERNS:
            match = re.search(pattern, outcome)
            if match:
                if comparison == "bracket":
                    low = float(match.group("low"))
                    high = float(match.group("high"))
                    return (low, high), "bracket"
                else:
                    threshold = float(match.group("threshold"))
                    return threshold, comparison

    return None


def parse_market_criteria(market: Dict[str, Any]) -> Optional[WeatherMarketCriteria]:
    """
    Parse natural language market question into structured criteria.

    Returns None if parsing fails.
    """
    question = market.get("question", "")
    description = market.get("description", "")
    outcomes = market.get("outcomes", [])

    # Try temperature patterns first
    for pattern in TEMPERATURE_PATTERNS:
        match = re.search(pattern, question)
        if match:
            groups = match.groupdict()
            city = standardize_city_name(groups.get("city", ""))

            if not city:
                continue

            date = parse_date(groups.get("date", ""))
            if not date:
                continue

            # Extract threshold from outcomes
            threshold_result = extract_threshold_from_outcomes(outcomes)
            if threshold_result is None:
                continue

            threshold, comparison = threshold_result

            # Get station info
            station_data = WEATHER_STATIONS.get(city)
            station = None
            if station_data:
                station = WeatherStation(
                    station_id=station_data["station_id"],
                    name=station_data["name"],
                    latitude=station_data["latitude"],
                    longitude=station_data["longitude"],
                    elevation_m=station_data["elevation_m"],
                    timezone=station_data["timezone"],
                    resolution_source=station_data["resolution_source"],
                    cluster=station_data["cluster"],
                )

            # Extract tokens
            tokens = market.get("tokens", [])
            token_id_yes = tokens[0]["token_id"] if len(tokens) > 0 else ""
            token_id_no = tokens[1]["token_id"] if len(tokens) > 1 else ""

            return WeatherMarketCriteria(
                market_id=market.get("id", ""),
                condition_id=market.get("condition_id", market.get("id", "")),
                token_id_yes=token_id_yes,
                token_id_no=token_id_no,
                question=question,
                description=description,
                location=city,
                station=station,
                resolution_date=date,
                variable="temperature_max",
                threshold=threshold if not isinstance(threshold, tuple) else threshold[0],
                comparison=comparison,
                unit="fahrenheit",
                resolution_source="Weather Underground",
                current_price_yes=None,
                current_price_no=None,
                liquidity=float(market.get("liquidity", 0)),
                volume=float(market.get("volume", 0)),
                outcomes=outcomes,
            )

    # Try precipitation patterns
    for pattern in PRECIPITATION_PATTERNS:
        match = re.search(pattern, question)
        if match:
            groups = match.groupdict()
            city = standardize_city_name(groups.get("city", ""))

            if not city:
                continue

            date = parse_date(groups.get("date", ""))
            if not date:
                continue

            # Get station info
            station_data = WEATHER_STATIONS.get(city)
            station = None
            if station_data:
                station = WeatherStation(
                    station_id=station_data["station_id"],
                    name=station_data["name"],
                    latitude=station_data["latitude"],
                    longitude=station_data["longitude"],
                    elevation_m=station_data["elevation_m"],
                    timezone=station_data["timezone"],
                    resolution_source=station_data["resolution_source"],
                    cluster=station_data["cluster"],
                )

            # Extract tokens
            tokens = market.get("tokens", [])
            token_id_yes = tokens[0]["token_id"] if len(tokens) > 0 else ""
            token_id_no = tokens[1]["token_id"] if len(tokens) > 1 else ""

            return WeatherMarketCriteria(
                market_id=market.get("id", ""),
                condition_id=market.get("condition_id", market.get("id", "")),
                token_id_yes=token_id_yes,
                token_id_no=token_id_no,
                question=question,
                description=description,
                location=city,
                station=station,
                resolution_date=date,
                variable="precipitation",
                threshold=0.01,  # Any measurable precipitation
                comparison=">",
                unit="inches",
                resolution_source="Weather Underground",
                current_price_yes=None,
                current_price_no=None,
                liquidity=float(market.get("liquidity", 0)),
                volume=float(market.get("volume", 0)),
                outcomes=outcomes,
            )

    return None
