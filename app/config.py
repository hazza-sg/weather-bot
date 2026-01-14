"""Configuration management for Weather Trader."""
import os
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Wallet Configuration
    private_key: Optional[str] = Field(default=None, alias="PRIVATE_KEY")
    wallet_address: Optional[str] = Field(default=None, alias="WALLET_ADDRESS")

    # Server Configuration
    server_host: str = Field(default="127.0.0.1", alias="SERVER_HOST")
    server_port: int = Field(default=8741, alias="SERVER_PORT")

    # Trading Configuration
    initial_bankroll: float = Field(default=100.0, alias="INITIAL_BANKROLL")
    test_mode: bool = Field(default=False, alias="WEATHER_TRADER_TEST_MODE")

    # Logging
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # Polygon RPC
    polygon_rpc_url: str = Field(
        default="https://polygon-rpc.com",
        alias="POLYGON_RPC_URL"
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


# Strategy Parameters
STRATEGY_CONFIG = {
    "min_edge": 0.05,
    "max_edge": 0.50,
    "min_model_agreement": 0.60,
    "min_liquidity": 1000,
    "min_days_to_resolution": 0.5,
    "max_days_to_resolution": 7,
    "optimal_days_range": (2, 5),
}

# Position Sizing Configuration
POSITION_SIZING_CONFIG = {
    "kelly_fraction": 0.25,
    "max_position_pct": 0.05,
    "min_position": 1.0,
    "max_position": 10.0,
}

# Diversification Configuration
DIVERSIFICATION_CONFIG = {
    "max_total_exposure_pct": 0.75,
    "max_cluster_exposure_pct": 0.30,
    "max_same_day_resolution_pct": 0.40,
    "max_system_correlated_pct": 0.25,
    "min_positions_for_50_pct": 2,
    "min_positions_for_75_pct": 3,
    "target_non_temperature_pct": 0.25,
}

# Risk Management Configuration
RISK_LIMITS = {
    "max_daily_loss_pct": 0.10,
    "max_weekly_loss_pct": 0.25,
    "max_monthly_loss_pct": 0.40,
    "max_single_trade": 10.0,
    "min_single_trade": 1.0,
    "min_hours_before_resolution": 12,
    "cooldown_after_loss_minutes": 30,
}

# Data Source Configuration
DATA_CONFIG = {
    "forecast_models": ["gfs_seamless", "ecmwf_ifs025", "icon_seamless"],
    "forecast_update_hours": 6,
    "market_scan_minutes": 15,
    "price_check_seconds": 60,
}

# Execution Configuration
EXECUTION_CONFIG = {
    "max_slippage_pct": 0.02,
    "order_timeout_seconds": 300,
    "order_check_interval": 10,
}

# Geographic Clusters
GEOGRAPHIC_CLUSTERS: Dict[str, Dict[str, Any]] = {
    "US_NORTHEAST": {
        "cities": ["NYC_LAGUARDIA", "BOSTON_LOGAN", "PHILADELPHIA_INTL", "WASHINGTON_DULLES"],
        "correlation_coefficient": 0.75,
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

# Weather Station Database
WEATHER_STATIONS: Dict[str, Dict[str, Any]] = {
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
    "LOS_ANGELES_INTL": {
        "station_id": "KLAX",
        "name": "Los Angeles International Airport",
        "latitude": 33.9425,
        "longitude": -118.4081,
        "elevation_m": 38,
        "timezone": "America/Los_Angeles",
        "resolution_source": "Weather Underground",
        "cluster": "US_WEST_COAST"
    },
}

# City name aliases for parsing
CITY_ALIASES: Dict[str, str] = {
    "NYC": "NYC_LAGUARDIA",
    "New York": "NYC_LAGUARDIA",
    "New York City": "NYC_LAGUARDIA",
    "Manhattan": "NYC_LAGUARDIA",
    "London": "LONDON_CITY",
    "Miami": "MIAMI_INTL",
    "Los Angeles": "LOS_ANGELES_INTL",
    "LA": "LOS_ANGELES_INTL",
    "Boston": "BOSTON_LOGAN",
}


def get_settings() -> Settings:
    """Get application settings."""
    return Settings()


def get_data_dir() -> Path:
    """Get the application data directory."""
    if os.name == "posix":
        data_dir = Path.home() / "Library" / "Application Support" / "WeatherTrader"
    else:
        data_dir = Path.home() / ".weathertrader"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def get_log_dir() -> Path:
    """Get the application log directory."""
    if os.name == "posix":
        log_dir = Path.home() / "Library" / "Logs" / "WeatherTrader"
    else:
        log_dir = get_data_dir() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir
