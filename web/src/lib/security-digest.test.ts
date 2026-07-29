import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import matter from 'gray-matter'
import { describe, expect, it } from 'vitest'

import { generateMetadata } from '../app/research/[slug]/page'
import { getReport } from './research'

const SLUG = 'security-digest-2026-07-29'
const source = readFileSync(
  fileURLToPath(
    new URL('../../content/research/security-digest-2026-07-29.md', import.meta.url),
  ),
  'utf-8',
)
const parsed = matter(source)

const EXPECTED_RECORDS = [
  ['CVE-2026-16812', '2026-07-30'],
  ['CVE-2026-63030', '2026-07-24'],
  ['CVE-2026-0770', '2026-07-24'],
  ['CVE-2026-50522', '2026-07-25'],
  ['CVE-2026-16232', '2026-07-25'],
] as const

const CISA_FEED =
  'https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json'
const NVD_ROOT = 'https://nvd.nist.gov/vuln/detail/'

type KevRecord = { cve: string; due_date?: string }

function deadlineSummary(records: KevRecord[], asOf: string) {
  if (records.some((record) => !record.due_date)) {
    throw new Error('every admitted KEV record requires a due date')
  }
  return records.filter((record) => String(record.due_date) < asOf).length
}

describe('2026-07-29 security digest KEV truth', () => {
  it('derives four overdue entries from five complete admitted CISA records', () => {
    const provenance = parsed.data.provenance as {
      as_of?: string
      records?: KevRecord[]
      cisa_kev_catalog_version?: string
      cisa_kev_feed_sha256?: string
      retrieved_at?: string
    }
    const records = provenance.records ?? []

    expect(provenance.as_of).toBe('2026-07-29')
    expect(provenance.cisa_kev_catalog_version).toBe('2026.07.27')
    expect(provenance.cisa_kev_feed_sha256).toBe(
      'e0326281b91c4f9a5be6bc01b0d0edbbfa933643bc96e5382cd1081b16d8170a',
    )
    expect(provenance.retrieved_at).toMatch(/^2026-07-29T/)
    expect(records).toHaveLength(5)
    expect(deadlineSummary(records, provenance.as_of ?? '')).toBe(4)
    expect(parsed.data.description).toMatch(/Four of five.*past/i)
    expect(parsed.content).toMatch(/4 of 5.*past/i)
  })

  it('fails closed when an upstream summary omits any due date', () => {
    expect(() =>
      deadlineSummary(
        [
          { cve: 'CVE-complete', due_date: '2026-07-24' },
          { cve: 'CVE-missing' },
        ],
        '2026-07-29',
      ),
    ).toThrow(/requires a due date/)
  })

  it('renders every due date and direct CISA and NVD provenance links', () => {
    const report = getReport(SLUG)
    expect(report).not.toBeNull()
    expect(report?.html).toContain(`href="${CISA_FEED}"`)

    for (const [cve, dueDate] of EXPECTED_RECORDS) {
      expect(parsed.content).toContain(`CISA remediation due **${dueDate}**`)
      expect(report?.html).toContain(
        `href="https://www.cisa.gov/known-exploited-vulnerabilities-catalog?field_cve=${cve}"`,
      )
      expect(report?.html).toContain(`href="${NVD_ROOT}${cve}"`)
    }
  })

  it('exposes bounded authoritative sources in article metadata', async () => {
    const report = getReport(SLUG)
    expect(report?.sources).toEqual([
      { label: 'CISA Known Exploited Vulnerabilities catalog', url: CISA_FEED },
      { label: 'NIST National Vulnerability Database', url: 'https://nvd.nist.gov/vuln/' },
    ])

    const metadata = await generateMetadata({
      params: Promise.resolve({ slug: SLUG }),
    })
    expect(metadata.other?.citation).toEqual([
      CISA_FEED,
      'https://nvd.nist.gov/vuln/',
    ])
  })

  it('removes unsupported incident-frequency superlatives', () => {
    expect(parsed.content).not.toMatch(/most commonly cited/i)
    expect(parsed.content).not.toMatch(/top public-sector initial-access vector/i)
    expect(parsed.content).not.toMatch(/threat pack is/i)
    expect(parsed.content).not.toMatch(/\b5 of 24 prioritized\b/i)
  })
})
