import { useCallback, useEffect, useState } from 'react'
import type { LiveSnapshot } from '../types'

export function useLiveTelemetry(authHeader: string) {
  const [snapshot, setSnapshot] = useState<LiveSnapshot | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [authRequired, setAuthRequired] = useState(false)

  const refresh = useCallback(async () => {
    try {
      const response = await fetch('/api/v1/live', {
        headers: authHeader ? { Authorization: authHeader } : {},
      })
      if (response.status === 401) {
        setAuthRequired(true)
        setSnapshot(null)
        return
      }
      if (!response.ok) throw new Error(`Telemetry unavailable (${response.status})`)
      setSnapshot((await response.json()) as LiveSnapshot)
      setAuthRequired(false)
      setError('')
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Telemetry unavailable')
    } finally {
      setLoading(false)
    }
  }, [authHeader])

  useEffect(() => {
    setLoading(true)
    refresh()
    const timer = window.setInterval(refresh, 5_000)
    return () => window.clearInterval(timer)
  }, [refresh])

  return { snapshot, error, loading, authRequired, refresh }
}
