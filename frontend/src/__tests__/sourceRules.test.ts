/**
 * Cheap greps over the desk's own source, guarding two regressions that a
 * rendering test would not catch because the code in question silently does
 * nothing.
 *
 * 1. **Dead band keys.** `types.ts` and the old topology view read `node.load_band`,
 *    `node.activity_band` and `link.latency_band` for months after the backend
 *    stopped serving any of them. TypeScript was no help: a hand-maintained
 *    local copy of the payload type declared the fields, so every read was
 *    well-typed and evaluated to `undefined` at runtime. Nothing failed. The
 *    page just quietly showed nothing. A grep is the right shape of test for
 *    that, because the defect is a name that must not appear.
 *
 * 2. **The login.** Removing a login is not done when the form stops rendering;
 *    it is done when the credential handling, the auth header and the
 *    second-tier vocabulary are all gone from the source. Asserting on rendered
 *    markup would pass while `btoa(user + ':' + pass)` still sat in a branch
 *    nobody currently reaches.
 *
 * The scan reads code with comments removed, so the notes explaining *why* a
 * name is banned may go on naming it. `stripComments` is tested here too — if
 * it ever over-strips, these rules would quietly stop protecting anything.
 */

import { describe, expect, it } from 'vitest'
import { stripComments } from './stripComments'

interface SourceFile {
  path: string
  text: string
}

function sourceFiles(): SourceFile[] {
  /* Vite's raw eager glob keeps this browser package free of Node runtime
     types while still scanning every source file. The tests themselves name
     the forbidden strings, so exclude their directory explicitly. */
  const modules = import.meta.glob('../**/*.{ts,tsx}', {
    query: '?raw',
    import: 'default',
    eager: true,
  }) as Record<string, string>

  return Object.entries(modules)
    /* Vite normalizes files reached through `..` from this directory to
       `./name.test.ts`, so exclude tests by suffix as well as by directory. */
    .filter(
      ([path]) =>
        !path.includes('/__tests__/') &&
        !/\.test\.[^.]+$/.test(path) &&
        !path.endsWith('/stripComments.ts'),
    )
    .map(([path, source]) => ({
      path: path.replace(/^\.\.\//, ''),
      text: stripComments(source),
    }))
    .sort((a, b) => a.path.localeCompare(b.path))
}

const FILES = sourceFiles()

/** Reported so a future reorganisation that empties the scan fails loudly. */
describe('the source scan itself', () => {
  it('finds the desk source', () => {
    expect(FILES.length).toBeGreaterThanOrEqual(8)
    expect(FILES.map((file) => file.path)).toContain('App.tsx')
    expect(FILES.map((file) => file.path)).toContain('hooks/useLiveTelemetry.ts')
    expect(FILES.map((file) => file.path)).toContain('types.ts')
  })

  it('still holds the code after the prose is removed', () => {
    /* A stripper that ate everything would make every rule below vacuous. */
    for (const file of FILES.filter((candidate) => !candidate.path.endsWith('.d.ts'))) {
      expect(file.text).toMatch(/\b(export|import)\b/)
    }
    expect(FILES.find((file) => file.path === 'global.d.ts')?.text.trim()).toBe(
      "declare module '*.css' {}",
    )
  })
})

describe('stripComments', () => {
  it('removes line and block comments', () => {
    expect(stripComments('const a = 1 // load_band\n')).toBe('const a = 1 \n')
    expect(stripComments('/* load_band */const a = 1')).toBe('const a = 1')
    expect(stripComments('a\n/**\n * load_band\n */\nb')).toBe('a\n\nb')
  })

  it('keeps string literals, including ones that look like comments', () => {
    expect(stripComments(`const a = '// not a comment'`)).toBe(`const a = '// not a comment'`)
    expect(stripComments('const a = "/* still not */"')).toBe('const a = "/* still not */"')
    expect(stripComments('const a = `//x`')).toBe('const a = `//x`')
  })

  it('does not lose code that follows a comment', () => {
    expect(stripComments('/* x */ const load = 1')).toBe(' const load = 1')
    expect(stripComments('const a = 1 // x\nconst b = 2')).toBe('const a = 1 \nconst b = 2')
  })

  it('handles an escaped quote inside a string', () => {
    expect(stripComments(`const a = 'it\\'s' // gone`)).toBe(`const a = 'it\\'s' `)
  })
})

describe('no redaction-era band key survives', () => {
  /**
   * `usdm_band` is the one legitimate `_band` name left anywhere: capital stays
   * banded on purpose (design decision D1), so it is a real served field rather
   * than a leftover. Every other `_band` identifier is a key the backend no
   * longer sends.
   */
  const ALLOWED = new Set(['usdm_band'])

  it.each(['load_band', 'activity_band', 'latency_band', 'freshness_band'])(
    'never reads %s',
    (key) => {
      const offenders = FILES.filter((file) => file.text.includes(key)).map((file) => file.path)
      expect(offenders).toEqual([])
    },
  )

  it('reads no *_band identifier at all beyond the documented exception', () => {
    const offenders: string[] = []
    for (const file of FILES) {
      for (const match of file.text.matchAll(/\b[A-Za-z_][A-Za-z0-9_]*_band\b/g)) {
        if (!ALLOWED.has(match[0])) offenders.push(`${file.path}: ${match[0]}`)
      }
    }
    expect(offenders).toEqual([])
  })

  it('does not branch on the deleted two-tier flags', () => {
    const offenders: string[] = []
    for (const file of FILES) {
      for (const flag of ['public_view', 'public_policy']) {
        if (file.text.includes(flag)) offenders.push(`${file.path}: ${flag}`)
      }
    }
    expect(offenders).toEqual([])
  })
})

describe('the login is gone', () => {
  it.each([
    ['a Login component', /\bLogin\b/],
    ['a credentials state', /\bcreds\b|\bsetCreds\b|\bshowLogin\b|\bauthRequired\b/],
    ['an Authorization header', /Authorization/],
    ['basic-auth encoding', /\bbtoa\s*\(/],
    ['a password field', /type=["']password["']|current-password/],
    ['sign-in copy', /Sign in|Operator access|operator detail|aggregated \+ delayed/],
  ])('has no %s', (_what, pattern) => {
    const offenders = FILES.filter((file) => pattern.test(file.text)).map((file) => file.path)
    expect(offenders).toEqual([])
  })

  it('ships no Login file', () => {
    expect(FILES.map((file) => file.path).filter((path) => /Login/i.test(path))).toEqual([])
  })
})
