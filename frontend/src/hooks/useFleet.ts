import { useEffect, useState } from 'react'
import type { FleetCounts, FleetData } from '../types'

/**
 * Poll `/api/fleet`. The feed carries either coordination counts or the full
 * sanitized snapshot; the desk renders whichever it is given and never claims
 * that more exists somewhere else.
 */
export function useFleet() {
  const [fleet, setFleet] = useState<FleetData | FleetCounts | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    const fetchFleet = async () => {
      try {
        const response = await fetch('/api/fleet')
        if (!response.ok) throw new Error(`HTTP ${response.status}`)
        setFleet(await response.json())
        setError('')
      } catch (reason) {
        setError(reason instanceof Error ? reason.message : 'fleet fetch failed')
      }
    }

    fetchFleet()
    const id = setInterval(fetchFleet, 30_000)
    return () => clearInterval(id)
  }, [])

  return { fleet, error }
}
