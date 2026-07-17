import { useEffect, useState } from 'react'
import type { FleetCounts, FleetData } from '../types'

/** Poll /api/fleet. Authenticated users get the full sanitized snapshot;
 *  anonymous public read-only mode gets counts only (FleetCounts). */
export function useFleet(authHeader: string) {
  const [fleet, setFleet] = useState<FleetData | FleetCounts | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    const fetchFleet = async () => {
      try {
        const r = await fetch('/api/fleet', {
          headers: authHeader ? { Authorization: authHeader } : {},
        })
        if (r.status === 401) {
          setFleet(null)
          return
        }
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        setFleet(await r.json())
        setError('')
      } catch (e) {
        setError(e instanceof Error ? e.message : 'fleet fetch failed')
      }
    }

    fetchFleet()
    const id = setInterval(fetchFleet, 30000)
    return () => clearInterval(id)
  }, [authHeader])

  return { fleet, error }
}
