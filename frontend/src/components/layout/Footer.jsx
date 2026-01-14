import React from 'react'
import { useStore } from '../../store'

export default function Footer() {
  const { wsConnected, status } = useStore()
  const now = new Date().toLocaleTimeString()

  return (
    <footer className="h-10 bg-white border-t border-gray-200 flex items-center justify-between px-6 text-xs text-gray-500">
      <div className="flex items-center space-x-4">
        <span>
          Connection: {wsConnected ? 'Live' : 'Disconnected'}
        </span>
        <span>|</span>
        <span>
          Positions: {status.openPositions}
        </span>
      </div>

      <div className="flex items-center space-x-4">
        <span>Last Update: {now}</span>
        <span>|</span>
        <span>v1.0.0</span>
      </div>
    </footer>
  )
}
