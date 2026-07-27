import { describe, expect, it } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import { DecisionCockpit } from '../components/DecisionCockpit'
import type { LiveDesk } from '../types'

const desk: LiveDesk = {
  version: 1,
  updated_at: '2026-07-27T12:00:00Z',
  execution: 'gated',
  posture: 'neutral',
  leader: 'none',
  decisions: {
    pending: 1,
    pending_review: 1,
    pending_policy_blocked: 0,
    approved_awaiting_execution: 0,
    eligible_execution: 0,
    blocked: 0,
  },
  feeds: { fresh: 4, total: 4 },
  tracks: [
    // stale paper junk must never surface
    {
      strategy: 'sniper',
      status: 'stale',
      live_return_pct: 177.74,
      green_days: 0,
      target_days: 14,
      open_count: 0,
      data_flags: 1,
      freshness_s: 23000,
    },
  ],
  risk: {
    ledger_state: 'reconciled',
    new_risk: 'available',
    realized_drawdown_pct: 2.5,
    drawdown_limit_pct: 10,
    budget_remaining_pct: 7.5,
  },
  experiment: {
    status: 'collecting',
    qualified_days: 0,
    required_days: 14,
    collector: 'stale',
    last_committed_date: null,
  },
  validation: {
    oos_pass: 0,
    oos_total: 3,
    conflicts: 2,
    conflict_details: [
      {
        strategy: 'sniper',
        live_return_pct: 177.74,
        replay_return_pct: 1.2,
        gap_pp: 176.5,
      },
    ],
    replay_span_hours: 48,
    replay_data_through: '2026-07-01',
  },
}

const markup = renderToStaticMarkup(<DecisionCockpit desk={desk} />)

describe('DecisionCockpit live rails', () => {
  it('shows real plant language, not paper backtests', () => {
    expect(markup).toContain('LIVE RAILS')
    expect(markup).toContain('What the plant is doing')
    expect(markup).toContain('Robinhood Agentic')
    expect(markup).toContain('MegaETH')
    expect(markup).toContain('No paper tracks')
  })

  it('never renders paper strategy scoreboards', () => {
    expect(markup).not.toContain('Paper strategy evidence')
    expect(markup).not.toContain('sniper')
    expect(markup).not.toContain('177')
    expect(markup).not.toContain('reporting tracks')
    expect(markup).not.toContain('Live / replay audit')
    expect(markup).not.toContain('Sealed trial')
    expect(markup).not.toContain('strategy-ledger')
  })

  it('keeps decision queue and loss runway', () => {
    expect(markup).toContain('Awaiting review')
    expect(markup).toContain('Loss allowance')
    expect(markup).toContain('Single event P')
  })
})
