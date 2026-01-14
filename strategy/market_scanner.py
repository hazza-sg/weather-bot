"""Enhanced market scanner for discovering and parsing weather markets."""
import logging
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass

from app.config import WEATHER_STATIONS, CITY_ALIASES, STRATEGY_CONFIG

logger = logging.getLogger(__name__)


@dataclass
class ParsedMarket:
    """Fully parsed weather market with all criteria."""

    # Identifiers
    market_id: str
    condition_id: str
    token_id_yes: str
    token_id_no: str

    # Market info
    question: str
    description: str
    outcomes: List[str]

    # Parsed criteria
    market_type: str  # temperature_max, temperature_min, precipitation, hurricane
    location: str
    station_id: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    timezone: Optional[str]
    cluster: Optional[str]

    # Resolution criteria
    resolution_date: datetime
    variable: str
    threshold: float
    comparison: str  # >=, >, <=, <
    unit: str
    resolution_source: str

    # Market state
    liquidity: float
    volume: float

    # Computed
    days_to_resolution: float
    is_tradeable: bool

    def to_dict(self) -> dict:
        return {
            "market_id": self.market_id,
            "condition_id": self.condition_id,
            "token_id_yes": self.token_id_yes,
            "token_id_no": self.token_id_no,
            "question": self.question,
            "market_type": self.market_type,
            "location": self.location,
            "station_id": self.station_id,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "resolution_date": self.resolution_date.isoformat(),
            "variable": self.variable,
            "threshold": self.threshold,
            "comparison": self.comparison,
            "unit": self.unit,
            "liquidity": self.liquidity,
            "volume": self.volume,
            "days_to_resolution": self.days_to_resolution,
            "is_tradeable": self.is_tradeable,
        }


class MarketScanner:
    """
    Scan and parse weather markets from Polymarket.

    Handles various question formats:
    - Temperature high/low markets
    - Precipitation (rain/snow) markets
    - Hurricane landfall markets
    - Temperature bracket markets
    """

    # Temperature patterns
    TEMP_PATTERNS = [
        # "Highest temperature in NYC on January 20?"
        (r"[Hh]ighest\s+temperature\s+in\s+(?P<city>[\w\s]+?)\s+on\s+(?P<date>[\w\s\d,]+)\??", "temperature_max"),
        # "What will be the high temperature in NYC on Jan 20?"
        (r"[Ww]hat\s+will\s+be\s+the\s+high\s+(?:temperature\s+)?in\s+(?P<city>[\w\s]+?)\s+on\s+(?P<date>[\w\s\d,]+)\??", "temperature_max"),
        # "High temperature in NYC on January 20"
        (r"[Hh]igh\s+temperature\s+in\s+(?P<city>[\w\s]+?)\s+on\s+(?P<date>[\w\s\d,]+)", "temperature_max"),
        # "NYC high temperature on January 20"
        (r"(?P<city>[\w\s]+?)\s+high\s+temperature\s+on\s+(?P<date>[\w\s\d,]+)", "temperature_max"),
        # "Lowest temperature in NYC on January 20?"
        (r"[Ll]owest\s+temperature\s+in\s+(?P<city>[\w\s]+?)\s+on\s+(?P<date>[\w\s\d,]+)\??", "temperature_min"),
        # "Low temperature in NYC on January 20"
        (r"[Ll]ow\s+temperature\s+in\s+(?P<city>[\w\s]+?)\s+on\s+(?P<date>[\w\s\d,]+)", "temperature_min"),
        # "Will the high in NYC exceed 85°F on Jan 20?"
        (r"[Ww]ill\s+the\s+high\s+in\s+(?P<city>[\w\s]+?)\s+(?:exceed|be\s+above)\s+(?P<threshold>\d+)[°]?[FfCc]?\s+on\s+(?P<date>[\w\s\d,]+)\??", "temperature_max"),
        # "Will NYC temperature reach 85°F on Jan 20?"
        (r"[Ww]ill\s+(?P<city>[\w\s]+?)\s+temperature\s+reach\s+(?P<threshold>\d+)[°]?[FfCc]?\s+on\s+(?P<date>[\w\s\d,]+)\??", "temperature_max"),
    ]

    # Precipitation patterns
    PRECIP_PATTERNS = [
        # "Will it rain in NYC on January 20?"
        (r"[Ww]ill\s+it\s+rain\s+in\s+(?P<city>[\w\s]+?)\s+on\s+(?P<date>[\w\s\d,]+)\??", "precipitation"),
        # "Rain in NYC on January 20?"
        (r"[Rr]ain\s+in\s+(?P<city>[\w\s]+?)\s+on\s+(?P<date>[\w\s\d,]+)\??", "precipitation"),
        # "Any precipitation in NYC on January 20"
        (r"[Aa]ny\s+precipitation\s+in\s+(?P<city>[\w\s]+?)\s+on\s+(?P<date>[\w\s\d,]+)", "precipitation"),
        # "Will NYC get rain on January 20?"
        (r"[Ww]ill\s+(?P<city>[\w\s]+?)\s+get\s+(?:rain|precipitation)\s+on\s+(?P<date>[\w\s\d,]+)\??", "precipitation"),
        # "Snow in NYC on January 20?"
        (r"[Ss]now\s+in\s+(?P<city>[\w\s]+?)\s+on\s+(?P<date>[\w\s\d,]+)\??", "precipitation_snow"),
    ]

    # Hurricane patterns
    HURRICANE_PATTERNS = [
        # "Will Hurricane X make landfall in Florida by Date?"
        (r"[Ww]ill\s+[Hh]urricane\s+(?P<name>\w+)\s+make\s+landfall\s+in\s+(?P<location>[\w\s]+?)\s+by\s+(?P<date>[\w\s\d,]+)\??", "hurricane_landfall"),
        # "Hurricane X landfall before Date"
        (r"[Hh]urricane\s+(?P<name>\w+)\s+landfall\s+(?:before|by)\s+(?P<date>[\w\s\d,]+)", "hurricane_landfall"),
    ]

    # Outcome patterns for extracting threshold
    OUTCOME_PATTERNS = [
        # "85°F or higher"
        (r"(?P<threshold>\d+(?:\.\d+)?)\s*[°]?[Ff]\s+or\s+higher", ">=", "fahrenheit"),
        # "84°F or lower"
        (r"(?P<threshold>\d+(?:\.\d+)?)\s*[°]?[Ff]\s+or\s+lower", "<=", "fahrenheit"),
        # "Above 85°F"
        (r"[Aa]bove\s+(?P<threshold>\d+(?:\.\d+)?)\s*[°]?[Ff]", ">", "fahrenheit"),
        # "Below 85°F"
        (r"[Bb]elow\s+(?P<threshold>\d+(?:\.\d+)?)\s*[°]?[Ff]", "<", "fahrenheit"),
        # "At least 85°F"
        (r"[Aa]t\s+least\s+(?P<threshold>\d+(?:\.\d+)?)\s*[°]?[Ff]", ">=", "fahrenheit"),
        # "Under 85°F"
        (r"[Uu]nder\s+(?P<threshold>\d+(?:\.\d+)?)\s*[°]?[Ff]", "<", "fahrenheit"),
        # "85-86°F" (bracket)
        (r"(?P<low>\d+)\s*-\s*(?P<high>\d+)\s*[°]?[Ff]", "bracket", "fahrenheit"),
        # "Yes" / "No" for binary outcomes
        (r"^[Yy]es$", "yes", None),
        (r"^[Nn]o$", "no", None),
        # Celsius versions
        (r"(?P<threshold>\d+(?:\.\d+)?)\s*[°]?[Cc]\s+or\s+higher", ">=", "celsius"),
        (r"(?P<threshold>\d+(?:\.\d+)?)\s*[°]?[Cc]\s+or\s+lower", "<=", "celsius"),
    ]

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or STRATEGY_CONFIG

    def parse_market(self, market: Dict[str, Any]) -> Optional[ParsedMarket]:
        """
        Parse a raw market dictionary into a ParsedMarket.

        Args:
            market: Raw market data from Gamma API

        Returns:
            ParsedMarket if parsing succeeds, None otherwise
        """
        question = market.get("question", "")
        description = market.get("description", "")
        outcomes = market.get("outcomes", [])

        # Try temperature patterns
        for pattern, market_type in self.TEMP_PATTERNS:
            match = re.search(pattern, question)
            if match:
                return self._parse_temperature_market(market, match, market_type, outcomes)

        # Try precipitation patterns
        for pattern, market_type in self.PRECIP_PATTERNS:
            match = re.search(pattern, question)
            if match:
                return self._parse_precipitation_market(market, match, market_type)

        # Try hurricane patterns
        for pattern, market_type in self.HURRICANE_PATTERNS:
            match = re.search(pattern, question)
            if match:
                return self._parse_hurricane_market(market, match)

        return None

    def _parse_temperature_market(
        self,
        market: Dict,
        match: re.Match,
        market_type: str,
        outcomes: List[str],
    ) -> Optional[ParsedMarket]:
        """Parse a temperature market."""
        groups = match.groupdict()

        # Get city and station
        city_raw = groups.get("city", "").strip()
        city = self._standardize_city(city_raw)
        if not city:
            logger.debug(f"Unknown city: {city_raw}")
            return None

        station = WEATHER_STATIONS.get(city)

        # Parse date
        date_str = groups.get("date", "")
        resolution_date = self._parse_date(date_str)
        if not resolution_date:
            logger.debug(f"Could not parse date: {date_str}")
            return None

        # Extract threshold from outcomes or question
        threshold = groups.get("threshold")
        comparison = ">="
        unit = "fahrenheit"

        if threshold:
            threshold = float(threshold)
        else:
            # Try to extract from outcomes
            threshold_result = self._extract_threshold_from_outcomes(outcomes)
            if threshold_result:
                threshold, comparison, unit = threshold_result
            else:
                logger.debug(f"Could not extract threshold from outcomes: {outcomes}")
                return None

        # Calculate days to resolution
        now = datetime.utcnow()
        days_to_resolution = (resolution_date - now).total_seconds() / 86400

        # Check if tradeable
        is_tradeable = (
            days_to_resolution > self.config["min_days_to_resolution"]
            and days_to_resolution <= self.config["max_days_to_resolution"]
            and float(market.get("liquidity", 0)) >= self.config["min_liquidity"]
        )

        # Get tokens
        tokens = market.get("tokens", [])
        token_id_yes = tokens[0]["token_id"] if len(tokens) > 0 else ""
        token_id_no = tokens[1]["token_id"] if len(tokens) > 1 else ""

        return ParsedMarket(
            market_id=market.get("id", ""),
            condition_id=market.get("condition_id", market.get("id", "")),
            token_id_yes=token_id_yes,
            token_id_no=token_id_no,
            question=market.get("question", ""),
            description=market.get("description", ""),
            outcomes=outcomes,
            market_type=market_type,
            location=city,
            station_id=station["station_id"] if station else None,
            latitude=station["latitude"] if station else None,
            longitude=station["longitude"] if station else None,
            timezone=station["timezone"] if station else None,
            cluster=station["cluster"] if station else None,
            resolution_date=resolution_date,
            variable=market_type,
            threshold=threshold,
            comparison=comparison,
            unit=unit,
            resolution_source="Weather Underground",
            liquidity=float(market.get("liquidity", 0)),
            volume=float(market.get("volume", 0)),
            days_to_resolution=days_to_resolution,
            is_tradeable=is_tradeable,
        )

    def _parse_precipitation_market(
        self,
        market: Dict,
        match: re.Match,
        market_type: str,
    ) -> Optional[ParsedMarket]:
        """Parse a precipitation market."""
        groups = match.groupdict()

        city_raw = groups.get("city", "").strip()
        city = self._standardize_city(city_raw)
        if not city:
            return None

        station = WEATHER_STATIONS.get(city)

        date_str = groups.get("date", "")
        resolution_date = self._parse_date(date_str)
        if not resolution_date:
            return None

        now = datetime.utcnow()
        days_to_resolution = (resolution_date - now).total_seconds() / 86400

        is_tradeable = (
            days_to_resolution > self.config["min_days_to_resolution"]
            and days_to_resolution <= self.config["max_days_to_resolution"]
            and float(market.get("liquidity", 0)) >= self.config["min_liquidity"]
        )

        tokens = market.get("tokens", [])
        token_id_yes = tokens[0]["token_id"] if len(tokens) > 0 else ""
        token_id_no = tokens[1]["token_id"] if len(tokens) > 1 else ""

        return ParsedMarket(
            market_id=market.get("id", ""),
            condition_id=market.get("condition_id", market.get("id", "")),
            token_id_yes=token_id_yes,
            token_id_no=token_id_no,
            question=market.get("question", ""),
            description=market.get("description", ""),
            outcomes=market.get("outcomes", []),
            market_type=market_type,
            location=city,
            station_id=station["station_id"] if station else None,
            latitude=station["latitude"] if station else None,
            longitude=station["longitude"] if station else None,
            timezone=station["timezone"] if station else None,
            cluster=station["cluster"] if station else None,
            resolution_date=resolution_date,
            variable="precipitation",
            threshold=0.01,  # Any measurable precipitation
            comparison=">",
            unit="inches",
            resolution_source="Weather Underground",
            liquidity=float(market.get("liquidity", 0)),
            volume=float(market.get("volume", 0)),
            days_to_resolution=days_to_resolution,
            is_tradeable=is_tradeable,
        )

    def _parse_hurricane_market(
        self,
        market: Dict,
        match: re.Match,
    ) -> Optional[ParsedMarket]:
        """Parse a hurricane market."""
        groups = match.groupdict()

        name = groups.get("name", "Unknown")
        location = groups.get("location", "").strip()

        date_str = groups.get("date", "")
        resolution_date = self._parse_date(date_str)
        if not resolution_date:
            return None

        now = datetime.utcnow()
        days_to_resolution = (resolution_date - now).total_seconds() / 86400

        tokens = market.get("tokens", [])
        token_id_yes = tokens[0]["token_id"] if len(tokens) > 0 else ""
        token_id_no = tokens[1]["token_id"] if len(tokens) > 1 else ""

        return ParsedMarket(
            market_id=market.get("id", ""),
            condition_id=market.get("condition_id", market.get("id", "")),
            token_id_yes=token_id_yes,
            token_id_no=token_id_no,
            question=market.get("question", ""),
            description=market.get("description", ""),
            outcomes=market.get("outcomes", []),
            market_type="hurricane_landfall",
            location=location,
            station_id=None,
            latitude=None,
            longitude=None,
            timezone=None,
            cluster=None,
            resolution_date=resolution_date,
            variable="hurricane_landfall",
            threshold=1.0,  # Binary outcome
            comparison=">=",
            unit="binary",
            resolution_source="NHC",
            liquidity=float(market.get("liquidity", 0)),
            volume=float(market.get("volume", 0)),
            days_to_resolution=days_to_resolution,
            is_tradeable=days_to_resolution > 0,
        )

    def _standardize_city(self, raw_city: str) -> Optional[str]:
        """Map raw city string to canonical station key."""
        # Clean up the input
        city = raw_city.strip()

        # Direct alias lookup
        if city in CITY_ALIASES:
            return CITY_ALIASES[city]

        # Try title case
        title = city.title()
        if title in CITY_ALIASES:
            return CITY_ALIASES[title]

        # Try uppercase
        upper = city.upper()
        if upper in CITY_ALIASES:
            return CITY_ALIASES[upper]

        # Check if it's already a station key
        key = city.upper().replace(" ", "_")
        if key in WEATHER_STATIONS:
            return key

        # Try partial matches
        for alias, station in CITY_ALIASES.items():
            if alias.lower() in city.lower() or city.lower() in alias.lower():
                return station

        return None

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse date string to datetime."""
        date_str = date_str.strip().rstrip("?")

        current_year = datetime.utcnow().year
        next_year = current_year + 1

        formats = [
            "%B %d, %Y",    # January 20, 2026
            "%B %d %Y",     # January 20 2026
            "%b %d, %Y",    # Jan 20, 2026
            "%b %d %Y",     # Jan 20 2026
            "%B %d",        # January 20
            "%b %d",        # Jan 20
            "%m/%d/%Y",     # 01/20/2026
            "%m/%d",        # 01/20
            "%Y-%m-%d",     # 2026-01-20
        ]

        for fmt in formats:
            try:
                parsed = datetime.strptime(date_str, fmt)

                # If year not specified, determine correct year
                if parsed.year == 1900:
                    # Check if date is in the past this year
                    test_date = parsed.replace(year=current_year)
                    if test_date < datetime.utcnow() - timedelta(days=1):
                        parsed = parsed.replace(year=next_year)
                    else:
                        parsed = parsed.replace(year=current_year)

                return parsed
            except ValueError:
                continue

        return None

    def _extract_threshold_from_outcomes(
        self,
        outcomes: List[str],
    ) -> Optional[Tuple[float, str, str]]:
        """Extract threshold, comparison, and unit from outcomes."""
        for outcome in outcomes:
            for pattern, comparison, unit in self.OUTCOME_PATTERNS:
                match = re.search(pattern, outcome)
                if match:
                    if comparison == "bracket":
                        # Return lower bound of bracket
                        low = float(match.group("low"))
                        return low, ">=", unit
                    elif comparison in ("yes", "no"):
                        continue  # Skip yes/no patterns
                    else:
                        threshold = float(match.group("threshold"))
                        return threshold, comparison, unit

        return None

    async def scan_markets(
        self,
        market_client,
        max_days_ahead: int = 7,
    ) -> List[ParsedMarket]:
        """
        Scan for tradeable weather markets.

        Args:
            market_client: GammaAPIClient instance
            max_days_ahead: Maximum days until resolution

        Returns:
            List of parsed, tradeable markets
        """
        raw_markets = await market_client.get_active_markets(tag="climate-science")

        parsed_markets = []
        for market in raw_markets:
            parsed = self.parse_market(market)
            if parsed and parsed.is_tradeable:
                parsed_markets.append(parsed)

        logger.info(f"Scanned {len(raw_markets)} markets, found {len(parsed_markets)} tradeable")
        return parsed_markets
