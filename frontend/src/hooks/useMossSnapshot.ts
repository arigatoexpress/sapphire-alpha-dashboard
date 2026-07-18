import { useCallback, useEffect, useState } from 'react'
import type { MossSnapshot } from '../types'

export function useMossSnapshot(authHeader: string) {
  const [snapshot, setSnapshot] = useState<MossSnapshot | null>(null)
  const [error, setError] = useState('')

  const refresh = useCallback(async () => {
    try {
      const response = await fetch('/api/v1/moss', {
        headers: authHeader ? { Authorization: authHeader } : {},
      })
      if (!response.ok) throw new Error(`MOSS observation unavailable (${response.status})`)
      setSnapshot((await response.json()) as MossSnapshot)
      setError('')
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'MOSS observation unavailable')
    }
  }, [authHeader])

  useEffect(() => {
    refresh()
    const timer = window.setInterval(refresh, 15_000)
    return () => window.clearInterval(timer)
  }, [refresh])

  return { snapshot, error, refresh }
}
