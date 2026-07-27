import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { Panel } from '../components/ui'

describe('Panel', () => {
  it('can shrink inside a single-column mobile grid', () => {
    const markup = renderToStaticMarkup(<Panel>content</Panel>)

    expect(markup).toContain('min-w-0')
  })
})
