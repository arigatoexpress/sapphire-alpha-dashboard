import { useEffect, useState } from 'react'
import type { TradingViewAlert } from '../types'

export function useTradingViewAlerts(authHeader: string) {
  const [alerts, setAlerts] = useState<TradingViewAlert[]>([])
  const [error, setError] = useState('')

  useEffect(() => {
    if (!authHeader) return

    const fetchAlerts = async () => {
      try {
        const r = await fetch('/api/v1/tradingview/alerts?limit=25', {
          headers: { Authorization: authHeader },
        })
        if (r.status === 401) {
          setError('TradingView alerts: session expired')
          return
        }
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        const data = await r.json()
        setAlerts(data.alerts || [])
        setError('')
      } catch (e) {
        setError(e instanceof Error ? e.message : 'alerts fetch failed')
      }
    }

    fetchAlerts()
    const id = setInterval(fetchAlerts, 10000)
    return () => clearInterval(id)
  }, [authHeader])

  return { alerts, error }
}
