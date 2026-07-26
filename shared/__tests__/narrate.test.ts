import { describe, expect, it } from 'vitest'
import { narrate } from '../narrate'
import type { LiveLink, LiveNode, LiveSnapshot } from '../telemetry'
import realSnapshot from './fixtures/live-snapshot.json'
import emptySnapshot from './fixtures/empty-snapshot.json'

/* Golden cases are hand-built so the expected sentences stay stable. The real
   captured fixture is exercised separately, for properties rather than text. */

function node(partial: Partial<LiveNode> & Pick<LiveNode, 'id'>): LiveNode {
  return {
    zone: 'compute',
    label: 'A node',
    status: 'healthy',
    load: 'low',
    activity_rate: 0,
    freshness_s: 1,
    ...partial,
  }
}

function link(partial: Partial<LiveLink> & Pick<LiveLink, 'source' | 'target'>): LiveLink {
  return {
    status: 'healthy',
    latency_ms: null,
    event_rate: 0,
    signal_class: 'agent',
    ...partial,
  }
}

function snapshot(partial: Partial<LiveSnapshot> = {}): LiveSnapshot {
  return {
    version: 1,
    observed_at: '2026-07-25T22:00:00+00:00',
    sequence: 1,
    summary: {
      state: 'observing',
      active_agents: 0,
      events_per_min: 0,
      verified_today: 0,
      attention: 0,
    },
    nodes: [],
    links: [],
    agents: [],
    markets: {
      network: 'Robinhood Chain',
      status: 'current',
      feed_age_s: 1,
      events_per_min: 0,
      paper_strategies: 0,
      decision_gate: 'telegram',
      execution: 'off',
    },
    events: [],
    desk: {
      version: 1,
      updated_at: '2026-07-25T22:00:00+00:00',
      posture: 'capital_preservation',
      leader: 'none',
      validation: { oos_pass: 0, oos_total: 7, conflicts: 1 },
      decisions: { pending: 0 },
      execution: 'halted',
      feeds: { fresh: 7, total: 7 },
    },
    status: 'live',
    freshness_s: 4,
    served_at: '2026-07-25T22:00:04+00:00',
    ...partial,
  }
}

describe('narrate — healthy', () => {
  const healthy = snapshot({
    summary: {
      state: 'observing',
      active_agents: 3,
      events_per_min: 44,
      verified_today: 11,
      attention: 0,
    },
    nodes: [node({ id: 'gpu-compute' }), node({ id: 'markets', zone: 'markets' })],
    links: [link({ source: 'gpu-compute', target: 'markets', event_rate: 44 })],
    agents: [
      { id: 'coder', role: 'coder', state: 'working', activity: 'x', verification: 'pending', provider_class: 'local GPU', updated_at: '2026-07-25T22:00:00+00:00' },
      { id: 'review', role: 'review', state: 'working', activity: 'x', verification: 'pending', provider_class: 'local GPU', updated_at: '2026-07-25T22:00:00+00:00' },
      { id: 'fast', role: 'fast', state: 'working', activity: 'x', verification: 'verified', provider_class: 'local GPU', updated_at: '2026-07-25T22:00:00+00:00' },
    ],
  })

  it('produces the golden healthy narration', () => {
    expect(narrate(healthy)).toEqual({
      tone: 'healthy',
      sentences: [
        'The home graphics card is sending work to the trading desk, about 44 times a minute.',
        'Three agents are working.',
        'Nothing is waiting on you.',
      ],
      text:
        'The home graphics card is sending work to the trading desk, about 44 times a minute. ' +
        'Three agents are working. Nothing is waiting on you.',
    })
  })

  it('says so plainly when nothing is moving', () => {
    const quiet = snapshot({ nodes: healthy.nodes, links: [link({ source: 'gpu-compute', target: 'markets', event_rate: 0 })] })
    expect(narrate(quiet).sentences[0]).toBe('No measured connection is moving right now.')
  })

  it('does not turn an unmeasured rate into a quiet-system claim', () => {
    const unknown = snapshot({
      nodes: healthy.nodes,
      links: [link({ source: 'gpu-compute', target: 'markets', event_rate: null })],
    })
    expect(narrate(unknown).sentences[0]).toBe(
      'No connection supplied a traffic measurement in this report.',
    )
  })

  it('does not turn a missing attention count into nothing waiting', () => {
    const unknown = snapshot({
      summary: {
        state: 'observing',
        active_agents: null,
        events_per_min: null,
        verified_today: null,
        attention: null,
      },
      nodes: [node({ id: 'gpu-compute' })],
    })
    expect(narrate(unknown).sentences).toContain(
      'The report did not include a count of decisions waiting for a person.',
    )
    expect(narrate(unknown).sentences).not.toContain('Nothing is waiting on you.')
  })

  it('uses a plural verb for plural node names', () => {
    const plural = snapshot({
      nodes: [node({ id: 'intelligence', zone: 'intelligence' }), node({ id: 'markets', zone: 'markets' })],
      links: [link({ source: 'intelligence', target: 'markets', event_rate: 5 })],
    })
    expect(narrate(plural).sentences[0]).toBe(
      'The thinking agents are sending work to the trading desk, about 5 times a minute.',
    )
  })
})

describe('narrate — degraded', () => {
  const degraded = snapshot({
    summary: {
      state: 'degraded',
      active_agents: 1,
      events_per_min: 12,
      verified_today: 2,
      attention: 3,
    },
    nodes: [
      node({ id: 'gpu-compute' }),
      node({ id: 'markets', zone: 'markets' }),
      node({ id: 'archive', zone: 'archive', status: 'down' }),
      node({ id: 'orchestration', zone: 'orchestration', status: 'down' }),
    ],
    links: [link({ source: 'gpu-compute', target: 'markets', event_rate: 12 })],
    agents: [
      { id: 'coder', role: 'coder', state: 'working', activity: 'x', verification: 'pending', provider_class: 'local GPU', updated_at: '2026-07-25T22:00:00+00:00' },
    ],
  })

  it('produces the golden degraded narration', () => {
    expect(narrate(degraded)).toEqual({
      tone: 'degraded',
      sentences: [
        'The home graphics card is sending work to the trading desk, about 12 times a minute.',
        'One agent is working.',
        'Two parts are not reporting: the knowledge archive and the job scheduler.',
        'Three things are waiting for a person to decide.',
      ],
      text:
        'The home graphics card is sending work to the trading desk, about 12 times a minute. ' +
        'One agent is working. ' +
        'Two parts are not reporting: the knowledge archive and the job scheduler. ' +
        'Three things are waiting for a person to decide.',
    })
  })
})

describe('narrate — stale', () => {
  it('refuses to describe the present from an old snapshot', () => {
    const stale = snapshot({
      status: 'stale',
      freshness_s: 900,
      summary: { state: 'observing', active_agents: 9, events_per_min: 200, verified_today: 4, attention: 0 },
      nodes: [node({ id: 'gpu-compute' })],
    })
    const result = narrate(stale)
    expect(result).toEqual({
      tone: 'stale',
      sentences: [
        'The last report from the system arrived 15 minutes ago.',
        'What you see is that old report, not what the system is doing right now.',
      ],
      text:
        'The last report from the system arrived 15 minutes ago. ' +
        'What you see is that old report, not what the system is doing right now.',
    })
  })

  it('reads seconds when the gap is under two minutes', () => {
    const stale = snapshot({ status: 'stale', freshness_s: 95, nodes: [node({ id: 'gpu-compute' })] })
    expect(narrate(stale).sentences[0]).toBe('The last report from the system arrived 95 seconds ago.')
  })

  it('treats a missing freshness reading as unknown rather than guessing', () => {
    const stale = snapshot({ status: 'stale', freshness_s: null, nodes: [node({ id: 'gpu-compute' })] })
    expect(narrate(stale).sentences[0]).toBe('The last report from the system is out of date.')
  })
})

describe('narrate — empty', () => {
  it('produces the golden empty narration', () => {
    expect(narrate(snapshot({ status: 'offline', observed_at: null, freshness_s: null }))).toEqual({
      tone: 'empty',
      sentences: [
        'No live report has arrived yet.',
        'Nothing is being measured right now, so there is nothing to show.',
      ],
      text: 'No live report has arrived yet. Nothing is being measured right now, so there is nothing to show.',
    })
  })

  it('handles the real empty snapshot the backend serves', () => {
    const result = narrate(emptySnapshot as unknown as LiveSnapshot)
    expect(result.tone).toBe('empty')
    expect(result.sentences).toHaveLength(2)
  })
})

describe('narrate — never asserts what the data does not support', () => {
  const real = realSnapshot as unknown as LiveSnapshot

  it('never mentions latency when no link reports one', () => {
    expect(real.links.every((l) => l.latency_ms === null)).toBe(true)
    expect(narrate(real).text).not.toMatch(/\bms\b|millisecond|latency/i)
  })

  it('never claims agents are working when none are', () => {
    const idle = snapshot({
      nodes: [node({ id: 'gpu-compute' })],
      agents: [
        { id: 'coder', role: 'coder', state: 'idle', activity: 'x', verification: 'pending', provider_class: 'local GPU', updated_at: '2026-07-25T22:00:00+00:00' },
      ],
    })
    expect(narrate(idle).sentences).toContain('No agents are working right now.')
  })

  it('never renders a raw slug id in a sentence', () => {
    const text = narrate(real).text
    const slugs = real.nodes.map((n) => n.id).filter((id) => id.includes('-'))
    expect(slugs.length).toBeGreaterThan(0)
    for (const slug of slugs) expect(text).not.toContain(slug)
  })

  it('always ends in a full stop and starts with a capital', () => {
    for (const s of narrate(real).sentences) {
      expect(s).toMatch(/^[A-Z].*\.$/)
    }
  })
})
