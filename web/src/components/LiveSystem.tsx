'use client'

import { useEffect, useRef, useState } from 'react'

/**
 * Live system pulse, fed by the same public projection the operator desk reads.
 *
 * Everything here is measured. There is no demo mode, no synthetic fallback and
 * no animation that runs when the feed is quiet — if telemetry stops, this
 * says so rather than looping a pretty idle state. A visualisation that keeps
 * dancing over a dead feed is the exact thing this project argues against.
 */

type Node = {
  id: string
  zone: string
  label: string
  status: 'healthy' | 'degraded' | 'down' | 'unknown'
  load_band?: string
  activity_band?: string
}

type Link = {
  source: string
  target: string
  status: string
  signal_class: string
  activity_band?: string
}

type Snapshot = {
  status: 'live' | 'stale' | 'warming' | 'offline'
  freshness_s: number | null
  summary: {
    active_agents: number
    activity_band?: string
    verified_today: number
    attention: number
  }
  nodes: Node[]
  links: Link[]
}

/* Layout is by semantic zone, left to right: what the public can reach, then
   what decides, then what computes, then what settles. */
const ZONE_POS: Record<string, { x: number; y: number }> = {
  edge: { x: 80, y: 190 },
  orchestration: { x: 265, y: 105 },
  compute: { x: 480, y: 70 },
  intelligence: { x: 480, y: 260 },
  markets: { x: 700, y: 135 },
  archive: { x: 700, y: 295 },
}

const STATUS_COLOR: Record<string, string> = {
  healthy: 'var(--color-verified)',
  degraded: 'var(--color-degraded)',
  down: 'var(--color-failed)',
  unknown: 'var(--color-ink-faint)',
}

const BAND_SPEED: Record<string, number> = {
  quiet: 0,
  light: 7,
  active: 4,
  busy: 2.2,
}

function curve(a: { x: number; y: number }, b: { x: number; y: number }) {
  const bend = Math.max(40, Math.abs(b.x - a.x) * 0.42)
  return `M ${a.x} ${a.y} C ${a.x + bend} ${a.y}, ${b.x - bend} ${b.y}, ${b.x} ${b.y}`
}

export default function LiveSystem() {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null)
  const [failed, setFailed] = useState(false)
  const timer = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    let cancelled = false

    async function poll() {
      try {
        const response = await fetch('/api/v1/live', { headers: { Accept: 'application/json' } })
        if (!response.ok) throw new Error(String(response.status))
        const data = (await response.json()) as Snapshot
        if (!cancelled) {
          setSnapshot(data)
          setFailed(false)
        }
      } catch {
        if (!cancelled) setFailed(true)
      }
    }

    poll()
    // 20s: the public projection is delayed anyway, so polling faster would add
    // load without adding information.
    timer.current = setInterval(poll, 20_000)

    return () => {
      cancelled = true
      if (timer.current) clearInterval(timer.current)
    }
  }, [])

  const status = failed ? 'offline' : (snapshot?.status ?? 'warming')
  const live = status === 'live'
  const nodes = snapshot?.nodes ?? []
  const byId = new Map(nodes.map((node) => [node.id, node]))

  const tone =
    status === 'live'
      ? 'text-verified'
      : status === 'offline'
        ? 'text-failed'
        : 'text-degraded'

  return (
    <div className="border border-line bg-raised/60">
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-line px-6 py-4">
        <div className="flex items-center gap-2.5">
          <span
            aria-hidden="true"
            className={`inline-block h-1.5 w-1.5 ${
              live ? 'bg-verified pulse-verified' : status === 'offline' ? 'bg-failed' : 'bg-degraded'
            }`}
          />
          <p className={`font-mono text-[11px] tracking-[0.14em] uppercase ${tone}`}>
            {failed ? 'feed unreachable' : status}
          </p>
        </div>
        <p className="font-mono text-[11px] text-ink-faint">
          {snapshot?.freshness_s != null
            ? `observed ${Math.round(snapshot.freshness_s)}s ago`
            : 'awaiting first snapshot'}
        </p>
      </div>

      {/* Summary counters — real values or an explicit dash, never a filler zero. */}
      <dl className="grid gap-px border-b border-line bg-line sm:grid-cols-4">
        {[
          { label: 'Active agents', value: snapshot?.summary.active_agents },
          { label: 'Activity', value: snapshot?.summary.activity_band },
          { label: 'Verified today', value: snapshot?.summary.verified_today },
          { label: 'Needs attention', value: snapshot?.summary.attention },
        ].map((cell) => (
          <div key={cell.label} className="bg-void px-5 py-4">
            <dt className="font-mono text-[10px] tracking-[0.14em] text-ink-faint uppercase">
              {cell.label}
            </dt>
            <dd className="tnum mt-2 font-display text-2xl leading-none font-semibold text-ink">
              {cell.value ?? '—'}
            </dd>
          </div>
        ))}
      </dl>

      {nodes.length === 0 ? (
        <div className="flex flex-col items-center gap-3 px-6 py-20 text-center">
          <span aria-hidden="true" className="h-9 w-9 border border-dashed border-line-lit" />
          <p className="font-display text-base font-semibold text-ink-dim">
            {failed ? 'Telemetry feed unreachable' : 'No signed snapshot yet'}
          </p>
          <p className="max-w-sm font-mono text-[11px] leading-relaxed text-ink-faint">
            Nothing is drawn until real telemetry arrives. This panel stays empty rather
            than animating a placeholder.
          </p>
        </div>
      ) : (
        <div className="px-4 py-5 md:px-6">
          <svg
            viewBox="0 0 790 370"
            className="block w-full overflow-visible"
            role="img"
            aria-label={`Live system topology: ${nodes.length} nodes, status ${status}`}
          >
            {(snapshot?.links ?? []).map((link, i) => {
              const from = byId.get(link.source)
              const to = byId.get(link.target)
              if (!from || !to) return null
              const a = ZONE_POS[from.zone]
              const b = ZONE_POS[to.zone]
              if (!a || !b) return null

              const band = link.activity_band ?? 'quiet'
              const speed = BAND_SPEED[band] ?? 0
              const width = { quiet: 1, light: 2, active: 3.5, busy: 5 }[band] ?? 1
              const path = curve(a, b)

              return (
                <g key={`${link.source}-${link.target}-${i}`}>
                  <path d={path} fill="none" stroke="var(--color-line)" strokeWidth={width + 3} />
                  <path
                    d={path}
                    fill="none"
                    strokeWidth={width}
                    strokeLinecap="round"
                    stroke={
                      link.status === 'down'
                        ? 'var(--color-failed)'
                        : link.status === 'degraded'
                          ? 'var(--color-degraded)'
                          : 'var(--color-sapphire)'
                    }
                    strokeDasharray={speed ? '8 16' : undefined}
                    opacity={speed ? 1 : 0.3}
                    className={speed ? 'flow' : undefined}
                    style={speed ? { animationDuration: `${speed}s` } : undefined}
                  />
                  <title>{`${from.label} → ${to.label}: ${band}`}</title>
                </g>
              )
            })}

            {nodes.map((node) => {
              const point = ZONE_POS[node.zone]
              if (!point) return null
              return (
                <g key={node.id} transform={`translate(${point.x} ${point.y})`}>
                  <circle
                    r="34"
                    fill="var(--color-raised)"
                    stroke="var(--color-line-lit)"
                    strokeWidth="1"
                  />
                  <circle r="6" fill={STATUS_COLOR[node.status] ?? STATUS_COLOR.unknown} />
                  <text
                    y="-15"
                    textAnchor="middle"
                    className="fill-ink-faint font-mono text-[8px] tracking-[0.14em] uppercase"
                  >
                    {node.zone}
                  </text>
                  <text
                    y="24"
                    textAnchor="middle"
                    className="fill-ink font-display text-[12px] font-semibold"
                  >
                    {node.label}
                  </text>
                  {node.activity_band && (
                    <text
                      y="40"
                      textAnchor="middle"
                      className="fill-ink-faint font-mono text-[8px]"
                    >
                      {node.activity_band}
                    </text>
                  )}
                </g>
              )
            })}
          </svg>

          <p className="mt-4 border-t border-line pt-4 font-mono text-[11px] text-ink-faint">
            Line weight and speed are measured event rates. A quiet link does not animate.
          </p>
        </div>
      )}
    </div>
  )
}
