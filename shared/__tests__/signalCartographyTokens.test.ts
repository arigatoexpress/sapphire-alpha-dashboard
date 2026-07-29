/**
 * Task 099 red goldens: signal-cartography token and type-role parity.
 * These must fail on the Task-093 dark terminal palette and pass only after
 * the blue-hour observatory system lands in shared/theme.css.
 */
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const themePath = resolve(__dirname, '../theme.css')
const theme = readFileSync(themePath, 'utf8')

/** Semantic color roles required by SAPPHIRE-ORCHESTRATOR-20260729-099. */
const REQUIRED_COLORS: Record<string, string> = {
  'observatory-ink': '#102A36',
  'atlas-blue': '#174A67',
  glacier: '#F3F8F7',
  skywash: '#D8EBEE',
  'signal-coral': '#E86F51',
  'caution-gold': '#E3AF35',
}

const TYPE_ROLES = {
  display: 'Newsreader',
  body: 'Space Grotesk',
  mono: 'JetBrains Mono',
} as const

describe('signal-cartography token parity', () => {
  it.each(Object.entries(REQUIRED_COLORS))(
    'defines --color-%s as %s',
    (name, hex) => {
      const pattern = new RegExp(
        `--color-${name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\s*:\\s*${hex}`,
        'i',
      )
      expect(theme).toMatch(pattern)
    },
  )

  it('maps canvas/text/structure/action/stale roles to the blue-hour system', () => {
    // Glacier must be the body canvas; observatory-ink the primary text.
    expect(theme).toMatch(/body\s*\{[^}]*background:\s*var\(--color-glacier\)/s)
    expect(theme).toMatch(/body\s*\{[^}]*color:\s*var\(--color-observatory-ink\)/s)
  })

  it('assigns Newsreader / Space Grotesk / JetBrains Mono to display, body, mono roles', () => {
    expect(theme).toMatch(
      new RegExp(`--font-display:[^;]*${TYPE_ROLES.display}`, 'i'),
    )
    expect(theme).toMatch(
      new RegExp(`--font-body:[^;]*${TYPE_ROLES.body}`, 'i'),
    )
    expect(theme).toMatch(
      new RegExp(`--font-mono:[^;]*${TYPE_ROLES.mono}`, 'i'),
    )
  })

  it('does not keep the retired dark-terminal void canvas as body background', () => {
    expect(theme).not.toMatch(/body\s*\{[^}]*background:\s*var\(--color-void\)/s)
    // Hard-coded void hex must not remain the document canvas.
    expect(theme).not.toMatch(/body\s*\{[^}]*background:\s*#071018/s)
  })
})

describe('public and operator import the same shared theme', () => {
  it('web globals and frontend index both import shared/theme.css', () => {
    const webGlobals = readFileSync(
      resolve(__dirname, '../../web/src/app/globals.css'),
      'utf8',
    )
    const feIndex = readFileSync(
      resolve(__dirname, '../../frontend/src/index.css'),
      'utf8',
    )
    expect(webGlobals).toMatch(/@import\s+['"][^'"]*shared\/theme\.css['"]/)
    expect(feIndex).toMatch(/@import\s+['"][^'"]*shared\/theme\.css['"]/)
  })
})
