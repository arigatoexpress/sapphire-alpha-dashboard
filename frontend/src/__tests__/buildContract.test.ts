import { describe, expect, it } from 'vitest'
import { parseBuildIdentity, shortBuildValue } from '@shared/build'

const surface = {
  entrypoint_url: '/',
  entrypoint_sha256: 'a'.repeat(64),
  asset_count: 4,
  manifest_sha256: 'b'.repeat(64),
}
const operatorSurface = { ...surface, entrypoint_url: '/dashboard' }

describe('shared build contract', () => {
  it('accepts the complete public-safe schema', () => {
    const payload = {
      schema: 1,
      source_sha: 'c'.repeat(40),
      build_id: 'build-123',
      runtime_service: 'sapphire-alpha-dashboard',
      runtime_revision: 'sapphire-alpha-dashboard-00042-abc',
      surfaces: { operator: operatorSurface, public: surface },
      complete: true,
    }

    expect(parseBuildIdentity(payload)).toEqual(payload)
  })

  it('rejects malformed digests and missing surfaces', () => {
    expect(parseBuildIdentity({ schema: 1 })).toBeNull()
    expect(
      parseBuildIdentity({
        schema: 1,
        source_sha: 'unknown',
        build_id: 'unknown',
        runtime_service: 'local',
        runtime_revision: 'local',
        surfaces: {
          operator: { ...surface, manifest_sha256: 'not-a-digest' },
          public: surface,
        },
        complete: false,
      }),
    ).toBeNull()
  })

  it('rejects an internally inconsistent complete claim', () => {
    expect(
      parseBuildIdentity({
        schema: 1,
        source_sha: 'unknown',
        build_id: 'unknown',
        runtime_service: 'local',
        runtime_revision: 'local',
        surfaces: {
          operator: operatorSurface,
          public: surface,
        },
        complete: true,
      }),
    ).toBeNull()
  })

  it('keeps absent values explicit', () => {
    expect(shortBuildValue(null)).toBe('not observed')
    expect(shortBuildValue('1234567890abcdef', 8)).toBe('12345678')
  })
})
