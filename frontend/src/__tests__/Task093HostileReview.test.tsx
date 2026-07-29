import { describe, expect, it } from 'vitest'

import { buildEvidenceSegments } from '../App'
import type { FleetCounts } from '../types'

describe('Task 093 hostile stale-UI contract', () => {
  it('withdraws stale fleet counts instead of rendering present-tense nouns', () => {
    const fleet: FleetCounts = {
      leases: 2,
      gates_open: 1,
      snapshot_age_s: 600,
    }

    const coordination = buildEvidenceSegments({
      snapshot: null,
      widgets: null,
      moss: null,
      fleet,
      execution: null,
      errors: { live: '', widgets: '', fleet: '', moss: '' },
    }).find(({ id }) => id === 'fleet')

    expect(coordination?.tone).toBe('degraded')
    expect(coordination?.value).toBe('not observed')
  })
})
