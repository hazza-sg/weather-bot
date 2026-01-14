export const ROUTES = {
  OVERVIEW: '/',
  MARKETS: '/markets',
  POSITIONS: '/positions',
  HISTORY: '/history',
  RISK: '/risk',
  SETTINGS: '/settings',
}

export const STATUS = {
  ACTIVE: 'active',
  PAUSED: 'paused',
  STOPPED: 'stopped',
  LOADING: 'loading',
}

export const MARKET_STATUS = {
  WATCHING: 'watching',
  OPPORTUNITY: 'opportunity',
  POSITION_OPEN: 'position_open',
}

export const TRADE_RESULT = {
  WIN: 'win',
  LOSS: 'loss',
  PENDING: 'pending',
}

export const WS_CHANNELS = {
  ALL: 'all',
  PRICES: 'prices',
  POSITIONS: 'positions',
  TRADES: 'trades',
  ALERTS: 'alerts',
  SYSTEM: 'system',
}
