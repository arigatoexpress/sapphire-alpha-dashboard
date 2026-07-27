import { describe, expect, it } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import Home from './page'

const markup = renderToStaticMarkup(<Home />)

describe('professional homepage', () => {
  it('states a clear value proposition', () => {
    expect(markup).toContain('Markets, researched')
    expect(markup).toContain('See today’s opinions')
    expect(markup).toContain('Live desk')
  })

  it('explains the research method with visuals', () => {
    expect(markup).toContain('Speculate with discipline')
    expect(markup).toContain('Event probability')
    expect(markup).toContain('Path bands')
    expect(markup).toContain('Falsifier first')
    expect(markup).toContain('Robinhood Agentic')
    expect(markup).toContain('MegaETH')
    expect(markup).toContain('Research methodology')
  })

  it('states what is and is not published', () => {
    expect(markup).toContain('We publish')
    expect(markup).toContain('We do not publish')
    expect(markup).toMatch(/[Pp]aper backtest/)
    expect(markup).toContain('Not investment advice')
  })
})
