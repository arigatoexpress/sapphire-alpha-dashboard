/**
 * Product goldens for the sovereign market-laboratory surface.
 */
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import Home from './page'
import Nav, { ROUTES } from '@/components/Nav'
import Footer from '@/components/Footer'

const markup = renderToStaticMarkup(<Home />)
const navMarkup = renderToStaticMarkup(<Nav />)
const footerMarkup = renderToStaticMarkup(<Footer />)

const REQUIRED_ROUTES = [
  { href: '/research', label: 'Research' },
  { href: '/proof', label: 'Method' },
  { href: '/dashboard', label: 'Live desk' },
] as const

const LEGACY_ROUTES = [
  '/trading',
  '/security',
  '/proof',
  '/onchain',
  '/about',
] as const

describe('public evidence-studio composition', () => {
  it('states the product thesis and two real paths without empty marketing CTAs', () => {
    expect(markup).toContain('Find the signal.')
    expect(markup).toContain('Prove the path.')
    expect(markup).toContain('Enter mission control')
    expect(markup).toContain('Read the operating thesis')
    expect(markup).not.toMatch(/Get started|Book a demo|Join waitlist|Learn more today/i)
    expect(markup).not.toMatch(/\$[0-9]+[KkMmBb]?\+?\s*(AUM|TVL|volume)/i)
  })

  it('renders the truth rail as the signature with honest evidence states', () => {
    expect(markup).toMatch(/Truth rail/i)
    for (const state of ['paused', 'source-only']) {
      expect(markup.toLowerCase()).toContain(state)
    }
    expect(markup).toMatch(/data-evidence-state=/)
    expect(markup).toContain('/api/v1/live')
  })

  it('never claims live or autonomous operation in static shell while unobserved', () => {
    // Static SSR shell has no admitted live observation — forbid present-tense
    // live/autonomous marketing claims that lack persisted evidence.
    expect(markup).not.toMatch(/\blive trading\b/i)
    expect(markup).not.toMatch(/\bautonomous (trading|execution|capital)\b/i)
    expect(markup).not.toMatch(/\b24\/7 uptime\b/i)
    expect(markup).not.toMatch(/\balways on\b/i)
    expect(markup).toMatch(/not observed|unavailable|unknown|source-only|paused|stale/i)
  })

  it('exposes a receipt-bound dossier and explicit method', () => {
    expect(markup).toMatch(/Featured evidence dossier/i)
    expect(markup).toMatch(/One loop\. Four hard contracts/i)
    expect(markup).toContain('Verify projection integrity')
  })
})

describe('public navigation and route inventory', () => {
  it('surfaces Research, Method, and Live desk as primary paths', () => {
    for (const route of REQUIRED_ROUTES) {
      expect(navMarkup).toContain(route.href)
      expect(navMarkup).toContain(route.label)
    }
  })

  it('retires the old Research OS brand from primary chrome', () => {
    expect(navMarkup).toContain('Sapphire')
    expect(footerMarkup).toContain('sovereign market laboratory')
    expect(navMarkup + footerMarkup).not.toContain('Research OS')
  })

  it('keeps every real public route addressable from nav or footer', () => {
    const combined = navMarkup + footerMarkup
    for (const href of LEGACY_ROUTES) {
      expect(combined).toContain(href)
    }
    // Primary research path present in ROUTES export or composed nav.
    expect(
      ROUTES.some((r) => r.href === '/research/') || combined.includes('/research/'),
    ).toBe(true)
  })

  it('uses semantic landmarks and a skip link target', () => {
    const layout = readFileSync(resolve(__dirname, 'layout.tsx'), 'utf8')
    expect(layout).toMatch(/Skip to content/)
    expect(layout).toMatch(/id="main"/)
    expect(navMarkup).toMatch(/aria-label="Primary"/)
    expect(footerMarkup).toMatch(/<footer/)
  })
})

describe('token parity and motion contracts (source)', () => {
  const theme = readFileSync(
    resolve(__dirname, '../../../shared/theme.css'),
    'utf8',
  )

  it.each([
    ['observatory-ink', '#102A36'],
    ['atlas-blue', '#174A67'],
    ['glacier', '#F3F8F7'],
    ['skywash', '#D8EBEE'],
    ['signal-coral', '#B54632'],
    ['caution-gold', '#8A6100'],
  ] as const)('defines --color-%s as %s', (name, hex) => {
    expect(theme).toMatch(
      new RegExp(`--color-${name}\\s*:\\s*${hex}`, 'i'),
    )
  })

  it('uses glacier canvas and Newsreader/Space Grotesk/JetBrains Mono roles', () => {
    expect(theme).toMatch(/body\s*\{[^}]*background:\s*var\(--color-glacier\)/s)
    expect(theme).toMatch(/body\s*\{[^}]*color:\s*var\(--color-observatory-ink\)/s)
    expect(theme).toMatch(/--font-display:[^;]*Newsreader/i)
    expect(theme).toMatch(/--font-body:[^;]*Space Grotesk/i)
    expect(theme).toMatch(/--font-mono:[^;]*JetBrains Mono/i)
  })

  it('documents reduced-motion safety for the evidence-horizon entrance', () => {
    const globals = readFileSync(resolve(__dirname, 'globals.css'), 'utf8')
    const css = globals + theme
    expect(css).toMatch(/prefers-reduced-motion:\s*reduce/)
    expect(css).toMatch(/evidence-horizon|horizon-enter/)
  })

  it('does not introduce remote font, analytics, or charting dependencies', () => {
    const pkg = JSON.parse(
      readFileSync(resolve(__dirname, '../../package.json'), 'utf8'),
    ) as { dependencies: Record<string, string>; devDependencies?: Record<string, string> }
    const all = { ...pkg.dependencies, ...pkg.devDependencies }
    for (const forbidden of [
      'recharts',
      'chart.js',
      'd3',
      'framer-motion',
      '@mui/material',
      'styled-components',
      'gtag',
      'analytics',
      '@vercel/analytics',
    ]) {
      expect(all[forbidden]).toBeUndefined()
    }
    const layout = readFileSync(resolve(__dirname, 'layout.tsx'), 'utf8')
    expect(layout).not.toMatch(/fonts\.googleapis|fonts\.gstatic|typekit\.net/)
  })
})

describe('coherent public route skin', () => {
  const webSkin = readFileSync(resolve(__dirname, 'sovereign.css'), 'utf8')

  it('re-skins every retained public route with the sovereign laboratory tokens', () => {
    expect(webSkin).toMatch(/body\s*\{[^}]*--color-glacier:\s*#080b10/s)
    expect(webSkin).toMatch(/body\s*\{[^}]*--color-observatory-ink:\s*#e9edf5/s)
    expect(webSkin).toMatch(/body\s*\{[^}]*--color-sapphire:\s*#72a7ff/s)
  })
})
