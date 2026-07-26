import { useCallback, useEffect, useState } from 'react'
import type { MossSnapshot } from '../types'

/** Poll `/api/v1/moss`. Funding arrives as a band; see `MossSnapshot`. */
export function useMossSnapshot() {
  const [snapshot, setSnapshot] = useState<MossSnapshot | null>(null)
  const [error, setError] = useState('')

  const refresh = useCallback(async () => {
    try {
      const response = await fetch('/api/v1/moss')
      if (!response.ok) throw new Error(`MOSS observation unavailable (${response.status})`)
      setSnapshot((await response.json()) as MossSnapshot)
      setError('')
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'MOSS observation unavailable')
    }
  }, [])

  useEffect(() => {
    refresh()
    const timer = window.setInterval(refresh, 15_000)
    return () => window.clearInterval(timer)
  }, [refresh])

  return { snapshot, error, refresh }
}
