import { describe, expect, it } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import Home from './page'

/**
 * Contract for the single-page dashboard. The specifics of copy can drift, but
 * these load-bearing claims must remain on the page — they are the reasons the
 * site is honest rather than a brochure.
 */
const markup = renderToStaticMarkup(<Home />)

describe('single-page dashboard', () => {
  it('leads with one clear proposition and two entry points', () => {
    expect(markup).toContain('A trading system')
    expect(markup).toContain('you can watch work.')
    expect(markup).toContain('See the system')
    expect(markup).toContain('Open the observatory')
  })

  it('cites its evidence source and refuses to invent unknowns', () => {
    // The evidence provenance line is the promise that keeps the rest of the
    // page honest — removing it also removes the reader's ability to check.
    expect(markup).toContain('Source:')
    expect(markup).toContain('/api/v1/live')
    expect(markup).toContain('unknown stays unknown')
  })

  it('renders all five anchored sections in order', () => {
    const order = ['id="system"', 'id="intelligence"', 'id="research"', 'id="proof"', 'id="about"']
    let last = -1
    for (const id of order) {
      const at = markup.indexOf(id)
      expect(at, `${id} missing or out of order`).toBeGreaterThan(last)
      last = at
    }
  })

  it('anchors intelligence in named strategies and the human gate', () => {
    // Strategy class names must appear verbatim — they are the load-bearing
    // claim about what code actually runs.
    for (const strategy of ['RegimeAwareRSI', 'SapphireComposite']) {
      expect(markup).toContain(strategy)
    }
    expect(markup).toContain('PAPER')
    expect(markup).toContain('Telegram')
  })

  it('surfaces the settlement rail and mandate boundaries', () => {
    // Robinhood Chain: id and family, no full-length wallet.
    expect(markup).toContain('Robinhood Chain')
    expect(markup).toContain('4663')
    expect(markup).not.toMatch(/0x[a-fA-F0-9]{40}/)

    // BRODIE mandate: the four safety boundaries that had to hold.
    expect(markup).toContain('BRODIE')
    expect(markup).toContain('Per-order cap')
    expect(markup).toContain('Daily loss ceiling')
    expect(markup).toContain('Leverage floor')
    expect(markup).toContain('Human approval')
  })

  it('publishes an observable test surface with a reproducible command', () => {
    // The test count and the shell one-liner must ship together — this is the
    // same discipline as every other figure on the site.
    expect(markup).toContain('Test surface')
    expect(markup).toContain('grep')
  })

  it('names the operator', () => {
    expect(markup).toContain('Ari Spector')
    expect(markup).toContain('Houston')
  })
})
