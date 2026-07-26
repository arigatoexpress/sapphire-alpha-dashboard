import { describe, expect, it } from 'vitest'
import { linkId, type LiveSnapshot } from '../telemetry'
import realSnapshot from './fixtures/live-snapshot.json'
import emptySnapshot from './fixtures/empty-snapshot.json'

/* The TypeScript type is a claim about what the endpoint serves. These tests
   check that claim against captured payloads, so a drift in the Python schema
   shows up here rather than as `undefined` on the page. */

const snapshot = realSnapshot as unknown as LiveSnapshot

function keysDeep(value: unknown, out: string[] = []): string[] {
  if (Array.isArray(value)) {
    for (const item of value) keysDeep(item, out)
  } else if (value !== null && typeof value === 'object') {
    for (const [key, child] of Object.entries(value)) {
      out.push(key)
      keysDeep(child, out)
    }
  }
  return out
}

describe('telemetry — the captured payloads match the type', () => {
  it('carries no redaction artefact anywhere in the tree', () => {
    for (const payload of [realSnapshot, emptySnapshot]) {
      const keys = keysDeep(payload)
      expect(keys.filter((key) => key.endsWith('_band'))).toEqual([])
      expect(keys).not.toContain('public_view')
      expect(keys).not.toContain('public_policy')
      expect(keys).not.toContain('activity_band')
      expect(keys).not.toContain('latency_band')
    }
  })

  it('gives every node the fields the type promises, with activity nullable', () => {
    expect(snapshot.nodes.length).toBeGreaterThan(0)
    for (const node of snapshot.nodes) {
      expect(typeof node.id).toBe('string')
      expect(typeof node.label).toBe('string')
      expect(['idle', 'low', 'medium', 'high']).toContain(node.load)
      expect(node.activity_rate === null || typeof node.activity_rate === 'number').toBe(true)
      expect(typeof node.freshness_s).toBe('number')
    }
    expect(snapshot.nodes.some((node) => node.activity_rate === null)).toBe(true)
    expect(snapshot.nodes.some((node) => typeof node.activity_rate === 'number')).toBe(true)
  })

  it('keeps both link measurements nullable', () => {
    for (const link of snapshot.links) {
      expect(link.event_rate === null || typeof link.event_rate === 'number').toBe(true)
      expect(link.latency_ms === null || typeof link.latency_ms === 'number').toBe(true)
    }
    expect(snapshot.links.some((link) => link.event_rate === null)).toBe(true)
    expect(snapshot.links.some((link) => typeof link.event_rate === 'number')).toBe(true)
  })

  it('does not preserve the captured proxy rates as measurements', () => {
    const windowsNodeIds = new Set([
      'win-workhorse',
      'agent-worker',
      'telegram-bot',
      'ollama-inference',
      'knowledge-archive',
    ])
    const windowsNodes = snapshot.nodes.filter((node) => windowsNodeIds.has(node.id))
    const windowsLinks = snapshot.links.filter(
      (link) => windowsNodeIds.has(link.source) || windowsNodeIds.has(link.target),
    )
    expect(windowsNodes.length).toBeGreaterThan(0)
    expect(windowsLinks.length).toBeGreaterThan(0)
    expect(windowsNodes.every((node) => node.activity_rate === null)).toBe(true)
    expect(windowsLinks.every((link) => link.event_rate === null)).toBe(true)
    expect(snapshot.summary.events_per_min).toBeNull()
    expect(snapshot.summary.verified_today).toBeNull()
    expect(snapshot.summary.attention).toBeNull()
    expect(snapshot.markets.paper_strategies).toBeNull()
  })

  it('derives the available active-agent count from the agent list', () => {
    const active = snapshot.agents.filter(
      (agent) => agent.state === 'working' || agent.state === 'verifying',
    ).length
    expect(snapshot.summary.active_agents).toBe(active)
  })

  it('only links declared nodes, in one direction', () => {
    const ids = new Set(snapshot.nodes.map((node) => node.id))
    for (const link of snapshot.links) {
      expect(ids.has(link.source)).toBe(true)
      expect(ids.has(link.target)).toBe(true)
      expect(link.source).not.toBe(link.target)
    }
  })

  it('gives links a unique, direction-carrying identity', () => {
    const ids = snapshot.links.map(linkId)
    expect(new Set(ids).size).toBe(ids.length)
    expect(linkId({ source: 'a', target: 'b' })).not.toBe(linkId({ source: 'b', target: 'a' }))
  })

  it('models the empty snapshot the backend really serves', () => {
    const empty = emptySnapshot as unknown as LiveSnapshot
    expect(empty.observed_at).toBeNull()
    expect(empty.freshness_s).toBeNull()
    expect(empty.markets.feed_age_s).toBeNull()
    expect(empty.markets.events_per_min).toBeNull()
    expect(empty.markets.paper_strategies).toBeNull()
    expect(empty.summary.active_agents).toBeNull()
    expect(empty.summary.events_per_min).toBeNull()
    expect(empty.summary.verified_today).toBeNull()
    expect(empty.summary.attention).toBeNull()
    expect(empty.summary.state).toBe('not observed')
    expect(empty).not.toHaveProperty('received_at')
  })
})
