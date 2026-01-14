/**
 * Format a number as currency
 */
export function formatCurrency(value, decimals = 2) {
  if (value === null || value === undefined) return '-'
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(value)
}

/**
 * Format a number as percentage
 */
export function formatPercent(value, decimals = 1) {
  if (value === null || value === undefined) return '-'
  return `${(value * 100).toFixed(decimals)}%`
}

/**
 * Format a number with sign
 */
export function formatPnl(value, decimals = 2) {
  if (value === null || value === undefined) return '-'
  const sign = value >= 0 ? '+' : ''
  return `${sign}${formatCurrency(value, decimals)}`
}

/**
 * Format time remaining
 */
export function formatTimeRemaining(hours) {
  if (hours === null || hours === undefined) return '-'

  if (hours < 0) return 'Resolved'
  if (hours < 1) return `${Math.round(hours * 60)}m`
  if (hours < 24) return `${Math.round(hours)}h`
  if (hours < 48) return '1d'
  return `${Math.round(hours / 24)}d`
}

/**
 * Format a date
 */
export function formatDate(date, options = {}) {
  if (!date) return '-'
  const d = new Date(date)
  return d.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    ...options,
  })
}

/**
 * Format a datetime
 */
export function formatDateTime(date) {
  if (!date) return '-'
  const d = new Date(date)
  return d.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

/**
 * Format uptime in human readable format
 */
export function formatUptime(seconds) {
  if (!seconds) return '0s'

  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)

  if (hours > 0) {
    return `${hours}h ${minutes}m`
  }
  return `${minutes}m`
}

/**
 * Get color class based on value (positive/negative)
 */
export function getPnlColor(value) {
  if (value > 0) return 'text-green-600'
  if (value < 0) return 'text-red-600'
  return 'text-gray-600'
}

/**
 * Get status indicator color
 */
export function getStatusColor(status) {
  switch (status) {
    case 'active':
      return 'bg-green-500'
    case 'paused':
      return 'bg-yellow-500'
    case 'stopped':
    case 'halted':
      return 'bg-red-500'
    default:
      return 'bg-gray-500'
  }
}
