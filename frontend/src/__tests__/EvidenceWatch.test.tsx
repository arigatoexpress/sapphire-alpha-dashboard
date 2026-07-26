import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { EvidenceWatch } from '../components/EvidenceWatch'
import type { PublicWidgets } from '../types'

const widgets: PublicWidgets = {
  gate: {
    state: 'disarmed',
    label: 'Disarmed',
    armed: false,
    killswitch: false,
    mode: 'telegram',
    executor_alive: false,
    updated_at: '2026-07-26T21:20:42.946276+00:00',
  },
  wallet: { disclosure: 'withheld' },
  telegram_queue: {
    pending: null,
    gate: 'telegram',
    status: 'not_observed',
    recent_count: null,
    proposals: [],
  },
  recent_signals: [
    {
      id: 'sig-001',
      instrument: 'BTC',
      side: 'watch',
      timestamp: '2026-07-26T20:52:00+00:00',
    },
  ],
  research: {
    clips: [
      {
        id: 'cycle-risk-repricing',
        title: 'Late-cycle risk is repricing faster than spot momentum',
        observed_at: '2026-07-26T20:40:00+00:00',
      },
      {
        id: 'liquidity-countercase',
        title: 'Liquidity remains the strongest countercase to defensive posture',
        observed_at: '2026-07-26T20:35:00+00:00',
      },
    ],
    live: true,
    policy: {
      research_role: 'evidence_not_authority',
      single_input_cap: 0.25,
      minimum_independent_checks: 2,
      can_set_conviction: false,
      can_authorize_execution: false,
    },
  },
  tradingview: {
    status: 'ok',
    last_ping: '2026-07-26T21:20:43.598888+00:00',
    pending_alerts: 0,
  },
  business_health: {
    services: [
      { name: 'gpu_gateway', status: 'unreachable' },
      { name: 'remote_gpu_gateway', status: 'not_configured' },
      { name: 'ops_server', status: 'ok' },
    ],
    ok_count: 1,
    total: 3,
    timestamp: '2026-07-26T21:20:43.613325+00:00',
  },
  system_health: {
    dashboard: 'ok',
    gate: 'disarmed',
    telegram: 'not_observed',
    tradingview: 'ok',
    timestamp: '2026-07-26T21:20:43.613612+00:00',
  },
  rendered_at: '2026-07-26T21:20:43.613618+00:00',
}

describe('evidence watch', () => {
  const markup = renderToStaticMarkup(<EvidenceWatch widgets={widgets} error="" />)

  it('shows the reviewed research and signal intake that the backend already publishes', () => {
    expect(markup).toContain('Evidence watch')
    expect(markup).toContain('Late-cycle risk is repricing faster than spot momentum')
    expect(markup).toContain('Liquidity remains the strongest countercase')
    expect(markup).toContain('BTC')
    expect(markup).toContain('watch')
  })

  it('makes the evidence limits visible beside the evidence', () => {
    expect(markup).toContain('2 independent checks')
    expect(markup).toContain('25% input cap')
    expect(markup).toContain('Cannot set conviction')
    expect(markup).toContain('Cannot authorize execution')
  })

  it('turns infrastructure labels into plain operator language', () => {
    expect(markup).toContain('System watch')
    expect(markup).toContain('Trading gate')
    expect(markup).toContain('Disarmed')
    expect(markup).toContain('Execution process')
    expect(markup).toContain('Stopped')
    expect(markup).toContain('Decision relay')
    expect(markup).toContain('Not observed')
    expect(markup).toContain('Signal intake')
    expect(markup).toContain('Current')
    expect(markup).toContain('Primary compute')
    expect(markup).toContain('Unavailable')
    expect(markup).not.toContain('gpu_gateway')
    expect(markup).not.toContain('remote_gpu_gateway')
    expect(markup).not.toContain('ops_server')
  })

  it('uses directional empty states instead of invented zeroes', () => {
    const empty = renderToStaticMarkup(
      <EvidenceWatch
        widgets={{
          ...widgets,
          recent_signals: [],
          research: { ...widgets.research, clips: [], live: false },
        }}
        error=""
      />,
    )

    expect(empty).toContain('No reviewed evidence has been published yet')
    expect(empty).toContain('No signal record is available')
    expect(empty).not.toContain('0 research')
    expect(empty).not.toContain('0 signals')
  })

  it('does not turn a missing policy response into an observed prohibition', () => {
    const absent = renderToStaticMarkup(<EvidenceWatch widgets={null} error="" />)

    expect(absent).toContain('not observed')
    expect(absent).not.toContain('Cannot set conviction')
    expect(absent).not.toContain('Cannot authorize execution')
  })
})
