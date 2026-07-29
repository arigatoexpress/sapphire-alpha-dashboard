import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import Nav from './Nav'
import { ROUTES, PRIMARY_ROUTES } from './Nav'

describe('responsive navigation', () => {
  it('keeps the compact live-truth action through tablet widths', () => {
    const html = renderToStaticMarkup(<Nav />)

    expect(html).toContain('hidden items-center gap-6 lg:flex')
    expect(html).toContain('uppercase lg:hidden')
    expect(html).toContain('Live truth')
    expect(html).not.toContain('gap-7 md:flex')
  })

  it('never wraps a primary-nav label mid-word at tablet widths', () => {
    const html = renderToStaticMarkup(<Nav />)
    // Every primary label + the Live truth pill get whitespace-nowrap so
    // hyphenated names like "On-Chain" cannot break across two lines.
    const nowrapCount = (html.match(/whitespace-nowrap/g) ?? []).length
    expect(nowrapCount).toBeGreaterThanOrEqual(PRIMARY_ROUTES.length + 1)
  })

  it('makes the proof ledger a first-class route', () => {
    expect(ROUTES).toContainEqual({ href: '/proof/', label: 'Proof' })
  })

  it('surfaces Research, Systems, Strategy, On-Chain, and Security as primary paths', () => {
    const html = renderToStaticMarkup(<Nav />)
    for (const route of PRIMARY_ROUTES) {
      // Next.js Link may or may not preserve the trailing slash at SSR time.
      const stem = route.href.replace(/\/$/, '')
      expect(html).toMatch(new RegExp(`href="${stem}\\/?"`))
      expect(html).toContain(route.label)
    }
  })
})
