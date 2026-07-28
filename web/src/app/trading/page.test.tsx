import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import Trading from './page'

const markup = renderToStaticMarkup(<Trading />)

describe('trading architecture page', () => {
  it('labels the execution flow as an inert design, never current runtime truth', () => {
    expect(markup).toContain('Design contract')
    expect(markup).toContain('Runtime unavailable')
    expect(markup).toContain('Task 065')
    expect(markup).not.toContain('killswitch        absent')
    expect(markup).not.toContain('status="live"')
    expect(markup).not.toContain('It is an autonomous execution system running')
  })

  it('keeps the public surface descriptive and non-controlling on mobile', () => {
    expect(markup).not.toMatch(/<button|<input|<form/)
    expect(markup).toContain('No control on this page can clear a pause')
  })
})
