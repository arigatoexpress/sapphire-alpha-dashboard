import { describe, expect, it } from 'vitest'
import type { LiveSnapshot } from '../telemetry'
import { linkId } from '../telemetry'
import {
  AGENT_VOCABULARY,
  describeAgent,
  describeLink,
  describeNode,
  NODE_VOCABULARY,
  LINK_VOCABULARY,
  UNDESCRIBED,
} from '../vocabulary'
import realSnapshot from './fixtures/live-snapshot.json'

const snapshot = realSnapshot as unknown as LiveSnapshot

/* Jargon a visitor should never have to decode. The point of the vocabulary is
   that none of it reaches the screen. */
const JARGON = [
  'MOSS', 'RAG', 'killswitch', 'kill switch', 'tier probe', 'HMAC', 'Ollama', 'LLM',
  'Tailscale', 'launchd', 'cron', 'webhook', 'API', 'endpoint', 'daemon', 'telemetry',
  'inference', 'embedding', 'vector', 'repo', 'CI', 'GPU', 'L2', 'RPC',
]

describe('vocabulary — totality against a real snapshot', () => {
  it('describes every node id in the snapshot', () => {
    const missing = snapshot.nodes.filter((n) => !describeNode(n.id).known).map((n) => n.id)
    expect(missing).toEqual([])
  })

  it('describes every link in the snapshot', () => {
    const missing = snapshot.links.filter((l) => !describeLink(l).known).map(linkId)
    expect(missing).toEqual([])
  })

  it('describes every agent id in the snapshot', () => {
    const missing = snapshot.agents.filter((a) => !describeAgent(a.id).known).map((a) => a.id)
    expect(missing).toEqual([])
  })

  it('covers a snapshot with something in it', () => {
    expect(snapshot.nodes.length).toBeGreaterThan(0)
    expect(snapshot.links.length).toBeGreaterThan(0)
    expect(snapshot.agents.length).toBeGreaterThan(0)
  })
})

describe('vocabulary — the lookup is total', () => {
  it('returns a loud fallback for an unknown node rather than the raw id', () => {
    const described = describeNode('some-new-box')
    expect(described.known).toBe(false)
    expect(described.plainName).toBe(UNDESCRIBED.plainName)
    expect(described.oneLiner).toBe(UNDESCRIBED.oneLiner)
    expect(described.id).toBe('some-new-box')
  })

  it('returns a loud fallback for an unknown link', () => {
    expect(describeLink({ source: 'a', target: 'b' }).known).toBe(false)
  })

  it('returns a loud fallback for an unknown agent', () => {
    expect(describeAgent('mystery').known).toBe(false)
  })

  it('never puts a raw slug id into the fallback name a visitor reads', () => {
    expect(UNDESCRIBED.plainName).not.toMatch(/[a-z]+-[a-z]+/)
    expect(describeNode('win-workhorse-2').plainName).not.toContain('win-workhorse-2')
  })

  it('the fallback reads as a defect, not as a description', () => {
    expect(UNDESCRIBED.plainName.toLowerCase()).toContain('missing')
  })
})

describe('vocabulary — plain English', () => {
  const entries = [
    ...Object.entries(NODE_VOCABULARY),
    ...Object.entries(LINK_VOCABULARY),
    ...Object.entries(AGENT_VOCABULARY),
  ]

  it('has entries', () => {
    expect(entries.length).toBeGreaterThan(30)
  })

  it('uses no unexplained jargon', () => {
    const offences: string[] = []
    for (const [key, entry] of entries) {
      const haystack = `${entry.plainName} ${entry.oneLiner}`
      for (const word of JARGON) {
        const pattern = new RegExp(`\\b${word.replace(/ /g, '\\s')}\\b`, 'i')
        if (pattern.test(haystack)) offences.push(`${key}: ${word}`)
      }
    }
    expect(offences).toEqual([])
  })

  it('never uses a bare hostname or slug as a plain name', () => {
    for (const [key, entry] of entries) {
      expect(entry.plainName, key).not.toMatch(/[a-z0-9]+-[a-z0-9]+/)
      expect(entry.plainName, key).not.toMatch(/\./)
    }
  })

  it('gives every entry a one-liner that is a real sentence', () => {
    for (const [key, entry] of entries) {
      expect(entry.oneLiner, key).toMatch(/^[A-Z].*\.$/)
      expect(entry.oneLiner.length, key).toBeGreaterThan(20)
    }
  })

  it('keeps plain names short enough to render as labels', () => {
    for (const [key, entry] of entries) {
      expect(entry.plainName.length, key).toBeLessThanOrEqual(40)
      expect(entry.plainName.length, key).toBeGreaterThan(2)
    }
  })
})
