/**
 * Task 099 red goldens for the operator signal-cartography desk.
 * Fail on the pre-rebuild decision-observatory shell; pass after redesign.
 */
import { describe, expect, it } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import { LegacyObservatory as App, buildEvidenceSegments } from '../App'
import { liveSnapshot } from './fixture'
import type { PublicWidgets } from '../types'

const markup = renderToStaticMarkup(<App />)

function pausedWidgets(): PublicWidgets {
  return {
    gate: {
      state: 'paused',
      label: 'Paused',
      armed: false,
      killswitch: true,
      pause_state: 'active',
      mode: 'paused',
      executor_alive: false,
      updated_at: '2026-07-28T18:00:00Z',
    },
    wallet: { disclosure: 'withheld' },
    recent_signals: [],
    research: {
      clips: [],
      live: false,
      policy: {
        research_role: 'unverified_advisory_input',
        single_input_cap: 0.35,
        minimum_distinct_inputs: 4,
        review_status: 'unverified',
        primary_source_provenance: 'not_attested',
        can_set_conviction: false,
        can_authorize_execution: false,
      },
    },
    tradingview: { status: 'standby', last_ping: null, pending_alerts: null },
    business_health: { services: [], ok_count: 0, total: 0, timestamp: '' },
    system_health: {
      dashboard: 'ok',
      gate: 'paused',
      tradingview: 'standby',
      timestamp: '',
    },
    rendered_at: '2026-07-28T19:00:00Z',
  } as unknown as PublicWidgets
}

describe('operator current-decision band', () => {
  it('opens on a single CURRENT DECISION band, not a decorative metric grid', () => {
    expect(markup).toMatch(/CURRENT DECISION/i)
    expect(markup).toMatch(/HOLD|REFUSE|ATTENDED ACTION|not observed|unavailable/i)
    expect(markup).toMatch(/Pause|authority/i)
    expect(markup).toMatch(/Evidence freshness|freshness/i)
    expect(markup).toMatch(/next gate|Exact next/i)
    expect(markup).not.toMatch(/\$0\.00|NaN%|TODO metric|lorem ipsum/i)
  })

  it('keeps the evidence horizon with withdrawn values when nothing is observed', () => {
    expect(markup).toMatch(/Evidence horizon/i)
    expect(markup).toContain('not observed')
    expect(markup.match(/role="tab"/g)?.length).toBeGreaterThanOrEqual(5)
    expect(markup).toMatch(/role="tabpanel"/)
  })

  it('exposes keyboard-readable horizon controls and landmarks', () => {
    expect(markup).toMatch(/<main/)
    expect(markup).toMatch(/aria-label=/)
    expect(markup).toMatch(/role="tablist"/)
  })
})

describe('pause / stale / unknown withdrawal', () => {
  it('forbids live/autonomous claims when pause is active on the gate', () => {
    const html = renderToStaticMarkup(<App initialWidgets={pausedWidgets()} />)
    expect(html).not.toMatch(/\blive trading\b/i)
    expect(html).not.toMatch(/\bautonomous capital\b/i)
    expect(html).not.toMatch(/\bautonomous trading\b/i)
  })

  it('withdraws stale fleet and unknown nested values (Task 093 preserved)', () => {
    const segments = buildEvidenceSegments({
      snapshot: null,
      widgets: null,
      moss: null,
      fleet: { leases: 2, gates_open: 1, snapshot_age_s: 600 },
      execution: null,
      errors: { live: '', widgets: '', fleet: '', moss: '' },
    })
    const fleet = segments.find((s) => s.id === 'fleet')
    expect(fleet?.tone).toBe('degraded')
    expect(fleet?.value).toBe('not observed')

    const staleSnap = liveSnapshot()
    staleSnap.status = 'stale'
    staleSnap.markets.status = 'current'
    staleSnap.markets.execution = 'gated'
    const nested = buildEvidenceSegments({
      snapshot: staleSnap,
      widgets: null,
      moss: null,
      fleet: null,
      execution: 'gated',
      errors: { live: '', widgets: '', fleet: '', moss: '' },
    })
    expect(nested.find((s) => s.id === 'market')?.value).toBe('stale')
    expect(nested.find((s) => s.id === 'execution')?.value).toBe('unknown')
  })

  it('keeps observed_at distinct from response/render time', () => {
    const OBSERVED = '2026-07-28T18:00:00Z'
    const SERVED = '2026-07-28T19:00:00Z'
    const segment = buildEvidenceSegments({
      snapshot: null,
      widgets: {
        research: {
          clips: [
            {
              id: 'r1',
              title: 'Note',
              observed_at: OBSERVED,
              age_s: 3600,
            },
          ],
          live: false,
          policy: {
            research_role: 'unverified_advisory_input',
            single_input_cap: 0.35,
            minimum_distinct_inputs: 4,
            review_status: 'unverified',
            primary_source_provenance: 'not_attested',
            can_set_conviction: false,
            can_authorize_execution: false,
          },
        },
        rendered_at: SERVED,
      } as PublicWidgets,
      moss: null,
      fleet: null,
      execution: null,
      errors: { live: '', widgets: '', fleet: '', moss: '' },
    }).find((s) => s.id === 'research')

    expect(segment?.observedAt).toContain('18:00:00')
    expect(segment?.observedAt).not.toContain('19:00:00')
  })
})

describe('operator surface contracts', () => {
  it('does not add Telegram control, force-clear, or unbacked wallet CTAs', () => {
    expect(markup).not.toMatch(/force-clear|Force clear/i)
    expect(markup).not.toMatch(/Open Telegram|Telegram bot control/i)
    expect(markup).not.toMatch(/Connect wallet|Enable broker|Place order/i)
  })

  it('marks horizon segments with evidence-state attributes', () => {
    expect(markup).toMatch(/data-evidence-state=/)
  })
})
