import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

import { getReport, getReports } from './research'

const AUDIT_SLUG = 'what-the-machine-room-refused-to-invent'
const auditSource = readFileSync(
  fileURLToPath(
    new URL('../../content/research/what-the-machine-room-refused-to-invent.md', import.meta.url),
  ),
  'utf-8',
)

describe('the published Machine Room measurement audit', () => {
  it('is explicitly published and discoverable through the real corpus reader', () => {
    const listing = getReports().find((report) => report.slug === AUDIT_SLUG)
    expect(listing).toMatchObject({
      title: 'What the Machine Room refused to invent',
      date: '2026-07-25',
    })
    expect(listing?.tags).toContain('telemetry')
    expect(auditSource).toMatch(/^---[\s\S]*\npublish: true\n---/m)
  })

  it('contains evidence, limits, and falsifiable follow-up rather than a launch claim', () => {
    const report = getReport(AUDIT_SLUG)
    expect(report?.html).toContain('Scope and method')
    expect(report?.html).toContain('What would prove the repair')
    expect(report?.html).toContain('does not claim latency, throughput, or uptime')
    expect(report?.minutes).toBeGreaterThanOrEqual(4)
  })

  it('contains no private identifiers or capital detail', () => {
    expect(auditSource).not.toMatch(/0x[a-f0-9]{8,}/i)
    expect(auditSource).not.toMatch(/\b(?:\d{1,3}\.){3}\d{1,3}\b/)
    expect(auditSource).not.toMatch(/\/Users\/|[A-Z]:\\Users\\/i)
    expect(auditSource).not.toMatch(/\$\d|wallet address|current holdings|position siz/i)
  })
})

describe('retired public-delay story', () => {
  const publicCopy = [
    '../app/page.tsx',
    '../app/architecture/page.tsx',
    '../app/trading/page.tsx',
    '../app/onchain/page.tsx',
    '../app/research/page.tsx',
    '../data/metrics.ts',
    '../../content/research/how-research-is-published.md',
  ].map((relative) =>
    readFileSync(fileURLToPath(new URL(relative, import.meta.url)), 'utf-8'),
  ).join('\n')

  it('does not describe live telemetry as a delayed second tier', () => {
    expect(publicCopy).not.toMatch(/delayed (?:public )?projection/i)
    expect(publicCopy).not.toMatch(/public projection lags/i)
    expect(publicCopy).not.toMatch(/figures shown publicly are delayed/i)
    expect(publicCopy).not.toMatch(/delayed or summarised public tier/i)
  })

  it('states the surviving capital boundary as omission or banding', () => {
    expect(publicCopy).toContain('capital surface remains banded')
    expect(publicCopy).toContain('Current holdings and sizes are absent')
  })
})
