'use client'

import { useMemo } from 'react'
import { MESH, MESH_LINKS, type MeshNode } from '@/data/mesh'
import { formatAge, formatObservedAt, humanize, useLiveTelemetry } from '@/lib/live'

/**
 * Animated topology of the compute mesh. Four nodes (Mac hub, Windows GPU,
 * two Raspberry Pi sentinels), all reachable over Tailscale, drawn as inline
 * SVG. Motion is CSS keyframes on stroke-dashoffset — no library, and the
 * `prefers-reduced-motion` block in globals.css turns every animation off.
 *
 * Live status per node comes from /api/v1/live. The mapping is deliberately
 * modest: the anonymous payload does not know the shape of the private compute
 * fleet, so we surface the summary counters ("active_agents", "attention") and
 * whether any track under each node is stale, rather than fabricate per-machine
 * health signals we cannot observe.
 */

const VIEW = { w: 1200, h: 720 }
const NODE_RX = 78
const NODE_RY = 46

type Tone = 'active' | 'processing' | 'idle' | 'alert' | 'unknown'

const NODE_INTENT: Record<MeshNode['id'], string> = {
  mac: 'Orchestration · human-approval rail',
  win: 'Inference · execution under caps',
  pi1: 'Edge observation · always-on collector',
  pi2: 'Redundant collector · event-bus shadow',
}

function nodeCentre(id: MeshNode['id']) {
  const n = MESH.find((m) => m.id === id)!
  return {
    x: (n.x / 100) * (VIEW.w - 120) + 60,
    y: (n.y / 100) * (VIEW.h - 160) + 60,
  }
}

function ToneRing({ x, y, tone, index }: { x: number; y: number; tone: Tone; index: number }) {
  return (
    <>
      <ellipse
        cx={x}
        cy={y}
        rx={NODE_RX + 12}
        ry={NODE_RY + 12}
        className={`topology-node-ring topology-node-ring--${tone}`}
        style={{ animationDelay: `${-index * 0.35}s` }}
      />
      <circle
        cx={x + NODE_RX - 12}
        cy={y - NODE_RY + 14}
        r={4.5}
        className={`topology-node-dot topology-node-dot--${tone}`}
      />
    </>
  )
}

function LinkFlow({
  a,
  b,
  index,
  intensity,
}: {
  a: MeshNode['id']
  b: MeshNode['id']
  index: number
  intensity: 'idle' | 'light' | 'heavy'
}) {
  const pa = nodeCentre(a)
  const pb = nodeCentre(b)
  const particleCount = intensity === 'heavy' ? 3 : intensity === 'light' ? 2 : 1
  const period = intensity === 'heavy' ? 3.2 : intensity === 'light' ? 4.4 : 6

  return (
    <g className={`topology-link topology-link--${intensity}`}>
      <line x1={pa.x} y1={pa.y} x2={pb.x} y2={pb.y} className="topology-link-base" />
      {Array.from({ length: particleCount }).map((_, i) => (
        <line
          key={i}
          x1={pa.x}
          y1={pa.y}
          x2={pb.x}
          y2={pb.y}
          className="topology-link-flow"
          style={{
            animationDuration: `${period}s`,
            animationDelay: `${-((i / particleCount) * period + index * 0.4)}s`,
          }}
        />
      ))}
    </g>
  )
}

function deriveTones(state: ReturnType<typeof useLiveTelemetry>) {
  const data = state.data
  const activeAgents = data?.summary?.active_agents ?? 0
  const attention = data?.summary?.attention ?? 0

  // Every node opens as "unknown" until a real observation lands.
  const tones: Record<MeshNode['id'], Tone> = {
    mac: 'unknown',
    win: 'unknown',
    pi1: 'unknown',
    pi2: 'unknown',
  }

  if (state.status === 'error') return tones

  if (data) {
    // Working agents currently observed. Anything > 0 flips the two collectors
    // to "active" because that is where their `local CPU` agents run.
    const anyWorking = (data.agents ?? []).some((a) => a.state === 'working')
    const anyVerifying = (data.agents ?? []).some((a) => a.state === 'verifying')
    const anyBlocked = (data.agents ?? []).some((a) => a.state === 'blocked' || a.state === 'failed')

    // Mac is the commander — active whenever the snapshot itself is fresh.
    const fresh = (data.freshness_s ?? Infinity) < 180
    tones.mac = fresh ? 'active' : 'idle'

    // Windows GPU — flip to processing on any verifying agent, active on working,
    // idle otherwise. Alert if any track under it is failed/blocked.
    const executionHalted = data.desk?.execution === 'halted'
    tones.win = anyBlocked
      ? 'alert'
      : anyVerifying
      ? 'processing'
      : anyWorking && !executionHalted
      ? 'active'
      : 'idle'

    // Pis: active whenever collectors report working. Attention > 0 lifts pi1 to
    // "processing" so the operator sees something is under review.
    tones.pi1 = anyWorking ? (attention > 0 ? 'processing' : 'active') : 'idle'
    tones.pi2 = anyWorking ? 'active' : 'idle'
  }

  if (state.status === 'stale') {
    for (const id of Object.keys(tones) as MeshNode['id'][]) {
      if (tones[id] === 'active') tones[id] = 'idle'
    }
  }

  return { tones, activeAgents, attention }
}

export default function SystemTopology() {
  const live = useLiveTelemetry()
  const derived = useMemo(() => deriveTones(live), [live])
  const tones = 'tones' in derived ? derived.tones : derived

  const linkIntensity = useMemo<'idle' | 'light' | 'heavy'>(() => {
    if (live.status !== 'ok' && live.status !== 'stale') return 'idle'
    const events = live.data?.markets?.events_per_min ?? 0
    if (events > 200) return 'heavy'
    if (events > 10) return 'light'
    return 'idle'
  }, [live])

  const observedLabel =
    live.status === 'loading'
      ? 'awaiting first snapshot'
      : live.status === 'error'
      ? 'unavailable'
      : formatObservedAt(live.data?.observed_at)

  const ageLabel = live.data?.freshness_s != null ? formatAge(live.data.freshness_s) : 'not observed'
  const eventsLabel =
    live.data?.markets?.events_per_min != null
      ? `${Math.round(live.data.markets.events_per_min)} evt/min`
      : 'not observed'

  return (
    <section id="system" className="section topology" aria-labelledby="system-title">
      <header className="section-head">
        <p className="section-kicker">01 · System</p>
        <h2 id="system-title" className="section-title">
          Four machines watch.<span>All the time.</span>
        </h2>
        <p className="section-lede">
          A private mesh of small computers. Every node reaches every other node
          over Tailscale — no single machine holds all the truth. The green ring
          is a live status pulse; the moving particles are network activity, and
          they slow down when the market feed slows down.
        </p>
      </header>

      <div className="topology-canvas">
        <svg
          viewBox={`0 0 ${VIEW.w} ${VIEW.h}`}
          role="img"
          aria-labelledby="topology-title topology-desc"
          className="topology-svg"
          preserveAspectRatio="xMidYMid meet"
        >
          <title id="topology-title">Live topology of the Sapphire compute mesh</title>
          <desc id="topology-desc">
            Four machines — a Mac orchestrator, a Windows GPU executor, and two
            Raspberry Pi edge sensors — connected in a full mesh over Tailscale.
            Rings pulse when a node is active; particles flow between nodes at
            the current market event rate.
          </desc>

          <defs>
            <radialGradient id="topology-halo" cx="0.5" cy="0.5" r="0.5">
              <stop offset="0%" stopColor="var(--color-sapphire)" stopOpacity="0.18" />
              <stop offset="100%" stopColor="var(--color-sapphire)" stopOpacity="0" />
            </radialGradient>
          </defs>

          {MESH_LINKS.map(([a, b], i) => (
            <LinkFlow key={`${a}-${b}`} a={a} b={b} index={i} intensity={linkIntensity} />
          ))}

          {MESH.map((n, i) => {
            const p = nodeCentre(n.id)
            const tone = tones[n.id]
            return (
              <g key={n.id} className="topology-node" style={{ animationDelay: `${i * 90}ms` }}>
                <ellipse
                  cx={p.x}
                  cy={p.y}
                  rx={NODE_RX + 26}
                  ry={NODE_RY + 26}
                  fill="url(#topology-halo)"
                  opacity={tone === 'active' || tone === 'processing' ? 0.9 : 0.35}
                />
                <ToneRing x={p.x} y={p.y} tone={tone} index={i} />
                <rect
                  x={p.x - NODE_RX}
                  y={p.y - NODE_RY}
                  width={NODE_RX * 2}
                  height={NODE_RY * 2}
                  className={`topology-node-box topology-node-box--${tone}`}
                />
                <text x={p.x} y={p.y - NODE_RY + 22} className="topology-node-role">
                  {n.role.toUpperCase()}
                </text>
                <text x={p.x} y={p.y - 4} className="topology-node-host">
                  {n.hostname}
                </text>
                <text x={p.x} y={p.y + 16} className="topology-node-hw">
                  {n.hardware}
                </text>
                <text x={p.x} y={p.y + NODE_RY - 12} className="topology-node-intent">
                  {NODE_INTENT[n.id]}
                </text>
              </g>
            )
          })}
        </svg>
      </div>

      <div className="topology-legend">
        <div className="topology-legend-row">
          <span className="topology-legend-key">
            <span className="topology-legend-dot topology-legend-dot--active" /> Active
          </span>
          <span className="topology-legend-key">
            <span className="topology-legend-dot topology-legend-dot--processing" /> Processing
          </span>
          <span className="topology-legend-key">
            <span className="topology-legend-dot topology-legend-dot--idle" /> Idle
          </span>
          <span className="topology-legend-key">
            <span className="topology-legend-dot topology-legend-dot--alert" /> Alert
          </span>
        </div>
        <dl className="topology-legend-meta">
          <div>
            <dt>Snapshot</dt>
            <dd>{observedLabel}</dd>
          </div>
          <div>
            <dt>Freshness</dt>
            <dd>{ageLabel}</dd>
          </div>
          <div>
            <dt>Market feed</dt>
            <dd>{eventsLabel}</dd>
          </div>
          <div>
            <dt>State</dt>
            <dd>{humanize(live.data?.summary?.state ?? live.data?.status)}</dd>
          </div>
        </dl>
        <p className="topology-legend-source">
          Source: <code>/api/v1/live</code> · authority: none · unknown stays unknown.
        </p>
      </div>
    </section>
  )
}
