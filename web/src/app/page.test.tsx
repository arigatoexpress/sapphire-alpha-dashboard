import { describe, expect, it } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import Home from './page'

const markup = renderToStaticMarkup(<Home />)

describe('sovereign command desk home', () => {
  it('opens as an instrument surface for the trading plant', () => {
    expect(markup).toContain('Sovereign trading plant')
    expect(markup).toContain('Autonomous capital.')
    expect(markup).toContain('Instrument-grade control')
    expect(markup).toContain('Open live desk')
  })

  it('exposes analysis lenses into research, strategy, plant, and desk', () => {
    expect(markup).toContain('Analyze the whole system')
    expect(markup).toContain('Portfolio multi-lens')
    expect(markup).toContain('Free-reign agentic')
    expect(markup).toContain('Living plant map')
    expect(markup).toContain('Operator desk')
  })

  it('does not fall back to the previous generic trust slogan', () => {
    expect(markup).not.toContain("don't trust")
    expect(markup).not.toContain('don’t trust')
  })
})
