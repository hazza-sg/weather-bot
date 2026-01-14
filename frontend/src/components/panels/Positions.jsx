import React, { useEffect } from 'react'
import { X } from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent } from '../common/Card'
import { useStore } from '../../store'
import {
  formatCurrency,
  formatPercent,
  formatPnl,
  formatTimeRemaining,
  getPnlColor,
} from '../../utils/formatters'

export default function Positions() {
  const { positions, fetchPositions, closePosition, portfolio } = useStore()

  useEffect(() => {
    fetchPositions()
  }, [fetchPositions])

  const handleClosePosition = async (positionId) => {
    if (window.confirm('Close this position at current market price?')) {
      await closePosition(positionId)
    }
  }

  const totalExposure = positions.reduce((sum, p) => sum + p.size, 0)
  const totalUnrealized = positions.reduce((sum, p) => sum + p.unrealized_pnl, 0)

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">
          Open Positions ({positions.length})
        </h1>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-2 gap-4">
        <Card>
          <CardContent className="py-4">
            <p className="text-sm text-gray-500">Total Exposure</p>
            <p className="text-2xl font-semibold">{formatCurrency(totalExposure)}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="py-4">
            <p className="text-sm text-gray-500">Total Unrealized P&L</p>
            <p className={`text-2xl font-semibold ${getPnlColor(totalUnrealized)}`}>
              {formatPnl(totalUnrealized)} ({formatPercent(totalUnrealized / totalExposure || 0)})
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Position Cards */}
      {positions.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center">
            <p className="text-gray-500">No open positions</p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {positions.map((position) => (
            <Card key={position.position_id}>
              <CardContent>
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <h3 className="text-lg font-semibold text-gray-900">
                      {position.description}
                    </h3>

                    <div className="mt-4 grid grid-cols-2 md:grid-cols-4 gap-4">
                      <div>
                        <p className="text-sm text-gray-500">Side</p>
                        <p className="font-medium">{position.side}</p>
                      </div>
                      <div>
                        <p className="text-sm text-gray-500">Entry</p>
                        <p className="font-medium">{formatCurrency(position.entry_price)}</p>
                      </div>
                      <div>
                        <p className="text-sm text-gray-500">Current</p>
                        <p className="font-medium">{formatCurrency(position.current_price)}</p>
                      </div>
                      <div>
                        <p className="text-sm text-gray-500">Size</p>
                        <p className="font-medium">{formatCurrency(position.size)}</p>
                      </div>
                    </div>

                    <div className="mt-4 grid grid-cols-2 md:grid-cols-4 gap-4">
                      <div>
                        <p className="text-sm text-gray-500">Resolves</p>
                        <p className="font-medium">
                          {formatTimeRemaining(position.hours_to_resolution)}
                        </p>
                      </div>
                      <div>
                        <p className="text-sm text-gray-500">Unrealized P&L</p>
                        <p className={`font-medium ${getPnlColor(position.unrealized_pnl)}`}>
                          {formatPnl(position.unrealized_pnl)} ({formatPercent(position.unrealized_pnl_pct)})
                        </p>
                      </div>
                      <div>
                        <p className="text-sm text-gray-500">Forecast</p>
                        <p className="font-medium">
                          {formatPercent(position.forecast_probability)}
                        </p>
                      </div>
                      <div>
                        <p className="text-sm text-gray-500">Edge at Entry</p>
                        <p className="font-medium">
                          {formatPercent(position.edge_at_entry)}
                        </p>
                      </div>
                    </div>
                  </div>

                  <button
                    onClick={() => handleClosePosition(position.position_id)}
                    className="ml-4 p-2 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors"
                    title="Close Position"
                  >
                    <X className="h-5 w-5" />
                  </button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
