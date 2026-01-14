import React, { useEffect, useState } from 'react'
import { Download } from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent } from '../common/Card'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '../common/Table'
import { useStore } from '../../store'
import {
  formatCurrency,
  formatPercent,
  formatPnl,
  formatDateTime,
  getPnlColor,
} from '../../utils/formatters'

export default function History() {
  const { trades, tradeStats, fetchTrades, fetchTradeStats } = useStore()
  const [period, setPeriod] = useState('month')
  const [resultFilter, setResultFilter] = useState('all')

  useEffect(() => {
    fetchTrades({ limit: 100 })
    fetchTradeStats(period)
  }, [fetchTrades, fetchTradeStats, period])

  const filteredTrades = trades.filter((trade) => {
    if (resultFilter === 'all') return true
    return trade.result === resultFilter
  })

  const handleExportCSV = () => {
    // Simple CSV export
    const headers = ['Date', 'Market', 'Side', 'Entry', 'Exit', 'Size', 'P&L', 'Result']
    const rows = trades.map((t) => [
      new Date(t.entry_time).toISOString(),
      t.description || t.market_id,
      t.side,
      t.entry_price,
      t.exit_price || '',
      t.size,
      t.realized_pnl || '',
      t.result || 'pending',
    ])

    const csv = [headers.join(','), ...rows.map((r) => r.join(','))].join('\n')
    const blob = new Blob([csv], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `trades_${new Date().toISOString().split('T')[0]}.csv`
    a.click()
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Trade History</h1>
        <button
          onClick={handleExportCSV}
          className="inline-flex items-center px-4 py-2 bg-white border border-gray-300 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-50"
        >
          <Download className="h-4 w-4 mr-2" />
          Export CSV
        </button>
      </div>

      {/* Stats Summary */}
      {tradeStats && (
        <Card>
          <CardContent>
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-gray-900">Period: {period}</h3>
              <div className="flex space-x-2">
                {['day', 'week', 'month', 'all'].map((p) => (
                  <button
                    key={p}
                    onClick={() => setPeriod(p)}
                    className={`px-3 py-1 text-sm rounded ${
                      period === p
                        ? 'bg-primary-100 text-primary-700'
                        : 'bg-gray-100 text-gray-600'
                    }`}
                  >
                    {p.charAt(0).toUpperCase() + p.slice(1)}
                  </button>
                ))}
              </div>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
              <div>
                <p className="text-sm text-gray-500">Total Trades</p>
                <p className="text-xl font-semibold">{tradeStats.total_trades}</p>
              </div>
              <div>
                <p className="text-sm text-gray-500">Win Rate</p>
                <p className="text-xl font-semibold">{formatPercent(tradeStats.win_rate)}</p>
              </div>
              <div>
                <p className="text-sm text-gray-500">Total P&L</p>
                <p className={`text-xl font-semibold ${getPnlColor(tradeStats.total_pnl)}`}>
                  {formatPnl(tradeStats.total_pnl)}
                </p>
              </div>
              <div>
                <p className="text-sm text-gray-500">Avg Win</p>
                <p className="text-xl font-semibold text-green-600">
                  {formatPnl(tradeStats.avg_win)}
                </p>
              </div>
              <div>
                <p className="text-sm text-gray-500">Avg Loss</p>
                <p className="text-xl font-semibold text-red-600">
                  -{formatCurrency(tradeStats.avg_loss)}
                </p>
              </div>
              <div>
                <p className="text-sm text-gray-500">Profit Factor</p>
                <p className="text-xl font-semibold">{tradeStats.profit_factor.toFixed(2)}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Filters */}
      <div className="flex items-center space-x-4">
        <span className="text-sm font-medium text-gray-700">Filter:</span>
        <div className="flex space-x-2">
          {['all', 'win', 'loss', 'pending'].map((filter) => (
            <button
              key={filter}
              onClick={() => setResultFilter(filter)}
              className={`px-3 py-1.5 text-sm font-medium rounded-lg ${
                resultFilter === filter
                  ? 'bg-primary-100 text-primary-700'
                  : 'bg-gray-100 text-gray-600'
              }`}
            >
              {filter.charAt(0).toUpperCase() + filter.slice(1)}
            </button>
          ))}
        </div>
      </div>

      {/* Trades Table */}
      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Date/Time</TableHead>
                <TableHead>Market</TableHead>
                <TableHead>Side</TableHead>
                <TableHead>Entry</TableHead>
                <TableHead>Exit</TableHead>
                <TableHead>Size</TableHead>
                <TableHead>P&L</TableHead>
                <TableHead>Result</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredTrades.map((trade) => (
                <TableRow key={trade.trade_id}>
                  <TableCell>{formatDateTime(trade.entry_time)}</TableCell>
                  <TableCell>
                    <div>
                      <p className="font-medium">{trade.description || trade.market_id}</p>
                      <p className="text-xs text-gray-500">{trade.location}</p>
                    </div>
                  </TableCell>
                  <TableCell>{trade.side}</TableCell>
                  <TableCell>{formatCurrency(trade.entry_price)}</TableCell>
                  <TableCell>
                    {trade.exit_price ? formatCurrency(trade.exit_price) : '-'}
                  </TableCell>
                  <TableCell>{formatCurrency(trade.size)}</TableCell>
                  <TableCell className={getPnlColor(trade.realized_pnl)}>
                    {trade.realized_pnl !== null ? formatPnl(trade.realized_pnl) : '-'}
                  </TableCell>
                  <TableCell>
                    <span
                      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                        trade.result === 'win'
                          ? 'bg-green-100 text-green-800'
                          : trade.result === 'loss'
                          ? 'bg-red-100 text-red-800'
                          : 'bg-gray-100 text-gray-800'
                      }`}
                    >
                      {trade.result || 'Pending'}
                    </span>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  )
}
