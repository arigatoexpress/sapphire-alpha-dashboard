import { describe, expect, it } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import Home from './page'

const markup = renderToStaticMarkup(<Home />)

describe('the public market aperture', () => {
  it('opens with Sapphire Alpha’s current decision posture', () => {
    expect(markup).toContain('data-market-aperture="true"')
    expect(markup).toContain('Preserve optionality.')
    expect(markup).toContain('The mandate sets conviction')
    expect(markup).toContain('Cycle model')
  })

  it('keeps research evidence separate from execution', () => {
    expect(markup).toContain('Evidence, not authority')
    expect(markup).toContain('Execution stays outside this lens')
  })

  it('does not fall back to the previous generic trust slogan', () => {
    expect(markup).not.toContain('Verify,')
    expect(markup).not.toContain('don’t trust')
  })
})
