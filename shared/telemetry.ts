/**
 * The shape of `GET /api/v1/live`, un-redacted.
 *
 * Single source of truth for both surfaces (`web/` and `frontend/`). It mirrors
 * `backend/live_telemetry.py`:
 *   - `validate_snapshot()` defines the stored object exactly (allowed/required
 *     key sets and the enum constants at the top of that file);
 *   - `LiveStore.get()` adds the four serving fields at the bottom of this type;
 *   - `_empty_snapshot()` is the degenerate case served before any ingest, and
 *     it is *not* schema-identical to a real one — see the notes below.
 *
 * If the Python schema changes, change this file in the same commit.
 */

/* ---- enums, mirroring the module constants in live_telemetry.py ---- */

/** `_ZONES` */
export type Zone = 'edge' | 'orchestration' | 'compute' | 'intelligence' | 'markets' | 'archive'

/** `_HEALTH` */
export type Health = 'healthy' | 'degraded' | 'down' | 'unknown'

/**
 * `_LOAD`. Served as `load`. It reads like a redaction band and is not one:
 * producers measure a categorical load directly, there is no underlying number,
 * and nothing is being withheld. It was *called* `load_band` until the
 * redaction tier was deleted; the backend still accepts that name on the wire
 * from producers and renames it before storing or serving (live_telemetry.py
 * `validate_snapshot` and `_normalize_stored`). Consumers only ever see `load`.
 */
export type NodeLoad = 'idle' | 'low' | 'medium' | 'high'

/**
 * `_SUMMARY_STATES`, plus `'not observed'`, which only `_empty_snapshot()`
 * produces and which the ingest validator would reject.
 */
export type SummaryState = 'observing' | 'quiet' | 'degraded' | 'offline' | 'not observed'

/** `_SIGNAL_CLASSES` */
export type SignalClass = 'network' | 'agent' | 'market' | 'reliability' | 'archive'

/** `_AGENT_STATES` */
export type AgentState = 'working' | 'verifying' | 'idle' | 'blocked' | 'offline'

/** `_VERIFICATION` */
export type Verification = 'verified' | 'pending' | 'failed' | 'not_applicable'

/** `_PROVIDERS` */
export type ProviderClass =
  | 'local GPU'
  | 'local CPU'
  | 'cloud reasoning'
  | 'hybrid'
  | 'rule-only'
  | 'unassigned'

/** `_MARKET_STATES` */
export type MarketStatus = 'current' | 'delayed' | 'stale' | 'offline'

/** `_GATES` */
export type DecisionGate = 'telegram' | 'manual' | 'off'

/** `_EXECUTION` */
export type Execution = 'off' | 'paper' | 'gated'

/** `_EVENT_STATES` */
export type EventStatus = 'observed' | 'verified' | 'pending' | 'degraded' | 'failed' | 'recovered'

/** Added by `LiveStore.get()`, not by the ingest schema. */
export type ServingStatus = 'live' | 'stale' | 'warming' | 'offline'

/* ---- objects ---- */

export interface LiveSummary {
  state: SummaryState
  active_agents: number | null
  /** Events per minute across the whole system, or null without a complete event log. */
  events_per_min: number | null
  verified_today: number | null
  /** How many things are waiting for a person. */
  attention: number | null
}

export interface LiveNode {
  /** Semantic slug, `^[a-z0-9][a-z0-9-]{0,39}$`. Never a hostname. */
  id: string
  zone: Zone
  label: string
  status: Health
  load: NodeLoad
  /** Events per minute attributed to this node, or null when no event source observes it. */
  activity_rate: number | null
  /** Age of this node's own reading, in seconds. */
  freshness_s: number
}

export interface LiveLink {
  /** A `LiveNode.id`. */
  source: string
  /** A `LiveNode.id`, never equal to `source`. */
  target: string
  status: Health
  /**
   * Round-trip time in milliseconds, or `null` when nothing measured it.
   * The Mac publisher times the public edge and the routed compute tier; the
   * Windows inference collector times its request round trip. Semantic paths
   * without an addressable RTT source remain null. A feed timestamp lag is
   * freshness, not latency.
   */
  latency_ms: number | null
  /** Events per minute across this edge, or null when no event source observes it. */
  event_rate: number | null
  signal_class: SignalClass
}

export interface LiveAgent {
  id: string
  role: string
  state: AgentState
  activity: string
  verification: Verification
  provider_class: ProviderClass
  updated_at: string
}

export interface LiveMarkets {
  network: string
  status: MarketStatus
  /** `null` only on the empty snapshot. */
  feed_age_s: number | null
  events_per_min: number | null
  paper_strategies: number | null
  decision_gate: DecisionGate
  execution: Execution
}

export interface LiveEvent {
  id: string
  observed_at: string
  event_class: SignalClass
  /** A zone, not a node id. */
  source: Zone
  /** A zone, not a node id. */
  target: Zone
  label: string
  status: EventStatus
}

export type DeskPosture =
  | 'capital_preservation'
  | 'selective_risk'
  | 'risk_seeking'
  | 'neutral'
  | 'unknown'

export type DeskLeader = 'credible' | 'none' | 'unknown'
export type DeskExecution = 'halted' | 'off' | 'gated' | 'unknown'

/**
 * Public-safe desk conclusions. This intentionally excludes instruments,
 * positions, balances, proposal ids, people, and named research sources.
 */
export interface LiveDesk {
  version: 1
  updated_at: string | null
  posture: DeskPosture
  leader: DeskLeader
  validation: {
    oos_pass: number | null
    oos_total: number | null
    conflicts: number | null
  }
  decisions: { pending: number | null }
  execution: DeskExecution
  feeds: { fresh: number | null; total: number | null }
}

export interface LiveSnapshot {
  version: 1
  /** ISO-8601 with a timezone, or `null` when nothing has been ingested. */
  observed_at: string | null
  sequence: number | null
  summary: LiveSummary
  nodes: LiveNode[]
  links: LiveLink[]
  agents: LiveAgent[]
  markets: LiveMarkets
  events: LiveEvent[]
  desk: LiveDesk

  /* Serving fields, added by LiveStore.get(). */
  status: ServingStatus
  /** Age of the whole snapshot in seconds; `null` when there is no snapshot. */
  freshness_s: number | null
  served_at: string
  /** Absent on the empty snapshot. */
  received_at?: string
}

/** Stable identity for an edge. Links have no id of their own. */
export function linkId(link: Pick<LiveLink, 'source' | 'target'>): string {
  return `${link.source}->${link.target}`
}
