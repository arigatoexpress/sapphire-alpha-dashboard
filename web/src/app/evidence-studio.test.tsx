import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import Home from './page'
import { FEATURED_OBSERVATION } from '@/data/metrics'

const markup = renderToStaticMarkup(<Home />)

describe('sovereign market laboratory replacement', () => {
  it('opens with the product thesis, not dashboard chrome or the retired homepage', () => {
    expect(markup).toContain('A sovereign market laboratory')
    expect(markup).toContain('Find the signal.')
    expect(markup).toContain('Prove the path.')
    expect(markup).toContain('Enter mission control')
    expect(markup).not.toContain('Markets are noisy. The evidence shouldn’t be.')
    expect(markup).not.toContain('System Atlas')
  })

  it('uses the intelligence field as the subject-specific signature', () => {
    expect(markup).toContain('data-signature="intelligence-field"')
    for (const label of ['Markets', 'Onchain', 'Memory', 'Policy']) {
      expect(markup).toContain(label)
    }
    expect(markup).toContain('Observe')
    expect(markup).toContain('Reason')
    expect(markup).toContain('Decide')
    expect(markup).toContain('Act')
  })

  it('states every active program without inventing coverage or readiness', () => {
    expect(markup).toContain('Robinhood Chain')
    expect(markup).toContain('Receipt-backed pilot')
    expect(markup).toContain('MegaETH')
    expect(markup).toContain('Discovery — no admitted feed')
    expect(markup).toContain('Solana')
    expect(markup).toContain('Connector planned')
    expect(markup).not.toMatch(/live MegaETH|live Solana|real-time volume/i)
  })

  it('retains one receipt-bound public specimen and its hard limits', () => {
    expect(markup).toContain('AAPL / USDG')
    expect(markup).toContain(FEATURED_OBSERVATION.receiptSha256.slice(0, 12))
    expect(markup).toContain(FEATURED_OBSERVATION.range.startBlock)
    expect(markup).toContain(FEATURED_OBSERVATION.range.endBlock)
    expect(markup).toContain('Observation, not signal')
    expect(markup).toContain('No volume, ranking, finality, or trading authority')
    expect(markup).toContain(FEATURED_OBSERVATION.verify)
    expect(markup).not.toMatch(/buy|sell|alpha score|expected return/i)
  })

  it('keeps runtime truth fail-closed and gives visitors its evidence contract', () => {
    expect(markup).toContain('Truth rail')
    expect(markup).toContain('/api/v1/live')
    expect(markup).toContain('No current runtime claim')
    expect(markup).toContain('Source')
    expect(markup).toContain('Freshness')
    expect(markup).toContain('Falsifier')
    expect(markup).toContain('Authority')
  })

  it('ships a responsive, accessible visual contract with restrained motion', () => {
    const css = readFileSync(resolve(__dirname, 'sovereign.css'), 'utf8')
    expect(css).toContain('.sovereign-home')
    expect(css).toContain('.intelligence-field')
    expect(css).toMatch(/@media\s*\(max-width:\s*760px\)/)
    expect(css).toMatch(/prefers-reduced-motion:\s*reduce/)
    expect(markup).toContain('aria-labelledby="sovereign-title"')
    expect(markup).toContain('aria-label="Sapphire intelligence field"')
  })

  it('keeps the inspected bespoke social card wired to public metadata', () => {
    const layoutSource = readFileSync(resolve(__dirname, 'layout.tsx'), 'utf8')
    expect(layoutSource).toContain("url: '/og.png'")
    expect(layoutSource).toContain("images: ['/og.png']")
    const image = readFileSync(resolve(__dirname, '../../public/og.png'))
    expect(image.subarray(0, 8).toString('hex')).toBe('89504e470d0a1a0a')
  })
})
