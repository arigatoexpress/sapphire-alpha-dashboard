/**
 * The observatory shell rendered before effects run. This is the most
 * conservative state: no endpoint has reported, so unknown must stay unknown.
 */

import { describe, expect, it } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import App, { buildEvidenceSegments } from '../App'
import { liveSnapshot } from './fixture'

const markup = renderToStaticMarkup(<App />)

describe('anonymous decision observatory', () => {
  it('opens on CURRENT DECISION then thesis instruments', () => {
    expect(markup).toContain('CURRENT DECISION')
    expect(markup).toMatch(/HOLD|REFUSE|ATTENDED ACTION/)
    expect(markup).toContain('Operator desk · read-only view')
    expect(markup).toContain('Thesis now')
    expect(markup).toContain('No thesis observed.')
    expect(markup).toContain('Narrative &amp; regime')
    expect(markup).toContain('What would change the view')
    expect(markup).toContain('Learning loop')
    expect(markup).toContain('Execution floor')
    expect(markup).toContain('Needs attention')
    expect(markup).toContain('Evidence horizon')
  })

  it.each([
    ['a password field', /type="password"/],
    ['a sign-in control', /Sign in/],
    ['an operator-access form', /Operator access|Enter observatory/],
    ['a username field', /autocomplete="username"/i],
  ])('does not render %s', (_what, pattern) => {
    expect(markup).not.toMatch(pattern)
  })

  it('uses visible brand text as the home link name', () => {
    expect(markup).toContain('href="/"')
    expect(markup).not.toContain('aria-label="Sapphire Alpha home"')
  })

  it('puts current operational evidence above the missing-thesis state', () => {
    const liveMarkup = renderToStaticMarkup(
      <App initialSnapshot={liveSnapshot()} />,
    )

    expect(liveMarkup).toContain('SYSTEM NOW')
    expect(liveMarkup).toContain('Snapshot')
    expect(liveMarkup).toContain('live · 4s ago')
    expect(liveMarkup).toContain('Market activity')
    expect(liveMarkup).toContain('599 / min')
    expect(liveMarkup).toContain('Current components')
    expect(liveMarkup).toContain('7 / 10')
    expect(liveMarkup).toContain('Home compute')
    expect(liveMarkup).toContain('healthy · 0s ago')
    expect(liveMarkup.indexOf('SYSTEM NOW')).toBeLessThan(
      liveMarkup.indexOf('CURRENT DECISION'),
    )
  })

  it('renders the current allowlisted sovereign thesis without private research fields', () => {
    const snapshot = liveSnapshot()
    snapshot.desk.epistemics.fresh = false
    snapshot.desk.epistemics.thesis = null
    snapshot.research = {
      observed_at: new Date().toISOString(),
      thesis: {
        claim: 'Bitcoin has put in the cycle low for this corrective phase.',
        stance: 'uncertain',
        probability: 0.524,
        horizon_days: 90,
      },
    }

    const researchMarkup = renderToStaticMarkup(<App initialSnapshot={snapshot} />)

    expect(researchMarkup).toContain('Bitcoin has put in the cycle low for this corrective phase.')
    expect(researchMarkup).toContain('52%')
    expect(researchMarkup).toContain('uncertain')
    expect(researchMarkup).toContain('90 days')
    const researchEvidence = buildEvidenceSegments({
      snapshot,
      widgets: null,
      moss: null,
      fleet: null,
      execution: snapshot.desk.execution,
      errors: { live: '', widgets: '', fleet: '', moss: '' },
    }).find((segment) => segment.id === 'research')
    expect(researchEvidence?.source).toBe('/api/v1/live · research')
    expect(researchEvidence?.tone).toBe('current')
    expect(researchMarkup).not.toContain('No thesis observed.')
    expect(researchMarkup).not.toMatch(/position|account|raw prompt/i)
  })

  it('withdraws retained research everywhere when the live poll later fails', () => {
    const snapshot = liveSnapshot()
    snapshot.research = {
      observed_at: new Date().toISOString(),
      thesis: {
        claim: 'Bitcoin has put in the cycle low for this bear/corrective phase',
        stance: 'uncertain',
        probability: 0.525,
        horizon_days: 90,
      },
    }

    const failedMarkup = renderToStaticMarkup(
      <App initialSnapshot={snapshot} initialLiveError="Telemetry unavailable (429)" />,
    )
    const researchEvidence = buildEvidenceSegments({
      snapshot,
      widgets: null,
      moss: null,
      fleet: null,
      execution: snapshot.desk.execution,
      errors: { live: 'Telemetry unavailable (429)', widgets: '', fleet: '', moss: '' },
    }).find((segment) => segment.id === 'research')

    expect(failedMarkup).not.toContain(
      'Bitcoin has put in the cycle low for this bear/corrective phase',
    )
    expect(failedMarkup).not.toContain('1 current thesis')
    expect(failedMarkup).toContain('No thesis observed.')
    expect(researchEvidence?.value).not.toBe('1 current thesis')
    expect(researchEvidence?.tone).not.toBe('current')
  })

  it('withdraws a research projection after its independent 24-hour TTL', () => {
    const snapshot = liveSnapshot()
    snapshot.research = {
      observed_at: new Date(Date.now() - 24 * 60 * 60 * 1000 - 1).toISOString(),
      thesis: {
        claim: 'Bitcoin has put in the cycle low for this bear/corrective phase',
        stance: 'uncertain',
        probability: 0.525,
        horizon_days: 90,
      },
    }

    const expiredMarkup = renderToStaticMarkup(<App initialSnapshot={snapshot} />)

    expect(expiredMarkup).not.toContain(
      'Bitcoin has put in the cycle low for this bear/corrective phase',
    )
    expect(expiredMarkup).not.toContain('1 current thesis')
  })

  it('withdraws research when the retained parent freshness exceeds runtime TTL', () => {
    const snapshot = liveSnapshot()
    snapshot.status = 'live'
    snapshot.freshness_s = 181
    snapshot.research = {
      observed_at: new Date().toISOString(),
      thesis: {
        claim: 'Bitcoin has put in the cycle low for this bear/corrective phase',
        stance: 'uncertain',
        probability: 0.525,
        horizon_days: 90,
      },
    }

    const staleMarkup = renderToStaticMarkup(<App initialSnapshot={snapshot} />)

    expect(staleMarkup).not.toContain(
      'Bitcoin has put in the cycle low for this bear/corrective phase',
    )
    expect(staleMarkup).not.toContain('1 current thesis')
  })
})

describe('evidence contract', () => {
  it('keeps every source on one interactive horizon', () => {
    expect(markup.match(/role="tab"/g)).toHaveLength(7)
    for (const segment of [
      'Snapshot',
      'Market feed',
      'Decision gate',
      'Execution',
      'Research',
      'Coordination',
      'On-chain',
    ]) {
      expect(markup).toContain(segment)
    }
    for (const field of ['Source', 'Observed', 'Freshness', 'Authority', 'Uncertainty']) {
      expect(markup).toContain(field)
    }
  })

  it('preserves description-list semantics inside the active tab panel', () => {
    expect(markup).toMatch(
      /<div id="evidence-horizon-detail" role="tabpanel"[^>]*><dl class="evidence-horizon-detail">/,
    )
    expect(markup).not.toMatch(/<dl[^>]*role="tabpanel"/)
  })

  it('demotes retained live values when a later poll fails', () => {
    const snapshot = liveSnapshot()
    const segments = buildEvidenceSegments({
      snapshot,
      widgets: null,
      moss: null,
      fleet: null,
      execution: snapshot.desk?.execution ?? snapshot.markets.execution,
      errors: {
        live: 'poll failed',
        widgets: '',
        fleet: '',
        moss: '',
      },
    })

    for (const segment of segments.slice(0, 4)) {
      expect(segment.tone).toBe('degraded')
    }
    expect(segments[0].observedAt).toContain('Z')
    expect(segments[0].uncertainty).toContain('last report')
  })

  it('refuses fresh-looking nested values when the persisted parent is stale', () => {
    const snapshot = liveSnapshot()
    snapshot.status = 'stale'
    snapshot.markets.status = 'current'
    snapshot.markets.decision_gate = 'manual'
    snapshot.markets.execution = 'gated'
    snapshot.desk.execution = 'gated'

    const segments = buildEvidenceSegments({
      snapshot,
      widgets: null,
      moss: null,
      fleet: null,
      execution: snapshot.desk.execution,
      errors: { live: '', widgets: '', fleet: '', moss: '' },
    })

    expect(segments[1].value).toBe('stale')
    expect(segments[2].value).toBe('unknown')
    expect(segments[3].value).toBe('unknown')
    for (const segment of segments.slice(0, 4)) {
      expect(segment.tone).toBe('degraded')
    }
  })

  it('renders missing pause truth as unavailable instead of clear', () => {
    const snapshot = liveSnapshot()
    snapshot.desk.safety_floor.pause_clear = null
    const widgets: import('../types').PublicWidgets = {
      gate: {
        state: 'unavailable',
        label: 'Pause state unavailable',
        armed: null,
        killswitch: null,
        pause_state: 'unknown',
        mode: 'unavailable',
        executor_alive: null,
        updated_at: null,
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
        gate: 'unavailable',
        tradingview: 'standby',
        timestamp: '',
      },
      rendered_at: '2026-07-28T18:00:00Z',
    }

    const markupWithUnknownPause = renderToStaticMarkup(
      <App initialWidgets={widgets} />,
    )

    expect(markupWithUnknownPause).toContain('Pause state is unavailable')
    expect(markupWithUnknownPause).not.toContain('Pause is clear')
  })

  it('orders the thesis pulse and changes before evidence details', () => {
    expect(markup.indexOf('01 · Thesis pulse')).toBeLessThan(
      markup.indexOf('02 · Needs attention'),
    )
    expect(markup.indexOf('02 · Needs attention')).toBeLessThan(
      markup.indexOf('03 · What changed'),
    )
    expect(markup.indexOf('03 · What changed')).toBeLessThan(
      markup.indexOf('04 · Evidence'),
    )
  })

  it('makes the control-surface boundary explicit', () => {
    expect(markup).toContain('This page observes the desk.')
    expect(markup).toContain('controls isolated')
  })

  it('never invents a deployed build identity and links to the manifest', () => {
    expect(markup).toContain('Build not verified')
    expect(markup).toContain('href="/api/build"')
    expect(markup).toContain('inspect manifest')
  })
})

describe('honest empty state', () => {
  it('does not turn missing observations into zero, safe, or live', () => {
    expect(markup).toContain('not observed')
    expect(markup).toContain('Pause state is unavailable')
    expect(markup).toContain('No event report yet')
    expect(markup).toContain('No component report has arrived yet')
    expect(markup).not.toContain('0 / 0')
    expect(markup).not.toMatch(/>off(?:line)?</)
  })

  it('does not resurrect the discarded card-wall language', () => {
    expect(markup).not.toContain('Plant status')
    expect(markup).not.toContain('System mesh')
    expect(markup).not.toContain('LIVE RAILS')
    expect(markup).not.toContain('Autonomous capital')
    expect(markup).not.toMatch(/\bOOS\b/)
    expect(markup).not.toMatch(/\bbacktest\b/i)
    expect(markup).not.toMatch(/\bsealed trial\b/i)
  })

  it('states the measurement rule in plain language', () => {
    expect(markup).toContain('A number is observed, or it is absent.')
    expect(markup).toContain('unknown—not zero, safe, or live')
    expect(markup).toContain('Waiting for the first observed event.')
  })
})

describe('research provenance truth', () => {
  it('labels timestamped analyst text as unverified rather than reviewed', () => {
    const widgets = {
      gate: {
        state: 'unavailable',
        label: 'Pause state unavailable',
        armed: null,
        killswitch: null,
        pause_state: 'unknown',
        mode: 'unavailable',
        executor_alive: null,
        updated_at: null,
      },
      wallet: { disclosure: 'withheld' },
      recent_signals: [],
      research: {
        clips: [
          {
            id: 'clip-1',
            title: 'Timestamped analyst text',
            observed_at: '2026-07-28T18:00:00Z',
            age_s: 5,
          },
        ],
        live: false,
        policy: {
          research_role: 'unverified_advisory_input',
          single_input_cap: 0.25,
          minimum_distinct_inputs: 4,
          review_status: 'unverified',
          primary_source_provenance: 'not_attested',
          can_set_conviction: false,
          can_authorize_execution: false,
        },
      },
      tradingview: { status: 'not_observed', last_ping: null, pending_alerts: null },
      business_health: { services: [], ok_count: 0, total: 0, timestamp: '' },
      system_health: {
        dashboard: 'ok',
        gate: 'unavailable',
        tradingview: 'not_observed',
        timestamp: '',
      },
      rendered_at: '2026-07-28T18:00:05Z',
    } as unknown as import('../types').PublicWidgets

    const researchMarkup = renderToStaticMarkup(<App initialWidgets={widgets} />)

    expect(researchMarkup).toContain('1 unverified')
    expect(researchMarkup).toContain('Unverified advisory input')
    expect(researchMarkup).not.toMatch(/\breviewed\b/i)
  })
})
