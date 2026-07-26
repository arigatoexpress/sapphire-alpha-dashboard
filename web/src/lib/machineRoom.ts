/**
 * The Machine Room's view model: live snapshot in, plain English out.
 *
 * Everything here is pure. The renderer (`components/MachineRoom.tsx`) does
 * layout, fetching and motion; every judgement about *what a number means* and
 * *whether there is a number at all* is made in this file, because that is the
 * part that can be wrong in a way a screenshot review would never catch.
 *
 * Two rules this module exists to enforce:
 *
 *  1. **An absent measurement never renders as a value.** A `null`
 *     `latency_ms` must read "not measured" and must never become a
 *     plausible-looking millisecond figure. The older public payload is even
 *     stricter: its bands describe categories, not readings, so none of them
 *     may become a number or drive motion.
 *
 *  2. **"Not measured" and "measured, and it is zero" are different claims.**
 *     One link genuinely carries no traffic (`event_rate: 0`). Saying that is
 *     information. Collapsing it into "unknown" throws it away; collapsing
 *     "unknown" into "zero" invents a reading. They stay distinct end to end.
 *
 * Plain words come from `@shared/vocabulary` for anything with an id. The enum
 * values (`healthy`, `idle`, `telegram`, …) have no entry there — vocabulary
 * maps ids, not states — so their plain-English equivalents live here.
 */

import {
  linkId,
  type AgentState,
  type DecisionGate,
  type EventStatus,
  type Execution,
  type Health,
  type LiveAgent,
  type LiveDesk,
  type LiveEvent,
  type LiveLink,
  type LiveMarkets,
  type LiveNode,
  type LiveSnapshot,
  type MarketStatus,
  type NodeLoad,
  type ProviderClass,
  type ServingStatus,
  type SignalClass,
  type SummaryState,
  type Verification,
  type Zone,
} from '@shared/telemetry'
import {
  narrate,
  STALE_AFTER_SECONDS,
  type Narration,
  type NarrationTone,
} from '@shared/narrate'
import {
  LINK_VOCABULARY,
  NODE_VOCABULARY,
  describeLink,
  describeNode,
} from '@shared/vocabulary'

/* ---------------------------------------------------------------- measurement */

/**
 * A reading, or the honest absence of one. The two cases are separate types so
 * a renderer physically cannot print `value` without first checking `measured`.
 */
export type Measurement =
  | { measured: false; text: string; value?: undefined }
  | { measured: true; text: string; value: number }

const NOT_MEASURED = 'not measured'

function unmeasured(text: string = NOT_MEASURED): Measurement {
  return { measured: false, text }
}

/** Rejects NaN and ±Infinity as well as null: neither is a reading. */
function isReading(value: number | null | undefined): value is number {
  return typeof value === 'number' && Number.isFinite(value)
}

/* --------------------------------------------------------------- feed shape */

/**
 * The deployed endpoint may be one of two honest-but-different contracts:
 *
 * - `exact`: the current schema, whose numeric fields can be printed and can
 *   drive motion;
 * - `banded`: the previous public schema, whose words such as "busy" and
 *   "under 20 ms" cannot be reversed into a reading.
 *
 * Normalising at the fetch boundary lets the rest of the component keep one
 * topology shape while carrying the precision as a separate, mandatory fact.
 * The placeholder zeroes inside a banded `snapshot` are never exposed: tests
 * assert that `machineView` masks every one of them.
 */
export type TelemetryPrecision = 'exact' | 'banded'

export interface MachineReading {
  snapshot: LiveSnapshot
  precision: TelemetryPrecision
}

type JsonObject = Record<string, unknown>

const HEALTH = ['healthy', 'degraded', 'down', 'unknown'] as const
const LOAD = ['idle', 'low', 'medium', 'high'] as const
const ZONES = ['edge', 'orchestration', 'compute', 'intelligence', 'markets', 'archive'] as const
const SUMMARY_STATES = ['observing', 'quiet', 'degraded', 'offline', 'not observed'] as const
const SIGNAL_CLASSES = ['network', 'agent', 'market', 'reliability', 'archive'] as const
const AGENT_STATES = ['working', 'verifying', 'idle', 'blocked', 'offline'] as const
const VERIFICATIONS = ['verified', 'pending', 'failed', 'not_applicable'] as const
const PROVIDERS = ['local GPU', 'local CPU', 'cloud reasoning', 'hybrid', 'rule-only', 'unassigned'] as const
const MARKET_STATES = ['current', 'delayed', 'stale', 'offline'] as const
const GATES = ['telegram', 'manual', 'off'] as const
const EXECUTIONS = ['off', 'paper', 'gated'] as const
const EVENT_STATES = ['observed', 'verified', 'pending', 'degraded', 'failed', 'recovered'] as const
const SERVING_STATES = ['live', 'stale', 'warming', 'offline'] as const
const DESK_POSTURES = ['capital_preservation', 'selective_risk', 'risk_seeking', 'neutral', 'unknown'] as const
const DESK_LEADERS = ['credible', 'none', 'unknown'] as const
const DESK_EXECUTIONS = ['halted', 'off', 'gated', 'unknown'] as const
const PUBLIC_STRATEGIES = [
  'flow-follow', 'sniper', 'equity', 'rotation',
  'mean-rev', 'smart-money', 'breakout',
] as const
const ID = /^[a-z0-9][a-z0-9-]{0,39}$/

function object(value: unknown): JsonObject | null {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
    ? value as JsonObject
    : null
}

function text(value: unknown, { empty = false, limit = 200 }: { empty?: boolean; limit?: number } = {}): string | null {
  if (typeof value !== 'string') return null
  const clean = value.trim()
  if ((!empty && clean.length === 0) || clean.length > limit) return null
  return clean
}

function identifier(value: unknown): string | null {
  const clean = text(value, { limit: 40 })
  return clean !== null && ID.test(clean) ? clean : null
}

function number(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) && value >= 0 ? value : null
}

function signedNumber(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

function integer(value: unknown): number | null {
  return typeof value === 'number' && Number.isSafeInteger(value) && value >= 0 ? value : null
}

// Producers use a nanosecond clock for sequence. It is larger than JavaScript's
// exact-integer range, but the browser never calculates with or displays it;
// it only needs to preserve the decoded JSON value in the snapshot shape.
function sequenceNumber(value: unknown): number | null {
  return typeof value === 'number' && Number.isInteger(value) && value >= 0 ? value : null
}

function member<const T extends readonly string[]>(value: unknown, allowed: T): T[number] | null {
  return typeof value === 'string' && allowed.includes(value) ? value as T[number] : null
}

function nullableNumber(value: unknown): number | null | undefined {
  if (value === null) return null
  const parsed = number(value)
  return parsed === null ? undefined : parsed
}

function nullableInteger(value: unknown): number | null | undefined {
  if (value === null) return null
  const parsed = sequenceNumber(value)
  return parsed === null ? undefined : parsed
}

function nullableText(value: unknown): string | null | undefined {
  if (value === null) return null
  const parsed = text(value)
  return parsed === null ? undefined : parsed
}

function unknownDesk(): LiveDesk {
  return {
    version: 1,
    updated_at: null,
    posture: 'unknown',
    leader: 'unknown',
    validation: {
      oos_pass: null,
      oos_total: null,
      conflicts: null,
      conflict_details: [],
      replay_span_hours: null,
      replay_data_through: null,
    },
    decisions: {
      pending: null,
      pending_review: null,
      approved_awaiting_execution: null,
      eligible_execution: null,
      blocked: null,
    },
    execution: 'unknown',
    feeds: { fresh: null, total: null },
  }
}

function parseDesk(value: unknown): LiveDesk | null {
  if (value === undefined) return unknownDesk()
  const input = object(value)
  const validation = object(input?.validation)
  const decisions = object(input?.decisions)
  const feeds = object(input?.feeds)
  if (!input || input.version !== 1 || !validation || !decisions || !feeds) return null
  const updatedAt = nullableText(input.updated_at)
  const posture = member(input.posture, DESK_POSTURES)
  const leader = member(input.leader, DESK_LEADERS)
  const execution = member(input.execution, DESK_EXECUTIONS)
  const oosPass = nullableInteger(validation.oos_pass)
  const oosTotal = nullableInteger(validation.oos_total)
  const conflicts = nullableInteger(validation.conflicts)
  const conflictDetails = validation.conflict_details === undefined
    ? []
    : collect(validation.conflict_details, (item) => {
        const strategy = member(item.strategy, PUBLIC_STRATEGIES)
        const liveReturn = signedNumber(item.live_return_pct)
        const replayReturn = signedNumber(item.replay_return_pct)
        const gap = number(item.gap_pp)
        if (strategy === null || liveReturn === null || replayReturn === null || gap === null) {
          return null
        }
        return {
          strategy,
          live_return_pct: liveReturn,
          replay_return_pct: replayReturn,
          gap_pp: gap,
        }
      })
  const replaySpanHours = validation.replay_span_hours === undefined
    ? null
    : nullableNumber(validation.replay_span_hours)
  const replayDataThrough = validation.replay_data_through === undefined
    ? null
    : nullableText(validation.replay_data_through)
  const pending = nullableInteger(decisions.pending)
  const pendingReview =
    decisions.pending_review === undefined ? null : nullableInteger(decisions.pending_review)
  const approvedAwaiting =
    decisions.approved_awaiting_execution === undefined
      ? null
      : nullableInteger(decisions.approved_awaiting_execution)
  const eligibleExecution =
    decisions.eligible_execution === undefined
      ? null
      : nullableInteger(decisions.eligible_execution)
  const blocked =
    decisions.blocked === undefined ? null : nullableInteger(decisions.blocked)
  const fresh = nullableInteger(feeds.fresh)
  const total = nullableInteger(feeds.total)
  if (
    updatedAt === undefined || posture === null || leader === null || execution === null ||
    oosPass === undefined || oosTotal === undefined || conflicts === undefined ||
    conflictDetails === null || conflictDetails.length > 7 ||
    (validation.conflict_details !== undefined && conflictDetails.length !== conflicts) ||
    new Set(conflictDetails.map((item) => item.strategy)).size !== conflictDetails.length ||
    replaySpanHours === undefined || replayDataThrough === undefined ||
    pending === undefined || pendingReview === undefined || approvedAwaiting === undefined ||
    eligibleExecution === undefined || blocked === undefined ||
    fresh === undefined || total === undefined
  ) return null
  if (pendingReview !== null && pending !== pendingReview) return null
  if (
    approvedAwaiting !== null &&
    eligibleExecution !== null &&
    blocked !== null &&
    eligibleExecution + blocked !== approvedAwaiting
  ) return null
  return {
    version: 1,
    updated_at: updatedAt,
    posture,
    leader,
    validation: {
      oos_pass: oosPass,
      oos_total: oosTotal,
      conflicts,
      conflict_details: conflictDetails,
      replay_span_hours: replaySpanHours,
      replay_data_through: replayDataThrough,
    },
    decisions: {
      pending,
      pending_review: pendingReview,
      approved_awaiting_execution: approvedAwaiting,
      eligible_execution: eligibleExecution,
      blocked,
    },
    execution,
    feeds: { fresh, total },
  }
}

function collect<T>(value: unknown, parse: (item: JsonObject, index: number) => T | null): T[] | null {
  if (!Array.isArray(value)) return null
  const output: T[] = []
  for (let index = 0; index < value.length; index += 1) {
    const item = object(value[index])
    if (item === null) return null
    const parsed = parse(item, index)
    if (parsed === null) return null
    output.push(parsed)
  }
  return output
}

function parseSummary(value: unknown, precision: TelemetryPrecision): LiveSnapshot['summary'] | null {
  const input = object(value)
  if (input === null) return null
  const state = member(input.state, SUMMARY_STATES) as SummaryState | null
  const activeAgents = nullableInteger(input.active_agents)
  const eventsPerMin = precision === 'exact' ? nullableNumber(input.events_per_min) : null
  const verifiedToday = nullableInteger(input.verified_today)
  const attention = nullableInteger(input.attention)
  if (
    state === null ||
    activeAgents === undefined ||
    eventsPerMin === undefined ||
    verifiedToday === undefined ||
    attention === undefined
  ) return null
  if (precision === 'banded' && text(input.activity_band, { limit: 40 }) === null) return null
  return {
    state,
    active_agents: activeAgents,
    events_per_min: eventsPerMin,
    verified_today: verifiedToday,
    attention,
  }
}

function parseNodes(value: unknown, precision: TelemetryPrecision): LiveNode[] | null {
  return collect(value, (input) => {
    const id = identifier(input.id)
    const zone = member(input.zone, ZONES) as Zone | null
    const label = text(input.label, { limit: 80 })
    const status = member(input.status, HEALTH) as Health | null
    const load = member(
      precision === 'exact' ? input.load : input.load_band,
      LOAD,
    ) as NodeLoad | null
    const activity = precision === 'exact' ? nullableNumber(input.activity_rate) : null
    const freshness = precision === 'exact' ? number(input.freshness_s) : 0
    if (
      id === null ||
      zone === null ||
      label === null ||
      status === null ||
      load === null ||
      activity === undefined ||
      freshness === null
    ) return null
    if (
      precision === 'banded' &&
      (
        text(input.activity_band, { limit: 40 }) === null ||
        text(input.freshness_band, { limit: 40 }) === null
      )
    ) return null
    return {
      id,
      zone,
      label,
      status,
      load,
      activity_rate: activity,
      freshness_s: freshness,
    }
  })
}

function parseLinks(value: unknown, precision: TelemetryPrecision): LiveLink[] | null {
  return collect(value, (input) => {
    const source = identifier(input.source)
    const target = identifier(input.target)
    const status = member(input.status, HEALTH) as Health | null
    const signalClass = member(input.signal_class, SIGNAL_CLASSES) as SignalClass | null
    const latency = precision === 'exact' ? nullableNumber(input.latency_ms) : null
    const rate = precision === 'exact' ? nullableNumber(input.event_rate) : null
    if (
      source === null ||
      target === null ||
      source === target ||
      status === null ||
      signalClass === null ||
      latency === undefined ||
      rate === undefined
    ) return null
    if (
      precision === 'banded' &&
      (
        text(input.latency_band, { limit: 40 }) === null ||
        text(input.activity_band, { limit: 40 }) === null
      )
    ) return null
    return {
      source,
      target,
      status,
      latency_ms: latency,
      event_rate: rate,
      signal_class: signalClass,
    }
  })
}

function parseAgents(value: unknown): LiveAgent[] | null {
  return collect(value, (input) => {
    const id = identifier(input.id)
    const role = text(input.role, { limit: 80 })
    const state = member(input.state, AGENT_STATES) as AgentState | null
    const activity = text(input.activity)
    const verification = member(input.verification, VERIFICATIONS) as Verification | null
    const provider = member(input.provider_class, PROVIDERS) as ProviderClass | null
    const updatedAt = text(input.updated_at)
    if (
      id === null ||
      role === null ||
      state === null ||
      activity === null ||
      verification === null ||
      provider === null ||
      updatedAt === null
    ) return null
    return {
      id,
      role,
      state,
      activity,
      verification,
      provider_class: provider,
      updated_at: updatedAt,
    }
  })
}

function parseMarkets(value: unknown, precision: TelemetryPrecision): LiveMarkets | null {
  const input = object(value)
  if (input === null) return null
  const network = text(input.network, { empty: true, limit: 80 })
  const status = member(input.status, MARKET_STATES) as MarketStatus | null
  const feedAge = precision === 'exact' ? nullableNumber(input.feed_age_s) : null
  const eventsPerMin = precision === 'exact' ? nullableNumber(input.events_per_min) : null
  const paperStrategies = nullableInteger(input.paper_strategies)
  const gate = member(input.decision_gate, GATES) as DecisionGate | null
  const execution = member(input.execution, EXECUTIONS) as Execution | null
  if (
    network === null ||
    status === null ||
    feedAge === undefined ||
    eventsPerMin === undefined ||
    paperStrategies === undefined ||
    gate === null ||
    execution === null
  ) return null
  if (
    precision === 'banded' &&
    (
      text(input.feed_freshness, { limit: 40 }) === null ||
      text(input.activity_band, { limit: 40 }) === null
    )
  ) return null
  return {
    network,
    status,
    feed_age_s: feedAge,
    events_per_min: eventsPerMin,
    paper_strategies: paperStrategies,
    decision_gate: gate,
    execution,
  }
}

function parseEvents(value: unknown): LiveEvent[] | null {
  return collect(value, (input) => {
    const id = identifier(input.id)
    const observedAt = text(input.observed_at)
    const eventClass = member(input.event_class, SIGNAL_CLASSES) as SignalClass | null
    const source = member(input.source, ZONES) as Zone | null
    const target = member(input.target, ZONES) as Zone | null
    const label = text(input.label, { limit: 160 })
    const status = member(input.status, EVENT_STATES) as EventStatus | null
    if (
      id === null ||
      observedAt === null ||
      eventClass === null ||
      source === null ||
      target === null ||
      label === null ||
      status === null
    ) return null
    return {
      id,
      observed_at: observedAt,
      event_class: eventClass,
      source,
      target,
      label,
      status,
    }
  })
}

function looksExact(input: JsonObject): boolean {
  const summary = object(input.summary)
  if (nullableNumber(summary?.events_per_min) === undefined) return false
  if (!Array.isArray(input.nodes) || !Array.isArray(input.links)) return false
  return input.nodes.every((item) => {
    const node = object(item)
    return (
      node !== null &&
      nullableNumber(node.activity_rate) !== undefined &&
      number(node.freshness_s) !== null
    )
  }) && input.links.every((item) => {
    const link = object(item)
    return (
      link !== null &&
      nullableNumber(link.event_rate) !== undefined &&
      nullableNumber(link.latency_ms) !== undefined
    )
  })
}

/**
 * Parse an endpoint response without trusting a TypeScript assertion.
 *
 * An invalid or half-migrated payload returns `null`, causing the component to
 * keep its last good reading and mark the feed unreachable. Exact wins only
 * when every numeric display field is present; everything else must satisfy
 * the complete legacy banded contract.
 */
export function normalizeLivePayload(value: unknown): MachineReading | null {
  const input = object(value)
  if (input === null || input.version !== 1) return null
  const precision: TelemetryPrecision = looksExact(input) ? 'exact' : 'banded'

  if (
    precision === 'banded' &&
    input.public_view !== true &&
    object(input.summary)?.activity_band === undefined
  ) return null

  const observedAt = nullableText(input.observed_at)
  const sequence = nullableInteger(input.sequence)
  const summary = parseSummary(input.summary, precision)
  const nodes = parseNodes(input.nodes, precision)
  const links = parseLinks(input.links, precision)
  const markets = parseMarkets(input.markets, precision)
  const events = parseEvents(input.events)
  const desk = parseDesk(input.desk)
  const servingStatus = member(input.status, SERVING_STATES) as ServingStatus | null
  const freshness = nullableNumber(input.freshness_s)
  const servedAt = text(input.served_at)

  if (
    observedAt === undefined ||
    sequence === undefined ||
    summary === null ||
    nodes === null ||
    links === null ||
    markets === null ||
    events === null ||
    desk === null ||
    servingStatus === null ||
    freshness === undefined ||
    servedAt === null
  ) return null

  // Legacy agents deliberately omitted ids and timestamps. They contain no
  // display fact the Machine Room needs, so preserving them by inventing ids
  // would be the exact category error this boundary exists to prevent.
  const agents = precision === 'exact' ? parseAgents(input.agents) : []
  if (agents === null || (precision === 'banded' && !Array.isArray(input.agents))) return null

  const receivedAt =
    input.received_at === undefined ? undefined : text(input.received_at) ?? null
  if (receivedAt === null) return null

  return {
    precision,
    snapshot: {
      version: 1,
      observed_at: observedAt,
      sequence,
      summary,
      nodes,
      links,
      agents,
      markets,
      events,
      desk,
      status: servingStatus,
      freshness_s: freshness,
      served_at: servedAt,
      ...(receivedAt === undefined ? {} : { received_at: receivedAt }),
    },
  }
}

/**
 * Round-trip time across a link.
 *
 * `null` is the normal case right now: `telemetry/collector.py` fills this from
 * `link_latencies`, which is empty unless latency probes are configured, so
 * every one of the nine links reports `null`. When probes land this starts
 * returning a number with no change here or in the renderer.
 */
export function describeLatency(latencyMs: number | null | undefined): Measurement {
  if (!isReading(latencyMs) || latencyMs < 0) return unmeasured()
  const rounded = latencyMs >= 10 ? Math.round(latencyMs) : Math.round(latencyMs * 10) / 10
  return { measured: true, value: rounded, text: `${rounded} ms to answer` }
}

/**
 * A rate in events per minute, said the way a person would say it. Zero is a
 * measurement and gets its own words, distinct from having no measurement.
 */
export function describeRate(perMinute: number | null | undefined): Measurement {
  if (!isReading(perMinute) || perMinute < 0) return unmeasured()
  if (perMinute === 0) return { measured: true, value: 0, text: 'nothing moving' }
  if (perMinute < 1) return { measured: true, value: perMinute, text: 'less than once a minute' }
  const rounded = Math.round(perMinute)
  return {
    measured: true,
    value: rounded,
    text: rounded === 1 ? 'about once a minute' : `about ${rounded} times a minute`,
  }
}

/** Fastest and slowest a flow line is allowed to travel, in seconds per cycle. */
const FLOW_FASTEST_S = 0.9
const FLOW_SLOWEST_S = 7
/** A stable visual reference ceiling; larger exact rates simply clamp to it. */
const FLOW_REFERENCE_RATE = 600

/**
 * Where a rate sits on the scale, 0 (nothing) to 1 (as busy as the system gets).
 * Logarithmic because useful rates can span orders of magnitude: on a linear
 * scale all but the busiest link can look identical.
 */
export function rateIntensity(perMinute: number | null | undefined): number {
  if (!isReading(perMinute) || perMinute <= 0) return 0
  const scaled = Math.log10(1 + perMinute) / Math.log10(1 + FLOW_REFERENCE_RATE)
  return Math.min(1, Math.max(0, scaled))
}

/**
 * Seconds per animation cycle for a measured rate, or `null` for "do not
 * animate this". Faster is always busier, and the figure itself is printed next
 * to the line, so the motion is annotated by its own datum rather than asking
 * to be believed.
 */
export function flowSeconds(perMinute: number | null | undefined): number | null {
  const intensity = rateIntensity(perMinute)
  if (intensity === 0) return null
  const seconds = FLOW_SLOWEST_S - intensity * (FLOW_SLOWEST_S - FLOW_FASTEST_S)
  return Math.round(seconds * 100) / 100
}

/** Line weight in px, 1 (or unmeasured) to 4 (as busy as it gets). */
export function flowWeight(perMinute: number | null | undefined): number {
  return Math.round((1 + rateIntensity(perMinute) * 3) * 10) / 10
}

/** How long ago a reading was taken, in words. */
export function describeAge(seconds: number | null | undefined): Measurement {
  if (!isReading(seconds) || seconds < 0) return unmeasured()
  const whole = Math.round(seconds)
  if (whole < 5) return { measured: true, value: whole, text: 'just now' }
  if (whole < 60) return { measured: true, value: whole, text: `${whole} seconds ago` }
  if (whole < 3600) {
    const minutes = Math.round(whole / 60)
    return { measured: true, value: whole, text: `${minutes} minute${minutes === 1 ? '' : 's'} ago` }
  }
  if (whole < 86_400) {
    const hours = Math.round(whole / 3600)
    return { measured: true, value: whole, text: `${hours} hour${hours === 1 ? '' : 's'} ago` }
  }
  const days = Math.round(whole / 86_400)
  return { measured: true, value: whole, text: `${days} day${days === 1 ? '' : 's'} ago` }
}

/* --------------------------------------------------------------- plain words */

/** `_HEALTH` in plain English. No "degraded", no "down". */
export function healthWord(status: Health | null): string {
  switch (status) {
    case 'healthy':
      return 'Working'
    case 'degraded':
      return 'Struggling'
    case 'down':
      return 'Not answering'
    case 'unknown':
      return 'No reading'
    default:
      return 'No reading'
  }
}

/** `_LOAD` in plain English. */
export function loadWord(load: NodeLoad | null): string {
  switch (load) {
    case 'idle':
      return 'Nothing to do'
    case 'low':
      return 'A little to do'
    case 'medium':
      return 'Plenty to do'
    case 'high':
      return 'As much as it can take'
    default:
      return 'No reading'
  }
}

/** Filled segments of a four-step busyness meter. `0` means there is no reading. */
export function loadSteps(load: NodeLoad | null): number {
  switch (load) {
    case 'idle':
      return 1
    case 'low':
      return 2
    case 'medium':
      return 3
    case 'high':
      return 4
    default:
      return 0
  }
}

/**
 * What is happening with money, in one sentence, from the real market fields.
 * This is the single most load-bearing claim on the page for a stranger, so it
 * is assembled from `execution` and `decision_gate` rather than written down.
 */
export function moneySentence(
  markets: LiveSnapshot['markets'] | null,
): string {
  if (!markets) return 'Nothing about trading has been measured yet.'

  const execution =
    markets.execution === 'off'
      ? 'No trades are being placed at all.'
      : markets.execution === 'paper'
        ? 'Trades are being written down as practice, with no real money behind them.'
        : 'Trades are placed only after a person has approved them.'

  const gate =
    markets.decision_gate === 'off'
      ? 'There is no approval step in front of them.'
      : 'A person has to approve anything real, in a chat message, before it happens.'

  const practising =
    markets.paper_strategies !== null && markets.paper_strategies > 0
      ? ` ${markets.paper_strategies} ${markets.paper_strategies === 1 ? 'strategy is' : 'strategies are'} being practised on paper.`
      : ''

  return `${execution} ${gate}${practising}`
}

/* -------------------------------------------------------------------- layout */

export interface Cell {
  /** 1-based, to be handed straight to CSS grid. */
  col: number
  row: number
}

/**
 * Where each part sits in the diagram.
 *
 * The real graph is two chains that never cross: the path this web page itself
 * travels (top lane), and the path a message from a phone travels (bottom
 * lane). Placing them by hand keeps that readable; placing them by *zone*, as
 * the previous panel did, drew seven of the eleven parts on top of each other,
 * because three parts share the compute zone and three more pair up elsewhere.
 */
export const NODE_PLACEMENT: Record<string, Cell> = {
  'public-edge': { col: 1, row: 1 },
  orchestration: { col: 2, row: 1 },
  'gpu-compute': { col: 3, row: 1 },
  intelligence: { col: 4, row: 1 },
  markets: { col: 5, row: 1 },

  'telegram-bot': { col: 1, row: 2 },
  'agent-worker': { col: 2, row: 2 },
  'ollama-inference': { col: 3, row: 2 },
  'win-workhorse': { col: 4, row: 2 },
  archive: { col: 5, row: 2 },

  'knowledge-archive': { col: 3, row: 3 },
}

export const GRID_COLUMNS = 5

/**
 * A cell for every node, including ones nobody has placed yet.
 *
 * A part that appears in the feed without a hand-placed cell is put in the
 * first free one instead of defaulting to a shared position, so a new node can
 * never silently land on top of an existing one — the failure the zone-keyed
 * layout had. It will look out of place, which is the correct signal.
 */
export function placeNodes(ids: string[]): Map<string, Cell> {
  const placed = new Map<string, Cell>()
  const taken = new Set<string>()
  const key = (cell: Cell) => `${cell.col}:${cell.row}`

  for (const id of ids) {
    const cell = NODE_PLACEMENT[id]
    if (cell && !taken.has(key(cell))) {
      placed.set(id, cell)
      taken.add(key(cell))
    }
  }

  let cursor = 0
  for (const id of ids) {
    if (placed.has(id)) continue
    let cell: Cell
    do {
      cell = { col: (cursor % GRID_COLUMNS) + 1, row: Math.floor(cursor / GRID_COLUMNS) + 1 }
      cursor += 1
    } while (taken.has(key(cell)))
    placed.set(id, cell)
    taken.add(key(cell))
  }

  return placed
}

/* ---------------------------------------------------------------- view model */

export interface MachineNodeView {
  id: string
  plainName: string
  oneLiner: string
  /** False when vocabulary has no entry — a defect to fix, never a raw slug. */
  named: boolean
  col: number
  row: number
  health: Health | null
  healthWord: string
  load: NodeLoad | null
  loadWord: string
  loadSteps: number
  activity: Measurement
  /** Seconds per pulse of this part's indicator, or `null` for "do not pulse". */
  pulseSeconds: number | null
  age: Measurement
  /** This part's own reading is older than the whole feed is allowed to be. */
  ownReadingStale: boolean
}

export interface MachineLinkView {
  id: string
  source: string
  target: string
  plainName: string
  oneLiner: string
  named: boolean
  health: Health | null
  rate: Measurement
  latency: Measurement
  /** Seconds per flow cycle, or `null` for "do not animate". */
  flowSeconds: number | null
  weight: number
}

export interface MachineVital {
  label: string
  value: string
  note: string
}

export type MachineMode = 'live' | 'stale' | 'waiting' | 'unreachable'

export interface MachineView {
  mode: MachineMode
  /** True once a real snapshot has been read. False = the map, with no readings. */
  hasReading: boolean
  /** Null until a response passes the schema boundary. */
  precision: TelemetryPrecision | null
  /** The precision boundary in words, for the visible status line. */
  detailNote: string
  /** Short status word for the badge. Plain English, never an enum value. */
  statusWord: string
  age: Measurement
  narration: Narration
  nodes: MachineNodeView[]
  links: MachineLinkView[]
  vitals: MachineVital[]
  money: string
  /** Ids that reached the screen without a plain-English name. Should be empty. */
  unnamed: string[]
}

/** The declared architecture, used before any reading has arrived. */
const MAP_NODE_IDS = Object.keys(NODE_VOCABULARY)
const MAP_LINKS = Object.keys(LINK_VOCABULARY).map((id) => {
  const [source, target] = id.split('->')
  return { source, target }
})

function vitalsFrom(
  snapshot: LiveSnapshot | null,
  precision: TelemetryPrecision,
): MachineVital[] {
  const perMin =
    snapshot && precision === 'exact'
      ? describeRate(snapshot.summary.events_per_min)
      : unmeasured()
  return [
    {
      label: 'Helpers working',
      value:
        snapshot?.summary.active_agents !== null && snapshot?.summary.active_agents !== undefined
          ? String(snapshot.summary.active_agents)
          : '—',
      note: 'AI helpers with a job in hand at this moment.',
    },
    {
      label: 'Things happening',
      value: perMin.measured ? String(Math.round(perMin.value)) : '—',
      note:
        snapshot && precision === 'banded'
          ? 'This older report does not supply an exact rate.'
          : 'Separate events the system recorded in the last minute.',
    },
    {
      label: 'Checked and confirmed',
      value:
        snapshot?.summary.verified_today !== null && snapshot?.summary.verified_today !== undefined
          ? String(snapshot.summary.verified_today)
          : '—',
      note: 'Pieces of work checked by something other than whoever did them, today.',
    },
    {
      label: 'Waiting for a person',
      value:
        snapshot?.summary.attention !== null && snapshot?.summary.attention !== undefined
          ? String(snapshot.summary.attention)
          : '—',
      note: 'Decisions the system will not make on its own.',
    },
  ]
}

/**
 * Re-date a snapshot by the time that has passed since it was fetched.
 *
 * A page left open is the failure mode that made the old panel dishonest: it
 * read a snapshot once and then kept describing it in the present tense
 * forever. Age is the snapshot's own measured `freshness_s` plus real elapsed
 * wall-clock time, so leaving the tab open eventually — and correctly — flips
 * the narration to "what you see is an old report".
 */
export function ageSnapshot(snapshot: LiveSnapshot, elapsedSeconds: number): LiveSnapshot {
  const elapsed = Math.max(0, isReading(elapsedSeconds) ? elapsedSeconds : 0)
  const base = isReading(snapshot.freshness_s) ? snapshot.freshness_s : null
  const aged = base === null ? null : base + elapsed
  return {
    ...snapshot,
    freshness_s: aged,
    status: aged !== null && aged > STALE_AFTER_SECONDS ? 'stale' : snapshot.status,
  }
}

export interface MachineViewOptions {
  /** The feed could not be reached at all. Distinct from "no snapshot yet". */
  unreachable?: boolean
  /** Whether numeric fields came from the exact or legacy banded contract. */
  precision?: TelemetryPrecision
}

function finishNarration(tone: NarrationTone, sentences: string[]): Narration {
  return { tone, sentences, text: sentences.join(' ') }
}

/**
 * The legacy response can safely narrate that a report arrived and whether it
 * is old. It cannot narrate a busiest flow, a node rate, or a timing because
 * none of those figures crossed the boundary.
 */
function narrateBanded(snapshot: LiveSnapshot, unreachable: boolean): Narration {
  if (unreachable) {
    return finishNarration('stale', [
      'The system cannot be reached right now.',
      'This is its last status report; it did not include exact rates or timings.',
    ])
  }

  const empty =
    snapshot.observed_at === null ||
    snapshot.status === 'offline' ||
    snapshot.status === 'warming' ||
    (snapshot.nodes.length === 0 && snapshot.links.length === 0)
  if (empty) {
    return finishNarration('empty', [
      'No live report has arrived yet.',
      'The endpoint answered, but it had no system reading to show.',
    ])
  }

  const stale =
    snapshot.status === 'stale' ||
    (snapshot.freshness_s !== null && snapshot.freshness_s > STALE_AFTER_SECONDS)
  if (stale) {
    return finishNarration('stale', [
      'The last report from the system is out of date.',
      'It was a status-only report, so exact rates and timings remain blank.',
    ])
  }

  const tone: NarrationTone =
    snapshot.summary.state === 'degraded' ||
    snapshot.nodes.some((node) => node.status === 'degraded' || node.status === 'down')
      ? 'degraded'
      : 'healthy'
  return finishNarration(tone, [
    'A live status report arrived from the system.',
    'This older feed reports categories, not exact rates or timings, so the map leaves those readings blank and stays still.',
  ])
}

export function machineView(
  snapshot: LiveSnapshot | null,
  options: MachineViewOptions = {},
): MachineView {
  const unnamed: string[] = []
  const precision = options.precision ?? 'exact'
  const exact = precision === 'exact'
  const hasObservation =
    snapshot !== null &&
    snapshot.observed_at !== null &&
    snapshot.status !== 'offline' &&
    snapshot.status !== 'warming' &&
    (
      snapshot.nodes.length > 0 ||
      snapshot.links.length > 0 ||
      snapshot.agents.length > 0
    )
  const observedSnapshot = hasObservation ? snapshot : null

  const sourceNodes = observedSnapshot?.nodes ?? []
  const nodeIds = sourceNodes.length > 0 ? sourceNodes.map((node) => node.id) : MAP_NODE_IDS
  const cells = placeNodes(nodeIds)

  const nodes: MachineNodeView[] = nodeIds.map((id) => {
    const reading = sourceNodes.find((node) => node.id === id) ?? null
    const described = describeNode(id)
    if (!described.known) unnamed.push(id)
    const cell = cells.get(id) ?? { col: 1, row: 1 }
    const activity = reading && exact ? describeRate(reading.activity_rate) : unmeasured()
    const age = reading && exact ? describeAge(reading.freshness_s) : unmeasured()

    return {
      id,
      plainName: described.plainName,
      oneLiner: described.oneLiner,
      named: described.known,
      col: cell.col,
      row: cell.row,
      health: reading?.status ?? null,
      healthWord: healthWord(reading?.status ?? null),
      load: reading?.load ?? null,
      loadWord: loadWord(reading?.load ?? null),
      loadSteps: loadSteps(reading?.load ?? null),
      activity,
      // Only a part that is both answering and measurably busy pulses. An idle
      // or unread part is still, which is itself the honest reading.
      pulseSeconds:
        exact && reading?.status === 'healthy' ? flowSeconds(reading.activity_rate) : null,
      age,
      ownReadingStale: exact && age.measured && age.value > STALE_AFTER_SECONDS,
    }
  })

  const known = new Set(nodes.map((node) => node.id))
  const sourceLinks = observedSnapshot?.links ?? []
  /* With no reading, the declared connections are drawn with no figures at all
     rather than the diagram being blank. `live === null` is what makes every
     measurement on such a link read as absent. */
  const linkSource: Array<{ live: LiveLink | null; edge: Pick<LiveLink, 'source' | 'target'> }> =
    sourceLinks.length > 0
      ? sourceLinks.map((link) => ({ live: link, edge: link }))
      : MAP_LINKS.map((edge) => ({ live: null, edge }))

  const links: MachineLinkView[] = linkSource
    // A link to a part that is not on the diagram would draw to nowhere.
    .filter(({ edge }) => known.has(edge.source) && known.has(edge.target))
    .map(({ live, edge }) => {
      const described = describeLink(edge)
      if (!described.known) unnamed.push(linkId(edge))

      return {
        id: linkId(edge),
        source: edge.source,
        target: edge.target,
        plainName: described.plainName,
        oneLiner: described.oneLiner,
        named: described.known,
        health: live?.status ?? null,
        rate: live && exact ? describeRate(live.event_rate) : unmeasured(),
        latency: live && exact ? describeLatency(live.latency_ms) : unmeasured(),
        flowSeconds: live && exact ? flowSeconds(live.event_rate) : null,
        weight: live && exact ? flowWeight(live.event_rate) : 1,
      }
    })

  const narration =
    snapshot && exact && options.unreachable
      ? finishNarration('stale', [
          'The system cannot be reached right now.',
          'The figures below are the last exact report it returned, not what it is doing now.',
        ])
      : snapshot && !exact
      ? narrateBanded(snapshot, options.unreachable ?? false)
      : narrate(
          snapshot ?? {
            version: 1,
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
              network: '',
              status: 'offline',
              feed_age_s: null,
              events_per_min: null,
              paper_strategies: null,
              decision_gate: 'off',
              execution: 'off',
            },
            events: [],
            desk: unknownDesk(),
            status: 'warming',
            freshness_s: null,
            served_at: '',
          },
        )

  const mode: MachineMode = options.unreachable
    ? 'unreachable'
    : snapshot === null || narration.tone === 'empty'
      ? 'waiting'
      : narration.tone === 'stale'
        ? 'stale'
        : 'live'

  const statusWord =
    mode === 'live'
      ? 'Live'
      : mode === 'stale'
        ? 'Out of date'
        : mode === 'unreachable'
          ? 'Cannot reach it'
          : 'Waiting for a reading'

  return {
    mode,
    hasReading: hasObservation,
    precision: hasObservation ? precision : null,
    detailNote:
      !hasObservation
        ? 'No feed detail yet.'
        : exact
          ? 'Exact numeric fields supplied by this report.'
          : 'Status bands only; exact rates and timings were not supplied.',
    statusWord,
    age: observedSnapshot ? describeAge(observedSnapshot.freshness_s) : unmeasured(),
    narration,
    nodes,
    links,
    vitals: vitalsFrom(observedSnapshot, precision),
    money: moneySentence(observedSnapshot?.markets ?? null),
    unnamed,
  }
}
