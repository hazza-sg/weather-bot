import React from 'react'
import clsx from 'clsx'

export default function ProgressBar({
  value,
  max = 100,
  label,
  showValue = true,
  size = 'md',
  variant = 'default'
}) {
  const percentage = Math.min((value / max) * 100, 100)

  const getVariantColor = () => {
    if (variant === 'danger' || percentage >= 85) return 'bg-red-500'
    if (variant === 'warning' || percentage >= 60) return 'bg-yellow-500'
    return 'bg-green-500'
  }

  const sizeClasses = {
    sm: 'h-1.5',
    md: 'h-2.5',
    lg: 'h-4',
  }

  return (
    <div className="w-full">
      {(label || showValue) && (
        <div className="flex justify-between mb-1">
          {label && (
            <span className="text-sm font-medium text-gray-700">{label}</span>
          )}
          {showValue && (
            <span className="text-sm text-gray-500">
              {value.toFixed(0)} / {max.toFixed(0)} ({percentage.toFixed(0)}%)
            </span>
          )}
        </div>
      )}
      <div className={clsx('w-full bg-gray-200 rounded-full', sizeClasses[size])}>
        <div
          className={clsx('rounded-full transition-all duration-300', sizeClasses[size], getVariantColor())}
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  )
}
