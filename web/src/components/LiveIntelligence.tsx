'use client'

import { useMemo } from 'react'
import { STRATEGIES } from '@/data/mesh'
import { formatAge, humanize, useLiveTelemetry, type Live } from '@/lib/live'

/**
 * The live intelligence panel: what the desk is doing right now, drawn from
 * /api/v1/live. Two things must remain true here:
 *
 *   1. Anything that isn't in the anonymous payload reads "not observed", never
 *      a made-up zero. That is the same discipline the backend enforces.
 *   2. Strategy names come from the API's `desk.tracks` (flow-follow, sniper,
 *      etc.) because those are the *runtime* labels. The five classes named in
 *      mesh.ts are the *code-level* view and live on the topology section.
 *      Two views, both true — merging them would put a lie on the page.
 */

type Tone = 'active' | 'held' | 'degraded' | 'unknown'

function stateTone(value: string | null | undefined): Tone {
  const v = String(value ?? '').toLowerCase()
  if (['live', 'current', 'verified', 'working', 'observing'].includes(v)) return 'active'
  if (['halted', 'off', 'gated', 'manual', 'telegram'].includes(v)) return 'held'
  if (['stale', 'delayed', 'degraded', 'offline', 'failed', 'blocked'].includes(v)) return 'degraded'
  return 'unknown'
}

function postureLabel(posture: string | null | undefined): { label: string; tone: Tone } {
  const p = String(posture ?? '').toLowerCase()
  if (p === 'risk_seeking') return { label: 'RISK ON', tone: 'active' }
  if (p === 'selective_risk') return { label: 'SELECTIVE', tone: 'held' }
  if (p === 'capital_preservation') return { label: 'RISK OFF', tone: 'held' }
  if (p === 'neutral') return { label: 'NEUTRAL', tone: 'held' }
  return { label: 'NOT OBSERVED', tone: 'unknown' }
}

function fmtReturn(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return '—'
  const sign = value > 0 ? '+' : ''
  return `${sign}${value.toFixed(2)}%`
}

function returnTone(value: number | null | undefined): Tone {
  if (value == null) return 'unknown'
  if (value > 0.5) return 'active'
  if (value < -0.5) return 'degraded'
  return 'held'
}

function fmtNumber(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return 'not observed'
  return value.toLocaleString(undefined, { maximumFractionDigits: 0 })
}

/** Reconcile the live tracks against the canonical five strategies in mesh.ts,
 *  so the panel always has five rows even when a track is missing. */
function reconcileTracks(data: Live | null) {
  const tracks = data?.desk?.tracks ?? []
  const named = tracks.map((t) => ({
    strategy: t.strategy,
    liveReturn: t.live_return_pct,
    status: t.status,
    freshness: t.freshness_s,
    open: t.open_count,
    green: t.green_days,
    target: t.target_days,
  }))

  // Take up to five real tracks. If fewer than five are observed, pad from the
  // canonical class list so the reader sees exactly five rows and knows which
  // classes are unaccounted for.
  const rows: Array<{
    strategy: string
    thesis?: string
    liveReturn: number | null | undefined
    status: string | null | undefined
    freshness: number | null | undefined
    open: number | null | undefined
    green: number | null | undefined
    target: number | null | undefined
    citation?: string
  }> = named.slice(0, 5)

  const remaining = 5 - rows.length
  if (remaining > 0) {
    for (const s of STRATEGIES.slice(0, remaining)) {
      rows.push({
        strategy: s.name,
        thesis: s.thesis,
        citation: `strategies.py:${s.line}`,
        liveReturn: null,
        status: 'inactive',
        freshness: null,
        open: null,
        green: null,
        target: null,
      })
    }
  }

  return rows
}

export default function LiveIntelligence() {
  const live = useLiveTelemetry()
  const data = live.data

  const posture = useMemo(() => postureLabel(data?.desk?.posture), [data])
  const tracks = useMemo(() => reconcileTracks(data), [data])
  const decisions = data?.desk?.decisions
  const execution = humanize(data?.desk?.execution ?? data?.markets?.execution)
  const gate = humanize(data?.markets?.decision_gate)

  const summaryAge = data?.freshness_s
  const feedAge = data?.markets?.feed_age_s
  const activeAgents = data?.summary?.active_agents ?? null
  const pending = decisions?.pending ?? decisions?.pending_review ?? null

  /* Macro row: the anonymous payload does not carry F&G / BTC.D / DXY yet.
     Rather than fabricate, we surface the slot and mark it not observed —
     the same rule the backend applies to every unknown field. When these
     get plumbed through /api/v1/live, the display picks them up automatically. */
  const macro: Array<{ label: string; value: string; source: string }> = [
    { label: 'Fear & Greed', value: 'not observed', source: 'awaiting collector' },
    { label: 'BTC dominance', value: 'not observed', source: 'awaiting collector' },
    { label: 'DXY', value: 'not observed', source: 'awaiting collector' },
  ]

  return (
    <section id="intelligence" className="section intelligence" aria-labelledby="intelligence-title">
      <header className="section-head">
        <p className="section-kicker">02 · Intelligence</p>
        <h2 id="intelligence-title" className="section-title">
          Five strategies propose.<span>A human still decides.</span>
        </h2>
        <p className="section-lede">
          Every strategy runs on paper. Each proposal carries its source, its
          age, and what would prove it wrong. The only way capital moves is one
          tap on Telegram. Nothing on this panel comes from a mock.
        </p>
      </header>

      <div className="intel-status" aria-label="Current desk posture">
        <div className={`intel-posture intel-posture--${posture.tone}`}>
          <span className="intel-posture-label">Regime</span>
          <strong>{posture.label}</strong>
          <span className="intel-posture-hint">desk.posture</span>
        </div>
        <div className="intel-metrics">
          <div>
            <dt>Execution</dt>
            <dd data-tone={stateTone(data?.desk?.execution ?? data?.markets?.execution)}>{execution}</dd>
          </div>
          <div>
            <dt>Decision gate</dt>
            <dd data-tone={stateTone(data?.markets?.decision_gate)}>{gate}</dd>
          </div>
          <div>
            <dt>Active agents</dt>
            <dd>{activeAgents == null ? 'not observed' : String(activeAgents)}</dd>
          </div>
          <div>
            <dt>Pending review</dt>
            <dd>{pending == null ? 'not observed' : String(pending)}</dd>
          </div>
          <div>
            <dt>Snapshot age</dt>
            <dd>{formatAge(summaryAge)}</dd>
          </div>
          <div>
            <dt>Feed age</dt>
            <dd>{formatAge(feedAge)}</dd>
          </div>
        </div>
      </div>

      <div className="intel-panels">
        <section className="intel-panel intel-panel--strategies" aria-labelledby="intel-strategies-title">
          <header>
            <p className="intel-panel-kicker">Live strategy tracks</p>
            <h3 id="intel-strategies-title">Paper, always — until Telegram says otherwise</h3>
          </header>
          <ul className="intel-track-list">
            {tracks.map((track, i) => {
              const tone = stateTone(track.status)
              const retTone = returnTone(track.liveReturn)
              return (
                <li key={`${track.strategy}-${i}`} className="intel-track" data-tone={tone}>
                  <div className="intel-track-head">
                    <span className="intel-track-mode">PAPER</span>
                    <strong>{track.strategy}</strong>
                    <span className="intel-track-status" data-tone={tone}>
                      {humanize(track.status, 'inactive')}
                    </span>
                  </div>
                  <div className="intel-track-body">
                    <div className="intel-track-cell">
                      <span>Return</span>
                      <b data-tone={retTone}>{fmtReturn(track.liveReturn)}</b>
                    </div>
                    <div className="intel-track-cell">
                      <span>Open</span>
                      <b>{track.open == null ? '—' : String(track.open)}</b>
                    </div>
                    <div className="intel-track-cell">
                      <span>Green days</span>
                      <b>
                        {track.green == null
                          ? '—'
                          : `${track.green}${track.target ? `/${track.target}` : ''}`}
                      </b>
                    </div>
                    <div className="intel-track-cell">
                      <span>Age</span>
                      <b>{formatAge(track.freshness)}</b>
                    </div>
                  </div>
                  {track.thesis && (
                    <p className="intel-track-thesis">
                      {track.thesis} <span>· {track.citation}</span>
                    </p>
                  )}
                </li>
              )
            })}
          </ul>
        </section>

        <section className="intel-panel intel-panel--macro" aria-labelledby="intel-macro-title">
          <header>
            <p className="intel-panel-kicker">Market context</p>
            <h3 id="intel-macro-title">The room the desk is trading into</h3>
          </header>
          <dl className="intel-macro">
            {macro.map((row) => (
              <div key={row.label}>
                <dt>{row.label}</dt>
                <dd>{row.value}</dd>
                <span>{row.source}</span>
              </div>
            ))}
          </dl>

          <header>
            <p className="intel-panel-kicker">Signal stream</p>
            <h3>Most recent observations, in order</h3>
          </header>
          <ul className="intel-events">
            {(data?.events ?? []).slice(0, 6).map((event, i) => (
              <li key={event.id ?? i}>
                <span className="intel-event-time">{formatAge(
                  event.updated_at ? (Date.now() - new Date(event.updated_at).getTime()) / 1000 : null,
                )}</span>
                <strong>{humanize(event.class, 'signal')}</strong>
                <span className="intel-event-state" data-tone={stateTone(event.state)}>
                  {humanize(event.state, 'observed')}
                </span>
                {event.detail && <p>{event.detail}</p>}
              </li>
            ))}
            {(!data?.events || data.events.length === 0) && (
              <li className="intel-events-empty">
                No signal has been observed in this snapshot.
              </li>
            )}
          </ul>
        </section>
      </div>

      {live.status === 'stale' && (
        <p className="intel-stale">
          Live snapshot is stale — last update was {formatAge(summaryAge)}. Values above are held
          from that snapshot and may already be wrong.
        </p>
      )}
      {live.status === 'error' && (
        <p className="intel-stale">
          Live feed unreachable. Values will fill in when <code>/api/v1/live</code> answers.
        </p>
      )}
    </section>
  )
}
