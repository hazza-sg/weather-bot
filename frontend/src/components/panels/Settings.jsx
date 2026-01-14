import React, { useState, useEffect } from 'react'
import { Save, RotateCcw, Bell, Monitor } from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent } from '../common/Card'
import { useAPI } from '../../hooks/useAPI'

export default function Settings() {
  const { get, put, post, loading } = useAPI()
  const [config, setConfig] = useState(null)
  const [alertPrefs, setAlertPrefs] = useState(null)
  const [saved, setSaved] = useState(false)
  const [activeTab, setActiveTab] = useState('trading')

  useEffect(() => {
    loadConfig()
    loadAlertPrefs()
  }, [])

  const loadConfig = async () => {
    try {
      const data = await get('/config')
      setConfig(data)
    } catch (error) {
      console.error('Failed to load config:', error)
    }
  }

  const loadAlertPrefs = async () => {
    try {
      const data = await get('/alerts/preferences')
      setAlertPrefs(data)
    } catch (error) {
      console.error('Failed to load alert preferences:', error)
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

  const handleSaveAlertPrefs = async () => {
    try {
      await put('/alerts/preferences', alertPrefs)
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } catch (error) {
      console.error('Failed to save alert preferences:', error)
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

  const updateAlertPref = (key, value) => {
    setAlertPrefs((prev) => ({
      ...prev,
      [key]: value,
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

  const NumberSetting = ({ section, setting, label, min, max, step = 1, prefix = '' }) => (
    <div className="py-4 border-b border-gray-100 last:border-0 flex items-center justify-between">
      <label className="text-sm font-medium text-gray-700">{label}</label>
      <div className="relative">
        {prefix && <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500">{prefix}</span>}
        <input
          type="number"
          min={min}
          max={max}
          step={step}
          value={config[section][setting]}
          onChange={(e) => updateSetting(section, setting, parseFloat(e.target.value))}
          className={`w-32 px-3 py-1.5 border border-gray-300 rounded-lg text-right ${prefix ? 'pl-7' : ''}`}
        />
      </div>
    </div>
  )

  const ToggleSetting = ({ checked, onChange, label, description }) => (
    <div className="py-4 border-b border-gray-100 last:border-0 flex items-center justify-between">
      <div>
        <label className="text-sm font-medium text-gray-700">{label}</label>
        {description && <p className="text-xs text-gray-500 mt-0.5">{description}</p>}
      </div>
      <button
        onClick={() => onChange(!checked)}
        className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
          checked ? 'bg-primary-600' : 'bg-gray-200'
        }`}
      >
        <span
          className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
            checked ? 'translate-x-6' : 'translate-x-1'
          }`}
        />
      </button>
    </div>
  )

  const tabs = [
    { id: 'trading', label: 'Trading' },
    { id: 'risk', label: 'Risk' },
    { id: 'alerts', label: 'Alerts' },
    { id: 'system', label: 'System' },
  ]

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

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <nav className="flex space-x-8">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`py-3 px-1 border-b-2 font-medium text-sm transition-colors ${
                activeTab === tab.id
                  ? 'border-primary-500 text-primary-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      {/* Trading Tab */}
      {activeTab === 'trading' && (
        <div className="space-y-6">
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
              <NumberSetting section="strategy" setting="min_liquidity" label="Minimum Liquidity" min={100} max={50000} step={100} prefix="$" />
            </CardContent>
          </Card>

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
              <NumberSetting section="position_sizing" setting="min_position" label="Minimum Position" min={0.10} max={10} step={0.10} prefix="$" />
              <NumberSetting section="position_sizing" setting="max_position" label="Maximum Position" min={1} max={100} step={1} prefix="$" />
              <SliderSetting section="position_sizing" setting="kelly_fraction" label="Kelly Fraction" min={0.10} max={0.50} />
            </CardContent>
          </Card>

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
      )}

      {/* Risk Tab */}
      {activeTab === 'risk' && (
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
      )}

      {/* Alerts Tab */}
      {activeTab === 'alerts' && alertPrefs && (
        <div className="space-y-6">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle className="flex items-center">
                <Bell className="h-5 w-5 mr-2" />
                Notification Settings
              </CardTitle>
              <button
                onClick={handleSaveAlertPrefs}
                disabled={loading}
                className="inline-flex items-center px-3 py-1.5 bg-primary-600 text-white text-sm font-medium rounded-lg hover:bg-primary-700"
              >
                <Save className="h-4 w-4 mr-1" />
                Save
              </button>
            </CardHeader>
            <CardContent>
              <ToggleSetting
                checked={alertPrefs.enabled}
                onChange={(v) => updateAlertPref('enabled', v)}
                label="Enable Notifications"
                description="Master toggle for all notifications"
              />
              <ToggleSetting
                checked={alertPrefs.desktop_notifications}
                onChange={(v) => updateAlertPref('desktop_notifications', v)}
                label="Desktop Notifications"
                description="Show system notifications"
              />
              <ToggleSetting
                checked={alertPrefs.sound_enabled}
                onChange={(v) => updateAlertPref('sound_enabled', v)}
                label="Sound Alerts"
                description="Play sound for important alerts"
              />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Alert Categories</CardTitle>
            </CardHeader>
            <CardContent>
              <ToggleSetting
                checked={alertPrefs.trade_alerts}
                onChange={(v) => updateAlertPref('trade_alerts', v)}
                label="Trade Alerts"
                description="Notifications for trade executions"
              />
              <ToggleSetting
                checked={alertPrefs.risk_alerts}
                onChange={(v) => updateAlertPref('risk_alerts', v)}
                label="Risk Alerts"
                description="Warnings and halt notifications"
              />
              <ToggleSetting
                checked={alertPrefs.market_alerts}
                onChange={(v) => updateAlertPref('market_alerts', v)}
                label="Market Alerts"
                description="New opportunities and market updates"
              />
              <ToggleSetting
                checked={alertPrefs.position_alerts}
                onChange={(v) => updateAlertPref('position_alerts', v)}
                label="Position Alerts"
                description="Position changes and P&L updates"
              />
              <ToggleSetting
                checked={alertPrefs.system_alerts}
                onChange={(v) => updateAlertPref('system_alerts', v)}
                label="System Alerts"
                description="Errors and system status"
              />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Thresholds</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="py-4 border-b border-gray-100 flex items-center justify-between">
                <div>
                  <label className="text-sm font-medium text-gray-700">Minimum Edge for Alert</label>
                  <p className="text-xs text-gray-500">Alert when edge exceeds this value</p>
                </div>
                <div className="flex items-center">
                  <input
                    type="number"
                    min={0.01}
                    max={0.50}
                    step={0.01}
                    value={alertPrefs.min_edge_for_alert}
                    onChange={(e) => updateAlertPref('min_edge_for_alert', parseFloat(e.target.value))}
                    className="w-20 px-3 py-1.5 border border-gray-300 rounded-lg text-right"
                  />
                  <span className="ml-2 text-sm text-gray-500">= {(alertPrefs.min_edge_for_alert * 100).toFixed(0)}%</span>
                </div>
              </div>
              <div className="py-4 border-b border-gray-100 flex items-center justify-between">
                <div>
                  <label className="text-sm font-medium text-gray-700">P&L Alert Threshold</label>
                  <p className="text-xs text-gray-500">Alert on P&L changes above this</p>
                </div>
                <div className="relative">
                  <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500">$</span>
                  <input
                    type="number"
                    min={1}
                    max={500}
                    step={5}
                    value={alertPrefs.pnl_alert_threshold}
                    onChange={(e) => updateAlertPref('pnl_alert_threshold', parseFloat(e.target.value))}
                    className="w-28 pl-7 pr-3 py-1.5 border border-gray-300 rounded-lg text-right"
                  />
                </div>
              </div>
              <div className="py-4 flex items-center justify-between">
                <div>
                  <label className="text-sm font-medium text-gray-700">Position Alert Threshold</label>
                  <p className="text-xs text-gray-500">Alert for positions above this size</p>
                </div>
                <div className="relative">
                  <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500">$</span>
                  <input
                    type="number"
                    min={1}
                    max={500}
                    step={5}
                    value={alertPrefs.position_alert_threshold}
                    onChange={(e) => updateAlertPref('position_alert_threshold', parseFloat(e.target.value))}
                    className="w-28 pl-7 pr-3 py-1.5 border border-gray-300 rounded-lg text-right"
                  />
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* System Tab */}
      {activeTab === 'system' && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center">
              <Monitor className="h-5 w-5 mr-2" />
              System Settings
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="py-4 border-b border-gray-100 flex items-center justify-between">
              <div>
                <label className="text-sm font-medium text-gray-700">Server Port</label>
                <p className="text-xs text-gray-500">Backend API port (requires restart)</p>
              </div>
              <input
                type="number"
                value={config.system?.server_port || 8741}
                disabled
                className="w-24 px-3 py-1.5 border border-gray-300 rounded-lg text-right bg-gray-50"
              />
            </div>
            <ToggleSetting
              checked={config.system?.auto_start_browser || true}
              onChange={() => {}}
              label="Auto-open Browser"
              description="Open browser when app starts"
            />
            <div className="py-4 flex items-center justify-between">
              <div>
                <label className="text-sm font-medium text-gray-700">Log Level</label>
                <p className="text-xs text-gray-500">Logging verbosity</p>
              </div>
              <select
                value={config.system?.log_level || 'INFO'}
                className="px-3 py-1.5 border border-gray-300 rounded-lg"
              >
                <option value="DEBUG">Debug</option>
                <option value="INFO">Info</option>
                <option value="WARNING">Warning</option>
                <option value="ERROR">Error</option>
              </select>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
