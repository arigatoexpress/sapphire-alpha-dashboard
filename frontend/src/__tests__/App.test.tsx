/**
 * The desk shell, rendered.
 *
 * Effects do not run under `renderToStaticMarkup`, so no fetch happens and the
 * page renders its no-data state — which is precisely the state that used to
 * show a login form. If a credential prompt could still appear, it would appear
 * here.
 */

import { describe, expect, it } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import emptyFixture from '../../../shared/__tests__/fixtures/empty-snapshot.json'
import App, { MarketPanel, SafetyRail } from '../App'
import type { LiveSnapshot } from '../types'

const markup = renderToStaticMarkup(<App />)

describe('no gate', () => {
  it('renders the desk without asking for anything', () => {
    expect(markup).toContain('Machine Room')
    expect(markup).toContain('Ari’s thesis is the mandate')
    expect(markup).toContain('Cowen')
    expect(markup).toContain('Hayes')
    expect(markup).toContain('Bankless')
    expect(markup).toContain('Limitless')
    expect(markup).toContain('Nadeau')
  })

  it.each([
    ['a password field', /type="password"/],
    ['a sign-in control', /Sign in/],
    ['the operator-access form', /Operator access|Enter observatory|Return to public view/],
    ['a username field', /autocomplete="username"/i],
  ])('has no %s', (_what, pattern) => {
    expect(markup).not.toMatch(pattern)
  })

  it('uses its visible brand text as the home link name', () => {
    expect(markup).toContain('href="/"')
    expect(markup).not.toContain('aria-label="Sapphire Alpha home"')
  })
})

describe('no second tier is described', () => {
  it.each([
    /aggregated \+ delayed/,
    /operator detail/,
    /Operator sign-in/,
    /aggregated, delayed/,
    /public projection/i,
  ])('does not claim %s exists', (pattern) => {
    expect(markup).not.toMatch(pattern)
  })

  it('states the single-view policy instead', () => {
    expect(markup).toContain('the figure the machines reported')
  })
})

describe('with nothing observed', () => {
  it('says so rather than printing zeroes', () => {
    /* Four hero metrics, the freshness readouts and the safety rail all have no
       reading before the first fetch. None of them may invent one. */
    expect(markup).toContain('not observed')
    expect(markup).not.toContain('0 / 0')
    expect(markup).toContain('No agent report has arrived yet')
    expect(markup).toContain('No event report has arrived yet')
  })

  it('does not turn an unknown safety state into off or offline', () => {
    expect(markup).not.toMatch(/>off</)
    expect(markup).not.toMatch(/>offline</)
  })

  it('ignores placeholder market defaults in an empty endpoint response', () => {
    const snapshot = emptyFixture as LiveSnapshot
    const safety = renderToStaticMarkup(<SafetyRail snapshot={snapshot} />)
    const market = renderToStaticMarkup(<MarketPanel snapshot={snapshot} />)

    expect(safety.match(/>not observed</g)?.length).toBe(4)
    expect(market).not.toMatch(/>off(?:line)?</i)
    expect(market).toContain('not observed')
  })

  it('narrates the absence in a full sentence', () => {
    expect(markup).toContain('Waiting for the first report to arrive')
  })
})
