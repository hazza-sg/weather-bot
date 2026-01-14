import { create } from 'zustand'

const API_BASE = '/api/v1'

export const useStore = create((set, get) => ({
  // System status
  status: {
    status: 'loading',
    tradingEnabled: false,
    uptime: 0,
    openPositions: 0,
    errors: [],
  },

  // Portfolio data
  portfolio: {
    bankroll: 0,
    initialBankroll: 0,
    totalExposure: 0,
    exposurePercentage: 0,
    unrealizedPnl: 0,
    dailyPnl: 0,
    weeklyPnl: 0,
    monthlyPnl: 0,
    totalTrades: 0,
    winRate: 0,
  },

  // Markets
  markets: [],
  opportunitiesCount: 0,

  // Positions
  positions: [],

  // Trades
  trades: [],
  tradeStats: null,

  // Risk
  riskStatus: null,

  // WebSocket
  wsConnected: false,

  // Actions
  fetchStatus: async () => {
    try {
      const res = await fetch(`${API_BASE}/status`)
      const data = await res.json()
      set({
        status: {
          status: data.status,
          tradingEnabled: data.trading_enabled,
          uptime: data.uptime_seconds,
          openPositions: data.open_positions_count,
          errors: data.errors || [],
        },
      })
    } catch (error) {
      console.error('Failed to fetch status:', error)
    }
  },

  fetchPortfolio: async () => {
    try {
      const res = await fetch(`${API_BASE}/portfolio/summary`)
      const data = await res.json()
      set({
        portfolio: {
          bankroll: data.bankroll,
          initialBankroll: data.initial_bankroll,
          totalExposure: data.total_exposure,
          exposurePercentage: data.exposure_percentage,
          unrealizedPnl: data.unrealized_pnl,
          dailyPnl: data.daily_pnl,
          weeklyPnl: data.weekly_pnl,
          monthlyPnl: data.monthly_pnl,
          totalTrades: data.total_trades,
          winRate: data.win_rate,
        },
      })
    } catch (error) {
      console.error('Failed to fetch portfolio:', error)
    }
  },

  fetchMarkets: async () => {
    try {
      const res = await fetch(`${API_BASE}/markets`)
      const data = await res.json()
      set({
        markets: data.markets,
        opportunitiesCount: data.opportunities_count,
      })
    } catch (error) {
      console.error('Failed to fetch markets:', error)
    }
  },

  fetchPositions: async () => {
    try {
      const res = await fetch(`${API_BASE}/portfolio/positions`)
      const data = await res.json()
      set({ positions: data.positions })
    } catch (error) {
      console.error('Failed to fetch positions:', error)
    }
  },

  fetchTrades: async (params = {}) => {
    try {
      const query = new URLSearchParams(params).toString()
      const res = await fetch(`${API_BASE}/trades?${query}`)
      const data = await res.json()
      set({ trades: data.trades })
    } catch (error) {
      console.error('Failed to fetch trades:', error)
    }
  },

  fetchTradeStats: async (period = 'month') => {
    try {
      const res = await fetch(`${API_BASE}/trades/stats?period=${period}`)
      const data = await res.json()
      set({ tradeStats: data })
    } catch (error) {
      console.error('Failed to fetch trade stats:', error)
    }
  },

  fetchRiskStatus: async () => {
    try {
      const res = await fetch(`${API_BASE}/risk/status`)
      const data = await res.json()
      set({ riskStatus: data })
    } catch (error) {
      console.error('Failed to fetch risk status:', error)
    }
  },

  // Control actions
  startTrading: async () => {
    try {
      const res = await fetch(`${API_BASE}/status/control/start`, { method: 'POST' })
      const data = await res.json()
      if (data.success) {
        get().fetchStatus()
      }
      return data
    } catch (error) {
      console.error('Failed to start trading:', error)
      return { success: false, message: error.message }
    }
  },

  pauseTrading: async () => {
    try {
      const res = await fetch(`${API_BASE}/status/control/pause`, { method: 'POST' })
      const data = await res.json()
      if (data.success) {
        get().fetchStatus()
      }
      return data
    } catch (error) {
      console.error('Failed to pause trading:', error)
      return { success: false, message: error.message }
    }
  },

  stopTrading: async () => {
    try {
      const res = await fetch(`${API_BASE}/status/control/stop`, { method: 'POST' })
      const data = await res.json()
      if (data.success) {
        get().fetchStatus()
      }
      return data
    } catch (error) {
      console.error('Failed to stop trading:', error)
      return { success: false, message: error.message }
    }
  },

  closePosition: async (positionId) => {
    try {
      const res = await fetch(`${API_BASE}/portfolio/positions/${positionId}`, {
        method: 'DELETE',
      })
      const data = await res.json()
      if (data.success) {
        get().fetchPositions()
        get().fetchPortfolio()
      }
      return data
    } catch (error) {
      console.error('Failed to close position:', error)
      return { success: false, message: error.message }
    }
  },

  // WebSocket handlers
  setWsConnected: (connected) => set({ wsConnected: connected }),

  handleWsMessage: (message) => {
    const { type, data } = message

    switch (type) {
      case 'price_update':
        // Update market price in state
        break
      case 'position_update':
        get().fetchPositions()
        break
      case 'trade_executed':
      case 'trade_resolved':
        get().fetchPortfolio()
        get().fetchPositions()
        break
      case 'system_status':
        get().fetchStatus()
        break
      default:
        break
    }
  },
}))
