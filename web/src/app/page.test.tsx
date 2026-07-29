import { describe, expect, it } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import Home from './page'

const markup = renderToStaticMarkup(<Home />)

describe('public signal-cartography home', () => {
  it('states one clear thesis and two honest entry points', () => {
    expect(markup).toContain('A system that shows its work.')
    expect(markup).toContain('Read research')
    expect(markup).toContain('System map')
  })

  it('shows the evidence horizon without inventing state', () => {
    expect(markup).toContain('Evidence horizon')
    expect(markup).toContain('Source:')
    expect(markup).toContain('authority: none')
    expect(markup).toContain('unknown stays unknown')
    expect(markup).toContain('not observed')
    expect(markup).toContain('data-evidence-state')
  })

  it('explains a falsifiable research method', () => {
    for (const stage of ['Observe', 'Form', 'Falsify', 'Gate', 'Score']) {
      expect(markup).toContain(stage)
    }
    expect(markup).toContain('Research ledger')
    expect(markup).toContain('Operating principles')
  })

  it('states the authority and disclosure boundary', () => {
    expect(markup).toContain('cannot trade')
    expect(markup).toContain('Not investment advice')
    expect(markup).toContain('paper backtest leaderboards')
    expect(markup).not.toContain('Autonomous capital')
    expect(markup).not.toContain('Plant status')
  })
})
