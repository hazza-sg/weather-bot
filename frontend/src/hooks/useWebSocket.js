import { useEffect, useRef, useCallback } from 'react'
import { useStore } from '../store'

const WS_URL = `ws://${window.location.hostname}:8741/ws`
const RECONNECT_DELAY = 1000
const MAX_RECONNECT_DELAY = 30000

export function useWebSocket() {
  const wsRef = useRef(null)
  const reconnectTimeoutRef = useRef(null)
  const reconnectDelayRef = useRef(RECONNECT_DELAY)

  const { setWsConnected, handleWsMessage } = useStore()

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      return
    }

    try {
      wsRef.current = new WebSocket(WS_URL)

      wsRef.current.onopen = () => {
        console.log('WebSocket connected')
        setWsConnected(true)
        reconnectDelayRef.current = RECONNECT_DELAY

        // Subscribe to all channels
        wsRef.current.send(JSON.stringify({
          type: 'subscribe',
          channels: ['all'],
        }))
      }

      wsRef.current.onclose = () => {
        console.log('WebSocket disconnected')
        setWsConnected(false)
        scheduleReconnect()
      }

      wsRef.current.onerror = (error) => {
        console.error('WebSocket error:', error)
      }

      wsRef.current.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data)
          handleWsMessage(message)
        } catch (error) {
          console.error('Failed to parse WebSocket message:', error)
        }
      }
    } catch (error) {
      console.error('Failed to connect WebSocket:', error)
      scheduleReconnect()
    }
  }, [setWsConnected, handleWsMessage])

  const scheduleReconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
    }

    reconnectTimeoutRef.current = setTimeout(() => {
      console.log(`Reconnecting in ${reconnectDelayRef.current}ms...`)
      connect()

      // Exponential backoff
      reconnectDelayRef.current = Math.min(
        reconnectDelayRef.current * 1.5,
        MAX_RECONNECT_DELAY
      )
    }, reconnectDelayRef.current)
  }, [connect])

  useEffect(() => {
    connect()

    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
      }
      if (wsRef.current) {
        wsRef.current.close()
      }
    }
  }, [connect])

  const sendMessage = useCallback((message) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message))
    }
  }, [])

  return { sendMessage }
}
