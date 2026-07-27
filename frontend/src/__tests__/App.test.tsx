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
import App, { AgentPanel, MarketPanel, SafetyRail } from '../App'
import type { LiveAgent, LiveSnapshot } from '../types'

const markup = renderToStaticMarkup(<App />)

describe('no gate', () => {
  it('renders the desk without asking for anything', () => {
    expect(markup).toContain('Plant status')
    expect(markup).toContain('No paper backtest leaderboards')
    expect(markup).toContain('Cycle model')
    expect(markup).toContain('Liquidity')
    expect(markup).toContain('Market structure')
    expect(markup).toContain('Frontier technology')
    expect(markup).toContain('Fundamentals')
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

describe('the market aperture', () => {
  it('makes plant posture the first-class decision surface', () => {
    expect(markup).toContain('data-market-aperture="true"')
    expect(markup).toContain('Plant status')
    expect(markup).toContain('designated rails')
    expect(markup).toContain('Cycle model')
  })

  it('labels the classified task-agent count without conflating it with services', () => {
    expect(markup).toContain('Task agents active')
    expect(markup).not.toContain('Agents working')
    expect(markup).toContain('System components')
    expect(markup).toContain('What is running')
    expect(markup).not.toContain('Agent presence')
  })

  it('keeps advisory research visibly outside execution authority', () => {
    expect(markup).toContain('Evidence, not authority')
    expect(markup).toContain('Execution stays outside this lens')
  })
})

describe('decision-first hierarchy', () => {
  it('puts live rails ahead of system routes', () => {
    expect(markup.indexOf('LIVE RAILS')).toBeLessThan(markup.indexOf('System mesh'))
    expect(markup).toContain('What the plant is doing')
    expect(markup).toContain('Robinhood Agentic')
    expect(markup).toContain('MegaETH')
    expect(markup).not.toContain('Paper strategy evidence')
  })

  it('keeps the system mesh open as a first-class analysis surface', () => {
    expect(markup).toContain('id="system"')
    expect(markup).toContain('System mesh')
    expect(markup).toContain('Routes, agents, market feed, fleet')
    expect(markup).not.toContain('<details id="system"')
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
    expect(markup).toContain('No component report has arrived yet')
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

describe('system component visibility', () => {
  it('shows every observed component and puts live work ahead of offline routes', () => {
    const offline: LiveAgent[] = Array.from({ length: 13 }, (_, index) => ({
      id: `offline-route-${index}`,
      role: `Offline route ${index}`,
      state: 'offline',
      activity: `offline activity ${index}`,
      verification: 'not_applicable',
      provider_class: 'unassigned',
      updated_at: '2026-07-24T12:00:00+00:00',
    }))
    const live: LiveAgent[] = [
      {
        id: 'live-source-one',
        role: 'Live source one',
        state: 'working',
        activity: 'reporting with source errors',
        verification: 'pending',
        provider_class: 'local CPU',
        updated_at: '2026-07-26T12:00:00+00:00',
      },
      {
        id: 'live-source-two',
        role: 'Live source two',
        state: 'working',
        activity: 'observing live signals',
        verification: 'verified',
        provider_class: 'local CPU',
        updated_at: '2026-07-26T12:00:00+00:00',
      },
    ]

    const panel = renderToStaticMarkup(
      <AgentPanel agents={[...offline, ...live]} observed />,
    )

    expect(panel).toContain('offline activity 0')
    expect(panel).toContain('offline activity 12')
    expect(panel).toContain('reporting with source errors')
    expect(panel.indexOf('reporting with source errors')).toBeLessThan(
      panel.indexOf('offline activity 0'),
    )
  })
})
