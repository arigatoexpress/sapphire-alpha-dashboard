import { describe, expect, it } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import ArchitectureMesh from './ArchitectureMesh'
import { MESH, STRATEGIES } from '@/data/mesh'

describe('ArchitectureMesh', () => {
  it('renders every mesh node with its hostname and role', () => {
    const markup = renderToStaticMarkup(<ArchitectureMesh variant="full" />)
    for (const node of MESH) {
      expect(markup).toContain(node.hostname)
      expect(markup).toContain(node.role.toUpperCase())
    }
  })

  it('renders every strategy by its real class name', () => {
    // The strategy set is the load-bearing claim: any drift between the
    // diagram and lib/analytics/strategies.py is a lie on the marketing site.
    const markup = renderToStaticMarkup(<ArchitectureMesh variant="full" />)
    for (const s of STRATEGIES) {
      expect(markup).toContain(s.name)
    }
    // No agent may claim live mode without approval — the diagram must say so.
    expect(markup).toContain('PAPER')
  })

  it('shows the four-stage pipeline in order, ending at the human gate', () => {
    const markup = renderToStaticMarkup(<ArchitectureMesh variant="full" />)
    const indices = ['Observe', 'Form', 'Falsify', 'Gate']
    let lastIndex = -1
    for (const stage of indices) {
      const at = markup.indexOf(stage)
      expect(at, `${stage} missing`).toBeGreaterThan(lastIndex)
      lastIndex = at
    }
    expect(markup).toContain('Telegram')
  })

  it('cites the source files for every load-bearing claim', () => {
    const markup = renderToStaticMarkup(<ArchitectureMesh variant="full" />)
    expect(markup).toContain('tailscale-acl.json')
    expect(markup).toContain('strategies.py')
    expect(markup).toContain('confirmation_firewall.py')
  })

  it('surfaces the chain settlement rail without leaking keys', () => {
    const markup = renderToStaticMarkup(<ArchitectureMesh variant="full" />)
    expect(markup).toContain('Robinhood Chain')
    expect(markup).toContain('4663')
    // Public wallet appears truncated; the full string must NOT appear because
    // even though it's public, this is where we practise the never-paste-keys
    // habit — a truncated address is enough to identify, and a full one is
    // the pattern we do not want anywhere near the render surface.
    expect(markup).toContain('0xc2B5')
    expect(markup).toContain('c9EB')
    // Sanity: no leading `0x` followed by 40 hex chars anywhere in the markup.
    expect(markup).not.toMatch(/0x[a-fA-F0-9]{40}/)
  })

  it('drops the legend in compact variant', () => {
    const compact = renderToStaticMarkup(<ArchitectureMesh variant="compact" />)
    expect(compact).not.toContain('Where the numbers come from')
    // But the diagram itself must still be intact.
    expect(compact).toContain('RegimeAwareRSI')
    expect(compact).toContain('macbook-pro-8')
  })
})
