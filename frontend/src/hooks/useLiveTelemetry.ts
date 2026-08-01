import { useCallback, useEffect, useState } from 'react'
import type { LiveSnapshot } from '../types'

/**
 * Poll `/api/v1/live`.
 *
 * There is no `Authorization` header and no 401 branch, because there is no
 * second tier to authenticate into: the endpoint serves one snapshot, the same
 * numbers at the same moment, to whoever asks. A 401 here would now be a real
 * server fault and is reported as one rather than swallowed into a login form.
 */
export function useLiveTelemetry() {
  const [snapshot, setSnapshot] = useState<LiveSnapshot | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(async () => {
    try {
      const response = await fetch('/api/v1/live', { cache: 'no-store' })
      if (!response.ok) throw new Error(`Telemetry unavailable (${response.status})`)
      setSnapshot((await response.json()) as LiveSnapshot)
      setError('')
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Telemetry unavailable')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    let timer: number | undefined

    const stopPolling = () => {
      if (timer !== undefined) window.clearInterval(timer)
      timer = undefined
    }
    const syncPolling = () => {
      stopPolling()
      if (document.visibilityState !== 'visible') return
      void refresh()
      timer = window.setInterval(refresh, 15_000)
    }

    syncPolling()
    document.addEventListener('visibilitychange', syncPolling)
    return () => {
      stopPolling()
      document.removeEventListener('visibilitychange', syncPolling)
    }
  }, [refresh])

  return { snapshot, error, loading, refresh }
}
