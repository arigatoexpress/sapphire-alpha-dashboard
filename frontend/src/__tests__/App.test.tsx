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
  it('opens on the operating boundary rather than a decorative dashboard', () => {
    expect(markup).toContain('Decision observatory · read only')
    expect(markup).toContain('Awaiting observed state.')
    expect(markup).toContain('Needs attention')
    expect(markup).toContain('Read and review only')
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

  it('orders attention and change before evidence details', () => {
    expect(markup.indexOf('01 · Needs attention')).toBeLessThan(
      markup.indexOf('02 · What changed'),
    )
    expect(markup.indexOf('02 · What changed')).toBeLessThan(
      markup.indexOf('03 · Authority'),
    )
    expect(markup.indexOf('03 · Authority')).toBeLessThan(
      markup.indexOf('04 · Evidence'),
    )
  })

  it('makes the non-authority boundary explicit', () => {
    expect(markup).toContain('Evidence may challenge. It may not authorize.')
    expect(markup).toContain('This surface cannot place a trade')
    expect(markup).toContain('Anonymous · read only · no execution authority')
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
    expect(markup).toContain('Waiting for the first report')
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
  })

  it('states the measurement rule in plain language', () => {
    expect(markup).toContain('A number is observed, or it is absent.')
    expect(markup).toContain('unknown—not zero, safe, or live')
    expect(markup).toContain('Waiting for the first observed event.')
  })
})
