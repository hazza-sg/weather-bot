import React, { useState, useEffect } from 'react'
import { TrendingUp, TrendingDown, AlertCircle } from 'lucide-react'
import { Modal, ModalFooter } from './Modal'
import { useAPI } from '../../hooks/useAPI'
import { formatCurrency, formatPercent } from '../../utils/formatters'

export default function TradeDialog({ isOpen, onClose, market = null }) {
  const { post, loading } = useAPI()
  const [formData, setFormData] = useState({
    market_id: '',
    side: 'YES',
    size: 10,
    price: null,
  })
  const [error, setError] = useState(null)
  const [success, setSuccess] = useState(false)

  useEffect(() => {
    if (market) {
      setFormData((prev) => ({
        ...prev,
        market_id: market.id,
        price: market.market_price,
      }))
    }
  }, [market])

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError(null)

    try {
      const result = await post('/trades', formData)
      if (result.trade_id) {
        setSuccess(true)
        setTimeout(() => {
          onClose()
          setSuccess(false)
          setFormData({ market_id: '', side: 'YES', size: 10, price: null })
        }, 1500)
      }
    } catch (err) {
      setError(err.message || 'Trade execution failed')
    }
  }

  const handleChange = (field, value) => {
    setFormData((prev) => ({ ...prev, [field]: value }))
  }

  const estimatedCost = formData.size
  const estimatedPayout = formData.price
    ? (formData.size / formData.price).toFixed(2)
    : '—'

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Manual Trade" size="md">
      {success ? (
        <div className="py-8 text-center">
          <div className="mx-auto w-12 h-12 bg-green-100 rounded-full flex items-center justify-center mb-4">
            <TrendingUp className="h-6 w-6 text-green-600" />
          </div>
          <h3 className="text-lg font-medium text-gray-900">Trade Executed!</h3>
          <p className="text-sm text-gray-500 mt-1">Your order has been placed successfully.</p>
        </div>
      ) : (
        <form onSubmit={handleSubmit}>
          {/* Market ID */}
          <div className="mb-4">
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Market ID
            </label>
            <input
              type="text"
              value={formData.market_id}
              onChange={(e) => handleChange('market_id', e.target.value)}
              placeholder="Enter market ID or token ID"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
              required
            />
            {market && (
              <p className="text-xs text-gray-500 mt-1">{market.description}</p>
            )}
          </div>

          {/* Side Selection */}
          <div className="mb-4">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Position
            </label>
            <div className="grid grid-cols-2 gap-3">
              <button
                type="button"
                onClick={() => handleChange('side', 'YES')}
                className={`flex items-center justify-center px-4 py-3 rounded-lg border-2 transition-colors ${
                  formData.side === 'YES'
                    ? 'border-green-500 bg-green-50 text-green-700'
                    : 'border-gray-200 hover:border-gray-300'
                }`}
              >
                <TrendingUp className="h-5 w-5 mr-2" />
                <span className="font-medium">YES</span>
              </button>
              <button
                type="button"
                onClick={() => handleChange('side', 'NO')}
                className={`flex items-center justify-center px-4 py-3 rounded-lg border-2 transition-colors ${
                  formData.side === 'NO'
                    ? 'border-red-500 bg-red-50 text-red-700'
                    : 'border-gray-200 hover:border-gray-300'
                }`}
              >
                <TrendingDown className="h-5 w-5 mr-2" />
                <span className="font-medium">NO</span>
              </button>
            </div>
          </div>

          {/* Size */}
          <div className="mb-4">
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Trade Size (USD)
            </label>
            <div className="relative">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500">$</span>
              <input
                type="number"
                min="1"
                max="100"
                step="1"
                value={formData.size}
                onChange={(e) => handleChange('size', parseFloat(e.target.value))}
                className="w-full pl-8 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                required
              />
            </div>
            <div className="flex justify-between mt-2">
              {[5, 10, 25, 50].map((amount) => (
                <button
                  key={amount}
                  type="button"
                  onClick={() => handleChange('size', amount)}
                  className="px-3 py-1 text-sm bg-gray-100 hover:bg-gray-200 rounded-lg"
                >
                  ${amount}
                </button>
              ))}
            </div>
          </div>

          {/* Price (optional) */}
          <div className="mb-4">
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Limit Price (optional)
            </label>
            <input
              type="number"
              min="0.01"
              max="0.99"
              step="0.01"
              value={formData.price || ''}
              onChange={(e) => handleChange('price', e.target.value ? parseFloat(e.target.value) : null)}
              placeholder="Market order if empty"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
            />
          </div>

          {/* Order Summary */}
          <div className="bg-gray-50 rounded-lg p-4 mb-4">
            <h4 className="text-sm font-medium text-gray-700 mb-2">Order Summary</h4>
            <div className="space-y-1 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-500">Cost:</span>
                <span className="font-medium">{formatCurrency(estimatedCost)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Max Payout:</span>
                <span className="font-medium">${estimatedPayout}</span>
              </div>
              {formData.price && (
                <div className="flex justify-between">
                  <span className="text-gray-500">Price:</span>
                  <span className="font-medium">{formatPercent(formData.price)}</span>
                </div>
              )}
            </div>
          </div>

          {/* Error */}
          {error && (
            <div className="flex items-center p-3 bg-red-50 text-red-700 rounded-lg mb-4">
              <AlertCircle className="h-5 w-5 mr-2 flex-shrink-0" />
              <span className="text-sm">{error}</span>
            </div>
          )}

          <ModalFooter>
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 rounded-lg"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading || !formData.market_id}
              className={`px-4 py-2 text-sm font-medium text-white rounded-lg ${
                formData.side === 'YES'
                  ? 'bg-green-600 hover:bg-green-700'
                  : 'bg-red-600 hover:bg-red-700'
              } disabled:opacity-50 disabled:cursor-not-allowed`}
            >
              {loading ? 'Executing...' : `Place ${formData.side} Order`}
            </button>
          </ModalFooter>
        </form>
      )}
    </Modal>
  )
}
