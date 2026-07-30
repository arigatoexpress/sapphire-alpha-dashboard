import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import Nav, { SECTIONS } from './Nav'

describe('site navigation', () => {
  it('exposes every anchored section that page.tsx renders', () => {
    // Anchors are the load-bearing claim of a single-page layout — if a section
    // renders but the nav does not point at it, the reader has no way to find it.
    const labels = SECTIONS.map((s) => s.label)
    for (const expected of ['System', 'Intelligence', 'Research', 'Proof', 'About']) {
      expect(labels).toContain(expected)
    }
    for (const section of SECTIONS) {
      expect(section.href).toMatch(/^\/#[a-z]+$/)
    }
  })

  it('renders every section link and the observatory CTA', () => {
    const html = renderToStaticMarkup(<Nav />)
    for (const section of SECTIONS) {
      expect(html).toContain(`href="${section.href}"`)
      expect(html).toContain(section.label)
    }
    // Both mobile + desktop point at the operator SPA; test the shared href stem
    // rather than a specific class name so the layout is free to change.
    expect(html).toMatch(/href="\/dashboard\/?"/)
  })
})
