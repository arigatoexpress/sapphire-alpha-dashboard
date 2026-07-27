import { describe, expect, it } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import Home from './page'

const markup = renderToStaticMarkup(<Home />)

describe('mission control home', () => {
  it('renders as a mission-control console', () => {
    expect(markup).toContain('MISSION CONTROL')
    expect(markup).toContain('Full stack.')
    expect(markup).toContain('Full visibility.')
    expect(markup).toContain('Open live desk')
  })

  it('exposes analysis modules for desk, strategy, research, plant', () => {
    expect(markup).toContain('Operator desk')
    expect(markup).toContain('Free-reign rails')
    expect(markup).toContain('Multi-lens book')
    expect(markup).toContain('Four-node plant')
    expect(markup).toContain('Proof ledger')
  })
})
