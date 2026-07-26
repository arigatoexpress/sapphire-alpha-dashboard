import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const setWidgets = vi.fn()
const setError = vi.fn()

vi.mock('react', () => ({
  useEffect: (effect: () => void | (() => void)) => {
    effect()
  },
  useState: (initial: unknown) => {
    if (initial === null) return [initial, setWidgets]
    return [initial, setError]
  },
}))

import { usePublicWidgets } from '../hooks/usePublicWidgets'

describe('usePublicWidgets', () => {
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

  it('fetches the current sanitized watchboard without using a browser cache', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue({ public_view: true }),
    })
    vi.stubGlobal('fetch', fetchMock)

    usePublicWidgets()

    await vi.waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith('/api/v1/widgets', { cache: 'no-store' })
    })
  })
})
