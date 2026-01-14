import React from 'react'
import clsx from 'clsx'

export function Card({ children, className, ...props }) {
  return (
    <div
      className={clsx(
        'bg-white rounded-xl border border-gray-200 shadow-sm',
        className
      )}
      {...props}
    >
      {children}
    </div>
  )
}

export function CardHeader({ children, className }) {
  return (
    <div
      className={clsx(
        'px-6 py-4 border-b border-gray-200',
        className
      )}
    >
      {children}
    </div>
  )
}

export function CardTitle({ children, className }) {
  return (
    <h3 className={clsx('text-lg font-semibold text-gray-900', className)}>
      {children}
    </h3>
  )
}

export function CardContent({ children, className }) {
  return (
    <div className={clsx('px-6 py-4', className)}>
      {children}
    </div>
  )
}

export function StatCard({ title, value, subtitle, trend, icon: Icon }) {
  const trendColor = trend > 0 ? 'text-green-600' : trend < 0 ? 'text-red-600' : 'text-gray-500'

  return (
    <Card>
      <CardContent>
        <div className="flex items-start justify-between">
          <div>
            <p className="text-sm font-medium text-gray-500">{title}</p>
            <p className="mt-1 text-2xl font-semibold text-gray-900">{value}</p>
            {subtitle && (
              <p className={clsx('mt-1 text-sm', trendColor)}>{subtitle}</p>
            )}
          </div>
          {Icon && (
            <div className="p-2 bg-primary-50 rounded-lg">
              <Icon className="h-6 w-6 text-primary-600" />
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  )
}
