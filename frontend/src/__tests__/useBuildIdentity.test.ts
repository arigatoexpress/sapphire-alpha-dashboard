import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const setBuild = vi.fn()

vi.mock('react', () => ({
  useEffect: (effect: () => void | (() => void)) => {
    effect()
  },
  useState: () => [null, setBuild],
}))

import { useBuildIdentity } from '../hooks/useBuildIdentity'

describe('useBuildIdentity', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('fetches the immutable runtime manifest without browser cache reuse', async () => {
    const surface = {
      entrypoint_url: '/',
      entrypoint_sha256: 'b'.repeat(64),
      asset_count: 3,
      manifest_sha256: 'c'.repeat(64),
    }
    const identity = {
      schema: 1,
      source_sha: 'a'.repeat(40),
      build_id: 'build-123',
      runtime_service: 'sapphire-alpha-dashboard',
      runtime_revision: 'sapphire-alpha-dashboard-00042-abc',
      surfaces: {
        operator: { ...surface, entrypoint_url: '/dashboard' },
        public: surface,
      },
      complete: true,
    }
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue(identity),
    })
    vi.stubGlobal('fetch', fetchMock)

    useBuildIdentity()

    await vi.waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith('/api/build', { cache: 'no-store' })
      expect(setBuild).toHaveBeenCalledWith(identity)
    })
  })
})
