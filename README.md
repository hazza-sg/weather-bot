# Weather Trader

Automated Polymarket weather prediction market trading application with a local GUI.

## Overview

Weather Trader is a fully automated trading system that exploits pricing inefficiencies in Polymarket's short-term weather prediction markets by comparing ensemble weather forecast probabilities against market-implied probabilities.

## Features

- **Automated Trading**: Discovers weather markets, calculates forecast probabilities, and executes trades when edge exists
- **Local Web Dashboard**: Full-featured GUI accessible at `localhost:8741`
- **macOS Application**: Native app bundle with menu bar integration
- **Risk Management**: Configurable exposure limits, drawdown halts, and diversification rules
- **Real-time Updates**: WebSocket-based live price and position updates

## Quick Start

### Development Mode

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

2. Install frontend dependencies:
```bash
cd frontend
npm install
cd ..
```

3. Start the backend:
```bash
python -m uvicorn app.main:app --reload --port 8741
```

4. In a separate terminal, start the frontend:
```bash
cd frontend
npm run dev
```

5. Open http://localhost:3000 in your browser

### Production Build (macOS)

1. Run the build script:
```bash
./scripts/build_macos.sh
```

2. The application will be created at `dist/WeatherTrader.app`

3. Optionally create a DMG installer:
```bash
./scripts/create_dmg.sh
```

## Configuration

Create a `.env` file based on `.env.example`:

```bash
cp .env.example .env
```

Required settings:
- `PRIVATE_KEY`: Your Polygon wallet private key
- `WALLET_ADDRESS`: Your wallet address

Optional settings:
- `INITIAL_BANKROLL`: Starting balance for position sizing calculations
- `LOG_LEVEL`: Logging verbosity (DEBUG, INFO, WARNING, ERROR)

## Architecture

```
weather-bot/
├── app/                    # FastAPI backend
│   ├── api/               # REST API routes
│   ├── models/            # Database and API models
│   └── services/          # Trading engine
├── data/                   # Data layer clients
│   ├── weather_client.py  # Open-Meteo API
│   └── market_client.py   # Polymarket Gamma API
├── execution/             # Order execution
│   └── clob_client.py     # Polymarket CLOB wrapper
├── frontend/              # React dashboard
│   └── src/
│       ├── components/    # UI components
│       └── store/         # State management
├── macos/                 # macOS integration
│   ├── menubar.py        # Menu bar controller
│   └── setup.py          # py2app configuration
└── scripts/               # Build scripts
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/status` | GET | System status |
| `/api/v1/portfolio/summary` | GET | Portfolio overview |
| `/api/v1/markets` | GET | Monitored markets |
| `/api/v1/trades` | GET | Trade history |
| `/api/v1/risk/status` | GET | Risk metrics |
| `/ws` | WebSocket | Real-time updates |

## Trading Strategy

The system implements a weather forecasting edge strategy:

1. **Market Discovery**: Scans Polymarket for active weather markets
2. **Forecast Retrieval**: Fetches ensemble forecasts from Open-Meteo
3. **Probability Calculation**: Converts ensemble members to threshold probabilities
4. **Edge Detection**: Compares forecast probability to market price
5. **Position Sizing**: Uses fractional Kelly criterion
6. **Risk Management**: Enforces exposure and diversification limits

## License

Proprietary - see specification documents for details.
