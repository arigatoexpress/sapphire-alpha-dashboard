import { describe, expect, it } from 'vitest'

import { buildEvidenceSegments } from '../App'
import type { FleetCounts, MossSnapshot, PublicWidgets } from '../types'

const OBSERVED_AT = '2026-07-28T18:00:00Z'
const REQUEST_TIME = '2026-07-28T19:00:00Z'

describe('persisted evidence timestamps', () => {
  it('never presents widget render time as the research observation', () => {
    const widgets = {
      research: {
        clips: [{
          id: 'research-001',
          title: 'Observed note',
          observed_at: OBSERVED_AT,
          age_s: 3600,
        }],
      },
      rendered_at: REQUEST_TIME,
    } as PublicWidgets

    const segment = buildEvidenceSegments({
      snapshot: null,
      widgets,
      moss: null,
      fleet: null,
      execution: null,
      errors: { live: '', widgets: '', fleet: '', moss: '' },
    }).find(({ id }) => id === 'research')

    expect(segment?.observedAt).toBe('2026-07-28 18:00:00Z')
    expect(segment?.observedAt).not.toContain('19:00:00')
    expect(segment?.freshness).toBe('1h ago')
    expect(segment?.uncertainty).not.toContain('age not computed')
  })

  it('never presents MOSS response time as the on-chain observation', () => {
    const moss = {
      status: 'live',
      freshness_s: 10,
      observed_at: OBSERVED_AT,
      served_at: REQUEST_TIME,
      authority: 'read-only',
    } as MossSnapshot

    const segment = buildEvidenceSegments({
      snapshot: null,
      widgets: null,
      moss,
      fleet: null,
      execution: null,
      errors: { live: '', widgets: '', fleet: '', moss: '' },
    }).find(({ id }) => id === 'moss')

    expect(segment?.observedAt).toBe('2026-07-28 18:00:00Z')
    expect(segment?.observedAt).not.toContain('19:00:00')
  })

  it('does not label stale or timeless fleet counts as current', () => {
    for (const fleet of [
      { leases: 2, gates_open: 1, snapshot_age_s: 600 },
      { leases: 2, gates_open: 1, snapshot_age_s: null },
    ] satisfies FleetCounts[]) {
      const segment = buildEvidenceSegments({
        snapshot: null,
        widgets: null,
        moss: null,
        fleet,
        execution: null,
        errors: { live: '', widgets: '', fleet: '', moss: '' },
      }).find(({ id }) => id === 'fleet')

      expect(segment?.tone).not.toBe('current')
    }
  })
})
