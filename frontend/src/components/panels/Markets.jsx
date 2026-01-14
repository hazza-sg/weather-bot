import React, { useEffect, useState } from 'react'
import { RefreshCw } from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent } from '../common/Card'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '../common/Table'
import { useStore } from '../../store'
import { formatPercent, formatCurrency, formatTimeRemaining } from '../../utils/formatters'

export default function Markets() {
  const { markets, opportunitiesCount, fetchMarkets } = useStore()
  const [filter, setFilter] = useState('all')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    handleRefresh()
  }, [])

  const handleRefresh = async () => {
    setLoading(true)
    await fetchMarkets()
    setLoading(false)
  }

  const filteredMarkets = markets.filter((market) => {
    if (filter === 'all') return true
    if (filter === 'opportunities') return market.status === 'opportunity'
    if (filter === 'positions') return market.position_open
    return true
  })

  const getRowHighlight = (market) => {
    if (market.status === 'opportunity' && market.is_tradeable) return 'green'
    if (market.position_open) return 'yellow'
    return undefined
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Markets</h1>
        <button
          onClick={handleRefresh}
          disabled={loading}
          className="inline-flex items-center px-4 py-2 bg-white border border-gray-300 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-50"
        >
          <RefreshCw className={`h-4 w-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {/* Filters */}
      <div className="flex items-center space-x-4">
        <span className="text-sm font-medium text-gray-700">Show:</span>
        <div className="flex space-x-2">
          {[
            { value: 'all', label: 'All Markets' },
            { value: 'opportunities', label: `Opportunities (${opportunitiesCount})` },
            { value: 'positions', label: 'Open Positions' },
          ].map((option) => (
            <button
              key={option.value}
              onClick={() => setFilter(option.value)}
              className={`px-3 py-1.5 text-sm font-medium rounded-lg transition-colors ${
                filter === option.value
                  ? 'bg-primary-100 text-primary-700'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              {option.label}
            </button>
          ))}
        </div>
      </div>

      {/* Markets Table */}
      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Market</TableHead>
                <TableHead>Resolution</TableHead>
                <TableHead>Forecast</TableHead>
                <TableHead>Market</TableHead>
                <TableHead>Edge</TableHead>
                <TableHead>Agreement</TableHead>
                <TableHead>Liquidity</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredMarkets.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={8} className="text-center py-8 text-gray-500">
                    No markets found
                  </TableCell>
                </TableRow>
              ) : (
                filteredMarkets.map((market) => (
                  <TableRow key={market.id} highlight={getRowHighlight(market)}>
                    <TableCell>
                      <div>
                        <p className="font-medium">{market.description}</p>
                        <p className="text-xs text-gray-500">{market.location}</p>
                      </div>
                    </TableCell>
                    <TableCell>
                      {formatTimeRemaining(market.hours_to_resolution)}
                    </TableCell>
                    <TableCell>
                      {market.forecast_probability
                        ? formatPercent(market.forecast_probability)
                        : '-'}
                    </TableCell>
                    <TableCell>
                      {market.market_price
                        ? formatPercent(market.market_price)
                        : '-'}
                    </TableCell>
                    <TableCell>
                      <span
                        className={
                          market.edge && market.edge >= 0.05
                            ? 'text-green-600 font-medium'
                            : ''
                        }
                      >
                        {market.edge ? formatPercent(market.edge) : '-'}
                      </span>
                    </TableCell>
                    <TableCell>
                      {market.model_agreement
                        ? formatPercent(market.model_agreement)
                        : '-'}
                    </TableCell>
                    <TableCell>{formatCurrency(market.liquidity, 0)}</TableCell>
                    <TableCell>
                      <span
                        className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                          market.status === 'opportunity'
                            ? 'bg-green-100 text-green-800'
                            : market.position_open
                            ? 'bg-yellow-100 text-yellow-800'
                            : 'bg-gray-100 text-gray-800'
                        }`}
                      >
                        {market.position_open
                          ? 'Position Open'
                          : market.status === 'opportunity'
                          ? 'Opportunity'
                          : 'Watching'}
                      </span>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  )
}
