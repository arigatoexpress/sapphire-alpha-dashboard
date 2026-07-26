import { useEffect, useState } from 'react'
import type { PublicWidgets } from '../types'

/**
 * Poll the already-sanitized public watchboard. The endpoint is a current-state
 * projection, so browser cache reuse would be a false freshness claim.
 */
export function usePublicWidgets() {
  const [widgets, setWidgets] = useState<PublicWidgets | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    const fetchWidgets = async () => {
      try {
        const response = await fetch('/api/v1/widgets', { cache: 'no-store' })
        if (!response.ok) throw new Error(`HTTP ${response.status}`)
        setWidgets(await response.json())
        setError('')
      } catch (reason) {
        setError(reason instanceof Error ? reason.message : 'watchboard fetch failed')
      }
    }

    fetchWidgets()
    const id = window.setInterval(fetchWidgets, 30_000)
    return () => window.clearInterval(id)
  }, [])

  return { widgets, error }
}
