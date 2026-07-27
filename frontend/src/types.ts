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
  LiveEvent,
  LiveSnapshot,
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

/* --- /api/v1/widgets ----------------------------------------------------- */

export interface PublicResearchClip {
  id: string
  title: string
  observed_at: string
}

export interface PublicSignal {
  id: string
  instrument: string
  side: string
  timestamp: string
}

export interface PublicServiceHealth {
  name: string
  status: string
}

/**
 * The anonymous widget projection. This is intentionally the public shape:
 * identities, exact balances, proposal bodies, infrastructure addresses, and
 * research attribution are not modelled because the endpoint does not expose
 * them.
 */
export interface PublicWidgets {
  gate: {
    state: string
    label: string
    armed: boolean
    killswitch: boolean
    mode: string
    executor_alive: boolean
    updated_at: string
  }
  wallet: { disclosure: string }
  telegram_queue: {
    pending: number | null
    gate: string
    status: string
    recent_count: number | null
    proposals: []
  }
  recent_signals: PublicSignal[]
  research: {
    clips: PublicResearchClip[]
    live: boolean
    policy: {
      research_role: string
      single_input_cap: number
      minimum_independent_checks: number
      can_set_conviction: boolean
      can_authorize_execution: boolean
    }
  }
  tradingview: {
    status: string
    last_ping: string
    pending_alerts: number | null
  }
  business_health: {
    services: PublicServiceHealth[]
    ok_count: number
    total: number
    timestamp: string
  }
  system_health: {
    dashboard: string
    gate: string
    telegram: string
    tradingview: string
    timestamp: string
  }
  rendered_at: string
}
