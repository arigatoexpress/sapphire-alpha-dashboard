import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import SystemAtlas from './SystemAtlas'
import { SYSTEM_ATLAS_STAGES } from '@/data/system-atlas'

const markup = renderToStaticMarkup(<SystemAtlas />)

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

  it('renders an accessible, no-JavaScript system path from a static contract', () => {
    expect(markup).toContain('aria-labelledby="system-atlas-title"')
    expect(markup).toContain('aria-label="System path in plain language"')
    expect(markup).toContain('<ol')
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
    expect(markup).toContain('runtime evidence: none')
    expect(markup).toContain('authority: none')
    expect(markup).not.toMatch(/\b\d+(?:\.\d+)?%\s+(?:win|return|alpha|accuracy)\b/i)
    expect(markup).not.toMatch(/\$\d+\s+(?:profit|pnl|made)\b/i)
  })
})

describe('system atlas motion and responsive contracts', () => {
  const css = readFileSync(resolve(__dirname, '../app/globals.css'), 'utf8')

  it('uses one bounded path animation and disables it for reduced motion', () => {
    expect(css).toMatch(/@keyframes\s+atlas-route/)
    expect(css).toMatch(/\.system-atlas__route/)
    expect(css).toMatch(/prefers-reduced-motion:\s*reduce/)
    expect(css).toMatch(
      /prefers-reduced-motion:\s*reduce[\s\S]*?\.system-atlas__route[\s\S]*?animation:\s*none/,
    )
  })

  it('includes a narrow-screen atlas layout', () => {
    expect(css).toMatch(/@media\s*\(max-width:\s*760px\)/)
    expect(css).toMatch(/\.system-atlas__map/)
    expect(css).toMatch(/\.system-atlas__path/)
  })
})
