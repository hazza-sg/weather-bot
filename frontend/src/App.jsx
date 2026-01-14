import React, { useEffect } from 'react'
import { Routes, Route } from 'react-router-dom'
import Sidebar from './components/layout/Sidebar'
import Header from './components/layout/Header'
import Footer from './components/layout/Footer'
import Overview from './components/panels/Overview'
import Markets from './components/panels/Markets'
import Positions from './components/panels/Positions'
import History from './components/panels/History'
import Risk from './components/panels/Risk'
import Settings from './components/panels/Settings'
import { useStore } from './store'
import { useWebSocket } from './hooks/useWebSocket'

function App() {
  const { fetchStatus, fetchPortfolio } = useStore()

  // Initialize WebSocket connection
  useWebSocket()

  // Fetch initial data
  useEffect(() => {
    fetchStatus()
    fetchPortfolio()

    // Refresh periodically
    const interval = setInterval(() => {
      fetchStatus()
      fetchPortfolio()
    }, 30000)

    return () => clearInterval(interval)
  }, [fetchStatus, fetchPortfolio])

  return (
    <div className="flex h-screen bg-slate-50">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Header />
        <main className="flex-1 overflow-auto p-6">
          <Routes>
            <Route path="/" element={<Overview />} />
            <Route path="/markets" element={<Markets />} />
            <Route path="/positions" element={<Positions />} />
            <Route path="/history" element={<History />} />
            <Route path="/risk" element={<Risk />} />
            <Route path="/settings" element={<Settings />} />
          </Routes>
        </main>
        <Footer />
      </div>
    </div>
  )
}

export default App
