import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import Home from './page'
import { FEATURED_OBSERVATION } from '@/data/metrics'

const markup = renderToStaticMarkup(<Home />)

describe('evidence-first studio replacement', () => {
  it('leads with a market-intelligence product instead of an architecture brochure', () => {
    expect(markup).toContain('Markets are noisy. The evidence shouldn’t be.')
    expect(markup).toContain('id="public-title"')
    expect(markup).toContain('Open the live desk')
    expect(markup).toContain('Inspect the method')
    expect(markup).not.toContain('What the system does')
    expect(markup).not.toContain('System Atlas')
  })

  it('renders the truth rail as the signature interaction contract', () => {
    expect(markup).toContain('Truth rail')
    for (const label of ['Observation', 'Claim', 'Falsifier', 'Confidence', 'Authority']) {
      expect(markup).toContain(label)
    }
    expect(markup).toContain('data-signature="truth-rail"')
    expect(markup).toContain('/api/v1/live')
  })

  it('ships one receipt-bound onchain specimen without overstating it', () => {
    expect(markup).toContain('AAPL / USDG')
    expect(markup).toContain(FEATURED_OBSERVATION.receiptSha256.slice(0, 12))
    expect(markup).toContain(FEATURED_OBSERVATION.range.startBlock)
    expect(markup).toContain(FEATURED_OBSERVATION.range.endBlock)
    expect(markup).toContain('Reconciled at depth 32')
    expect(markup).toContain('Not economically finalized')
    expect(markup).toContain('Observation, not signal')
    expect(markup).toContain('No volume, ranking, finality, or trading authority')
    expect(markup.match(/class="block-tick"/g)).toHaveLength(
      Number(FEATURED_OBSERVATION.range.endBlock) -
        Number(FEATURED_OBSERVATION.range.startBlock) +
        1,
    )
    expect(markup).not.toMatch(/class="block-track"[^>]*tabindex=/)
    const studioSource = readFileSync(
      resolve(__dirname, '../components/EvidenceStudio.tsx'),
      'utf8',
    )
    expect(studioSource).toContain('Number(observation.range.startBlock)')
    expect(studioSource).not.toContain("const BLOCKS = ['085'")
    expect(markup).not.toMatch(/buy|sell|alpha score|expected return/i)
  })

  it('keeps the public projection attached to integrity, source, and method evidence', () => {
    expect(FEATURED_OBSERVATION.verify).toMatch(/python3/)
    expect(markup).toContain(FEATURED_OBSERVATION.verify)
    expect(FEATURED_OBSERVATION.sourceUrl).toMatch(/^https:\/\//)
    expect(markup).toContain(FEATURED_OBSERVATION.sourceUrl)
    expect(FEATURED_OBSERVATION.methodUrl).toBe('/research/research-methodology')
    expect(markup).toContain(FEATURED_OBSERVATION.methodUrl)
    expect(markup).toContain('Verify projection integrity')
    expect(markup).not.toContain('Reproduce the public projection')
    const footerSource = readFileSync(
      resolve(__dirname, '../components/Footer.tsx'),
      'utf8',
    )
    expect(footerSource).toContain(
      'Inventory is reproducible. Evidence projections are hash-checked and scoped.',
    )
    expect(footerSource).not.toContain('Figures on this site are measured, not estimated.')
  })

  it('has a responsive reduced-motion visual contract without chart dependencies', () => {
    const css = readFileSync(resolve(__dirname, 'globals.css'), 'utf8')
    expect(css).toContain('.evidence-studio')
    expect(css).toContain('.truth-rail')
    expect(css).toMatch(/@media\s*\(max-width:\s*760px\)/)
    expect(css).toMatch(/prefers-reduced-motion:\s*reduce/)
    expect(css).toMatch(/\.block-track\s*\{[^}]*grid-template-columns:\s*repeat\(4,/s)
    expect(markup).not.toMatch(/class="truth-rail"[^>]*aria-live/)
    expect(markup).toContain('role="status"')

    const pkg = JSON.parse(
      readFileSync(resolve(__dirname, '../../package.json'), 'utf8'),
    ) as { dependencies: Record<string, string>; devDependencies?: Record<string, string> }
    const packages = { ...pkg.dependencies, ...pkg.devDependencies }
    for (const forbidden of ['recharts', 'chart.js', 'd3', 'framer-motion']) {
      expect(packages[forbidden]).toBeUndefined()
    }
  })

  it('ships the inspected bespoke social card through explicit metadata', () => {
    const layoutSource = readFileSync(resolve(__dirname, 'layout.tsx'), 'utf8')
    expect(layoutSource).toContain("url: '/og.png'")
    expect(layoutSource).toContain("images: ['/og.png']")

    const image = readFileSync(resolve(__dirname, '../../public/og.png'))
    expect(image.subarray(0, 8).toString('hex')).toBe('89504e470d0a1a0a')
    const legacyImage = readFileSync(
      resolve(__dirname, '../../public/opengraph-image'),
    )
    expect(legacyImage.equals(image)).toBe(true)
  })
})
