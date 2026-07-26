/**
 * The load-bearing assertion in this file is the first one: a link with no
 * exact latency must never put a number on the screen. Everything the site
 * argues rests on the difference between a reading and a plausible-looking
 * placeholder, and `latency_ms` is `null` on all nine links today — so the
 * failure mode is real, not hypothetical. The legacy compatibility cases go
 * further: categorical bands may preserve status, but may never be inverted
 * into a number or motion.
 *
 * The rest pins the distinctions that are easy to lose in a refactor:
 * "unmeasured" vs "measured zero", one cell per node, and a snapshot that ages
 * into staleness rather than being described in the present tense forever.
 */

import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

import type { LiveSnapshot } from '@shared/telemetry'
import { NODE_VOCABULARY, LINK_VOCABULARY } from '@shared/vocabulary'
import { STALE_AFTER_SECONDS } from '@shared/narrate'

import {
  GRID_COLUMNS,
  NODE_PLACEMENT,
  ageSnapshot,
  describeAge,
  describeLatency,
  describeRate,
  flowSeconds,
  flowWeight,
  healthWord,
  loadSteps,
  loadWord,
  machineView,
  moneySentence,
  normalizeLivePayload,
  placeNodes,
  rateIntensity,
} from './machineRoom'

/** The captured real snapshot the shared modules are tested against. */
const snapshot = JSON.parse(
  readFileSync(
    fileURLToPath(new URL('../../../shared/__tests__/fixtures/live-snapshot.json', import.meta.url)),
    'utf-8',
  ),
) as LiveSnapshot

const DIGIT = /\d/

/** The contract served before exact numeric public telemetry was deployed. */
const legacyPayload = {
  version: 1,
  observed_at: '2026-07-25T22:26:16.581294+00:00',
  sequence: 1785018376689960200,
  summary: {
    state: 'degraded',
    active_agents: 2,
    activity_band: 'busy',
    verified_today: 4,
    attention: 1,
  },
  nodes: [
    {
      id: 'public-edge',
      zone: 'edge',
      label: 'Public edge',
      status: 'healthy',
      load_band: 'low',
      activity_band: 'busy',
      freshness_band: 'current',
    },
    {
      id: 'orchestration',
      zone: 'orchestration',
      label: 'Orchestration',
      status: 'degraded',
      load_band: 'medium',
      activity_band: 'active',
      freshness_band: 'stale',
    },
  ],
  links: [
    {
      source: 'public-edge',
      target: 'orchestration',
      status: 'degraded',
      latency_band: 'under 20 ms',
      activity_band: 'busy',
      signal_class: 'network',
    },
  ],
  agents: [
    {
      role: 'Research scout',
      state: 'working',
      activity: 'Comparing signals',
      verification: 'pending',
      provider_class: 'local GPU',
    },
  ],
  markets: {
    network: 'Example network',
    status: 'current',
    feed_freshness: 'current',
    activity_band: 'busy',
    paper_strategies: 2,
    decision_gate: 'manual',
    execution: 'off',
  },
  events: [
    {
      id: 'event-one',
      observed_at: '2026-07-25T22:26:16.581294+00:00',
      event_class: 'agent',
      source: 'intelligence',
      target: 'archive',
      label: 'Result checked',
      status: 'verified',
    },
  ],
  public_view: true,
  public_policy: 'Activity is aggregated and delayed for safety.',
  status: 'live',
  freshness_s: 4.2,
  served_at: '2026-07-25T22:26:20.781294+00:00',
} as const

describe('describeLatency — an absent reading never becomes a number', () => {
  it('renders null as "not measured", with no digit anywhere in the text', () => {
    const result = describeLatency(null)
    expect(result.measured).toBe(false)
    expect(result.text).toBe('not measured')
    expect(result.text).not.toMatch(DIGIT)
    expect(result.value).toBeUndefined()
  })

  it.each([undefined, NaN, Infinity, -Infinity, -1])(
    'treats %p as no reading rather than as a value',
    (input) => {
      const result = describeLatency(input as number | null)
      expect(result.measured).toBe(false)
      expect(result.text).not.toMatch(DIGIT)
    },
  )

  it('renders a real measurement as a number', () => {
    expect(describeLatency(7.42)).toEqual({ measured: true, value: 7.4, text: '7.4 ms to answer' })
    expect(describeLatency(184.6)).toEqual({ measured: true, value: 185, text: '185 ms to answer' })
  })

  it('renders a measured zero as zero, not as missing', () => {
    const result = describeLatency(0)
    expect(result.measured).toBe(true)
    expect(result.value).toBe(0)
  })
})

describe('the captured exact-schema fixture, whose latencies are all null', () => {
  it('has no measured latency on any link (the premise of the test above)', () => {
    expect(snapshot.links).toHaveLength(9)
    expect(snapshot.links.every((link) => link.latency_ms === null)).toBe(true)
  })

  it('produces no latency digit anywhere in the view model', () => {
    const view = machineView(snapshot)
    expect(view.links).toHaveLength(9)
    for (const link of view.links) {
      expect(link.latency.measured).toBe(false)
      expect(link.latency.text).not.toMatch(DIGIT)
      expect(link.latency.value).toBeUndefined()
    }
  })

  it('prints a numeric rate supplied under the exact schema', () => {
    const view = machineView(snapshot)
    const busiest = view.links.find((link) => link.id === 'intelligence->markets')
    expect(busiest?.rate).toEqual({ measured: true, value: 599, text: 'about 599 times a minute' })
  })

  it('lights an edge up automatically once a latency arrives', () => {
    const instrumented: LiveSnapshot = {
      ...snapshot,
      links: snapshot.links.map((link, index) =>
        index === 0 ? { ...link, latency_ms: 12.5 } : link,
      ),
    }
    const view = machineView(instrumented)
    expect(view.links[0].latency).toEqual({
      measured: true,
      value: 13,
      text: '13 ms to answer',
    })
    // and nothing else changed its mind
    expect(view.links.slice(1).every((link) => !link.latency.measured)).toBe(true)
  })
})

describe('describeRate — measured zero is not the same claim as unmeasured', () => {
  it('says nothing is moving when the rate is a measured zero', () => {
    expect(describeRate(0)).toEqual({ measured: true, value: 0, text: 'nothing moving' })
  })

  it('says "not measured" when there is no rate at all', () => {
    expect(describeRate(null).measured).toBe(false)
    expect(describeRate(undefined).measured).toBe(false)
    expect(describeRate(NaN).measured).toBe(false)
  })

  it('never confuses the two on the exact-schema fixture', () => {
    const idle = machineView(snapshot).links.find((l) => l.id === 'gpu-compute->intelligence')
    expect(idle?.rate.measured).toBe(true)
    expect(idle?.rate.value).toBe(0)
    expect(idle?.latency.measured).toBe(false)
  })

  it('reads small and singular rates as English', () => {
    expect(describeRate(0.4).text).toBe('less than once a minute')
    expect(describeRate(1).text).toBe('about once a minute')
    expect(describeRate(24).text).toBe('about 24 times a minute')
  })
})

describe('motion is only ever driven by a measurement', () => {
  it('refuses to animate an unmeasured or zero rate', () => {
    expect(flowSeconds(null)).toBeNull()
    expect(flowSeconds(undefined)).toBeNull()
    expect(flowSeconds(0)).toBeNull()
    expect(flowSeconds(NaN)).toBeNull()
  })

  it('animates a busier link faster, strictly', () => {
    const rates = [1, 8, 16, 24, 63.6, 599]
    const durations = rates.map((rate) => flowSeconds(rate) as number)
    expect(durations.every((d) => d !== null)).toBe(true)
    for (let i = 1; i < durations.length; i += 1) {
      expect(durations[i]).toBeLessThan(durations[i - 1])
    }
  })

  it('keeps every duration inside the legible band', () => {
    for (const rate of [0.01, 1, 100, 599, 10_000]) {
      const seconds = flowSeconds(rate) as number
      expect(seconds).toBeGreaterThanOrEqual(0.9)
      expect(seconds).toBeLessThanOrEqual(7)
    }
  })

  it('draws a busier link thicker, and never thinner than a hairline', () => {
    expect(flowWeight(0)).toBe(1)
    expect(flowWeight(null)).toBe(1)
    expect(flowWeight(599)).toBeGreaterThan(flowWeight(8))
    expect(flowWeight(10_000)).toBeLessThanOrEqual(4)
  })

  it('scales rate intensity between 0 and 1 only', () => {
    expect(rateIntensity(-5)).toBe(0)
    expect(rateIntensity(0)).toBe(0)
    expect(rateIntensity(1e9)).toBe(1)
  })

  it('holds a part still unless it is both answering and measurably busy', () => {
    const view = machineView(snapshot)
    const byId = new Map(view.nodes.map((node) => [node.id, node]))
    // measured 0.0 events/min, and down
    expect(byId.get('intelligence')?.pulseSeconds).toBeNull()
    // measured 599 events/min, healthy
    expect(byId.get('markets')?.pulseSeconds).toBeGreaterThan(0)
  })

  it('holds a struggling part still even when it is busy', () => {
    const degraded: LiveSnapshot = {
      ...snapshot,
      nodes: snapshot.nodes.map((node) =>
        node.id === 'markets' ? { ...node, status: 'degraded' as const } : node,
      ),
    }
    const markets = machineView(degraded).nodes.find((n) => n.id === 'markets')
    expect(markets?.pulseSeconds).toBeNull()
  })
})

describe('the schema boundary — bands never become measurements', () => {
  it('accepts the current exact contract as exact', () => {
    const parsed = normalizeLivePayload(snapshot)
    expect(parsed?.precision).toBe('exact')
    expect(parsed?.snapshot.summary.events_per_min).toBe(snapshot.summary.events_per_min)
    expect(parsed?.snapshot.links[3].event_rate).toBe(snapshot.links[3].event_rate)
  })

  it('fails closed when queue stages contradict their total', () => {
    expect(
      normalizeLivePayload({
        ...snapshot,
        desk: {
          ...snapshot.desk,
          decisions: { ...snapshot.desk.decisions, blocked: 13 },
        },
      }),
    ).toBeNull()
  })

  it('accepts honest null rates in the exact contract and leaves them still', () => {
    const honest = {
      ...snapshot,
      summary: { ...snapshot.summary, events_per_min: null },
      nodes: snapshot.nodes.map((node, index) => ({
        ...node,
        activity_rate: index === 0 ? null : node.activity_rate,
      })),
      links: snapshot.links.map((link, index) => ({
        ...link,
        event_rate: index === 0 ? null : link.event_rate,
      })),
    }
    const parsed = normalizeLivePayload(honest)
    expect(parsed?.precision).toBe('exact')
    if (!parsed) throw new Error('honest nullable payload did not parse')
    const view = machineView(parsed.snapshot, { precision: parsed.precision })
    expect(view.nodes[0].activity.measured).toBe(false)
    expect(view.nodes[0].pulseSeconds).toBeNull()
    expect(view.links[0].rate.measured).toBe(false)
    expect(view.links[0].flowSeconds).toBeNull()
    expect(view.vitals.find((vital) => vital.label === 'Things happening')?.value).toBe('—')
  })

  it('accepts the previous public contract but leaves every hidden figure blank', () => {
    const parsed = normalizeLivePayload(legacyPayload)
    expect(parsed?.precision).toBe('banded')
    if (!parsed) throw new Error('legacy payload did not parse')

    const view = machineView(parsed.snapshot, { precision: parsed.precision })
    expect(view.precision).toBe('banded')
    expect(view.hasReading).toBe(true)
    expect(view.nodes.every((node) => !node.activity.measured)).toBe(true)
    expect(view.nodes.every((node) => !node.age.measured)).toBe(true)
    expect(view.nodes.every((node) => node.pulseSeconds === null)).toBe(true)
    expect(view.links.every((link) => !link.rate.measured)).toBe(true)
    expect(view.links.every((link) => !link.latency.measured)).toBe(true)
    expect(view.links.every((link) => link.flowSeconds === null)).toBe(true)
    expect(view.links.every((link) => link.weight === 1)).toBe(true)
    expect(view.vitals.find((vital) => vital.label === 'Things happening')?.value).toBe('—')
  })

  it('preserves direct categorical state without treating it as timing evidence', () => {
    const parsed = normalizeLivePayload(legacyPayload)
    if (!parsed) throw new Error('legacy payload did not parse')
    const view = machineView(parsed.snapshot, { precision: parsed.precision })
    expect(view.nodes.find((node) => node.id === 'public-edge')?.loadWord).toBe('A little to do')
    expect(view.nodes.find((node) => node.id === 'orchestration')?.healthWord).toBe('Struggling')
    expect(view.links[0].latency.text).toBe('not measured')
    expect(view.links[0].latency.text).not.toMatch(DIGIT)
  })

  it('does not repeat policy prose supplied by the legacy server', () => {
    const parsed = normalizeLivePayload(legacyPayload)
    if (!parsed) throw new Error('legacy payload did not parse')
    const renderedFacts = JSON.stringify(
      machineView(parsed.snapshot, { precision: parsed.precision }),
    )
    expect(renderedFacts).not.toContain(legacyPayload.public_policy)
    expect(renderedFacts).not.toContain('aggregated and delayed')
  })

  it('downgrades a mixed migration payload instead of trusting partial numbers', () => {
    const parsed = normalizeLivePayload({
      ...legacyPayload,
      summary: { ...legacyPayload.summary, events_per_min: 99 },
      nodes: legacyPayload.nodes.map((node, index) =>
        index === 0 ? { ...node, activity_rate: 99, freshness_s: 1 } : node,
      ),
    })
    expect(parsed?.precision).toBe('banded')
    if (!parsed) throw new Error('mixed payload did not parse safely')
    const view = machineView(parsed.snapshot, { precision: parsed.precision })
    expect(view.nodes[0].activity.measured).toBe(false)
    expect(view.nodes[0].pulseSeconds).toBeNull()
    expect(view.links[0].flowSeconds).toBeNull()
  })

  it('fails closed on a malformed contract', () => {
    expect(normalizeLivePayload({ version: 1 })).toBeNull()
    expect(normalizeLivePayload({ ...legacyPayload, status: 'superb' })).toBeNull()
    expect(
      normalizeLivePayload({
        ...legacyPayload,
        summary: { ...legacyPayload.summary, activity_band: undefined },
      }),
    ).toBeNull()
  })
})

describe('plain words — no enum value reaches the screen', () => {
  const JARGON = /\b(MOSS|RAG|GPU|API|inference|killswitch|kill switch|latency|degraded|idle|telemetry|node|endpoint)\b/i

  it('translates every health and load value', () => {
    for (const status of ['healthy', 'degraded', 'down', 'unknown', null] as const) {
      expect(healthWord(status)).not.toMatch(JARGON)
    }
    for (const load of ['idle', 'low', 'medium', 'high', null] as const) {
      expect(loadWord(load)).not.toMatch(JARGON)
    }
  })

  it('fills a busyness meter monotonically, and leaves it empty with no reading', () => {
    expect(loadSteps(null)).toBe(0)
    expect(loadSteps('idle')).toBe(1)
    expect(loadSteps('low')).toBe(2)
    expect(loadSteps('medium')).toBe(3)
    expect(loadSteps('high')).toBe(4)
  })

  it('keeps every rendered string on the exact-schema fixture free of jargon', () => {
    const view = machineView(snapshot)
    const strings = [
      view.statusWord,
      view.money,
      view.age.text,
      view.narration.text,
      ...view.vitals.flatMap((vital) => [vital.label, vital.note]),
      ...view.nodes.flatMap((node) => [
        node.plainName,
        node.oneLiner,
        node.healthWord,
        node.loadWord,
        node.activity.text,
        node.age.text,
      ]),
      ...view.links.flatMap((link) => [
        link.plainName,
        link.oneLiner,
        link.rate.text,
        link.latency.text,
      ]),
    ]
    for (const value of strings) {
      expect(value, `"${value}" contains jargon`).not.toMatch(JARGON)
    }
  })

  it('never renders a raw id as a name', () => {
    const view = machineView(snapshot)
    for (const node of view.nodes) {
      expect(node.named).toBe(true)
      expect(node.plainName).not.toBe(node.id)
      expect(node.plainName).not.toMatch(/-/)
    }
    expect(view.unnamed).toEqual([])
  })

  it('reports an unnamed part as a defect instead of printing its id', () => {
    const withStranger: LiveSnapshot = {
      ...snapshot,
      nodes: [
        ...snapshot.nodes,
        {
          id: 'brand-new-thing',
          zone: 'compute',
          label: 'Brand new thing',
          status: 'healthy',
          load: 'low',
          activity_rate: 1,
          freshness_s: 0,
        },
      ],
    }
    const view = machineView(withStranger)
    const stranger = view.nodes.find((node) => node.id === 'brand-new-thing')
    expect(stranger?.named).toBe(false)
    expect(stranger?.plainName).toBe('Missing description')
    expect(view.unnamed).toContain('brand-new-thing')
  })
})

describe('money — the claim a stranger most needs to be true', () => {
  it('says plainly that nothing is being traded, from the supplied fields', () => {
    const view = machineView(snapshot)
    expect(snapshot.markets.execution).toBe('off')
    expect(view.money).toContain('No trades are being placed at all.')
    expect(view.money).toContain('A person has to approve')
  })

  it('uses the strategy count supplied by the report rather than a site constant', () => {
    expect(moneySentence({ ...snapshot.markets, paper_strategies: 2 })).toContain(
      '2 strategies are being practised on paper',
    )
  })

  it('changes what it says when execution changes', () => {
    expect(moneySentence({ ...snapshot.markets, execution: 'paper' })).toContain('practice')
    expect(moneySentence({ ...snapshot.markets, execution: 'gated' })).toContain(
      'only after a person has approved them',
    )
  })

  it('says the approval step is missing when there is no gate', () => {
    expect(moneySentence({ ...snapshot.markets, decision_gate: 'off' })).toContain(
      'no approval step',
    )
  })

  it('claims nothing at all with no reading', () => {
    expect(moneySentence(null)).toBe('Nothing about trading has been measured yet.')
  })
})

describe('layout — no two parts share a cell', () => {
  it('places every part of the real snapshot in its own cell', () => {
    const cells = placeNodes(snapshot.nodes.map((node) => node.id))
    expect(cells.size).toBe(snapshot.nodes.length)
    const keys = [...cells.values()].map((cell) => `${cell.col}:${cell.row}`)
    expect(new Set(keys).size).toBe(keys.length)
  })

  it('has a hand-placed cell for every part vocabulary knows about', () => {
    for (const id of Object.keys(NODE_VOCABULARY)) {
      expect(NODE_PLACEMENT[id], `${id} has no cell`).toBeDefined()
    }
  })

  it('gives an unplaced newcomer a free cell rather than a shared one', () => {
    const ids = [...Object.keys(NODE_VOCABULARY), 'newcomer-a', 'newcomer-b']
    const cells = placeNodes(ids)
    expect(cells.size).toBe(ids.length)
    const keys = [...cells.values()].map((cell) => `${cell.col}:${cell.row}`)
    expect(new Set(keys).size).toBe(keys.length)
  })

  it('survives more parts than the grid has hand-placed cells', () => {
    const ids = Array.from({ length: GRID_COLUMNS * 9 }, (_, i) => `node-${i}`)
    const cells = placeNodes(ids)
    expect(cells.size).toBe(ids.length)
    const keys = [...cells.values()].map((cell) => `${cell.col}:${cell.row}`)
    expect(new Set(keys).size).toBe(keys.length)
    expect([...cells.values()].every((cell) => cell.col >= 1 && cell.col <= GRID_COLUMNS)).toBe(true)
  })

  it('keeps the two chains on their own rows, so no edge crosses another', () => {
    const cells = placeNodes(snapshot.nodes.map((node) => node.id))
    const publicLane = ['public-edge', 'orchestration', 'gpu-compute', 'intelligence', 'markets']
    publicLane.forEach((id, index) => {
      expect(cells.get(id)).toEqual({ col: index + 1, row: 1 })
    })
    const messageLane = ['telegram-bot', 'agent-worker', 'ollama-inference', 'win-workhorse']
    messageLane.forEach((id, index) => {
      expect(cells.get(id)).toEqual({ col: index + 1, row: 2 })
    })
  })

  it('draws every declared link, and only between parts that are on the diagram', () => {
    const view = machineView(snapshot)
    expect(view.links.map((link) => link.id).sort()).toEqual(Object.keys(LINK_VOCABULARY).sort())
  })

  it('drops a link that points at a part which is not shown', () => {
    const orphaned: LiveSnapshot = {
      ...snapshot,
      links: [
        ...snapshot.links,
        {
          source: 'public-edge',
          target: 'nowhere',
          status: 'healthy',
          latency_ms: null,
          event_rate: 5,
          signal_class: 'network',
        },
      ],
    }
    expect(machineView(orphaned).links.map((link) => link.id)).not.toContain('public-edge->nowhere')
  })
})

describe('ageing — a page left open stops claiming the present', () => {
  it('adds elapsed wall-clock time to the snapshot’s own age', () => {
    const aged = ageSnapshot({ ...snapshot, freshness_s: 4.2 }, 30)
    expect(aged.freshness_s).toBeCloseTo(34.2)
    expect(aged.status).toBe('live')
  })

  it('flips to stale once the total age crosses the threshold', () => {
    const aged = ageSnapshot({ ...snapshot, freshness_s: 4.2 }, STALE_AFTER_SECONDS)
    expect(aged.status).toBe('stale')
    expect(machineView(aged).mode).toBe('stale')
    expect(machineView(aged).narration.tone).toBe('stale')
  })

  it('does not flip early', () => {
    const aged = ageSnapshot({ ...snapshot, freshness_s: 0 }, STALE_AFTER_SECONDS - 1)
    expect(aged.status).toBe('live')
    expect(machineView(aged).mode).toBe('live')
  })

  it('never runs time backwards', () => {
    expect(ageSnapshot({ ...snapshot, freshness_s: 10 }, -50).freshness_s).toBe(10)
    expect(ageSnapshot({ ...snapshot, freshness_s: 10 }, NaN).freshness_s).toBe(10)
  })

  it('leaves an ageless snapshot ageless rather than inventing a zero', () => {
    expect(ageSnapshot({ ...snapshot, freshness_s: null }, 90).freshness_s).toBeNull()
  })

  it('says how old a reading is in words a person uses', () => {
    expect(describeAge(0).text).toBe('just now')
    expect(describeAge(41).text).toBe('41 seconds ago')
    expect(describeAge(120).text).toBe('2 minutes ago')
    expect(describeAge(7200).text).toBe('2 hours ago')
    expect(describeAge(86_400 * 3).text).toBe('3 days ago')
    expect(describeAge(null).text).toBe('not measured')
  })

  it('flags a part whose own reading is older than the whole feed may be', () => {
    const view = machineView(snapshot)
    const byId = new Map(view.nodes.map((node) => [node.id, node]))
    // fixture: intelligence last reported 84359s ago, markets 1.5s ago
    expect(byId.get('intelligence')?.ownReadingStale).toBe(true)
    expect(byId.get('markets')?.ownReadingStale).toBe(false)
  })
})

describe('with no reading at all', () => {
  const view = machineView(null)

  it('shows the map with every reading explicitly absent', () => {
    expect(view.hasReading).toBe(false)
    expect(view.nodes).toHaveLength(Object.keys(NODE_VOCABULARY).length)
    expect(view.nodes.every((node) => node.health === null)).toBe(true)
    expect(view.nodes.every((node) => node.loadSteps === 0)).toBe(true)
    expect(view.nodes.every((node) => !node.activity.measured)).toBe(true)
    expect(view.nodes.every((node) => node.pulseSeconds === null)).toBe(true)
    expect(view.links.every((link) => !link.rate.measured)).toBe(true)
    expect(view.links.every((link) => link.flowSeconds === null)).toBe(true)
  })

  it('prints no figure in any vital', () => {
    expect(view.vitals.every((vital) => vital.value === '—')).toBe(true)
  })

  it('narrates the absence rather than describing a system', () => {
    expect(view.narration.tone).toBe('empty')
    expect(view.mode).toBe('waiting')
    expect(view.statusWord).toBe('Waiting for a reading')
  })

  it('distinguishes an unreachable feed from one that has not spoken yet', () => {
    expect(machineView(null, { unreachable: true }).mode).toBe('unreachable')
    expect(machineView(null, { unreachable: true }).statusWord).toBe('Cannot reach it')
  })

  it('still names every part on the map', () => {
    expect(view.unnamed).toEqual([])
    expect(view.nodes.every((node) => node.named)).toBe(true)
    expect(view.links.every((link) => link.named)).toBe(true)
  })

  it('treats an exact-schema empty endpoint response as no reading, not four zeroes', () => {
    const empty: LiveSnapshot = {
      ...snapshot,
      observed_at: null,
      sequence: null,
      summary: {
        state: 'not observed',
        active_agents: null,
        events_per_min: null,
        verified_today: null,
        attention: null,
      },
      nodes: [],
      links: [],
      agents: [],
      markets: {
        network: 'Robinhood Chain',
        status: 'offline',
        feed_age_s: null,
        events_per_min: null,
        paper_strategies: null,
        decision_gate: 'off',
        execution: 'off',
      },
      events: [],
      status: 'warming',
      freshness_s: null,
    }
    const parsed = normalizeLivePayload(empty)
    expect(parsed?.precision).toBe('exact')
    if (!parsed) throw new Error('empty exact payload did not parse')
    const emptyView = machineView(parsed.snapshot, { precision: parsed.precision })
    expect(emptyView.hasReading).toBe(false)
    expect(emptyView.vitals.every((vital) => vital.value === '—')).toBe(true)
    expect(emptyView.money).toBe('Nothing about trading has been measured yet.')
    expect(emptyView.precision).toBeNull()
  })
})

describe('with a real reading', () => {
  const view = machineView(snapshot)

  it('reads live and repeats the feed’s own age', () => {
    expect(view.mode).toBe('live')
    expect(view.statusWord).toBe('Live')
    expect(view.age.text).toBe('just now')
  })

  it('counts the vitals straight out of the summary', () => {
    expect(view.vitals.map((vital) => vital.value)).toEqual(['9', '—', '—', '—'])
  })

  it('narrates what is happening in one plain paragraph', () => {
    expect(view.narration.tone).toBe('degraded')
    expect(view.narration.text).toContain('trading desk')
    expect(view.narration.text).not.toMatch(/\bnode\b|\bapi\b/i)
  })
})
