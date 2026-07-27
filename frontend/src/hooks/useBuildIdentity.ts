import { useEffect, useState } from 'react'
import { parseBuildIdentity } from '@shared/build'
import type { BuildIdentity } from '@shared/build'

/** Fetch once: build identity is immutable for the lifetime of a revision. */
export function useBuildIdentity() {
  const [build, setBuild] = useState<BuildIdentity | null>(null)

  useEffect(() => {
    let active = true

    fetch('/api/build', { cache: 'no-store' })
      .then((response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`)
        return response.json() as Promise<unknown>
      })
      .then((payload) => {
        if (active) setBuild(parseBuildIdentity(payload))
      })
      .catch(() => {
        if (active) setBuild(null)
      })

    return () => {
      active = false
    }
  }, [])

  return build
}
