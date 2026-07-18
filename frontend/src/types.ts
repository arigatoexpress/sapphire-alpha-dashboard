export type GateState = 'killswitch' | 'armed' | 'disarmed'

export interface Gate {
  state: GateState
  label: string
  armed: boolean
  killswitch: boolean
  mode: string
  // Operator-only fields — absent in the public read-only view.
  wallet_address?: string | null
  cap_usd?: number
  executor_alive: boolean
  updated_at: string
}

export interface Wallet {
  address: string | null
  n_open: number
  skin_in_game: boolean
  updated_at: string
  // Operator-only fields — absent in the public read-only view.
  deployed_usd?: number
  positions_count?: number
  fills_count?: number
  limits?: Record<string, number>
  // Public-view fields.
  funded?: boolean
  deployed_usd_approx?: number
}

export interface Proposal {
  id: string
  action: string
  instrument: string
  side: string
  confidence: string
  status: string
  timestamp: string
  wallet_address?: string | null
}

export interface TelegramQueue {
  pending: number
  gate: string
  status: string
  recent_count: number
  proposals: Proposal[]
}

export interface Signal {
  id: string
  instrument: string
  side: string
  // Operator-only fields — absent in the public read-only view.
  venue?: string
  confidence?: string
  timestamp: string
}

export interface Clip {
  id: string
  title: string
  source: string
  path: string
}

export interface TradingView {
  status: string
  last_ping: string
  pending_alerts: number
  // Operator-only fields — absent in the public read-only view.
  endpoint?: string
  recent_log?: string[]
}

export interface HealthService {
  name: string
  status: string
  http_status?: number
  detail?: string
}

export interface BusinessHealth {
  services: HealthService[]
  timestamp: string
  // Public-view aggregate counts.
  ok_count?: number
  total?: number
}

export interface SystemHealth {
  dashboard: string
  gate: GateState
  telegram: string
  tradingview: string
  timestamp: string
}

export interface TradingViewAlert {
  received_at: string
  alert: {
    symbol: string
    action: string
    price: number
    confidence: number | null
  }
  published: boolean
  channel: string
  signal_id: string
}

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

// Authenticated /api/fleet payload. Anonymous public read-only mode returns
// counts only: { public_view: true, leases: number, gates_open: number, snapshot_age_s }.
export interface FleetData {
  generated_at: string | null
  leases: FleetLease[]
  gates: FleetGate[]
  counts: { leases: number; gates_open: number }
  snapshot_age_s: number | null
}

export interface FleetCounts {
  public_view: true
  leases: number
  gates_open: number
  snapshot_age_s: number | null
}

export interface WidgetData {
  public_view?: boolean
  gate: Gate
  wallet: Wallet
  telegram_queue: TelegramQueue
  recent_signals: Signal[]
  defi_report: { clips: Clip[]; source: string; live: boolean }
  tradingview: TradingView
  business_health: BusinessHealth
  system_health: SystemHealth
  rendered_at: string
}

export type LiveStatus = 'live' | 'stale' | 'warming' | 'offline'
export type NodeHealth = 'healthy' | 'degraded' | 'down' | 'unknown'
export type ActivityBand = 'quiet' | 'light' | 'active' | 'busy'

export interface LiveNode {
  id: string
  zone: 'edge' | 'orchestration' | 'compute' | 'intelligence' | 'markets' | 'archive'
  label: string
  status: NodeHealth
  load_band: 'idle' | 'low' | 'medium' | 'high'
  activity_band?: ActivityBand
  activity_rate?: number
  freshness_band?: string
  freshness_s?: number
}

export interface LiveLink {
  source: string
  target: string
  status: NodeHealth
  signal_class: 'network' | 'agent' | 'market' | 'reliability' | 'archive'
  latency_band?: string
  latency_ms?: number | null
  activity_band?: ActivityBand
  event_rate?: number
}

export interface LiveAgent {
  role: string
  state: 'working' | 'verifying' | 'idle' | 'blocked' | 'offline'
  activity: string
  verification: 'verified' | 'pending' | 'failed' | 'not_applicable'
  provider_class: 'local GPU' | 'local CPU' | 'cloud reasoning' | 'hybrid' | 'unassigned'
}

export interface LiveEvent {
  id: string
  observed_at: string
  event_class: 'network' | 'agent' | 'market' | 'reliability' | 'archive'
  source: string
  target: string
  label: string
  status: 'observed' | 'verified' | 'pending' | 'degraded' | 'failed' | 'recovered'
}

export interface LiveSnapshot {
  version: number
  observed_at: string | null
  sequence: number | null
  status: LiveStatus
  freshness_s: number | null
  served_at: string
  public_view?: boolean
  public_policy?: string
  summary: {
    state: string
    active_agents: number
    activity_band?: ActivityBand
    events_per_min?: number
    verified_today: number
    attention: number
  }
  nodes: LiveNode[]
  links: LiveLink[]
  agents: LiveAgent[]
  markets: {
    network: string
    status: string
    feed_freshness?: string
    feed_age_s?: number | null
    activity_band?: ActivityBand
    events_per_min?: number
    paper_strategies: number
    decision_gate: string
    execution: string
  }
  events: LiveEvent[]
}
