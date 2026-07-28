import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import Trading from './page'

const markup = renderToStaticMarkup(<Trading />)

describe('trading architecture page', () => {
  it('labels the execution flow as an inert design, never current runtime truth', () => {
    expect(markup).toContain('Design contract')
    expect(markup).toContain('Runtime unavailable')
    expect(markup).toContain('Task 065')
    expect(markup).toContain('sell-to-close for one proven existing option')
    expect(markup).toContain('never an option purchase, roll, or exercise')
    expect(markup).not.toContain('killswitch        absent')
    expect(markup).not.toContain('status="live"')
    expect(markup).not.toContain('It is an autonomous execution system running')
    expect(markup).not.toContain('single-leg options on the designated agentic')
  })

  it('keeps the public surface descriptive and non-controlling on mobile', () => {
    expect(markup).not.toMatch(/<button|<input|<form/)
    expect(markup).toContain('No control on this page can clear a pause')
  })
})
