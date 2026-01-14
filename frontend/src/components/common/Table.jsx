import React from 'react'
import clsx from 'clsx'

export function Table({ children, className }) {
  return (
    <div className={clsx('overflow-x-auto', className)}>
      <table className="min-w-full divide-y divide-gray-200">
        {children}
      </table>
    </div>
  )
}

export function TableHeader({ children }) {
  return <thead className="bg-gray-50">{children}</thead>
}

export function TableBody({ children }) {
  return (
    <tbody className="bg-white divide-y divide-gray-200">
      {children}
    </tbody>
  )
}

export function TableRow({ children, className, onClick, highlight }) {
  return (
    <tr
      className={clsx(
        'hover:bg-gray-50 transition-colors',
        onClick && 'cursor-pointer',
        highlight === 'green' && 'bg-green-50',
        highlight === 'yellow' && 'bg-yellow-50',
        highlight === 'gray' && 'bg-gray-100',
        className
      )}
      onClick={onClick}
    >
      {children}
    </tr>
  )
}

export function TableHead({ children, className, sortable, sorted, onSort }) {
  return (
    <th
      className={clsx(
        'px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider',
        sortable && 'cursor-pointer hover:text-gray-700',
        className
      )}
      onClick={sortable ? onSort : undefined}
    >
      <div className="flex items-center space-x-1">
        <span>{children}</span>
        {sorted && (
          <span>{sorted === 'asc' ? '↑' : '↓'}</span>
        )}
      </div>
    </th>
  )
}

export function TableCell({ children, className }) {
  return (
    <td
      className={clsx(
        'px-6 py-4 whitespace-nowrap text-sm text-gray-900',
        className
      )}
    >
      {children}
    </td>
  )
}
