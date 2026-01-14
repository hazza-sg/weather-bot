import React, { useEffect } from 'react'
import { DollarSign, TrendingUp, Target, Activity } from 'lucide-react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import { Card, CardHeader, CardTitle, CardContent, StatCard } from '../common/Card'
import { useStore } from '../../store'
import { formatCurrency, formatPercent, formatPnl, getPnlColor } from '../../utils/formatters'

export default function Overview() {
  const { portfolio, status, trades, fetchTrades } = useStore()

  useEffect(() => {
    fetchTrades({ limit: 10 })
  }, [fetchTrades])

  // Mock performance data (would come from API in production)
  const performanceData = [
    { date: 'Jan 8', value: 200 },
    { date: 'Jan 9', value: 208 },
    { date: 'Jan 10', value: 215 },
    { date: 'Jan 11', value: 225 },
    { date: 'Jan 12', value: 232 },
    { date: 'Jan 13', value: 240 },
    { date: 'Jan 14', value: 247.5 },
  ]

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Overview</h1>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCard
          title="Bankroll"
          value={formatCurrency(portfolio.bankroll)}
          subtitle={formatPnl(portfolio.bankroll - portfolio.initialBankroll) + ' since start'}
          trend={portfolio.bankroll - portfolio.initialBankroll}
          icon={DollarSign}
        />
        <StatCard
          title="Exposure"
          value={formatCurrency(portfolio.totalExposure)}
          subtitle={formatPercent(portfolio.exposurePercentage) + ' of limit'}
          icon={Target}
        />
        <StatCard
          title="Today's P&L"
          value={formatPnl(portfolio.dailyPnl)}
          trend={portfolio.dailyPnl}
          icon={TrendingUp}
        />
        <StatCard
          title="Open Positions"
          value={status.openPositions}
          icon={Activity}
        />
      </div>

      {/* Performance Chart */}
      <Card>
        <CardHeader>
          <CardTitle>Performance</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={performanceData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis dataKey="date" stroke="#6b7280" fontSize={12} />
                <YAxis stroke="#6b7280" fontSize={12} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: 'white',
                    border: '1px solid #e5e7eb',
                    borderRadius: '8px',
                  }}
                  formatter={(value) => [formatCurrency(value), 'Bankroll']}
                />
                <Line
                  type="monotone"
                  dataKey="value"
                  stroke="#0ea5e9"
                  strokeWidth={2}
                  dot={{ fill: '#0ea5e9', strokeWidth: 2 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>

      {/* Activity and Recent Trades */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Today's Activity */}
        <Card>
          <CardHeader>
            <CardTitle>Today's Activity</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="flex justify-between">
                <span className="text-gray-600">Trades Executed</span>
                <span className="font-medium">{portfolio.totalTrades}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Win Rate</span>
                <span className="font-medium">{formatPercent(portfolio.winRate)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">P&L</span>
                <span className={`font-medium ${getPnlColor(portfolio.dailyPnl)}`}>
                  {formatPnl(portfolio.dailyPnl)}
                </span>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Recent Trades */}
        <Card>
          <CardHeader>
            <CardTitle>Recent Trades</CardTitle>
          </CardHeader>
          <CardContent>
            {trades.length === 0 ? (
              <p className="text-gray-500 text-center py-4">No recent trades</p>
            ) : (
              <div className="space-y-3">
                {trades.slice(0, 5).map((trade) => (
                  <div
                    key={trade.trade_id}
                    className="flex items-center justify-between py-2 border-b border-gray-100 last:border-0"
                  >
                    <div>
                      <p className="font-medium text-sm">{trade.description || trade.market_id}</p>
                      <p className="text-xs text-gray-500">
                        {trade.side} @ {formatCurrency(trade.entry_price)}
                      </p>
                    </div>
                    <div className="text-right">
                      {trade.realized_pnl !== null ? (
                        <span className={`font-medium ${getPnlColor(trade.realized_pnl)}`}>
                          {formatPnl(trade.realized_pnl)}
                        </span>
                      ) : (
                        <span className="text-gray-500 text-sm">Pending</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
