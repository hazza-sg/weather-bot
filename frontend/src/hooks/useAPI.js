import { useState, useCallback } from 'react'

const API_BASE = '/api/v1'

export function useAPI() {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const request = useCallback(async (endpoint, options = {}) => {
    setLoading(true)
    setError(null)

    try {
      const response = await fetch(`${API_BASE}${endpoint}`, {
        headers: {
          'Content-Type': 'application/json',
          ...options.headers,
        },
        ...options,
      })

      const data = await response.json()

      if (!response.ok) {
        throw new Error(data.message || 'Request failed')
      }

      return data
    } catch (err) {
      setError(err.message)
      throw err
    } finally {
      setLoading(false)
    }
  }, [])

  const get = useCallback((endpoint) => request(endpoint), [request])

  const post = useCallback(
    (endpoint, body) =>
      request(endpoint, {
        method: 'POST',
        body: JSON.stringify(body),
      }),
    [request]
  )

  const put = useCallback(
    (endpoint, body) =>
      request(endpoint, {
        method: 'PUT',
        body: JSON.stringify(body),
      }),
    [request]
  )

  const del = useCallback(
    (endpoint) =>
      request(endpoint, {
        method: 'DELETE',
      }),
    [request]
  )

  return { loading, error, get, post, put, del }
}
