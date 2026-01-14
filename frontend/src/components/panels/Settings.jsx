import React, { useState, useEffect } from 'react'
import { Save, RotateCcw } from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent } from '../common/Card'
import { useAPI } from '../../hooks/useAPI'

export default function Settings() {
  const { get, put, post, loading } = useAPI()
  const [config, setConfig] = useState(null)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    loadConfig()
  }, [])

  const loadConfig = async () => {
    try {
      const data = await get('/config')
      setConfig(data)
    } catch (error) {
      console.error('Failed to load config:', error)
    }
  }

  const handleSave = async (section) => {
    try {
      await put('/config', {
        section,
        settings: config[section],
      })
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } catch (error) {
      console.error('Failed to save config:', error)
    }
  }

  const handleReset = async () => {
    if (window.confirm('Reset all settings to defaults?')) {
      try {
        await post('/config/reset')
        await loadConfig()
      } catch (error) {
        console.error('Failed to reset config:', error)
      }
    }
  }

  const updateSetting = (section, key, value) => {
    setConfig((prev) => ({
      ...prev,
      [section]: {
        ...prev[section],
        [key]: value,
      },
    }))
  }

  if (!config) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-gray-500">Loading settings...</p>
      </div>
    )
  }

  const SliderSetting = ({ section, setting, label, min, max, step = 0.01, format = (v) => `${(v * 100).toFixed(0)}%` }) => (
    <div className="py-4 border-b border-gray-100 last:border-0">
      <div className="flex items-center justify-between mb-2">
        <label className="text-sm font-medium text-gray-700">{label}</label>
        <span className="text-sm text-gray-500">{format(config[section][setting])}</span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={config[section][setting]}
        onChange={(e) => updateSetting(section, setting, parseFloat(e.target.value))}
        className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer"
      />
    </div>
  )

  const NumberSetting = ({ section, setting, label, min, max, step = 1 }) => (
    <div className="py-4 border-b border-gray-100 last:border-0 flex items-center justify-between">
      <label className="text-sm font-medium text-gray-700">{label}</label>
      <input
        type="number"
        min={min}
        max={max}
        step={step}
        value={config[section][setting]}
        onChange={(e) => updateSetting(section, setting, parseFloat(e.target.value))}
        className="w-32 px-3 py-1.5 border border-gray-300 rounded-lg text-right"
      />
    </div>
  )

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Settings</h1>
        <div className="flex items-center space-x-3">
          {saved && (
            <span className="text-green-600 text-sm">Saved!</span>
          )}
          <button
            onClick={handleReset}
            className="inline-flex items-center px-4 py-2 bg-white border border-gray-300 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            <RotateCcw className="h-4 w-4 mr-2" />
            Reset All
          </button>
        </div>
      </div>

      {/* Trading Parameters */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>Trading Parameters</CardTitle>
          <button
            onClick={() => handleSave('strategy')}
            disabled={loading}
            className="inline-flex items-center px-3 py-1.5 bg-primary-600 text-white text-sm font-medium rounded-lg hover:bg-primary-700"
          >
            <Save className="h-4 w-4 mr-1" />
            Save
          </button>
        </CardHeader>
        <CardContent>
          <SliderSetting section="strategy" setting="min_edge" label="Minimum Edge" min={0.01} max={0.20} />
          <SliderSetting section="strategy" setting="max_edge" label="Maximum Edge" min={0.20} max={0.80} />
          <SliderSetting section="strategy" setting="min_model_agreement" label="Model Agreement" min={0.40} max={0.90} />
          <NumberSetting section="strategy" setting="min_liquidity" label="Minimum Liquidity ($)" min={100} max={50000} step={100} />
        </CardContent>
      </Card>

      {/* Position Sizing */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>Position Sizing</CardTitle>
          <button
            onClick={() => handleSave('position_sizing')}
            disabled={loading}
            className="inline-flex items-center px-3 py-1.5 bg-primary-600 text-white text-sm font-medium rounded-lg hover:bg-primary-700"
          >
            <Save className="h-4 w-4 mr-1" />
            Save
          </button>
        </CardHeader>
        <CardContent>
          <NumberSetting section="position_sizing" setting="min_position" label="Minimum Position ($)" min={0.10} max={10} step={0.10} />
          <NumberSetting section="position_sizing" setting="max_position" label="Maximum Position ($)" min={1} max={100} step={1} />
          <SliderSetting section="position_sizing" setting="kelly_fraction" label="Kelly Fraction" min={0.10} max={0.50} />
        </CardContent>
      </Card>

      {/* Risk Limits */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>Risk Limits</CardTitle>
          <button
            onClick={() => handleSave('risk')}
            disabled={loading}
            className="inline-flex items-center px-3 py-1.5 bg-primary-600 text-white text-sm font-medium rounded-lg hover:bg-primary-700"
          >
            <Save className="h-4 w-4 mr-1" />
            Save
          </button>
        </CardHeader>
        <CardContent>
          <SliderSetting section="risk" setting="max_daily_loss_pct" label="Daily Loss Limit" min={0.05} max={0.25} />
          <SliderSetting section="risk" setting="max_weekly_loss_pct" label="Weekly Loss Limit" min={0.10} max={0.50} />
          <SliderSetting section="risk" setting="max_monthly_loss_pct" label="Monthly Loss Limit" min={0.20} max={0.60} />
        </CardContent>
      </Card>

      {/* Diversification */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>Diversification</CardTitle>
          <button
            onClick={() => handleSave('diversification')}
            disabled={loading}
            className="inline-flex items-center px-3 py-1.5 bg-primary-600 text-white text-sm font-medium rounded-lg hover:bg-primary-700"
          >
            <Save className="h-4 w-4 mr-1" />
            Save
          </button>
        </CardHeader>
        <CardContent>
          <SliderSetting section="diversification" setting="max_total_exposure_pct" label="Maximum Exposure" min={0.25} max={1.0} />
          <SliderSetting section="diversification" setting="max_cluster_exposure_pct" label="Cluster Limit" min={0.15} max={0.50} />
          <SliderSetting section="diversification" setting="max_same_day_resolution_pct" label="Same-Day Limit" min={0.20} max={0.60} />
        </CardContent>
      </Card>
    </div>
  )
}
