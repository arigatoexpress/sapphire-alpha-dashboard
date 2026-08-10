import { describe, expect, it } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import Home from './page'

const markup = renderToStaticMarkup(<Home />)

describe('public evidence-studio home', () => {
  it('states one clear thesis and two honest entry points', () => {
    expect(markup).toContain('Find the signal.')
    expect(markup).toContain('Enter mission control')
    expect(markup).toContain('Read the operating thesis')
  })

  it('shows the truth rail without inventing runtime state', () => {
    expect(markup).toContain('Truth rail')
    expect(markup).toContain('source /api/v1/live')
    expect(markup).toContain('Authority')
    expect(markup).toContain('No current runtime claim')
    expect(markup).toContain('not observed')
    expect(markup).toContain('data-evidence-state')
  })

  it('explains a falsifiable research method', () => {
    for (const stage of ['Observe', 'Cross-check', 'Explain', 'Gate']) {
      expect(markup).toContain(stage)
    }
    expect(markup).toContain('Featured evidence dossier')
    expect(markup).toContain('Verify projection integrity')
  })

  it('states the authority and disclosure boundary', () => {
    expect(markup).toContain('cannot trade')
    expect(markup).toContain('Not investment advice')
    expect(markup).toContain('No volume, ranking, finality, or trading authority')
    expect(markup).not.toContain('Autonomous capital')
    expect(markup).not.toMatch(/expected return|guaranteed return/i)
  })
})
