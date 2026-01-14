# Polymarket Weather Trading Strategy: GUI Specification Addendum

**Version:** 1.0  
**Date:** January 2026  
**Purpose:** Local web dashboard specification for non-technical end users  
**Companion Document:** polymarket_weather_trading_strategy_spec.md  
**Target Platform:** macOS (Apple Silicon M1/M2/M3)

---

## 1. Executive Summary

### 1.1 Objective

Provide a graphical user interface for the Polymarket Weather Trading Strategy that enables complete operation, monitoring, and control without any command-line interaction. The interface must be accessible to users with zero coding experience while providing professional-grade visibility into trading operations.

### 1.2 Design Philosophy

The GUI follows three guiding principles. First, the user should never need to open Terminal.app or type commands. Second, all system state should be visible at a glance. Third, critical actions (start, stop, emergency halt) should require no more than one click.

### 1.3 Architecture Decision

The implementation uses a local web dashboard architecture consisting of a FastAPI backend serving a React frontend, packaged as a native macOS application using py2app. The user experience mirrors a standard macOS application: double-click to launch, interact through a browser window, quit from the menu bar.

---

## 2. System Architecture

### 2.1 Component Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         WEATHER TRADER APPLICATION                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                        macOS Application Shell                       │    │
│  │  (py2app bundle - WeatherTrader.app)                                │    │
│  │                                                                      │    │
│  │  ┌─────────────┐    ┌─────────────┐    ┌─────────────────────────┐  │    │
│  │  │ Menu Bar    │    │ Process     │    │ Browser                 │  │    │
│  │  │ Controller  │◄──►│ Manager     │◄──►│ Launcher                │  │    │
│  │  └─────────────┘    └─────────────┘    └─────────────────────────┘  │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                    │                                         │
│                                    ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                           Backend Server                             │    │
│  │  (FastAPI on localhost:8741)                                        │    │
│  │                                                                      │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌────────────────────────────┐ │    │
│  │  │ REST API     │  │ WebSocket    │  │ Trading Engine             │ │    │
│  │  │ Endpoints    │  │ Server       │  │ (from main spec)           │ │    │
│  │  └──────────────┘  └──────────────┘  └────────────────────────────┘ │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                    │                                         │
│                                    ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                         Frontend Dashboard                           │    │
│  │  (React SPA served at localhost:8741)                               │    │
│  │                                                                      │    │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────┐  │    │
│  │  │ Overview │ │ Markets  │ │Positions │ │ History  │ │ Settings  │  │    │
│  │  │ Panel    │ │ Panel    │ │ Panel    │ │ Panel    │ │ Panel     │  │    │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └───────────┘  │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Technology Stack

| Layer | Technology | Justification |
|-------|------------|---------------|
| Application Shell | py2app | Native macOS bundling for Python applications |
| Backend Framework | FastAPI 0.109+ | Async support, automatic OpenAPI docs, WebSocket native |
| Frontend Framework | React 18+ | Component-based, extensive ecosystem, Claude Code proficiency |
| UI Component Library | Tailwind CSS + shadcn/ui | Professional appearance, rapid development |
| Charts | Recharts | React-native, declarative, responsive |
| State Management | Zustand | Lightweight, minimal boilerplate |
| Real-time Updates | WebSocket | Native browser support, low latency |
| Data Persistence | SQLite | Local file, no external database server |
| Process Management | rumps | macOS menu bar integration |

### 2.3 Port Selection

The application uses port 8741 by default, selected to avoid conflicts with common development servers (3000, 5000, 8000, 8080). The port is configurable through the Settings panel if conflicts arise.

---

## 3. User Experience Specification

### 3.1 Application Lifecycle

**First Launch:**

1. User double-clicks WeatherTrader.app in Applications folder
2. macOS security prompt appears (first time only): "WeatherTrader.app is from an identified developer. Are you sure you want to open it?"
3. User clicks "Open"
4. Setup Wizard appears in browser (see Section 3.2)
5. User completes wallet configuration
6. Dashboard becomes available

**Subsequent Launches:**

1. User double-clicks WeatherTrader.app
2. Menu bar icon appears (small weather/chart icon)
3. Default browser opens to http://localhost:8741
4. Dashboard displays with current state

**Shutdown:**

1. User clicks menu bar icon
2. Dropdown menu appears with options: "Open Dashboard", "Pause Trading", "Quit"
3. User clicks "Quit"
4. Confirmation dialog: "Stop trading and quit? Open positions will remain until resolution."
5. User confirms
6. Application terminates gracefully

### 3.2 First-Time Setup Wizard

The setup wizard guides users through initial configuration without requiring technical knowledge.

**Step 1: Welcome**
- Brief explanation of the application
- "Next" button

**Step 2: Wallet Connection**
- Two options presented:
  - Option A: "I have a Polymarket account" → Instructions to export private key from existing wallet
  - Option B: "Create new wallet" → Generates new wallet, displays address for USDC funding
- Input field for private key (masked, with show/hide toggle)
- Validation indicator (green checkmark when valid format detected)

**Step 3: Initial Funding**
- Display wallet address with copy button
- QR code for mobile wallet transfers
- Explanation: "Send USDC (Polygon network) to this address to fund your trading account"
- Balance checker that refreshes every 10 seconds
- "Continue" button activates when balance > $10 detected

**Step 4: Risk Configuration**
- Slider: "How much of your balance should be available for trading?" (default: 100%)
- Explanation of the 75% maximum exposure rule
- Slider: "Maximum loss before pausing (daily)" (default: 10%)
- Simple language, no jargon

**Step 5: Confirmation**
- Summary of all settings
- "Start Trading" button
- Checkbox: "Start in Paused mode (monitor only)"

### 3.3 Menu Bar Integration

The menu bar icon provides quick access without opening the full dashboard.

**Menu Bar Icon States:**

| Icon State | Meaning |
|------------|---------|
| Green dot | Trading active, no issues |
| Yellow dot | Trading paused |
| Red dot | Error or halt condition |
| Pulsing | Trade executing |

**Dropdown Menu Items:**

```
┌──────────────────────────┐
│ WeatherTrader            │
├──────────────────────────┤
│ ● Trading Active         │
│                          │
│ Bankroll: $247.50        │
│ Today's P&L: +$12.30     │
│ Open Positions: 3        │
├──────────────────────────┤
│ Open Dashboard      ⌘D   │
│ Pause Trading       ⌘P   │
│ Emergency Stop      ⌘E   │
├──────────────────────────┤
│ Quit WeatherTrader  ⌘Q   │
└──────────────────────────┘
```

---

## 4. Dashboard Interface Specification

### 4.1 Navigation Structure

The dashboard uses a sidebar navigation pattern with the following sections:

```
┌─────────┬────────────────────────────────────────────────────────────────┐
│         │                                                                │
│ [Logo]  │  Header: Current Time | System Status | Quick Actions          │
│         │                                                                │
├─────────┼────────────────────────────────────────────────────────────────┤
│         │                                                                │
│ Overview│                                                                │
│         │                                                                │
│ Markets │                        Main Content Area                       │
│         │                                                                │
│Positions│                   (Changes based on selected                   │
│         │                         navigation item)                       │
│ History │                                                                │
│         │                                                                │
│  Risk   │                                                                │
│         │                                                                │
│ Settings│                                                                │
│         │                                                                │
│         │                                                                │
├─────────┼────────────────────────────────────────────────────────────────┤
│         │  Footer: Connection Status | Last Update | Version             │
└─────────┴────────────────────────────────────────────────────────────────┘
```

### 4.2 Overview Panel

The Overview panel is the default landing page, providing a comprehensive snapshot of system state.

**Layout:**

```
┌──────────────────────────────────────────────────────────────────────────┐
│                              OVERVIEW                                     │
├───────────────────┬───────────────────┬──────────────────────────────────┤
│                   │                   │                                  │
│   BANKROLL        │   EXPOSURE        │      TRADING STATUS              │
│   $247.50         │   $142.00 (57%)   │      ● ACTIVE                    │
│   ▲ +$47.50       │   ███████░░░      │      [Pause] [Stop]              │
│   since start     │   of 75% limit    │                                  │
│                   │                   │                                  │
├───────────────────┴───────────────────┴──────────────────────────────────┤
│                                                                          │
│   PERFORMANCE                                                            │
│   ┌────────────────────────────────────────────────────────────────────┐ │
│   │                                                                    │ │
│   │    $280 ┤                                              ●          │ │
│   │         │                                         ●────           │ │
│   │    $240 ┤                              ●─────●────                │ │
│   │         │                    ●────●────                           │ │
│   │    $200 ┤    ●────●────●────                                      │ │
│   │         └────┬─────┬─────┬─────┬─────┬─────┬─────┬────            │ │
│   │            Jan 8  Jan 9 Jan 10 Jan 11 Jan 12 Jan 13 Jan 14        │ │
│   └────────────────────────────────────────────────────────────────────┘ │
│                                                                          │
├─────────────────────────────┬────────────────────────────────────────────┤
│                             │                                            │
│   TODAY'S ACTIVITY          │   RECENT TRADES                            │
│                             │                                            │
│   Trades Executed: 4        │   14:32  NYC Temp 85°F+  YES  $5  ✓ +$3.20│
│   Win Rate: 75%             │   11:15  London High     NO   $8  ✓ +$4.80│
│   P&L: +$12.30              │   09:44  Miami Precip    YES  $3  ✗ -$3.00│
│   Edge Captured: 8.2%       │   08:20  NYC Temp 82°F+  YES  $6  ✓ +$7.30│
│                             │                                            │
└─────────────────────────────┴────────────────────────────────────────────┘
```

**Data Elements:**

| Element | Source | Update Frequency |
|---------|--------|------------------|
| Bankroll | Wallet USDC balance | 30 seconds |
| Exposure | Sum of open position values | Real-time (WebSocket) |
| Trading Status | System state machine | Real-time |
| Performance Chart | SQLite trade history | On new trade |
| Today's Activity | Aggregated from trade log | Real-time |
| Recent Trades | Last 10 resolved trades | On resolution |

### 4.3 Markets Panel

Displays all weather markets being monitored with edge calculations.

**Table Columns:**

| Column | Description | Sortable |
|--------|-------------|----------|
| Market | Location and date (e.g., "NYC Jan 20") | Yes |
| Event | Specific outcome (e.g., "High ≥85°F") | Yes |
| Resolution | Time until resolution | Yes |
| Forecast | Our probability estimate | Yes |
| Market | Current market price | Yes |
| Edge | Calculated edge percentage | Yes |
| Agreement | Model agreement score | Yes |
| Status | "Watching" / "Opportunity" / "Position Open" | Yes |
| Action | "Trade" button if criteria met | No |

**Row Highlighting:**

- Green background: Edge ≥ 5% and all criteria met (tradeable opportunity)
- Yellow background: Position currently open in this market
- White background: Monitoring, no action required
- Gray background: Excluded by diversification rules

**Filtering Options:**

- Show: All Markets / Opportunities Only / Open Positions Only
- Location: All / US Northeast / US Southeast / US West / Europe
- Time: All / Today / Tomorrow / This Week

**Detail Expansion:**

Clicking a row expands to show:
- Full market question text
- Resolution source and criteria
- Ensemble forecast breakdown by model
- Historical accuracy for this market type
- Diversification status (which limits apply)

### 4.4 Positions Panel

Displays all open positions with real-time P&L.

**Layout:**

```
┌──────────────────────────────────────────────────────────────────────────┐
│                           OPEN POSITIONS (3)                             │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │ NYC Temperature Jan 20 - High ≥85°F                                │  │
│  │                                                                    │  │
│  │ Side: YES          Entry: $0.42        Current: $0.58              │  │
│  │ Size: $8.00        Resolves: 18h 32m   Unrealized: +$3.05 (+38%)   │  │
│  │                                                                    │  │
│  │ Forecast: 62%      Market: 58%         Edge at Entry: 12%          │  │
│  │                                                                    │  │
│  │ [View Market]  [Close Position]                                    │  │
│  └────────────────────────────────────────────────────────────────────┘  │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │ London High Jan 19 - Below 45°F                                    │  │
│  │                                                                    │  │
│  │ Side: NO           Entry: $0.35        Current: $0.41              │  │
│  │ Size: $5.00        Resolves: 6h 15m    Unrealized: +$0.86 (+17%)   │  │
│  │                                                                    │  │
│  │ Forecast: 71%      Market: 59%         Edge at Entry: 8%           │  │
│  │                                                                    │  │
│  │ [View Market]  [Close Position]                                    │  │
│  └────────────────────────────────────────────────────────────────────┘  │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │ Miami Precipitation Jan 21 - Any Rain                              │  │
│  │                                                                    │  │
│  │ Side: YES          Entry: $0.28        Current: $0.24              │  │
│  │ Size: $4.00        Resolves: 2d 8h     Unrealized: -$0.57 (-14%)   │  │
│  │                                                                    │  │
│  │ Forecast: 35%      Market: 24%         Edge at Entry: 6%           │  │
│  │                                                                    │  │
│  │ [View Market]  [Close Position]                                    │  │
│  └────────────────────────────────────────────────────────────────────┘  │
│                                                                          │
├──────────────────────────────────────────────────────────────────────────┤
│  Total Exposure: $17.00    Total Unrealized P&L: +$3.34 (+19.6%)        │
└──────────────────────────────────────────────────────────────────────────┘
```

**Position Card Elements:**

| Element | Description |
|---------|-------------|
| Header | Market description |
| Side | YES or NO position |
| Entry Price | Price at which position was opened |
| Current Price | Live market price |
| Size | Dollar amount invested |
| Resolves | Countdown to resolution |
| Unrealized P&L | Current profit/loss (absolute and percentage) |
| Forecast | Current forecast probability |
| Market | Current market-implied probability |
| Edge at Entry | Edge when trade was placed |
| View Market | Opens Markets panel filtered to this market |
| Close Position | Manual sell (with confirmation dialog) |

**Unrealized P&L Coloring:**

- Green text: Positive P&L
- Red text: Negative P&L
- Bold: P&L exceeds ±25%

### 4.5 History Panel

Complete record of all trades with filtering and export capabilities.

**Table Columns:**

| Column | Description |
|--------|-------------|
| Date/Time | When trade was executed |
| Market | Market description |
| Side | YES or NO |
| Entry Price | Price paid |
| Exit Price | Price at resolution or sale |
| Size | Position size |
| P&L | Realized profit/loss |
| Result | Win/Loss/Pending |
| Edge | Edge at entry |
| Hold Time | Duration position was held |

**Filtering Options:**

- Date Range: Custom picker / Today / This Week / This Month / All Time
- Result: All / Wins / Losses
- Market Type: All / Temperature / Precipitation / Hurricane / Other
- Location: Dropdown of all traded locations

**Summary Statistics (displayed above table):**

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Period: This Month                                                     │
│                                                                         │
│  Total Trades: 47    Wins: 31 (66%)    Losses: 16 (34%)                │
│  Total P&L: +$127.40    Avg Win: +$8.20    Avg Loss: -$4.30            │
│  Profit Factor: 1.89    Avg Edge: 7.2%    Edge Captured: 5.8%          │
│                                                                         │
│  [Export CSV]  [Export PDF Report]                                      │
└─────────────────────────────────────────────────────────────────────────┘
```

**Export Functionality:**

- CSV Export: Raw data for spreadsheet analysis
- PDF Report: Formatted summary report with charts (see Section 7.3)

### 4.6 Risk Panel

Dedicated view for risk management and exposure monitoring.

**Layout:**

```
┌──────────────────────────────────────────────────────────────────────────┐
│                              RISK DASHBOARD                              │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  EXPOSURE LIMITS                                                         │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │                                                                    │  │
│  │  Total Exposure         $142 / $186 (76% of limit)                │  │
│  │  ████████████████████████████████████████████░░░░░░░░░░░░         │  │
│  │                                                                    │  │
│  │  US Northeast           $42 / $55 (76% of cluster limit)          │  │
│  │  ████████████████████████████░░░░░░░░░░                           │  │
│  │                                                                    │  │
│  │  US Southeast           $0 / $55                                  │  │
│  │  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░                          │  │
│  │                                                                    │  │
│  │  Western Europe         $35 / $55 (64% of cluster limit)          │  │
│  │  █████████████████████████░░░░░░░░░░░░░░░                         │  │
│  │                                                                    │  │
│  │  Same-Day Resolution    $65 / $74 (88% of limit)                  │  │
│  │  █████████████████████████████████████░░░░░                       │  │
│  │                                                                    │  │
│  └────────────────────────────────────────────────────────────────────┘  │
│                                                                          │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  DRAWDOWN STATUS                                                         │
│  ┌─────────────────────┬─────────────────────┬─────────────────────────┐ │
│  │                     │                     │                         │ │
│  │  DAILY              │  WEEKLY             │  MONTHLY                │ │
│  │                     │                     │                         │ │
│  │  P&L: +$12.30       │  P&L: +$34.50       │  P&L: +$127.40          │ │
│  │  Limit: -$24.75     │  Limit: -$61.88     │  Limit: -$99.00         │ │
│  │  Buffer: $37.05     │  Buffer: $96.38     │  Buffer: $226.40        │ │
│  │                     │                     │                         │ │
│  │  ● HEALTHY          │  ● HEALTHY          │  ● HEALTHY              │ │
│  │                     │                     │                         │ │
│  └─────────────────────┴─────────────────────┴─────────────────────────┘ │
│                                                                          │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  HALT CONDITIONS                                                         │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │                                                                    │  │
│  │  ✓ Daily loss limit         Not triggered                         │  │
│  │  ✓ Weekly loss limit        Not triggered                         │  │
│  │  ✓ Monthly loss limit       Not triggered                         │  │
│  │  ✓ System operational       All services running                  │  │
│  │  ✓ API connectivity         Connected to Polymarket               │  │
│  │  ✓ Forecast data            Last update: 2 hours ago              │  │
│  │                                                                    │  │
│  └────────────────────────────────────────────────────────────────────┘  │
│                                                                          │
│  [Manual Halt]  [Clear Daily P&L]  [Export Risk Report]                  │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

**Color Coding for Progress Bars:**

- Green (0-60% of limit): Healthy
- Yellow (60-85% of limit): Caution
- Red (85-100% of limit): Near limit
- Pulsing red (100%+): Limit breached

### 4.7 Settings Panel

User-configurable parameters organized into logical sections.

**Section: Trading Parameters**

| Setting | Type | Default | Range | Description |
|---------|------|---------|-------|-------------|
| Minimum Edge | Slider | 5% | 1-20% | Minimum edge required to trade |
| Maximum Edge | Slider | 50% | 20-80% | Edge above this flags data error |
| Model Agreement | Slider | 60% | 40-90% | Minimum model consensus |
| Minimum Liquidity | Input | $1,000 | $100-$50,000 | Market liquidity threshold |

**Section: Position Sizing**

| Setting | Type | Default | Range | Description |
|---------|------|---------|-------|-------------|
| Minimum Position | Input | $1.00 | $0.10-$10 | Smallest trade size |
| Maximum Position | Input | $10.00 | $1-$100 | Largest trade size |
| Kelly Fraction | Slider | 25% | 10-50% | Fraction of Kelly to use |

**Section: Risk Limits**

| Setting | Type | Default | Range | Description |
|---------|------|---------|-------|-------------|
| Maximum Exposure | Slider | 75% | 25-100% | Max % of bankroll deployed |
| Daily Loss Limit | Slider | 10% | 5-25% | Pause after this daily loss |
| Weekly Loss Limit | Slider | 25% | 10-50% | Pause after this weekly loss |
| Monthly Loss Limit | Slider | 40% | 20-60% | Full halt after this loss |

**Section: Diversification**

| Setting | Type | Default | Range | Description |
|---------|------|---------|-------|-------------|
| Cluster Limit | Slider | 30% | 15-50% | Max exposure per region |
| Same-Day Limit | Slider | 40% | 20-60% | Max resolving same day |
| Min Clusters for 50% | Dropdown | 2 | 1-4 | Required diversity |
| Min Clusters for 75% | Dropdown | 3 | 2-5 | Required diversity |

**Section: System**

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| Server Port | Input | 8741 | Local port for dashboard |
| Auto-start Browser | Toggle | On | Open browser on launch |
| Desktop Notifications | Toggle | On | macOS notification center |
| Sound Alerts | Toggle | Off | Audio for trades/errors |
| Log Level | Dropdown | Info | Verbosity of logging |

**Section: Wallet**

| Setting | Type | Description |
|---------|------|-------------|
| Wallet Address | Display (read-only) | Current connected wallet |
| View on Polygonscan | Button | Opens block explorer |
| Export Private Key | Button | Shows key with warning dialog |
| Disconnect Wallet | Button | Clears credentials (requires re-setup) |

**Settings Persistence:**

All settings are stored in `~/Library/Application Support/WeatherTrader/config.json` and persist across application restarts.

**Reset Options:**

- "Reset to Defaults" button for each section
- "Factory Reset" in System section (clears all data, requires confirmation)

---

## 5. Real-Time Updates via WebSocket

### 5.1 WebSocket Architecture

The frontend maintains a persistent WebSocket connection to receive real-time updates without polling.

**Connection Endpoint:** `ws://localhost:8741/ws`

**Message Protocol:**

All messages use JSON format with a `type` field indicating the message category.

```typescript
interface WebSocketMessage {
    type: string;
    timestamp: string;  // ISO 8601
    data: any;
}
```

### 5.2 Message Types

**Server → Client Messages:**

| Type | Trigger | Data |
|------|---------|------|
| `price_update` | Market price change | `{market_id, token_id, price, side}` |
| `position_update` | Position P&L change | `{position_id, current_price, unrealized_pnl}` |
| `trade_executed` | New trade placed | `{trade_id, market, side, size, price}` |
| `trade_resolved` | Position closed | `{trade_id, result, pnl}` |
| `edge_alert` | New opportunity | `{market_id, edge, forecast_prob, market_prob}` |
| `risk_alert` | Limit approaching | `{alert_type, current_value, limit_value}` |
| `system_status` | Status change | `{status, message}` |
| `forecast_update` | New forecast data | `{market_id, new_probability, model_agreement}` |
| `halt_triggered` | Trading halted | `{reason, can_auto_recover}` |

**Client → Server Messages:**

| Type | Purpose | Data |
|------|---------|------|
| `subscribe` | Subscribe to updates | `{channels: string[]}` |
| `unsubscribe` | Unsubscribe | `{channels: string[]}` |
| `ping` | Keep-alive | `{}` |

### 5.3 Subscription Channels

| Channel | Updates Included |
|---------|------------------|
| `prices` | All price updates for monitored markets |
| `positions` | Position P&L updates |
| `trades` | Trade execution and resolution |
| `alerts` | Edge alerts and risk warnings |
| `system` | System status changes |
| `all` | All channels (default) |

### 5.4 Reconnection Logic

The frontend implements automatic reconnection with exponential backoff:

```javascript
const INITIAL_RETRY_DELAY = 1000;  // 1 second
const MAX_RETRY_DELAY = 30000;     // 30 seconds
const BACKOFF_MULTIPLIER = 1.5;

// Retry sequence: 1s, 1.5s, 2.25s, 3.4s, 5.1s, ... up to 30s
```

During disconnection, the UI displays a banner: "Connection lost. Reconnecting..." with a spinner.

---

## 6. Backend API Specification

### 6.1 REST API Endpoints

**Base URL:** `http://localhost:8741/api/v1`

**Authentication:** None required (local access only). Endpoint binding restricted to `127.0.0.1`.

#### 6.1.1 System Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/status` | System health and status |
| POST | `/control/start` | Start trading |
| POST | `/control/pause` | Pause trading |
| POST | `/control/stop` | Emergency stop |
| GET | `/config` | Get current configuration |
| PUT | `/config` | Update configuration |
| POST | `/config/reset` | Reset to defaults |

**GET /status Response:**

```json
{
    "status": "active",
    "uptime_seconds": 14532,
    "trading_enabled": true,
    "last_trade_time": "2026-01-14T15:32:00Z",
    "open_positions_count": 3,
    "pending_orders_count": 0,
    "api_connected": true,
    "forecast_data_age_seconds": 7200,
    "errors": []
}
```

#### 6.1.2 Portfolio Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/portfolio/summary` | Overview metrics |
| GET | `/portfolio/positions` | Open positions |
| GET | `/portfolio/exposure` | Exposure breakdown |
| GET | `/portfolio/performance` | P&L timeseries |

**GET /portfolio/summary Response:**

```json
{
    "bankroll": 247.50,
    "initial_bankroll": 200.00,
    "total_exposure": 142.00,
    "exposure_percentage": 0.574,
    "unrealized_pnl": 3.34,
    "daily_pnl": 12.30,
    "weekly_pnl": 34.50,
    "monthly_pnl": 127.40,
    "total_trades": 47,
    "win_rate": 0.66,
    "profit_factor": 1.89
}
```

#### 6.1.3 Market Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/markets` | All monitored markets |
| GET | `/markets/{id}` | Single market detail |
| GET | `/markets/{id}/forecast` | Forecast breakdown |
| GET | `/opportunities` | Markets meeting entry criteria |

**GET /markets Response:**

```json
{
    "markets": [
        {
            "id": "0x1234...",
            "description": "NYC Temperature Jan 20 - High ≥85°F",
            "location": "NYC_LAGUARDIA",
            "resolution_date": "2026-01-20T23:59:59Z",
            "hours_to_resolution": 142.5,
            "forecast_probability": 0.62,
            "market_price": 0.52,
            "edge": 0.192,
            "model_agreement": 0.78,
            "liquidity": 8500,
            "status": "opportunity",
            "position_open": false
        }
    ],
    "count": 24,
    "opportunities_count": 3
}
```

#### 6.1.4 Trade Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/trades` | Trade history (paginated) |
| GET | `/trades/{id}` | Single trade detail |
| POST | `/trades` | Execute manual trade |
| DELETE | `/positions/{id}` | Close position manually |

**GET /trades Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| limit | int | 50 | Results per page |
| offset | int | 0 | Pagination offset |
| start_date | ISO date | - | Filter start |
| end_date | ISO date | - | Filter end |
| result | string | - | "win" or "loss" |
| market_type | string | - | Filter by type |

#### 6.1.5 Risk Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/risk/status` | Current risk metrics |
| GET | `/risk/limits` | Configured limits |
| POST | `/risk/reset-daily` | Reset daily P&L counter |
| POST | `/risk/clear-halt` | Clear halt condition (manual) |

### 6.2 Error Response Format

All errors return consistent JSON structure:

```json
{
    "error": true,
    "code": "INSUFFICIENT_BALANCE",
    "message": "Wallet balance insufficient for trade",
    "details": {
        "required": 15.00,
        "available": 12.50
    }
}
```

**HTTP Status Codes:**

| Code | Usage |
|------|-------|
| 200 | Success |
| 400 | Bad request / validation error |
| 404 | Resource not found |
| 409 | Conflict (e.g., trading halted) |
| 500 | Internal server error |
| 503 | Service unavailable (API disconnected) |

---

## 7. Additional Features

### 7.1 Desktop Notifications

The application sends macOS notifications for key events:

| Event | Title | Body | Sound |
|-------|-------|------|-------|
| Trade Executed | "Trade Placed" | "Bought YES on NYC Temp for $8.00" | Default |
| Trade Won | "Trade Won! 🎉" | "NYC Temp: +$3.20 profit" | Glass |
| Trade Lost | "Trade Lost" | "Miami Rain: -$3.00" | Basso |
| Opportunity | "New Opportunity" | "15% edge on London High" | Pop |
| Risk Warning | "Risk Alert ⚠️" | "Daily loss at 8% (limit: 10%)" | Sosumi |
| Trading Halted | "Trading Halted 🛑" | "Weekly loss limit reached" | Funk |
| Error | "System Error" | "API connection lost" | Basso |

Notifications are implemented using the `rumps` library for macOS integration.

### 7.2 Activity Log

A scrollable, searchable log accessible from any panel via a slide-out drawer.

**Log Entry Format:**

```
[2026-01-14 15:32:45] INFO    Trade executed: BUY YES NYC_TEMP_JAN20 @ $0.42 x $8.00
[2026-01-14 15:32:44] INFO    Entry criteria met: NYC_TEMP_JAN20 edge=12.3% agreement=78%
[2026-01-14 15:32:40] DEBUG   Price update: NYC_TEMP_JAN20 YES=$0.52 (was $0.51)
[2026-01-14 15:30:00] INFO    Forecast update: 24 markets updated from Open-Meteo
[2026-01-14 15:15:00] INFO    Market scan: Found 3 new weather markets
```

**Log Levels:**

| Level | Color | Description |
|-------|-------|-------------|
| ERROR | Red | System errors, API failures |
| WARN | Orange | Risk warnings, unusual conditions |
| INFO | Blue | Normal operations, trades |
| DEBUG | Gray | Detailed technical info (hidden by default) |

**Filter Options:**

- Level: All / Errors Only / Warnings+ / Info+
- Search: Free text search
- Time: Last hour / Today / All

### 7.3 PDF Report Generation

Exportable PDF report for record-keeping and analysis.

**Report Sections:**

1. **Summary Page**
   - Period covered
   - Starting and ending bankroll
   - Total P&L (absolute and percentage)
   - Number of trades
   - Win rate and profit factor

2. **Performance Chart**
   - Equity curve
   - Drawdown chart
   - Daily P&L bar chart

3. **Trade Analysis**
   - Breakdown by market type
   - Breakdown by location
   - Edge distribution histogram
   - Hold time analysis

4. **Trade Log**
   - Complete list of trades in period
   - Sorted by date

5. **Risk Metrics**
   - Maximum drawdown
   - Sharpe ratio (if sufficient trades)
   - Average exposure

**Generation Method:**

PDF is generated server-side using `reportlab` or `weasyprint` and served as a downloadable file.

### 7.4 Backup and Restore

**Automatic Backups:**

- Trade history backed up daily to `~/Library/Application Support/WeatherTrader/backups/`
- Retention: 30 days of daily backups
- Format: SQLite database snapshot

**Manual Export:**

- Full data export (JSON format) available in Settings
- Includes: all trades, configuration, position history

**Import:**

- Restore from backup file
- Validates data integrity before import
- Merges with existing data (no duplicates)

---

## 8. macOS Application Packaging

### 8.1 Application Bundle Structure

```
WeatherTrader.app/
├── Contents/
│   ├── Info.plist
│   ├── MacOS/
│   │   └── WeatherTrader          # Main executable
│   ├── Resources/
│   │   ├── icon.icns              # Application icon
│   │   ├── frontend/              # Built React app
│   │   │   ├── index.html
│   │   │   ├── static/
│   │   │   └── ...
│   │   └── ...
│   └── Frameworks/
│       └── Python.framework/      # Embedded Python
└── ...
```

### 8.2 Build Process

The application is packaged using py2app with the following setup:

```python
# setup.py
from setuptools import setup

APP = ['main.py']
DATA_FILES = [
    ('frontend', ['frontend/build/*']),
]
OPTIONS = {
    'argv_emulation': True,
    'plist': {
        'CFBundleName': 'WeatherTrader',
        'CFBundleDisplayName': 'Weather Trader',
        'CFBundleIdentifier': 'com.weathertrader.app',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0.0',
        'LSMinimumSystemVersion': '12.0',
        'LSUIElement': False,
        'NSHighResolutionCapable': True,
    },
    'packages': [
        'fastapi', 'uvicorn', 'httpx', 'py_clob_client',
        'rumps', 'sqlalchemy', 'requests'
    ],
    'iconfile': 'resources/icon.icns',
}

setup(
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
```

### 8.3 Build Commands

```bash
# Development build (for testing)
python setup.py py2app -A

# Production build (standalone)
python setup.py py2app

# Output location
dist/WeatherTrader.app
```

### 8.4 Code Signing (Optional but Recommended)

For distribution without Gatekeeper warnings:

```bash
# Sign the application
codesign --deep --force --verify --verbose \
    --sign "Developer ID Application: Your Name (TEAMID)" \
    dist/WeatherTrader.app

# Notarize with Apple
xcrun notarytool submit dist/WeatherTrader.app \
    --apple-id "your@email.com" \
    --password "app-specific-password" \
    --team-id "TEAMID"
```

Note: Code signing requires an Apple Developer account ($99/year). Without signing, users must right-click and select "Open" on first launch to bypass Gatekeeper.

### 8.5 Installation

**Distribution Method:**

Provide a DMG disk image containing:
- WeatherTrader.app
- Applications folder alias (for drag-and-drop installation)
- README.txt with brief instructions

**User Installation Steps:**

1. Download WeatherTrader.dmg
2. Double-click to mount
3. Drag WeatherTrader.app to Applications folder
4. Eject disk image
5. Launch from Applications

---

## 9. Development and Testing

### 9.1 Development Environment Setup

```bash
# Clone repository
git clone <repository-url>
cd weather-trader

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Install frontend dependencies
cd frontend
npm install
cd ..
```

### 9.2 Development Mode

Run backend and frontend separately for hot-reloading:

**Terminal 1 - Backend:**
```bash
uvicorn app.main:app --reload --port 8741
```

**Terminal 2 - Frontend:**
```bash
cd frontend
npm start
```

Frontend runs on port 3000 with proxy to backend at 8741.

### 9.3 Test Mode

A test mode allows paper trading without real funds:

```bash
# Start in test mode
python main.py --test-mode

# Or set environment variable
WEATHER_TRADER_TEST_MODE=true python main.py
```

**Test Mode Behavior:**

- Uses simulated wallet with configurable starting balance
- Connects to real Polymarket API for market data
- Simulates order fills at market price (no actual orders placed)
- Maintains separate test database
- Dashboard shows "TEST MODE" banner

### 9.4 Logging Configuration

```python
# logging_config.py
LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "[%(asctime)s] %(levelname)-7s %(name)s: %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S"
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "standard",
            "level": "INFO"
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": "~/Library/Logs/WeatherTrader/app.log",
            "maxBytes": 10485760,  # 10MB
            "backupCount": 5,
            "formatter": "standard",
            "level": "DEBUG"
        }
    },
    "root": {
        "level": "DEBUG",
        "handlers": ["console", "file"]
    }
}
```

---

## 10. Implementation Phases (GUI-Specific)

### Phase 1: Backend API Layer (Week 1)

| Task | Priority | Complexity |
|------|----------|------------|
| Create FastAPI application structure | High | Low |
| Implement REST endpoints for portfolio | High | Medium |
| Implement REST endpoints for markets | High | Medium |
| Implement REST endpoints for trades | High | Medium |
| Implement REST endpoints for config | High | Medium |
| Add WebSocket server | High | Medium |
| Connect to trading engine from main spec | High | High |

### Phase 2: Frontend Foundation (Week 2)

| Task | Priority | Complexity |
|------|----------|------------|
| Create React application with Vite | High | Low |
| Install and configure Tailwind + shadcn/ui | High | Low |
| Build navigation sidebar | High | Low |
| Build header with status indicators | High | Low |
| Implement WebSocket client with reconnection | High | Medium |
| Create reusable card components | Medium | Low |

### Phase 3: Dashboard Panels (Week 3)

| Task | Priority | Complexity |
|------|----------|------------|
| Build Overview panel | High | Medium |
| Build Markets panel with table | High | Medium |
| Build Positions panel | High | Medium |
| Build History panel with filters | High | Medium |
| Build Risk panel | High | Medium |
| Build Settings panel | High | Medium |

### Phase 4: Interactive Features (Week 4)

| Task | Priority | Complexity |
|------|----------|------------|
| Implement first-time setup wizard | High | High |
| Add manual trade execution | Medium | Medium |
| Add position close functionality | Medium | Medium |
| Implement PDF report generation | Medium | High |
| Add CSV export | Medium | Low |
| Build activity log drawer | Medium | Medium |

### Phase 5: macOS Integration (Week 5)

| Task | Priority | Complexity |
|------|----------|------------|
| Create menu bar controller with rumps | High | Medium |
| Implement desktop notifications | High | Low |
| Package with py2app | High | High |
| Create DMG installer | Medium | Medium |
| Test on clean macOS installation | High | Medium |
| Write user documentation | Medium | Low |

### Phase 6: Polish and Testing (Week 6)

| Task | Priority | Complexity |
|------|----------|------------|
| End-to-end testing | High | High |
| Performance optimization | Medium | Medium |
| Error handling and edge cases | High | Medium |
| UI/UX refinements | Medium | Low |
| Paper trading validation | High | Medium |

---

## 11. File Structure

```
weather-trader/
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI application
│   ├── config.py                  # Configuration management
│   ├── database.py                # SQLite connection
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes/
│   │   │   ├── status.py          # /status endpoints
│   │   │   ├── portfolio.py       # /portfolio endpoints
│   │   │   ├── markets.py         # /markets endpoints
│   │   │   ├── trades.py          # /trades endpoints
│   │   │   ├── risk.py            # /risk endpoints
│   │   │   └── config.py          # /config endpoints
│   │   └── websocket.py           # WebSocket handler
│   │
│   ├── services/
│   │   ├── trading_engine.py      # From main spec
│   │   ├── notification.py        # Desktop notifications
│   │   └── report_generator.py    # PDF generation
│   │
│   └── models/
│       ├── database_models.py     # SQLAlchemy models
│       └── api_models.py          # Pydantic schemas
│
├── frontend/
│   ├── package.json
│   ├── vite.config.js
│   ├── tailwind.config.js
│   │
│   ├── src/
│   │   ├── main.jsx               # Entry point
│   │   ├── App.jsx                # Root component
│   │   │
│   │   ├── components/
│   │   │   ├── layout/
│   │   │   │   ├── Sidebar.jsx
│   │   │   │   ├── Header.jsx
│   │   │   │   └── Footer.jsx
│   │   │   ├── common/
│   │   │   │   ├── Card.jsx
│   │   │   │   ├── Table.jsx
│   │   │   │   ├── Chart.jsx
│   │   │   │   └── ProgressBar.jsx
│   │   │   └── panels/
│   │   │       ├── Overview.jsx
│   │   │       ├── Markets.jsx
│   │   │       ├── Positions.jsx
│   │   │       ├── History.jsx
│   │   │       ├── Risk.jsx
│   │   │       └── Settings.jsx
│   │   │
│   │   ├── hooks/
│   │   │   ├── useWebSocket.js
│   │   │   └── useAPI.js
│   │   │
│   │   ├── store/
│   │   │   └── index.js           # Zustand store
│   │   │
│   │   └── utils/
│   │       ├── formatters.js
│   │       └── constants.js
│   │
│   └── public/
│       └── index.html
│
├── macos/
│   ├── setup.py                   # py2app configuration
│   ├── menubar.py                 # rumps menu bar controller
│   └── resources/
│       ├── icon.icns
│       └── icon.png
│
├── tests/
│   ├── test_api.py
│   ├── test_trading_engine.py
│   └── test_frontend.py
│
├── scripts/
│   ├── build_macos.sh             # Build script
│   └── create_dmg.sh              # DMG creation
│
├── requirements.txt
├── requirements-dev.txt
├── README.md
└── .env.example
```

---

## 12. Dependencies

### 12.1 Backend Dependencies

```
# requirements.txt

# Web Framework
fastapi>=0.109.0
uvicorn[standard]>=0.27.0
python-multipart>=0.0.6

# WebSocket
websockets>=12.0

# Database
sqlalchemy>=2.0.25
aiosqlite>=0.19.0

# Trading (from main spec)
py-clob-client>=0.1.0
httpx>=0.26.0
web3>=6.15.0

# Weather Data
requests>=2.31.0

# macOS Integration
rumps>=0.4.0
pyobjc-framework-Cocoa>=10.1

# PDF Generation
reportlab>=4.0.0
weasyprint>=60.0

# Utilities
python-dotenv>=1.0.0
pydantic>=2.5.0
pydantic-settings>=2.1.0

# Packaging
py2app>=0.28.0
```

### 12.2 Frontend Dependencies

```json
// package.json (partial)
{
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "react-router-dom": "^6.21.0",
    "zustand": "^4.4.7",
    "recharts": "^2.10.0",
    "tailwindcss": "^3.4.0",
    "@radix-ui/react-slot": "^1.0.2",
    "class-variance-authority": "^0.7.0",
    "clsx": "^2.1.0",
    "lucide-react": "^0.303.0",
    "date-fns": "^3.0.0"
  },
  "devDependencies": {
    "vite": "^5.0.0",
    "@vitejs/plugin-react": "^4.2.0",
    "autoprefixer": "^10.4.16",
    "postcss": "^8.4.32"
  }
}
```

---

## 13. Document Control

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | January 2026 | Strategy Team | Initial GUI specification |

---

**END OF GUI SPECIFICATION**

This document is an addendum to the main trading strategy specification. Both documents should be provided to the implementation team together.
