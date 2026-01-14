import React, { useEffect } from 'react'
import { AlertTriangle, CheckCircle, XCircle } from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent } from '../common/Card'
import ProgressBar from '../common/ProgressBar'
import { useStore } from '../../store'
import { formatCurrency, formatPnl, getPnlColor } from '../../utils/formatters'

export default function Risk() {
  const { riskStatus, fetchRiskStatus } = useStore()

  useEffect(() => {
    fetchRiskStatus()
    const interval = setInterval(fetchRiskStatus, 30000)
    return () => clearInterval(interval)
  }, [fetchRiskStatus])

  if (!riskStatus) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-gray-500">Loading risk data...</p>
      </div>
    )
  }

  const DrawdownCard = ({ title, pnl, limit, buffer }) => {
    const isHealthy = pnl > limit
    return (
      <Card>
        <CardContent>
          <h3 className="font-semibold text-gray-900 mb-4">{title}</h3>
          <div className="space-y-2">
            <div className="flex justify-between">
              <span className="text-gray-600">P&L</span>
              <span className={`font-medium ${getPnlColor(pnl)}`}>
                {formatPnl(pnl)}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">Limit</span>
              <span className="font-medium text-red-600">
                {formatCurrency(limit)}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">Buffer</span>
              <span className="font-medium">{formatCurrency(buffer)}</span>
            </div>
            <div className="flex items-center mt-3">
              {isHealthy ? (
                <>
                  <CheckCircle className="h-5 w-5 text-green-500 mr-2" />
                  <span className="text-green-600 font-medium">HEALTHY</span>
                </>
              ) : (
                <>
                  <XCircle className="h-5 w-5 text-red-500 mr-2" />
                  <span className="text-red-600 font-medium">BREACHED</span>
                </>
              )}
            </div>
          </div>
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Risk Dashboard</h1>

      {/* Halt Warning */}
      {riskStatus.is_halted && (
        <Card className="border-red-300 bg-red-50">
          <CardContent>
            <div className="flex items-center">
              <AlertTriangle className="h-6 w-6 text-red-600 mr-3" />
              <div>
                <h3 className="font-semibold text-red-800">Trading Halted</h3>
                <p className="text-red-600">{riskStatus.halt_reason}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Exposure Limits */}
      <Card>
        <CardHeader>
          <CardTitle>Exposure Limits</CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          <ProgressBar
            value={riskStatus.total_exposure}
            max={riskStatus.max_exposure}
            label="Total Exposure"
          />

          {Object.entries(riskStatus.cluster_exposure).map(([cluster, exposure]) => (
            <ProgressBar
              key={cluster}
              value={exposure}
              max={riskStatus.cluster_limits[cluster] || riskStatus.max_exposure * 0.3}
              label={cluster.replace('_', ' ')}
            />
          ))}

          {Object.entries(riskStatus.same_day_exposure).map(([date, exposure]) => (
            <ProgressBar
              key={date}
              value={exposure}
              max={riskStatus.same_day_limit}
              label={`Same-Day: ${date}`}
            />
          ))}
        </CardContent>
      </Card>

      {/* Drawdown Status */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <DrawdownCard
          title="DAILY"
          pnl={riskStatus.daily_pnl}
          limit={riskStatus.daily_limit}
          buffer={riskStatus.daily_buffer}
        />
        <DrawdownCard
          title="WEEKLY"
          pnl={riskStatus.weekly_pnl}
          limit={riskStatus.weekly_limit}
          buffer={riskStatus.weekly_buffer}
        />
        <DrawdownCard
          title="MONTHLY"
          pnl={riskStatus.monthly_pnl}
          limit={riskStatus.monthly_limit}
          buffer={riskStatus.monthly_buffer}
        />
      </div>

      {/* Halt Conditions */}
      <Card>
        <CardHeader>
          <CardTitle>Halt Conditions</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {Object.entries(riskStatus.halt_conditions).map(([key, condition]) => (
              <div key={key} className="flex items-center justify-between py-2 border-b border-gray-100 last:border-0">
                <div className="flex items-center">
                  {condition.triggered ? (
                    <XCircle className="h-5 w-5 text-red-500 mr-3" />
                  ) : (
                    <CheckCircle className="h-5 w-5 text-green-500 mr-3" />
                  )}
                  <span className="font-medium">
                    {key.replace('_', ' ').replace(/\b\w/g, (l) => l.toUpperCase())}
                  </span>
                </div>
                <span className={condition.triggered ? 'text-red-600' : 'text-gray-500'}>
                  {condition.message}
                </span>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
