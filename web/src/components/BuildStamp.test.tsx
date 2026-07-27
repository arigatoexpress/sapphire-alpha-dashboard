import { describe, expect, it } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import BuildStamp, { BuildStampRecord } from './BuildStamp'
import type { BuildIdentity } from '@shared/build'

describe('BuildStamp', () => {
  it('does not invent runtime provenance before the endpoint answers', () => {
    const markup = renderToStaticMarkup(<BuildStamp />)

    expect(markup).toContain('Runtime build not verified')
    expect(markup).toContain('href="/api/build"')
    expect(markup).toContain('Inspect manifest')
    expect(markup).not.toContain('unknown assets')
  })

  it('shows partial observed values instead of hiding them behind completeness', () => {
    const surface = {
      entrypoint_url: '/',
      entrypoint_sha256: null,
      asset_count: 0,
      manifest_sha256: null,
    }
    const build: BuildIdentity = {
      schema: 1,
      source_sha: 'a'.repeat(40),
      build_id: 'build-partial',
      runtime_service: 'local',
      runtime_revision: 'local',
      surfaces: { operator: surface, public: surface },
      complete: false,
    }
    const markup = renderToStaticMarkup(<BuildStampRecord build={build} />)

    expect(markup).toContain('aaaaaaaaaaaa')
    expect(markup).toContain('build-partial')
    expect(markup).toContain('incomplete')
    expect(markup).toContain('not observed/not observed')
  })
})
