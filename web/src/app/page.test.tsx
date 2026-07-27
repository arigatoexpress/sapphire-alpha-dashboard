import { describe, expect, it } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import Home from './page'

const markup = renderToStaticMarkup(<Home />)

describe('professional homepage', () => {
  it('states a clear value proposition', () => {
    expect(markup).toContain('Research-driven trading infrastructure')
    expect(markup).toContain('Latest research')
    expect(markup).toContain('Live desk')
  })

  it('explains the research method without jargon overload', () => {
    expect(markup).toContain('Speculate with discipline')
    expect(markup).toMatch(/[Oo]ne probability/)
    expect(markup).toContain('Falsify')
    expect(markup).toContain('Market research')
    expect(markup).toContain('Execution rails')
    expect(markup).toContain('Research methodology')
  })

  it('states what is and is not published', () => {
    expect(markup).toContain('We publish')
    expect(markup).toContain('We do not publish')
    expect(markup).toContain('Not investment advice')
  })
})
