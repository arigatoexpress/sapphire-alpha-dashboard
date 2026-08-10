import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import Nav from './Nav'
import { ROUTES } from './Nav'

describe('responsive navigation', () => {
  it('keeps the compact live-desk action through tablet widths', () => {
    const html = renderToStaticMarkup(<Nav />)

    expect(html).toContain('site-nav__links')
    expect(html).toContain('site-nav__desk')
    expect(html).toContain('Mission control')
    expect(html).toContain('aria-label="Live desk"')
    expect(html).not.toContain('gap-7 md:flex')
  })

  it('makes the proof ledger a first-class route', () => {
    expect(ROUTES).toContainEqual({ href: '/proof/', label: 'Proof' })
  })

  it('surfaces Research and Method as primary paths', () => {
    const html = renderToStaticMarkup(<Nav />)
    expect(html).toMatch(/href="\/research\/?"/)
    expect(html).toContain('Research')
    expect(html).toMatch(/href="\/proof\/?"/)
    expect(html).toContain('Method')
  })
})
