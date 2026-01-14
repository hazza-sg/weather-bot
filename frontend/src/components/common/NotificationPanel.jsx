import React, { useState, useEffect } from 'react'
import { Bell, Check, X, AlertTriangle, Info, CheckCircle, XCircle, RefreshCw } from 'lucide-react'
import { useAPI } from '../../hooks/useAPI'

const levelIcons = {
  info: Info,
  success: CheckCircle,
  warning: AlertTriangle,
  error: XCircle,
  critical: XCircle,
}

const levelColors = {
  info: 'text-blue-500 bg-blue-50',
  success: 'text-green-500 bg-green-50',
  warning: 'text-yellow-500 bg-yellow-50',
  error: 'text-red-500 bg-red-50',
  critical: 'text-red-700 bg-red-100',
}

export default function NotificationPanel({ isOpen, onClose }) {
  const { get, post, del, loading } = useAPI()
  const [alerts, setAlerts] = useState([])
  const [unreadCount, setUnreadCount] = useState(0)

  useEffect(() => {
    if (isOpen) {
      loadAlerts()
    }
  }, [isOpen])

  const loadAlerts = async () => {
    try {
      const data = await get('/alerts?limit=50')
      setAlerts(data.alerts || [])
      setUnreadCount(data.unread_count || 0)
    } catch (error) {
      console.error('Failed to load alerts:', error)
    }
  }

  const handleMarkAllRead = async () => {
    try {
      await post('/alerts/read-all')
      setAlerts((prev) => prev.map((a) => ({ ...a, read: true })))
      setUnreadCount(0)
    } catch (error) {
      console.error('Failed to mark all read:', error)
    }
  }

  const handleDismiss = async (alertId) => {
    try {
      await post(`/alerts/${alertId}/dismiss`)
      setAlerts((prev) => prev.filter((a) => a.id !== alertId))
    } catch (error) {
      console.error('Failed to dismiss alert:', error)
    }
  }

  const handleClearAll = async () => {
    if (window.confirm('Clear all alerts?')) {
      try {
        await del('/alerts')
        setAlerts([])
        setUnreadCount(0)
      } catch (error) {
        console.error('Failed to clear alerts:', error)
      }
    }
  }

  const formatTime = (timestamp) => {
    const date = new Date(timestamp)
    const now = new Date()
    const diffMs = now - date
    const diffMins = Math.floor(diffMs / 60000)
    const diffHours = Math.floor(diffMs / 3600000)

    if (diffMins < 1) return 'Just now'
    if (diffMins < 60) return `${diffMins}m ago`
    if (diffHours < 24) return `${diffHours}h ago`
    return date.toLocaleDateString()
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-y-0 right-0 w-96 bg-white shadow-xl z-40 flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200">
        <div className="flex items-center">
          <Bell className="h-5 w-5 text-gray-500 mr-2" />
          <h2 className="font-semibold text-gray-900">Notifications</h2>
          {unreadCount > 0 && (
            <span className="ml-2 px-2 py-0.5 text-xs font-medium bg-primary-100 text-primary-700 rounded-full">
              {unreadCount}
            </span>
          )}
        </div>
        <button
          onClick={onClose}
          className="p-1 text-gray-400 hover:text-gray-500 rounded-lg hover:bg-gray-100"
        >
          <X className="h-5 w-5" />
        </button>
      </div>

      {/* Actions */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-gray-100 bg-gray-50">
        <button
          onClick={handleMarkAllRead}
          disabled={unreadCount === 0}
          className="text-sm text-primary-600 hover:text-primary-700 disabled:text-gray-400"
        >
          Mark all read
        </button>
        <div className="flex items-center space-x-2">
          <button
            onClick={loadAlerts}
            disabled={loading}
            className="p-1 text-gray-400 hover:text-gray-500 rounded"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
          <button
            onClick={handleClearAll}
            disabled={alerts.length === 0}
            className="text-sm text-gray-500 hover:text-gray-700 disabled:text-gray-400"
          >
            Clear all
          </button>
        </div>
      </div>

      {/* Alerts List */}
      <div className="flex-1 overflow-y-auto">
        {alerts.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-64 text-gray-500">
            <Bell className="h-12 w-12 mb-3 text-gray-300" />
            <p className="text-sm">No notifications</p>
          </div>
        ) : (
          <div className="divide-y divide-gray-100">
            {alerts.map((alert) => {
              const Icon = levelIcons[alert.level] || Info
              const colorClass = levelColors[alert.level] || levelColors.info

              return (
                <div
                  key={alert.id}
                  className={`px-4 py-3 hover:bg-gray-50 transition-colors ${
                    !alert.read ? 'bg-blue-50/50' : ''
                  }`}
                >
                  <div className="flex items-start">
                    <div className={`p-1.5 rounded-lg ${colorClass}`}>
                      <Icon className="h-4 w-4" />
                    </div>
                    <div className="ml-3 flex-1 min-w-0">
                      <div className="flex items-center justify-between">
                        <p className="text-sm font-medium text-gray-900 truncate">
                          {alert.title}
                        </p>
                        <button
                          onClick={() => handleDismiss(alert.id)}
                          className="ml-2 p-0.5 text-gray-400 hover:text-gray-500 rounded"
                        >
                          <X className="h-4 w-4" />
                        </button>
                      </div>
                      <p className="text-sm text-gray-600 mt-0.5">{alert.message}</p>
                      <p className="text-xs text-gray-400 mt-1">{formatTime(alert.timestamp)}</p>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}

// Notification bell with badge for header
export function NotificationBell({ onClick, unreadCount = 0 }) {
  return (
    <button
      onClick={onClick}
      className="relative p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg"
    >
      <Bell className="h-5 w-5" />
      {unreadCount > 0 && (
        <span className="absolute top-0 right-0 transform translate-x-1/3 -translate-y-1/3 flex items-center justify-center w-5 h-5 text-xs font-bold text-white bg-red-500 rounded-full">
          {unreadCount > 9 ? '9+' : unreadCount}
        </span>
      )}
    </button>
  )
}
