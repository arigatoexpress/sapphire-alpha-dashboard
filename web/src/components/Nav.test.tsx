import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import Nav from './Nav'
import { ROUTES } from './Nav'

describe('responsive navigation', () => {
  it('keeps the compact desk action through tablet widths', () => {
    const html = renderToStaticMarkup(<Nav />)

    expect(html).toContain('hidden items-center gap-6 lg:flex')
    expect(html).toContain('uppercase lg:hidden')
    expect(html).not.toContain('gap-7 md:flex')
  })

  it('makes the proof ledger a first-class route', () => {
    expect(ROUTES).toContainEqual({ href: '/proof/', label: 'Proof' })
  })
})
