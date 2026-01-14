import React from 'react'
import { Play, Pause, Square, Wifi, WifiOff } from 'lucide-react'
import clsx from 'clsx'
import { useStore } from '../../store'
import { getStatusColor, formatUptime } from '../../utils/formatters'

export default function Header() {
  const {
    status,
    wsConnected,
    startTrading,
    pauseTrading,
    stopTrading
  } = useStore()

  const handleStart = async () => {
    await startTrading()
  }

  const handlePause = async () => {
    await pauseTrading()
  }

  const handleStop = async () => {
    if (window.confirm('Stop trading? Open positions will remain until resolution.')) {
      await stopTrading()
    }
  }

  return (
    <header className="h-16 bg-white border-b border-gray-200 flex items-center justify-between px-6">
      {/* Left side - Status */}
      <div className="flex items-center space-x-4">
        <div className="flex items-center">
          <span
            className={clsx(
              'h-3 w-3 rounded-full mr-2',
              getStatusColor(status.status)
            )}
          />
          <span className="text-sm font-medium text-gray-700 capitalize">
            {status.status}
          </span>
        </div>

        <div className="h-4 w-px bg-gray-300" />

        <div className="text-sm text-gray-500">
          Uptime: {formatUptime(status.uptime)}
        </div>

        <div className="h-4 w-px bg-gray-300" />

        <div className="flex items-center text-sm text-gray-500">
          {wsConnected ? (
            <>
              <Wifi className="h-4 w-4 mr-1 text-green-500" />
              Connected
            </>
          ) : (
            <>
              <WifiOff className="h-4 w-4 mr-1 text-red-500" />
              Disconnected
            </>
          )}
        </div>
      </div>

      {/* Right side - Controls */}
      <div className="flex items-center space-x-2">
        {status.status !== 'active' && (
          <button
            onClick={handleStart}
            className="inline-flex items-center px-4 py-2 bg-green-600 text-white text-sm font-medium rounded-lg hover:bg-green-700 transition-colors"
          >
            <Play className="h-4 w-4 mr-2" />
            Start
          </button>
        )}

        {status.status === 'active' && (
          <button
            onClick={handlePause}
            className="inline-flex items-center px-4 py-2 bg-yellow-500 text-white text-sm font-medium rounded-lg hover:bg-yellow-600 transition-colors"
          >
            <Pause className="h-4 w-4 mr-2" />
            Pause
          </button>
        )}

        {status.status !== 'stopped' && (
          <button
            onClick={handleStop}
            className="inline-flex items-center px-4 py-2 bg-red-600 text-white text-sm font-medium rounded-lg hover:bg-red-700 transition-colors"
          >
            <Square className="h-4 w-4 mr-2" />
            Stop
          </button>
        )}
      </div>
    </header>
  )
}
