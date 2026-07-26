import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const setSnapshot = vi.fn()
const setError = vi.fn()
const setLoading = vi.fn()

vi.mock('react', () => ({
  useCallback: (callback: () => Promise<void>) => callback,
  useEffect: (effect: () => void | (() => void)) => {
    effect()
  },
  useState: (initial: unknown) => {
    if (initial === null) return [initial, setSnapshot]
    if (initial === '') return [initial, setError]
    return [initial, setLoading]
  },
}))

import { useLiveTelemetry } from '../hooks/useLiveTelemetry'

describe('useLiveTelemetry', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.stubGlobal('window', {
      setInterval: vi.fn(() => 1),
      clearInterval: vi.fn(),
    })
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('bypasses the browser cache for every live snapshot request', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue({ version: 1 }),
    })
    vi.stubGlobal('fetch', fetchMock)

    useLiveTelemetry()

    await vi.waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith('/api/v1/live', { cache: 'no-store' })
    })
  })
})
