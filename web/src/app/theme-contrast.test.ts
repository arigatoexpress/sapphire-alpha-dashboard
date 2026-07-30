import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const css = readFileSync(resolve(__dirname, '../../../shared/theme.css'), 'utf8')

function token(name: string) {
  const value = css.match(new RegExp(`--color-${name}:\\s*(#[0-9a-f]{6})`, 'i'))?.[1]
  if (!value) throw new Error(`missing hexadecimal theme token --color-${name}`)
  return value
}

function luminance(hex: string) {
  const channels = hex
    .slice(1)
    .match(/.{2}/g)!
    .map((channel) => Number.parseInt(channel, 16) / 255)
    .map((channel) =>
      channel <= 0.04045
        ? channel / 12.92
        : ((channel + 0.055) / 1.055) ** 2.4,
    )
  return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]
}

function contrast(foreground: string, background: string) {
  const [lighter, darker] = [luminance(foreground), luminance(background)].sort(
    (a, b) => b - a,
  )
  return (lighter + 0.05) / (darker + 0.05)
}

describe('shared public and operator theme contrast', () => {
  const textTokens = [
    'observatory-ink',
    'atlas-blue',
    'ink-dim',
    'ink-faint',
    'signal-coral',
    'caution-gold',
    'verified',
    'failed',
  ]
  const surfaces = ['glacier', 'raised']

  it.each(
    textTokens.flatMap((foreground) =>
      surfaces.map((background) => [foreground, background] as const),
    ),
  )('%s is readable as normal text on %s', (foreground, background) => {
    const ratio = contrast(token(foreground), token(background))
    expect(
      ratio,
      `--color-${foreground} ${token(foreground)} on --color-${background} ${token(background)}`,
    ).toBeGreaterThanOrEqual(4.5)
  })
})
