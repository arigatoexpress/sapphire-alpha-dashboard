/**
 * Types for the payloads this desk actually fetches.
 *
 * The live-telemetry shape is **not** declared here. It is re-exported from
 * `@shared/telemetry`, which mirrors `backend/live_telemetry.py` and is pinned
 * by a test against a captured snapshot. A second hand-maintained copy is how
 * this file came to be reading `load_band`, `activity_band` and `latency_band`
 * months after the backend stopped serving any of them — three fields that
 * silently evaluated to `undefined` on every render. One contract, or it drifts
 * again.
 */

export type {
  AgentState,
  DecisionGate,
  DeskExecution,
  DeskLeader,
  DeskPosture,
  EventStatus,
  Execution,
  Health,
  LiveAgent,
  LiveEvent,
  LiveDesk,
  LiveLink,
  LiveMarkets,
  LiveNode,
  LiveSnapshot,
  LiveSummary,
  MarketStatus,
  NodeLoad,
  ProviderClass,
  ServingStatus,
  SignalClass,
  SummaryState,
  Verification,
  Zone,
} from '@shared/telemetry'

/* --- /api/v1/moss -------------------------------------------------------- */

/**
 * The MOSS wallet observation as this desk receives it.
 *
 * Capital is the one figure the site publishes as a band rather than a number.
 * That is a property of the page, not of a viewer: there is no sign-in here and
 * no view of this dashboard shows an exact balance, so exact-value fields are
 * deliberately not modelled. The band is the whole contract.
 */
export interface MossSnapshot {
  version: number
  status: import('@shared/telemetry').ServingStatus
  freshness_s: number | null
  served_at: string
  network?: string
  asset?: string
  /** Coarse funding band, e.g. `"four figures"`. Never an exact amount. */
  usdm_band?: string
  /** `"present"` / `"empty"` — enough gas to act, without saying how much. */
  eth_state?: string
  observation_freshness?: string
  custody?: string
  authority?: string
}

/* --- /api/fleet ---------------------------------------------------------- */

export interface FleetLease {
  agent: string
  repo: string
  purpose: string
  expires_at: string
}

export interface FleetGate {
  id: number
  title: string
  age_hours: number
  status: string
}

/** The detailed fleet snapshot, when the feed carries one. */
export interface FleetData {
  generated_at: string | null
  leases: FleetLease[]
  gates: FleetGate[]
  counts: { leases: number | null; gates_open: number | null }
  snapshot_age_s: number | null
}

/** The counts-only fleet feed: how many leases and open gates, and how old. */
export interface FleetCounts {
  leases: number | null
  gates_open: number | null
  snapshot_age_s: number | null
}
