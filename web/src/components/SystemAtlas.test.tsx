import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import SystemAtlas from './SystemAtlas'
import { SYSTEM_ATLAS_STAGES } from '@/data/system-atlas'
import type { LiveSnapshot } from '@shared/telemetry'
import liveFixture from '../../../shared/__tests__/fixtures/live-snapshot.json'

const markup = renderToStaticMarkup(<SystemAtlas />)
const live = liveFixture as LiveSnapshot
const liveMarkup = renderToStaticMarkup(<SystemAtlas snapshot={live} />)

describe('public system atlas', () => {
  it('explains the complete evidence path in plain language', () => {
    expect(markup).toContain('See the whole system in one orbit.')
    expect(markup).toContain('In plain language')
    for (const stage of [
      'Observe',
      'Research',
      'Agent market',
      'Policy boundary',
      'Public record',
    ]) {
      expect(markup).toContain(stage)
    }
    expect(markup).toContain('Nothing on this page can approve or place a trade.')
  })

  it('renders an accessible, no-JavaScript architecture contract when runtime is absent', () => {
    expect(markup).toContain('aria-labelledby="system-atlas-title"')
    expect(markup).toContain('Runtime topology not observed')
    expect(markup).toContain('<details')
    expect(markup).not.toContain('<canvas')

    for (const stage of SYSTEM_ATLAS_STAGES) {
      expect(markup).toContain(`data-atlas-stage="${stage.id}"`)
      expect(markup).toContain(stage.title)
      expect(markup).toContain(stage.plain)
      expect(markup).toContain(stage.source)
      expect(markup).toContain(stage.authority)
      expect(stage.source.trim().length).toBeGreaterThan(0)
      expect(stage.authority).toBe('none')
    }
  })

  it('describes agents as proposal-only roles, never current runtime workers', () => {
    for (const role of ['Researcher', 'Forecaster', 'Critic']) {
      expect(markup).toContain(role)
    }
    expect(markup).toContain('proposal-only')
    expect(markup).toContain('Runtime status is not asserted')
    expect(markup).not.toMatch(/\bagents? (are|is) (running|live|autonomous)\b/i)
    expect(markup).not.toMatch(/\bexecutes? trades?\b/i)
  })

  it('publishes expert provenance and state semantics without invented metrics', () => {
    expect(markup).toContain('Technical contract')
    expect(markup).toContain('Static architecture contract')
    expect(markup).toContain('runtime evidence: not observed')
    expect(markup).toContain('authority: none')
    expect(markup).not.toMatch(/\b\d+(?:\.\d+)?%\s+(?:win|return|alpha|accuracy)\b/i)
    expect(markup).not.toMatch(/\$\d+\s+(?:profit|pnl|made)\b/i)
  })

  it('renders every admitted runtime node and edge exactly once', () => {
    expect(liveMarkup).toContain('runtime evidence: live')
    expect(liveMarkup).toContain(live.observed_at!)

    for (const node of live.nodes) {
      expect(liveMarkup.match(new RegExp(`data-atlas-node="${node.id}"`, 'g'))).toHaveLength(1)
      expect(liveMarkup).toContain(node.label)
    }
    for (const link of live.links) {
      const id = `${link.source}-&gt;${link.target}`
      expect(liveMarkup.match(new RegExp(`data-atlas-link="${id}"`, 'g'))).toHaveLength(1)
    }
  })

  it('animates only an observed non-zero runtime flow and exposes unavailable node state as absence', () => {
    expect(liveMarkup).toMatch(
      /data-atlas-link="intelligence-&gt;markets"[^>]*data-flow="observed"/,
    )
    expect(liveMarkup).toMatch(
      /data-atlas-link="public-edge-&gt;orchestration"[^>]*data-flow="unavailable"/,
    )
    const publicEdge = liveMarkup.match(
      /data-atlas-node="public-edge"[\s\S]*?<\/li>/,
    )?.[0]
    expect(publicEdge).toContain('not observed')
    expect(publicEdge).not.toContain('0 evt/min')

    const unavailableOrchestration = liveMarkup.match(
      /data-atlas-node="orchestration"[\s\S]*?<\/li>/,
    )?.[0]
    expect(unavailableOrchestration).toContain('<dd>3h</dd>')
    expect(unavailableOrchestration).toContain('<dd>not observed</dd>')
    expect(unavailableOrchestration).not.toContain('<dd>medium</dd>')

    expect(liveMarkup).toContain('599 evt/min')
  })

  it('preserves a valid sub-unit rate instead of displaying animated flow as zero', () => {
    const lowRate = structuredClone(live)
    const observed = lowRate.links.find(
      (link) => link.source === 'intelligence' && link.target === 'markets',
    )!
    observed.event_rate = 0.2
    const lowRateMarkup = renderToStaticMarkup(
      <SystemAtlas snapshot={lowRate} />,
    )

    expect(lowRateMarkup).toMatch(
      /data-atlas-link="intelligence-&gt;markets"[^>]*data-flow="observed"/,
    )
    const observedLink = lowRateMarkup.match(
      /<line[^>]*data-atlas-link="intelligence-&gt;markets"[\s\S]*?<\/line>/,
    )?.[0]
    expect(observedLink).toContain('0.2 evt/min')
    expect(observedLink).not.toContain('; 0 evt/min')
  })

  it('withdraws current styling and motion when the retained snapshot is stale or a poll failed', () => {
    const stale = structuredClone(live)
    stale.status = 'stale'
    const staleMarkup = renderToStaticMarkup(<SystemAtlas snapshot={stale} />)
    const failedMarkup = renderToStaticMarkup(
      <SystemAtlas snapshot={live} sourceError="status 503" />,
    )

    for (const html of [staleMarkup, failedMarkup]) {
      expect(html).not.toContain('data-flow="observed"')
      expect(html).toContain('data-flow="unavailable"')
      expect(html).toContain('retained snapshot')
    }
  })
})

describe('system atlas motion and responsive contracts', () => {
  const css = readFileSync(resolve(__dirname, '../app/globals.css'), 'utf8')

  it('uses one bounded path animation and disables it for reduced motion', () => {
    expect(css).toMatch(/@keyframes\s+atlas-route/)
    expect(css).toMatch(/\.system-atlas__link\[data-flow='observed'\]/)
    expect(css).toMatch(/prefers-reduced-motion:\s*reduce/)
    expect(css).toMatch(
      /prefers-reduced-motion:\s*reduce[\s\S]*?\.system-atlas__link[\s\S]*?animation:\s*none/,
    )
  })

  it('includes a narrow-screen atlas layout', () => {
    expect(css).toMatch(/@media\s*\(max-width:\s*1180px\)/)
    expect(css).toMatch(/\.system-atlas__map/)
    expect(css).toMatch(/\.system-atlas__nodes/)
    expect(css).toMatch(
      /@media\s*\(max-width:\s*1180px\)[\s\S]*?\.system-atlas__empty\s*\{[\s\S]*?position:\s*relative/,
    )
  })
})
