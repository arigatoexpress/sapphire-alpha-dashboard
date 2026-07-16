export type GateState = 'killswitch' | 'armed' | 'disarmed'

export interface Gate {
  state: GateState
  label: string
  armed: boolean
  killswitch: boolean
  mode: string
  wallet_address: string | null
  cap_usd: number
  executor_alive: boolean
  updated_at: string
}

export interface Wallet {
  address: string | null
  deployed_usd: number
  n_open: number
  positions_count: number
  fills_count: number
  skin_in_game: boolean
  limits: Record<string, number>
  updated_at: string
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
  venue: string
  confidence: string
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
  endpoint: string
  last_ping: string
  pending_alerts: number
  recent_log: string[]
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

export interface WidgetData {
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
