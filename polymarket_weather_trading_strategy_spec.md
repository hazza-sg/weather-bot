# Polymarket Weather Trading Strategy: Technical Specification

**Version:** 1.0  
**Date:** January 2026  
**Purpose:** Complete implementation specification for automated weather prediction market trading  
**Target Implementation:** Python 3.11+ (primary) or C++17 (alternative)

---

## 1. Executive Summary

### 1.1 Objective

Build a fully automated trading system that exploits pricing inefficiencies in Polymarket's short-term weather prediction markets by comparing ensemble weather forecast probabilities against market-implied probabilities, executing trades when statistically significant edge exists.

### 1.2 Core Hypothesis

Meteorological ensemble forecasts provide well-calibrated probability distributions for weather outcomes 2-7 days in advance. Polymarket weather markets, due to lower liquidity and specialized knowledge requirements, often fail to efficiently incorporate this information. The resulting mispricing creates positive expected value trading opportunities.

### 1.3 Key Parameters

| Parameter | Value |
|-----------|-------|
| Position Size Range | $1.00 - $10.00 per trade |
| Maximum Total Exposure | 75% of allocated capital |
| Minimum Edge Threshold | 5% (configurable) |
| Optimal Entry Window | 2-5 days before resolution |
| Target Markets | Short-term temperature, precipitation, hurricane landfall |
| Execution Mode | Fully automated |

### 1.4 Success Metrics

The system should target:
- Win rate above 55% (given selective entry criteria)
- Positive expected value per trade after accounting for estimation uncertainty
- Maximum drawdown below 30% of allocated capital
- Sharpe ratio above 1.0 on annualized returns

---

## 2. System Architecture

### 2.1 High-Level Component Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        POLYMARKET WEATHER TRADING SYSTEM                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────────┐   ┌──────────────────┐   ┌──────────────────────────┐ │
│  │   DATA LAYER     │   │  STRATEGY LAYER  │   │    EXECUTION LAYER       │ │
│  │                  │   │                  │   │                          │ │
│  │  ┌────────────┐  │   │  ┌────────────┐  │   │  ┌────────────────────┐  │ │
│  │  │ Open-Meteo │  │   │  │  Market    │  │   │  │ Polymarket CLOB    │  │ │
│  │  │ Ensemble   │  │──▶│  │  Scanner   │  │──▶│  │ API Client         │  │ │
│  │  │ API        │  │   │  └────────────┘  │   │  └────────────────────┘  │ │
│  │  └────────────┘  │   │         │        │   │           │              │ │
│  │                  │   │         ▼        │   │           ▼              │ │
│  │  ┌────────────┐  │   │  ┌────────────┐  │   │  ┌────────────────────┐  │ │
│  │  │ NOAA NBM   │  │   │  │   Edge     │  │   │  │ Order Manager      │  │ │
│  │  │ Probabilis-│  │──▶│  │ Calculator │  │──▶│  │ (Place/Cancel)     │  │ │
│  │  │ tic Data   │  │   │  └────────────┘  │   │  └────────────────────┘  │ │
│  │  └────────────┘  │   │         │        │   │           │              │ │
│  │                  │   │         ▼        │   │           ▼              │ │
│  │  ┌────────────┐  │   │  ┌────────────┐  │   │  ┌────────────────────┐  │ │
│  │  │ Polymarket │  │   │  │  Position  │  │   │  │ Position Tracker   │  │ │
│  │  │ Gamma API  │  │──▶│  │   Sizer    │  │──▶│  │ & P&L Calculator   │  │ │
│  │  │ (Markets)  │  │   │  └────────────┘  │   │  └────────────────────┘  │ │
│  │  └────────────┘  │   │         │        │   │           │              │ │
│  │                  │   │         ▼        │   │           ▼              │ │
│  │  ┌────────────┐  │   │  ┌────────────┐  │   │  ┌────────────────────┐  │ │
│  │  │ Historical │  │   │  │Diversific- │  │   │  │ Risk Manager       │  │ │
│  │  │ Climate    │  │──▶│  │ation Filter│  │──▶│  │ (Limits/Halts)     │  │ │
│  │  │ Data       │  │   │  └────────────┘  │   │  └────────────────────┘  │ │
│  │  └────────────┘  │   │                  │   │                          │ │
│  └──────────────────┘   └──────────────────┘   └──────────────────────────┘ │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────────┐│
│  │                         PERSISTENCE & LOGGING                            ││
│  │  SQLite Database | JSON State Files | Structured Logging | Alert System  ││
│  └──────────────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Module Responsibilities

| Module | Responsibility |
|--------|----------------|
| `data/weather_client.py` | Fetch ensemble forecasts from Open-Meteo and NOAA |
| `data/market_client.py` | Fetch active markets and prices from Polymarket |
| `data/historical_client.py` | Access climatological baselines and verification data |
| `strategy/market_scanner.py` | Discover and parse weather markets from Gamma API |
| `strategy/edge_calculator.py` | Compute forecast probabilities and compare to market prices |
| `strategy/position_sizer.py` | Calculate position sizes using fractional Kelly criterion |
| `strategy/diversification.py` | Enforce geographic and temporal correlation limits |
| `execution/clob_client.py` | Wrapper around py-clob-client for order management |
| `execution/order_manager.py` | Place, track, and cancel orders |
| `execution/position_tracker.py` | Track open positions and calculate P&L |
| `risk/risk_manager.py` | Enforce exposure limits, drawdown halts |
| `utils/logging.py` | Structured logging with rotation |
| `utils/alerts.py` | Desktop/mobile notifications for critical events |
| `main.py` | Main event loop orchestrating all components |

### 2.3 Data Flow

1. **Market Discovery** (every 15 minutes): Query Gamma API for active Climate & Science markets
2. **Market Parsing**: Extract resolution criteria (location, date, threshold, comparison operator)
3. **Forecast Retrieval** (every 6 hours per market, or on model update): Fetch ensemble forecasts
4. **Probability Calculation**: Convert ensemble members to exceedance/threshold probabilities
5. **Price Retrieval** (every 60 seconds for candidate markets): Get current market midpoint
6. **Edge Calculation**: Compare forecast probability to market-implied probability
7. **Diversification Check**: Verify position would not violate correlation limits
8. **Position Sizing**: Calculate Kelly-optimal position size
9. **Order Execution**: Place limit order at or near midpoint
10. **Position Tracking**: Monitor fill status, update P&L
11. **Risk Monitoring**: Check drawdown limits, halt if breached

---

## 3. Data Sources

### 3.1 Weather Forecast Data

#### 3.1.1 Open-Meteo Ensemble API (Primary Source)

**Endpoint:** `https://api.open-meteo.com/v1/ensemble`

**Authentication:** None required (rate limits apply to excessive usage)

**Available Models:**

| Model | Ensemble Members | Update Frequency | Forecast Horizon |
|-------|------------------|------------------|------------------|
| GEFS (gfs_seamless) | 31 | 4x daily (00, 06, 12, 18 UTC) | 16 days |
| ECMWF IFS (ecmwf_ifs025) | 51 | 2x daily (00, 12 UTC) | 15 days |
| ICON-EPS (icon_seamless) | 40 | 4x daily | 7.5 days |
| GEM (gem_global_ensemble) | 21 | 2x daily | 16 days |

**Request Parameters:**

```python
params = {
    "latitude": 40.7128,
    "longitude": -74.006,
    "hourly": [
        "temperature_2m",
        "precipitation",
        "precipitation_probability",
        "weather_code"
    ],
    "models": [
        "gfs_seamless",
        "ecmwf_ifs025",
        "icon_seamless"
    ],
    "forecast_days": 7,
    "timezone": "America/New_York"
}
```

**Response Structure:**

```json
{
    "latitude": 40.71,
    "longitude": -74.01,
    "hourly": {
        "time": ["2026-01-15T00:00", "2026-01-15T01:00", ...],
        "temperature_2m_gfs_seamless_member0": [32.5, 31.8, ...],
        "temperature_2m_gfs_seamless_member1": [33.1, 32.2, ...],
        ...
        "temperature_2m_ecmwf_ifs025_member0": [32.8, 31.9, ...],
        ...
    }
}
```

**Critical Implementation Notes:**

- Ensemble members are returned as separate arrays suffixed with `_member{N}`
- Temperature is in Celsius; convert to Fahrenheit for US markets: `F = C * 9/5 + 32`
- Hourly data must be aggregated to daily max/min for temperature bracket markets
- Handle missing members gracefully (some models have fewer members)

#### 3.1.2 NOAA National Blend of Models (Secondary Source)

**Purpose:** Provides direct probabilistic forecasts (percentiles, exceedance probabilities) without requiring ensemble post-processing.

**Access:** AWS S3 bucket `s3://noaa-nbm-pds/`

**File Pattern:** `blend.{YYYYMMDD}/{HH}/core/blend.t{HH}z.core.f{FFF}.{region}.grib2`

**Key Variables:**

| Variable | Description | Use Case |
|----------|-------------|----------|
| TMP | Temperature | Daily high/low markets |
| TMAX/TMIN | Daily max/min temperature | Temperature bracket markets |
| APCP | Accumulated precipitation | Precipitation markets |
| PPROB | Probability of precipitation | Rain/snow markets |

**Implementation Notes:**

- Requires GRIB2 parsing library (pygrib, cfgrib, or xarray with cfgrib engine)
- NBM provides percentiles (10th, 25th, 50th, 75th, 90th) for temperature
- US coverage only; use Open-Meteo for international markets
- 2.5 km resolution; use nearest grid point to market location

#### 3.1.3 Weather Station Mapping

Markets specify exact weather stations for resolution. Map station identifiers to coordinates:

```python
WEATHER_STATIONS = {
    "NYC_LAGUARDIA": {
        "station_id": "KLGA",
        "latitude": 40.7769,
        "longitude": -73.8740,
        "elevation_m": 6,
        "timezone": "America/New_York",
        "resolution_source": "Weather Underground"
    },
    "LONDON_CITY": {
        "station_id": "EGLC",
        "latitude": 51.5053,
        "longitude": 0.0553,
        "elevation_m": 5,
        "timezone": "Europe/London",
        "resolution_source": "Weather Underground"
    },
    "MIAMI_INTL": {
        "station_id": "KMIA",
        "latitude": 25.7959,
        "longitude": -80.2870,
        "elevation_m": 3,
        "timezone": "America/New_York",
        "resolution_source": "Weather Underground"
    }
    # Add additional stations as markets are discovered
}
```

### 3.2 Market Data

#### 3.2.1 Polymarket Gamma API (Market Discovery)

**Base URL:** `https://gamma-api.polymarket.com`

**Key Endpoints:**

| Endpoint | Purpose | Rate Limit |
|----------|---------|------------|
| `GET /markets?active=true` | List all active markets | 12.5 req/sec |
| `GET /markets?tag=climate-science` | Filter by category | 12.5 req/sec |
| `GET /markets/{condition_id}` | Single market details | 12.5 req/sec |
| `GET /events/{event_slug}` | Event with all markets | 12.5 req/sec |

**Market Response Structure:**

```json
{
    "id": "0x1234...",
    "condition_id": "0xabcd...",
    "question": "Highest temperature in NYC on January 20?",
    "description": "This market resolves based on Weather Underground data...",
    "outcomes": ["85°F or higher", "84°F or lower"],
    "tokens": [
        {"token_id": "123456789", "outcome": "Yes"},
        {"token_id": "987654321", "outcome": "No"}
    ],
    "end_date_iso": "2026-01-20T23:59:59Z",
    "active": true,
    "closed": false,
    "volume": "125000.00",
    "liquidity": "8500.00"
}
```

#### 3.2.2 Polymarket CLOB API (Pricing and Execution)

**Base URL:** `https://clob.polymarket.com`

**Authentication:** EIP-712 signatures with HMAC-SHA256

**Key Endpoints:**

| Endpoint | Auth | Purpose |
|----------|------|---------|
| `GET /book?token_id={id}` | No | Order book depth |
| `GET /midpoint?token_id={id}` | No | Current midpoint price |
| `GET /price?token_id={id}&side={BUY/SELL}` | No | Best available price |
| `POST /order` | Yes | Place limit order |
| `DELETE /order/{order_id}` | Yes | Cancel order |
| `GET /orders?market={id}` | Yes | List open orders |
| `GET /positions` | Yes | List current positions |

**Order Request Structure:**

```json
{
    "tokenID": "123456789",
    "price": 0.45,
    "size": 10.0,
    "side": "BUY",
    "feeRateBps": 0,
    "nonce": 1234567890,
    "expiration": 0,
    "taker": "0x0000..."
}
```

**WebSocket Feed:**

```
URL: wss://ws-subscriptions-clob.polymarket.com/ws/market

Subscribe: {"type": "subscribe", "channel": "market", "market": "{token_id}"}

Message Types:
- price_change: {"type": "price_change", "price": 0.45, "side": "buy"}
- trade: {"type": "trade", "price": 0.46, "size": 100.0}
- book_update: {"type": "book_update", "bids": [...], "asks": [...]}
```

### 3.3 Historical Climate Data

#### 3.3.1 Open-Meteo Historical API

**Endpoint:** `https://archive-api.open-meteo.com/v1/archive`

**Purpose:** Retrieve climatological baselines for probability calibration

**Parameters:**

```python
params = {
    "latitude": 40.7128,
    "longitude": -74.006,
    "start_date": "1990-01-01",
    "end_date": "2025-12-31",
    "daily": ["temperature_2m_max", "temperature_2m_min", "precipitation_sum"],
    "timezone": "America/New_York"
}
```

**Use Cases:**

- Calculate climatological probability of temperature exceeding threshold for given date
- Identify anomalous forecast conditions (deviations from normal)
- Validate forecast calibration over historical period

---

## 4. Market Discovery and Parsing

### 4.1 Market Identification

Weather markets are identified by:

1. **Category Tag:** `climate-science` or `weather`
2. **Question Pattern:** Contains keywords like "temperature", "high", "low", "precipitation", "rain", "snow", "hurricane"
3. **Resolution Date:** Near-term (within 7 days of current date)

**Market Scanner Pseudocode:**

```python
def discover_weather_markets():
    """
    Fetch and filter active weather markets from Gamma API.
    Returns list of parsed market objects with resolution criteria.
    """
    raw_markets = gamma_api.get_markets(active=True, tag="climate-science")
    
    weather_markets = []
    for market in raw_markets:
        parsed = parse_market_criteria(market)
        if parsed is None:
            continue  # Could not parse resolution criteria
        
        days_to_resolution = (parsed.resolution_date - datetime.now()).days
        
        # Filter for tradeable time window
        if days_to_resolution < 0 or days_to_resolution > 7:
            continue
        
        # Filter for minimum liquidity
        if float(market.liquidity) < 1000:
            continue
        
        weather_markets.append(parsed)
    
    return weather_markets
```

### 4.2 Resolution Criteria Parsing

Markets must be parsed to extract structured resolution criteria. This is non-trivial as market questions use natural language.

**Target Data Structure:**

```python
@dataclass
class WeatherMarketCriteria:
    market_id: str
    token_id_yes: str
    token_id_no: str
    location: str  # Standardized location key
    station: WeatherStation
    resolution_date: datetime
    variable: str  # "temperature_max", "temperature_min", "precipitation"
    threshold: float
    comparison: str  # ">=", ">", "<=", "<"
    unit: str  # "fahrenheit", "celsius", "inches", "mm"
    resolution_source: str  # "Weather Underground", "NOAA", etc.
    current_price_yes: float
    current_price_no: float
    liquidity: float
    volume: float
```

**Parsing Rules for Temperature Markets:**

| Pattern | Extraction |
|---------|------------|
| "Highest temperature in {CITY} on {DATE}" | variable=temperature_max, location=CITY, date=DATE |
| "{N}°F or higher" | threshold=N, comparison=">=" |
| "{N}°F or lower" | threshold=N, comparison="<=" |
| "above {N}°F" | threshold=N, comparison=">" |
| "below {N}°F" | threshold=N, comparison="<" |
| "between {A} and {B}°F" | Create two thresholds, A <= T < B |

**Parsing Implementation:**

```python
import re
from datetime import datetime

TEMPERATURE_PATTERNS = [
    # "Highest temperature in NYC on January 20?"
    r"[Hh]ighest temperature in (?P<city>[\w\s]+) on (?P<date>[\w\s\d]+)\?",
    # "Will the high in London exceed 50°F on Feb 5?"
    r"[Hh]igh in (?P<city>[\w\s]+) exceed (?P<threshold>\d+)°[FfCc] on (?P<date>[\w\s\d]+)",
]

OUTCOME_PATTERNS = [
    # "85°F or higher"
    r"(?P<threshold>\d+)°[Ff]\s+or\s+higher",
    # "84°F or lower"
    r"(?P<threshold>\d+)°[Ff]\s+or\s+lower",
    # "85-86°F" (bracket)
    r"(?P<low>\d+)-(?P<high>\d+)°[Ff]",
]

def parse_market_criteria(market: dict) -> Optional[WeatherMarketCriteria]:
    """
    Parse natural language market question into structured criteria.
    Returns None if parsing fails.
    """
    question = market.get("question", "")
    description = market.get("description", "")
    outcomes = market.get("outcomes", [])
    
    # Attempt to match temperature patterns
    for pattern in TEMPERATURE_PATTERNS:
        match = re.search(pattern, question)
        if match:
            city = standardize_city_name(match.group("city"))
            date = parse_date(match.group("date"))
            threshold = extract_threshold(outcomes)
            comparison = extract_comparison(outcomes)
            
            if city and date and threshold is not None:
                return WeatherMarketCriteria(
                    market_id=market["condition_id"],
                    token_id_yes=market["tokens"][0]["token_id"],
                    token_id_no=market["tokens"][1]["token_id"],
                    location=city,
                    station=WEATHER_STATIONS.get(city),
                    resolution_date=date,
                    variable="temperature_max",
                    threshold=threshold,
                    comparison=comparison,
                    unit="fahrenheit",
                    resolution_source="Weather Underground",
                    current_price_yes=None,  # Fetched separately
                    current_price_no=None,
                    liquidity=float(market.get("liquidity", 0)),
                    volume=float(market.get("volume", 0))
                )
    
    # Add additional pattern matching for precipitation, hurricanes, etc.
    return None
```

### 4.3 Location Standardization

Map variations in city names to canonical station identifiers:

```python
CITY_ALIASES = {
    "NYC": "NYC_LAGUARDIA",
    "New York": "NYC_LAGUARDIA",
    "New York City": "NYC_LAGUARDIA",
    "Manhattan": "NYC_LAGUARDIA",
    "London": "LONDON_CITY",
    "Miami": "MIAMI_INTL",
    "Los Angeles": "LOS_ANGELES_INTL",
    "LA": "LOS_ANGELES_INTL",
    # Add comprehensive mappings
}

def standardize_city_name(raw_city: str) -> Optional[str]:
    """Map raw city string to canonical station key."""
    normalized = raw_city.strip().title()
    return CITY_ALIASES.get(normalized) or CITY_ALIASES.get(raw_city.upper())
```

---

## 5. Edge Detection Methodology

### 5.1 Forecast Probability Calculation

#### 5.1.1 Ensemble-Based Probability

Convert ensemble forecast members to exceedance probability:

```python
def calculate_exceedance_probability(
    ensemble_values: List[float],
    threshold: float,
    comparison: str
) -> float:
    """
    Calculate probability of threshold exceedance from ensemble members.
    
    Args:
        ensemble_values: List of forecast values from all ensemble members
        threshold: The threshold value (e.g., 85°F)
        comparison: One of ">=", ">", "<=", "<"
    
    Returns:
        Probability between 0 and 1
    """
    if not ensemble_values:
        return None
    
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
    
    # Raw probability
    raw_prob = n_exceed / n_members
    
    # Apply Laplace smoothing to avoid 0% or 100% extremes
    # Equivalent to adding 1 success and 1 failure
    smoothed_prob = (n_exceed + 1) / (n_members + 2)
    
    return smoothed_prob
```

#### 5.1.2 Multi-Model Probability Aggregation

Combine probabilities from multiple forecast models:

```python
def aggregate_model_probabilities(
    model_probabilities: Dict[str, float],
    model_weights: Optional[Dict[str, float]] = None
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
        return None, 0.0
    
    if model_weights is None:
        # Equal weighting by default
        model_weights = {m: 1.0 for m in model_probabilities}
    
    # Normalize weights
    total_weight = sum(model_weights.get(m, 0) for m in model_probabilities)
    
    # Weighted mean
    weighted_sum = sum(
        model_probabilities[m] * model_weights.get(m, 0)
        for m in model_probabilities
    )
    mean_prob = weighted_sum / total_weight
    
    # Model agreement score (1 - normalized standard deviation)
    probs = list(model_probabilities.values())
    if len(probs) > 1:
        std_dev = statistics.stdev(probs)
        # Normalize: 0 std = 1.0 agreement, 0.5 std = 0 agreement
        agreement = max(0, 1 - 2 * std_dev)
    else:
        agreement = 1.0
    
    return mean_prob, agreement
```

#### 5.1.3 Temperature Bracket Probability

For markets with discrete temperature brackets (e.g., "85-86°F"):

```python
def calculate_bracket_probability(
    ensemble_values: List[float],
    lower_bound: float,
    upper_bound: float,
    inclusive_lower: bool = True,
    inclusive_upper: bool = False
) -> float:
    """
    Calculate probability of temperature falling within bracket.
    
    Standard bracket convention: [lower, upper) - inclusive lower, exclusive upper
    """
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
```

### 5.2 Market-Implied Probability

The market price directly represents the implied probability:

```python
def get_market_implied_probability(market: WeatherMarketCriteria) -> float:
    """
    Fetch current market price as implied probability.
    
    For a "Yes" token priced at $0.45, the market-implied probability
    of the "Yes" outcome is 45%.
    """
    midpoint = clob_client.get_midpoint(market.token_id_yes)
    
    if midpoint is None:
        # Fall back to best bid/ask average
        book = clob_client.get_order_book(market.token_id_yes)
        best_bid = book["bids"][0]["price"] if book["bids"] else 0
        best_ask = book["asks"][0]["price"] if book["asks"] else 1
        midpoint = (best_bid + best_ask) / 2
    
    return midpoint
```

### 5.3 Edge Calculation

```python
@dataclass
class EdgeCalculation:
    forecast_probability: float
    market_probability: float
    edge: float  # Percentage edge
    expected_value: float  # EV per dollar wagered
    model_agreement: float  # 0-1 confidence score
    recommended_side: str  # "YES" or "NO"
    confidence_level: str  # "LOW", "MEDIUM", "HIGH"

def calculate_edge(
    forecast_prob: float,
    market_price: float,
    model_agreement: float
) -> EdgeCalculation:
    """
    Calculate trading edge and expected value.
    
    Edge = (Forecast Probability / Market Probability) - 1
    
    Positive edge on YES: forecast_prob > market_price (buy YES)
    Positive edge on NO: forecast_prob < market_price (buy NO, or equivalently, YES is overpriced)
    """
    # Edge on YES side
    if market_price > 0:
        edge_yes = (forecast_prob / market_price) - 1
    else:
        edge_yes = float('inf') if forecast_prob > 0 else 0
    
    # Edge on NO side
    no_market_price = 1 - market_price
    no_forecast_prob = 1 - forecast_prob
    if no_market_price > 0:
        edge_no = (no_forecast_prob / no_market_price) - 1
    else:
        edge_no = float('inf') if no_forecast_prob > 0 else 0
    
    # Determine recommended side
    if edge_yes > edge_no and edge_yes > 0:
        recommended_side = "YES"
        edge = edge_yes
        # EV = (prob_win * payout) - stake, per $1 wagered
        # If we buy YES at market_price, we pay market_price for potential payout of $1
        # EV = forecast_prob * (1 / market_price - 1) = forecast_prob / market_price - forecast_prob
        # Simplified: EV per $1 of potential profit
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
    
    # Confidence level based on model agreement and edge magnitude
    if model_agreement >= 0.8 and edge >= 0.15:
        confidence = "HIGH"
    elif model_agreement >= 0.6 and edge >= 0.08:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"
    
    return EdgeCalculation(
        forecast_probability=forecast_prob,
        market_probability=market_price,
        edge=edge,
        expected_value=ev,
        model_agreement=model_agreement,
        recommended_side=recommended_side,
        confidence_level=confidence
    )
```

### 5.4 Entry Criteria

A trade is executed only when all of the following conditions are met:

```python
ENTRY_CRITERIA = {
    "min_edge": 0.05,  # 5% minimum edge
    "max_edge": 0.50,  # 50% max edge (higher suggests data error)
    "min_model_agreement": 0.60,  # 60% model agreement
    "min_liquidity": 1000,  # $1,000 minimum liquidity
    "min_days_to_resolution": 0.5,  # 12 hours minimum
    "max_days_to_resolution": 7,  # 7 days maximum
    "optimal_days_range": (2, 5),  # Optimal entry window
}

def meets_entry_criteria(
    edge_calc: EdgeCalculation,
    market: WeatherMarketCriteria,
    current_time: datetime
) -> Tuple[bool, str]:
    """
    Check if trade meets all entry criteria.
    
    Returns:
        Tuple of (should_trade: bool, reason: str)
    """
    days_to_resolution = (market.resolution_date - current_time).total_seconds() / 86400
    
    # Edge bounds
    if edge_calc.edge < ENTRY_CRITERIA["min_edge"]:
        return False, f"Edge {edge_calc.edge:.1%} below minimum {ENTRY_CRITERIA['min_edge']:.1%}"
    
    if edge_calc.edge > ENTRY_CRITERIA["max_edge"]:
        return False, f"Edge {edge_calc.edge:.1%} suspiciously high - verify data"
    
    # Model agreement
    if edge_calc.model_agreement < ENTRY_CRITERIA["min_model_agreement"]:
        return False, f"Model agreement {edge_calc.model_agreement:.1%} below threshold"
    
    # Liquidity
    if market.liquidity < ENTRY_CRITERIA["min_liquidity"]:
        return False, f"Liquidity ${market.liquidity:.0f} below minimum"
    
    # Time to resolution
    if days_to_resolution < ENTRY_CRITERIA["min_days_to_resolution"]:
        return False, f"Only {days_to_resolution:.1f} days to resolution - too close"
    
    if days_to_resolution > ENTRY_CRITERIA["max_days_to_resolution"]:
        return False, f"{days_to_resolution:.1f} days to resolution - too far out"
    
    # Recommended side must exist
    if edge_calc.recommended_side is None:
        return False, "No positive edge on either side"
    
    return True, "All criteria met"
```

---

## 6. Position Sizing

### 6.1 Fractional Kelly Criterion

```python
def calculate_kelly_fraction(
    probability: float,
    odds: float
) -> float:
    """
    Calculate full Kelly fraction.
    
    Kelly formula: f* = (bp - q) / b
    
    Where:
        f* = fraction of bankroll to wager
        b = decimal odds - 1 (net profit per unit wagered)
        p = probability of winning
        q = probability of losing (1 - p)
    
    For prediction markets:
        - If buying YES at price P, odds = (1/P) - 1 = (1-P)/P
        - Potential profit per dollar = (1-P)/P dollars
    """
    if probability <= 0 or probability >= 1:
        return 0
    
    q = 1 - probability
    b = odds  # Net odds (profit per unit stake)
    
    kelly = (b * probability - q) / b
    
    # Kelly can be negative (don't bet) or > 1 (leverage)
    # Clamp to [0, 1] for this implementation
    return max(0, min(1, kelly))


def calculate_position_size(
    bankroll: float,
    forecast_prob: float,
    market_price: float,
    side: str,  # "YES" or "NO"
    kelly_fraction: float = 0.25,
    max_position_pct: float = 0.05,
    min_position: float = 1.0,
    max_position: float = 10.0
) -> float:
    """
    Calculate position size using fractional Kelly criterion.
    
    Args:
        bankroll: Total allocated capital
        forecast_prob: Our estimated probability of YES outcome
        market_price: Current YES token price
        side: Which side to bet ("YES" or "NO")
        kelly_fraction: Fraction of Kelly to use (0.25 = quarter Kelly)
        max_position_pct: Maximum position as percentage of bankroll
        min_position: Minimum position size in dollars
        max_position: Maximum position size in dollars
    
    Returns:
        Position size in dollars
    """
    if side == "YES":
        prob = forecast_prob
        price = market_price
    else:
        prob = 1 - forecast_prob
        price = 1 - market_price
    
    # Net odds: potential profit per dollar risked
    # If we pay $0.40 for a contract worth $1 if we win, net odds = (1-0.40)/0.40 = 1.5
    if price <= 0 or price >= 1:
        return 0
    
    net_odds = (1 - price) / price
    
    # Full Kelly
    full_kelly = calculate_kelly_fraction(prob, net_odds)
    
    # Apply Kelly fraction
    position_pct = full_kelly * kelly_fraction
    
    # Apply maximum position constraint
    position_pct = min(position_pct, max_position_pct)
    
    # Calculate dollar amount
    position = bankroll * position_pct
    
    # Apply min/max constraints
    position = max(min_position, min(max_position, position))
    
    # Round to 2 decimal places
    return round(position, 2)
```

### 6.2 Position Sizing Configuration

```python
POSITION_SIZING_CONFIG = {
    "kelly_fraction": 0.25,  # Quarter Kelly (conservative)
    "max_position_pct": 0.05,  # 5% max per trade
    "min_position": 1.0,  # $1 minimum
    "max_position": 10.0,  # $10 maximum (per user specification)
}
```

---

## 7. Diversification Rules

### 7.1 Geographic Cluster Definitions

```python
GEOGRAPHIC_CLUSTERS = {
    "US_NORTHEAST": {
        "cities": ["NYC_LAGUARDIA", "BOSTON_LOGAN", "PHILADELPHIA_INTL", "WASHINGTON_DULLES"],
        "correlation_coefficient": 0.75,  # Estimated correlation within cluster
    },
    "US_SOUTHEAST": {
        "cities": ["MIAMI_INTL", "ATLANTA_HARTSFIELD", "HOUSTON_HOBBY", "NEW_ORLEANS_ARMSTRONG"],
        "correlation_coefficient": 0.70,
    },
    "US_WEST_COAST": {
        "cities": ["LOS_ANGELES_INTL", "SAN_FRANCISCO_INTL", "SEATTLE_TACOMA", "PHOENIX_SKY"],
        "correlation_coefficient": 0.60,
    },
    "WESTERN_EUROPE": {
        "cities": ["LONDON_CITY", "PARIS_CDG", "AMSTERDAM_SCHIPHOL", "FRANKFURT_MAIN"],
        "correlation_coefficient": 0.70,
    },
}

def get_cluster_for_location(location: str) -> Optional[str]:
    """Return cluster name for a given location, or None if independent."""
    for cluster_name, cluster_data in GEOGRAPHIC_CLUSTERS.items():
        if location in cluster_data["cities"]:
            return cluster_name
    return None
```

### 7.2 Diversification Configuration

```python
DIVERSIFICATION_CONFIG = {
    # Maximum total exposure as percentage of bankroll
    "max_total_exposure_pct": 0.75,
    
    # Maximum exposure to any single geographic cluster
    # (as percentage of deployed capital, not total bankroll)
    "max_cluster_exposure_pct": 0.30,
    
    # Maximum exposure to markets resolving on the same day
    # (as percentage of deployed capital)
    "max_same_day_resolution_pct": 0.40,
    
    # Maximum exposure to correlated weather system
    # (as percentage of deployed capital)
    "max_system_correlated_pct": 0.25,
    
    # Minimum number of uncorrelated positions for deployment levels
    "min_positions_for_50_pct": 2,  # Need 2 different clusters for 50% deployment
    "min_positions_for_75_pct": 3,  # Need 3 different clusters for 75% deployment
    
    # Target allocation to non-temperature markets when available
    "target_non_temperature_pct": 0.25,
}
```

### 7.3 Diversification Filter Implementation

```python
@dataclass
class PortfolioState:
    total_exposure: float
    positions: List[Position]
    cluster_exposure: Dict[str, float]
    resolution_date_exposure: Dict[str, float]
    
def check_diversification_limits(
    new_trade: TradeCandidate,
    portfolio: PortfolioState,
    bankroll: float
) -> Tuple[bool, str, float]:
    """
    Check if adding a new trade would violate diversification limits.
    
    Returns:
        Tuple of (allowed: bool, reason: str, max_allowed_size: float)
    """
    config = DIVERSIFICATION_CONFIG
    max_total = bankroll * config["max_total_exposure_pct"]
    
    # Check 1: Total exposure limit
    if portfolio.total_exposure >= max_total:
        return False, "Maximum total exposure reached", 0
    
    remaining_capacity = max_total - portfolio.total_exposure
    max_allowed = min(new_trade.proposed_size, remaining_capacity)
    
    # Check 2: Geographic cluster limit
    cluster = get_cluster_for_location(new_trade.location)
    if cluster:
        deployed_capital = portfolio.total_exposure
        if deployed_capital > 0:
            cluster_limit = deployed_capital * config["max_cluster_exposure_pct"]
            current_cluster_exposure = portfolio.cluster_exposure.get(cluster, 0)
            cluster_remaining = cluster_limit - current_cluster_exposure
            
            if cluster_remaining <= 0:
                return False, f"Cluster {cluster} at maximum exposure", 0
            
            max_allowed = min(max_allowed, cluster_remaining)
    
    # Check 3: Same-day resolution limit
    resolution_date = new_trade.resolution_date.strftime("%Y-%m-%d")
    deployed_capital = portfolio.total_exposure
    if deployed_capital > 0:
        same_day_limit = deployed_capital * config["max_same_day_resolution_pct"]
        current_same_day = portfolio.resolution_date_exposure.get(resolution_date, 0)
        same_day_remaining = same_day_limit - current_same_day
        
        if same_day_remaining <= 0:
            return False, f"Same-day resolution limit reached for {resolution_date}", 0
        
        max_allowed = min(max_allowed, same_day_remaining)
    
    # Check 4: Minimum position count for deployment level
    n_clusters = len(set(
        get_cluster_for_location(p.location) 
        for p in portfolio.positions 
        if get_cluster_for_location(p.location)
    ))
    
    new_exposure = portfolio.total_exposure + max_allowed
    new_exposure_pct = new_exposure / max_total
    
    if new_exposure_pct > 0.50 and n_clusters < config["min_positions_for_50_pct"]:
        # Check if new trade adds a new cluster
        new_cluster = get_cluster_for_location(new_trade.location)
        if new_cluster and new_cluster not in portfolio.cluster_exposure:
            pass  # Adding new cluster is allowed
        else:
            # Cap exposure at 50% until more clusters added
            max_allowed = min(max_allowed, max_total * 0.50 - portfolio.total_exposure)
            if max_allowed <= 0:
                return False, "Need positions in more clusters before increasing exposure", 0
    
    if new_exposure_pct > 0.75 and n_clusters < config["min_positions_for_75_pct"]:
        max_allowed = min(max_allowed, max_total * 0.75 - portfolio.total_exposure)
        if max_allowed <= 0:
            return False, "Need positions in more clusters for full deployment", 0
    
    if max_allowed < 1.0:  # Below minimum position size
        return False, "Remaining capacity below minimum position size", 0
    
    return True, "Diversification check passed", max_allowed
```

---

## 8. Risk Management

### 8.1 Exposure Limits

```python
RISK_LIMITS = {
    # Drawdown-based halts
    "max_daily_loss_pct": 0.10,  # Halt trading after 10% daily loss
    "max_weekly_loss_pct": 0.25,  # Halt trading after 25% weekly loss
    "max_monthly_loss_pct": 0.40,  # Manual review required after 40% monthly loss
    
    # Per-trade limits (redundant with position sizing, but enforced at execution)
    "max_single_trade": 10.0,  # Hard cap per user specification
    "min_single_trade": 1.0,
    
    # Timing-based rules
    "min_hours_before_resolution": 12,  # Don't enter in final 12 hours
    "cooldown_after_loss_minutes": 30,  # Brief pause after significant loss
}
```

### 8.2 Risk Manager Implementation

```python
class RiskManager:
    def __init__(self, config: dict, initial_bankroll: float):
        self.config = config
        self.initial_bankroll = initial_bankroll
        self.daily_pnl = 0.0
        self.weekly_pnl = 0.0
        self.monthly_pnl = 0.0
        self.last_loss_time = None
        self.is_halted = False
        self.halt_reason = None
    
    def update_pnl(self, realized_pnl: float, timestamp: datetime):
        """Update P&L trackers when a position closes."""
        self.daily_pnl += realized_pnl
        self.weekly_pnl += realized_pnl
        self.monthly_pnl += realized_pnl
        
        if realized_pnl < 0:
            self.last_loss_time = timestamp
        
        self._check_halt_conditions()
    
    def reset_daily_pnl(self):
        """Call at start of each trading day."""
        self.daily_pnl = 0.0
    
    def reset_weekly_pnl(self):
        """Call at start of each trading week."""
        self.weekly_pnl = 0.0
    
    def reset_monthly_pnl(self):
        """Call at start of each trading month."""
        self.monthly_pnl = 0.0
    
    def _check_halt_conditions(self):
        """Check if any halt condition is triggered."""
        if self.daily_pnl / self.initial_bankroll < -self.config["max_daily_loss_pct"]:
            self.is_halted = True
            self.halt_reason = f"Daily loss limit breached: {self.daily_pnl:.2f}"
        
        elif self.weekly_pnl / self.initial_bankroll < -self.config["max_weekly_loss_pct"]:
            self.is_halted = True
            self.halt_reason = f"Weekly loss limit breached: {self.weekly_pnl:.2f}"
        
        elif self.monthly_pnl / self.initial_bankroll < -self.config["max_monthly_loss_pct"]:
            self.is_halted = True
            self.halt_reason = f"Monthly loss limit breached: {self.monthly_pnl:.2f}"
    
    def can_trade(self, current_time: datetime) -> Tuple[bool, str]:
        """Check if trading is currently allowed."""
        if self.is_halted:
            return False, self.halt_reason
        
        # Check cooldown after loss
        if self.last_loss_time:
            cooldown_minutes = self.config.get("cooldown_after_loss_minutes", 0)
            if (current_time - self.last_loss_time).total_seconds() < cooldown_minutes * 60:
                return False, f"In cooldown period after loss"
        
        return True, "Trading allowed"
    
    def validate_trade(
        self,
        trade: TradeCandidate,
        current_time: datetime
    ) -> Tuple[bool, str]:
        """Validate a specific trade against risk rules."""
        # Check size limits
        if trade.size > self.config["max_single_trade"]:
            return False, f"Trade size ${trade.size} exceeds max ${self.config['max_single_trade']}"
        
        if trade.size < self.config["min_single_trade"]:
            return False, f"Trade size ${trade.size} below min ${self.config['min_single_trade']}"
        
        # Check time to resolution
        hours_to_resolution = (trade.resolution_date - current_time).total_seconds() / 3600
        if hours_to_resolution < self.config["min_hours_before_resolution"]:
            return False, f"Only {hours_to_resolution:.1f} hours to resolution"
        
        return True, "Trade validated"
```

### 8.3 Automatic Recovery

```python
def check_auto_recovery(risk_manager: RiskManager, current_time: datetime) -> bool:
    """
    Check if halt conditions have cleared and trading can resume.
    
    Auto-recovery rules:
    - Daily halt: Clears at start of next trading day
    - Weekly halt: Clears at start of next trading week
    - Monthly halt: Requires manual intervention (no auto-recovery)
    """
    if not risk_manager.is_halted:
        return True
    
    if "Daily" in risk_manager.halt_reason:
        # Check if new day
        # Implementation depends on tracking halt timestamp
        pass
    
    if "Weekly" in risk_manager.halt_reason:
        # Check if new week
        pass
    
    if "Monthly" in risk_manager.halt_reason:
        # No auto-recovery for monthly halt
        return False
    
    return False
```

---

## 9. Execution Logic

### 9.1 Polymarket CLOB Client Setup

```python
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, OrderType

class PolymarketExecutor:
    def __init__(
        self,
        private_key: str,
        wallet_address: str,
        chain_id: int = 137  # Polygon mainnet
    ):
        self.client = ClobClient(
            host="https://clob.polymarket.com",
            key=private_key,
            chain_id=chain_id,
            signature_type=0,  # EOA wallet
            funder=wallet_address
        )
        
        # Derive or create API credentials
        self.api_creds = self.client.create_or_derive_api_creds()
        self.client.set_api_creds(self.api_creds)
    
    def get_midpoint(self, token_id: str) -> Optional[float]:
        """Get current midpoint price for a token."""
        try:
            response = self.client.get_midpoint(token_id)
            return float(response.get("mid", 0))
        except Exception as e:
            logging.error(f"Error fetching midpoint for {token_id}: {e}")
            return None
    
    def get_order_book(self, token_id: str) -> dict:
        """Get full order book."""
        try:
            return self.client.get_order_book(token_id)
        except Exception as e:
            logging.error(f"Error fetching order book for {token_id}: {e}")
            return {"bids": [], "asks": []}
    
    def place_limit_order(
        self,
        token_id: str,
        side: str,  # "BUY" or "SELL"
        price: float,
        size: float
    ) -> Optional[str]:
        """
        Place a limit order.
        
        Returns order_id if successful, None if failed.
        """
        try:
            order_args = OrderArgs(
                token_id=token_id,
                price=price,
                size=size,
                side=side,
                fee_rate_bps=0,  # No fees on Polymarket
            )
            
            signed_order = self.client.create_order(order_args)
            response = self.client.post_order(signed_order, OrderType.GTC)
            
            return response.get("orderID")
        
        except Exception as e:
            logging.error(f"Error placing order: {e}")
            return None
    
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an existing order."""
        try:
            self.client.cancel(order_id)
            return True
        except Exception as e:
            logging.error(f"Error canceling order {order_id}: {e}")
            return False
    
    def get_open_orders(self, market_id: Optional[str] = None) -> List[dict]:
        """Get all open orders, optionally filtered by market."""
        try:
            return self.client.get_orders(market=market_id)
        except Exception as e:
            logging.error(f"Error fetching orders: {e}")
            return []
    
    def get_positions(self) -> List[dict]:
        """Get current positions."""
        try:
            return self.client.get_positions()
        except Exception as e:
            logging.error(f"Error fetching positions: {e}")
            return []
```

### 9.2 Order Execution Strategy

```python
def execute_trade(
    executor: PolymarketExecutor,
    market: WeatherMarketCriteria,
    side: str,
    size: float,
    max_slippage_pct: float = 0.02
) -> Optional[str]:
    """
    Execute a trade with slippage protection.
    
    Strategy:
    1. Get current midpoint
    2. Place limit order at midpoint (or slightly better)
    3. If not filled within timeout, adjust price toward market
    4. Cancel if slippage exceeds limit
    """
    token_id = market.token_id_yes if side == "YES" else market.token_id_no
    
    # Get current pricing
    midpoint = executor.get_midpoint(token_id)
    if midpoint is None:
        logging.error("Could not get midpoint price")
        return None
    
    # For buying, we want to pay at or below midpoint
    # For selling, we want to receive at or above midpoint
    if side == "BUY":
        initial_price = midpoint
        max_price = midpoint * (1 + max_slippage_pct)
    else:
        initial_price = midpoint
        min_price = midpoint * (1 - max_slippage_pct)
    
    # Place initial order at midpoint
    order_id = executor.place_limit_order(
        token_id=token_id,
        side="BUY",  # Always buying tokens (YES or NO tokens)
        price=round(initial_price, 4),
        size=size
    )
    
    if order_id is None:
        logging.error("Failed to place initial order")
        return None
    
    logging.info(f"Placed order {order_id}: {side} {size} @ {initial_price}")
    
    return order_id
```

### 9.3 Order Monitoring and Fill Detection

```python
import asyncio

async def monitor_order_fill(
    executor: PolymarketExecutor,
    order_id: str,
    timeout_seconds: int = 300,
    check_interval: int = 10
) -> Tuple[bool, float]:
    """
    Monitor an order until filled, canceled, or timeout.
    
    Returns:
        Tuple of (is_filled: bool, filled_amount: float)
    """
    start_time = asyncio.get_event_loop().time()
    
    while True:
        elapsed = asyncio.get_event_loop().time() - start_time
        if elapsed > timeout_seconds:
            logging.warning(f"Order {order_id} timed out after {timeout_seconds}s")
            executor.cancel_order(order_id)
            return False, 0.0
        
        # Check order status
        orders = executor.get_open_orders()
        order = next((o for o in orders if o.get("id") == order_id), None)
        
        if order is None:
            # Order no longer open - either filled or canceled
            # Check positions to confirm fill
            # This is simplified; production code should query trade history
            logging.info(f"Order {order_id} no longer open - assuming filled")
            return True, 0.0  # Would need to track actual fill amount
        
        filled_amount = float(order.get("sizeFilled", 0))
        if filled_amount > 0:
            logging.info(f"Order {order_id} partially filled: {filled_amount}")
        
        await asyncio.sleep(check_interval)
```

---

## 10. Main Event Loop

### 10.1 Core Loop Structure

```python
import asyncio
import schedule
from datetime import datetime, timedelta

class WeatherTradingBot:
    def __init__(self, config: dict):
        self.config = config
        self.bankroll = config["initial_bankroll"]
        
        # Initialize components
        self.weather_client = OpenMeteoClient()
        self.market_client = GammaAPIClient()
        self.executor = PolymarketExecutor(
            private_key=config["private_key"],
            wallet_address=config["wallet_address"]
        )
        self.risk_manager = RiskManager(
            config=RISK_LIMITS,
            initial_bankroll=self.bankroll
        )
        self.portfolio = PortfolioState(
            total_exposure=0,
            positions=[],
            cluster_exposure={},
            resolution_date_exposure={}
        )
        
        # State tracking
        self.active_markets: Dict[str, WeatherMarketCriteria] = {}
        self.forecasts: Dict[str, ForecastData] = {}
        self.pending_orders: Dict[str, Order] = {}
    
    async def run(self):
        """Main event loop."""
        logging.info("Starting Weather Trading Bot")
        
        # Schedule periodic tasks
        schedule.every(15).minutes.do(self.discover_markets)
        schedule.every(6).hours.do(self.update_forecasts)
        schedule.every(1).minutes.do(self.check_opportunities)
        schedule.every(5).minutes.do(self.update_portfolio)
        schedule.every(1).hours.do(self.log_status)
        
        # Daily/weekly resets
        schedule.every().day.at("00:00").do(self.risk_manager.reset_daily_pnl)
        schedule.every().monday.at("00:00").do(self.risk_manager.reset_weekly_pnl)
        
        # Initial data load
        await self.discover_markets()
        await self.update_forecasts()
        
        # Main loop
        while True:
            schedule.run_pending()
            await asyncio.sleep(1)
    
    async def discover_markets(self):
        """Discover and parse active weather markets."""
        logging.info("Discovering weather markets...")
        
        raw_markets = await self.market_client.get_active_markets(tag="climate-science")
        
        for market in raw_markets:
            parsed = parse_market_criteria(market)
            if parsed and self._is_tradeable_timeframe(parsed):
                self.active_markets[parsed.market_id] = parsed
        
        logging.info(f"Found {len(self.active_markets)} tradeable weather markets")
    
    async def update_forecasts(self):
        """Fetch latest ensemble forecasts for all active markets."""
        logging.info("Updating forecasts...")
        
        for market_id, market in self.active_markets.items():
            try:
                forecast = await self.weather_client.get_ensemble_forecast(
                    latitude=market.station.latitude,
                    longitude=market.station.longitude,
                    target_date=market.resolution_date,
                    variable=market.variable
                )
                self.forecasts[market_id] = forecast
            except Exception as e:
                logging.error(f"Error fetching forecast for {market_id}: {e}")
        
        logging.info(f"Updated forecasts for {len(self.forecasts)} markets")
    
    async def check_opportunities(self):
        """Scan for trading opportunities."""
        current_time = datetime.utcnow()
        
        # Check if trading is allowed
        can_trade, reason = self.risk_manager.can_trade(current_time)
        if not can_trade:
            logging.warning(f"Trading halted: {reason}")
            return
        
        for market_id, market in self.active_markets.items():
            try:
                await self._evaluate_market(market, current_time)
            except Exception as e:
                logging.error(f"Error evaluating market {market_id}: {e}")
    
    async def _evaluate_market(self, market: WeatherMarketCriteria, current_time: datetime):
        """Evaluate a single market for trading opportunity."""
        # Get forecast
        forecast = self.forecasts.get(market.market_id)
        if not forecast:
            return
        
        # Calculate forecast probability
        ensemble_values = self._extract_ensemble_values(forecast, market)
        if not ensemble_values:
            return
        
        forecast_prob, model_agreement = self._calculate_probability(
            ensemble_values, market.threshold, market.comparison
        )
        
        # Get market price
        market_price = self.executor.get_midpoint(market.token_id_yes)
        if market_price is None:
            return
        
        # Calculate edge
        edge_calc = calculate_edge(forecast_prob, market_price, model_agreement)
        
        # Check entry criteria
        should_trade, reason = meets_entry_criteria(edge_calc, market, current_time)
        if not should_trade:
            logging.debug(f"Market {market.market_id}: {reason}")
            return
        
        # Check diversification
        trade_candidate = TradeCandidate(
            market=market,
            side=edge_calc.recommended_side,
            proposed_size=POSITION_SIZING_CONFIG["max_position"],
            resolution_date=market.resolution_date,
            location=market.location
        )
        
        allowed, div_reason, max_size = check_diversification_limits(
            trade_candidate, self.portfolio, self.bankroll
        )
        if not allowed:
            logging.debug(f"Market {market.market_id}: {div_reason}")
            return
        
        # Calculate position size
        position_size = calculate_position_size(
            bankroll=self.bankroll,
            forecast_prob=forecast_prob,
            market_price=market_price,
            side=edge_calc.recommended_side,
            **POSITION_SIZING_CONFIG
        )
        
        position_size = min(position_size, max_size)
        
        # Validate with risk manager
        trade_candidate.size = position_size
        valid, risk_reason = self.risk_manager.validate_trade(trade_candidate, current_time)
        if not valid:
            logging.debug(f"Market {market.market_id}: {risk_reason}")
            return
        
        # Execute trade
        logging.info(
            f"TRADE SIGNAL: {market.market_id} | "
            f"Side: {edge_calc.recommended_side} | "
            f"Size: ${position_size:.2f} | "
            f"Edge: {edge_calc.edge:.1%} | "
            f"Forecast: {forecast_prob:.1%} vs Market: {market_price:.1%}"
        )
        
        order_id = await execute_trade(
            executor=self.executor,
            market=market,
            side=edge_calc.recommended_side,
            size=position_size
        )
        
        if order_id:
            self.pending_orders[order_id] = trade_candidate
            await self._update_portfolio_exposure(trade_candidate)
    
    def _is_tradeable_timeframe(self, market: WeatherMarketCriteria) -> bool:
        """Check if market is within tradeable timeframe."""
        days_to_resolution = (market.resolution_date - datetime.utcnow()).days
        return 0 < days_to_resolution <= 7
    
    async def update_portfolio(self):
        """Update portfolio state from exchange."""
        positions = self.executor.get_positions()
        # Update self.portfolio with current positions
        # Recalculate exposure by cluster and resolution date
        pass
    
    def log_status(self):
        """Log current bot status."""
        logging.info(
            f"STATUS | Bankroll: ${self.bankroll:.2f} | "
            f"Exposure: ${self.portfolio.total_exposure:.2f} | "
            f"Daily P&L: ${self.risk_manager.daily_pnl:.2f} | "
            f"Active Markets: {len(self.active_markets)} | "
            f"Open Positions: {len(self.portfolio.positions)}"
        )
```

### 10.2 Entry Point

```python
# main.py

import asyncio
import logging
import os
from dotenv import load_dotenv

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)s | %(message)s',
        handlers=[
            logging.FileHandler('trading_bot.log'),
            logging.StreamHandler()
        ]
    )

def load_config() -> dict:
    load_dotenv()
    
    return {
        "initial_bankroll": float(os.getenv("INITIAL_BANKROLL", 100)),
        "private_key": os.getenv("PRIVATE_KEY"),
        "wallet_address": os.getenv("WALLET_ADDRESS"),
        # Add other config from environment
    }

async def main():
    setup_logging()
    config = load_config()
    
    # Validate required config
    if not config["private_key"] or not config["wallet_address"]:
        logging.error("Missing required configuration: PRIVATE_KEY, WALLET_ADDRESS")
        return
    
    bot = WeatherTradingBot(config)
    await bot.run()

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 11. Configuration Summary

### 11.1 Master Configuration File

```python
# config.py

MASTER_CONFIG = {
    # === STRATEGY PARAMETERS ===
    "strategy": {
        "min_edge": 0.05,
        "max_edge": 0.50,
        "min_model_agreement": 0.60,
        "min_liquidity": 1000,
        "min_days_to_resolution": 0.5,
        "max_days_to_resolution": 7,
        "optimal_days_range": (2, 5),
    },
    
    # === POSITION SIZING ===
    "position_sizing": {
        "kelly_fraction": 0.25,
        "max_position_pct": 0.05,
        "min_position": 1.0,
        "max_position": 10.0,
    },
    
    # === DIVERSIFICATION ===
    "diversification": {
        "max_total_exposure_pct": 0.75,
        "max_cluster_exposure_pct": 0.30,
        "max_same_day_resolution_pct": 0.40,
        "max_system_correlated_pct": 0.25,
        "min_positions_for_50_pct": 2,
        "min_positions_for_75_pct": 3,
        "target_non_temperature_pct": 0.25,
    },
    
    # === RISK MANAGEMENT ===
    "risk": {
        "max_daily_loss_pct": 0.10,
        "max_weekly_loss_pct": 0.25,
        "max_monthly_loss_pct": 0.40,
        "min_hours_before_resolution": 12,
        "cooldown_after_loss_minutes": 30,
    },
    
    # === DATA SOURCES ===
    "data": {
        "forecast_models": ["gfs_seamless", "ecmwf_ifs025", "icon_seamless"],
        "forecast_update_hours": 6,
        "market_scan_minutes": 15,
        "price_check_seconds": 60,
    },
    
    # === EXECUTION ===
    "execution": {
        "max_slippage_pct": 0.02,
        "order_timeout_seconds": 300,
        "order_check_interval": 10,
    },
    
    # === GEOGRAPHIC CLUSTERS ===
    "clusters": {
        "US_NORTHEAST": ["NYC_LAGUARDIA", "BOSTON_LOGAN", "PHILADELPHIA_INTL", "WASHINGTON_DULLES"],
        "US_SOUTHEAST": ["MIAMI_INTL", "ATLANTA_HARTSFIELD", "HOUSTON_HOBBY", "NEW_ORLEANS_ARMSTRONG"],
        "US_WEST_COAST": ["LOS_ANGELES_INTL", "SAN_FRANCISCO_INTL", "SEATTLE_TACOMA", "PHOENIX_SKY"],
        "WESTERN_EUROPE": ["LONDON_CITY", "PARIS_CDG", "AMSTERDAM_SCHIPHOL", "FRANKFURT_MAIN"],
    },
}
```

### 11.2 Environment Variables

```bash
# .env file

# Required
PRIVATE_KEY=0x...your_wallet_private_key...
WALLET_ADDRESS=0x...your_wallet_address...

# Optional (with defaults)
INITIAL_BANKROLL=100
LOG_LEVEL=INFO
POLYGON_RPC_URL=https://polygon-rpc.com

# Alert notifications (optional)
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
```

---

## 12. Implementation Phases

### Phase 1: Infrastructure (Week 1)

| Task | Priority | Complexity |
|------|----------|------------|
| Set up Python project structure | High | Low |
| Implement Open-Meteo API client | High | Medium |
| Implement Gamma API client | High | Medium |
| Implement CLOB API authentication | High | High |
| Create SQLite database schema | Medium | Low |
| Set up logging infrastructure | Medium | Low |

### Phase 2: Strategy Core (Week 2)

| Task | Priority | Complexity |
|------|----------|------------|
| Build market parser for weather markets | High | High |
| Implement ensemble probability calculator | High | Medium |
| Build edge calculation module | High | Medium |
| Implement Kelly position sizer | High | Medium |
| Create diversification filter | High | High |
| Build risk manager | High | Medium |

### Phase 3: Execution (Week 3)

| Task | Priority | Complexity |
|------|----------|------------|
| Implement order placement | High | Medium |
| Build order monitoring | High | Medium |
| Create position tracker | High | Medium |
| Implement P&L calculator | Medium | Medium |
| Build WebSocket price feed | Medium | High |

### Phase 4: Integration (Week 4)

| Task | Priority | Complexity |
|------|----------|------------|
| Integrate main event loop | High | High |
| Add alert notifications | Medium | Low |
| Implement graceful shutdown | Medium | Medium |
| Add health monitoring | Medium | Medium |
| Create admin CLI | Low | Medium |

### Phase 5: Testing & Refinement (Week 5+)

| Task | Priority | Complexity |
|------|----------|------------|
| Unit tests for all modules | High | Medium |
| Integration tests | High | High |
| Paper trading mode | High | Medium |
| Backtest framework | Medium | High |
| Performance optimization | Medium | Medium |
| Documentation | Medium | Low |

---

## 13. Appendices

### Appendix A: Weather Station Database

```python
WEATHER_STATIONS = {
    "NYC_LAGUARDIA": {
        "station_id": "KLGA",
        "name": "LaGuardia Airport",
        "latitude": 40.7769,
        "longitude": -73.8740,
        "elevation_m": 6,
        "timezone": "America/New_York",
        "resolution_source": "Weather Underground",
        "cluster": "US_NORTHEAST"
    },
    "BOSTON_LOGAN": {
        "station_id": "KBOS",
        "name": "Boston Logan International",
        "latitude": 42.3656,
        "longitude": -71.0096,
        "elevation_m": 6,
        "timezone": "America/New_York",
        "resolution_source": "Weather Underground",
        "cluster": "US_NORTHEAST"
    },
    "MIAMI_INTL": {
        "station_id": "KMIA",
        "name": "Miami International Airport",
        "latitude": 25.7959,
        "longitude": -80.2870,
        "elevation_m": 3,
        "timezone": "America/New_York",
        "resolution_source": "Weather Underground",
        "cluster": "US_SOUTHEAST"
    },
    "LONDON_CITY": {
        "station_id": "EGLC",
        "name": "London City Airport",
        "latitude": 51.5053,
        "longitude": 0.0553,
        "elevation_m": 5,
        "timezone": "Europe/London",
        "resolution_source": "Weather Underground",
        "cluster": "WESTERN_EUROPE"
    },
    # Add additional stations as needed
}
```

### Appendix B: API Endpoint Reference

| Service | Endpoint | Rate Limit | Auth |
|---------|----------|------------|------|
| Open-Meteo Ensemble | `api.open-meteo.com/v1/ensemble` | Reasonable use | None |
| Open-Meteo Historical | `archive-api.open-meteo.com/v1/archive` | Reasonable use | None |
| Polymarket Gamma | `gamma-api.polymarket.com/markets` | 12.5 req/sec | None |
| Polymarket CLOB | `clob.polymarket.com/*` | 40 req/sec | EIP-712 |
| Polymarket WS | `ws-subscriptions-clob.polymarket.com` | 500 instruments | None |
| NOAA NBM | `s3://noaa-nbm-pds/` | Unlimited | None |

### Appendix C: Error Codes and Handling

| Error | Cause | Action |
|-------|-------|--------|
| `INSUFFICIENT_BALANCE` | Not enough USDC | Halt trading, alert |
| `ORDER_REJECTED` | Invalid order params | Log, skip market |
| `RATE_LIMITED` | Too many requests | Exponential backoff |
| `MARKET_CLOSED` | Market resolved | Remove from active list |
| `FORECAST_UNAVAILABLE` | API error | Use cached/skip |
| `PARSE_ERROR` | Malformed market | Log, skip market |

### Appendix D: Glossary

| Term | Definition |
|------|------------|
| **Edge** | Percentage advantage of forecast probability over market price |
| **Ensemble** | Multiple model runs with perturbed initial conditions |
| **Exceedance Probability** | P(X >= threshold) from forecast distribution |
| **Kelly Criterion** | Optimal bet sizing formula maximizing log-growth |
| **Midpoint** | Average of best bid and ask prices |
| **NBM** | National Blend of Models (NOAA probabilistic product) |
| **Token ID** | Unique identifier for YES/NO contract on Polymarket |
| **USDC** | USD Coin stablecoin used for Polymarket settlement |

---

## 14. Document Control

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | January 2026 | Strategy Team | Initial specification |

---

**END OF SPECIFICATION**

This document contains proprietary trading strategy information. Implementation should be conducted with appropriate risk management and regulatory compliance considerations.
