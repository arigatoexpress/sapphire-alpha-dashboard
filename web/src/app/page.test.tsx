import { describe, expect, it } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import Home from './page'

const markup = renderToStaticMarkup(<Home />)

describe('public evidence observatory', () => {
  it('states one clear proposition and two honest entry points', () => {
    expect(markup).toContain('Evidence')
    expect(markup).toContain('before action.')
    expect(markup).toContain('Read the evidence')
    expect(markup).toContain('Open the observatory')
  })

  it('shows the live evidence contract without inventing state', () => {
    expect(markup).toContain('Evidence horizon')
    expect(markup).toContain('Source:')
    expect(markup).toContain('authority: none')
    expect(markup).toContain('unknown stays unknown')
    expect(markup).toContain('not observed')
  })

  it('explains a falsifiable research method', () => {
    for (const stage of ['Observe', 'Form', 'Falsify', 'Gate', 'Score']) {
      expect(markup).toContain(stage)
    }
    expect(markup).toContain('one probability at one timestamp')
    expect(markup).toContain('Bear, base, and bull belong to the path')
    expect(markup).toContain('publish the error')
  })

  it('states the authority and disclosure boundary', () => {
    expect(markup).toContain('Authority held.')
    expect(markup).toContain('No execution is available from this page.')
    expect(markup).toContain('cannot place a trade')
    expect(markup).toContain('Not investment advice')
    expect(markup).toContain('paper backtest leaderboards')
    expect(markup).not.toContain('Autonomous capital')
    expect(markup).not.toContain('Plant status')
  })
})
