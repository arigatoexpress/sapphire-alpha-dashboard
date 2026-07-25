import type { CSSProperties } from 'react'
import type { ActivityBand, LiveLink, LiveNode } from '../types'

const POSITIONS: Record<LiveNode['zone'], { x: number; y: number }> = {
  edge: { x: 85, y: 220 },
  orchestration: { x: 270, y: 125 },
  compute: { x: 495, y: 84 },
  intelligence: { x: 495, y: 300 },
  markets: { x: 725, y: 155 },
  archive: { x: 725, y: 340 },
}

const BAND: Record<ActivityBand, { width: number; duration: number }> = {
  quiet: { width: 1, duration: 0 },
  light: { width: 2, duration: 7 },
  active: { width: 3.5, duration: 4 },
  busy: { width: 5, duration: 2.2 },
}

/* Kept in sync with the `.signal-*` rules in index.css. Held close to sapphire
   so the loom reads as one instrument rather than a category chart. */
const LEGEND = [
  { label: 'network', color: '#4aa8d8' },
  { label: 'intelligence', color: '#3d78ff' },
  { label: 'markets', color: '#7c8cf0' },
  { label: 'archive', color: '#6f59a9' },
]

function activity(link: LiveLink): ActivityBand {
  if (link.activity_band) return link.activity_band
  const rate = link.event_rate ?? 0
  return rate <= 0 ? 'quiet' : rate < 10 ? 'light' : rate < 60 ? 'active' : 'busy'
}

function curve(source: { x: number; y: number }, target: { x: number; y: number }) {
  const bend = Math.max(42, Math.abs(target.x - source.x) * 0.42)
  return `M ${source.x} ${source.y} C ${source.x + bend} ${source.y}, ${target.x - bend} ${target.y}, ${target.x} ${target.y}`
}

export function SignalLoom({ nodes, links, status }: { nodes: LiveNode[]; links: LiveLink[]; status: string }) {
  const byId = new Map(nodes.map((node) => [node.id, node]))

  return (
    <section
      className="border border-line bg-raised/60"
      aria-labelledby="loom-title"
    >
      <div className="flex flex-wrap items-start justify-between gap-4 border-b border-line px-6 py-5">
        <div>
          <p className="font-mono text-[11px] tracking-[0.2em] text-sapphire uppercase">
            Live architecture
          </p>
          <h2
            id="loom-title"
            className="mt-2 font-display text-xl font-semibold tracking-[-0.015em] text-ink"
          >
            Signal Loom
          </h2>
        </div>
        <p className="font-mono text-[11px] text-ink-faint">
          Motion is measured. Quiet systems stay quiet.
        </p>
      </div>
      {nodes.length === 0 ? (
        <div className="flex flex-col items-center gap-3 px-6 py-24 text-center">
          <span
            aria-hidden="true"
            className="h-10 w-10 border border-dashed border-line-lit"
          />
          <strong className="font-display text-base font-semibold text-ink-dim">
            {status === 'warming'
              ? 'Building the delayed public view'
              : 'Home telemetry not observed'}
          </strong>
          <span className="font-mono text-[11px] text-ink-faint">
            The display will animate only after a signed snapshot arrives.
          </span>
        </div>
      ) : (
        <div className="px-6 py-5">
          <svg className="loom" viewBox="0 0 820 430" role="img" aria-label="Live semantic topology and measured signal flows">
            <defs>
              <marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
                <path d="M 0 0 L 10 5 L 0 10 z" />
              </marker>
            </defs>
            {links.map((link, index) => {
              const fromNode = byId.get(link.source)
              const toNode = byId.get(link.target)
              if (!fromNode || !toNode) return null
              const from = POSITIONS[fromNode.zone]
              const to = POSITIONS[toNode.zone]
              const band = activity(link)
              const profile = BAND[band]
              const style = { '--flow-duration': `${profile.duration}s`, '--flow-width': profile.width } as CSSProperties
              return (
                <g key={`${link.source}-${link.target}-${index}`} className={`loom-link signal-${link.signal_class} status-${link.status} band-${band}`} style={style}>
                  <path className="link-bed" d={curve(from, to)} />
                  <path className="link-current" d={curve(from, to)} markerEnd="url(#arrow)" />
                  <title>{`${fromNode.label} to ${toNode.label}: ${band}, ${link.latency_band ?? (link.latency_ms == null ? 'latency not observed' : `${link.latency_ms} ms`)}`}</title>
                </g>
              )
            })}
            {nodes.map((node) => {
              const point = POSITIONS[node.zone]
              return (
                <g key={node.id} className={`loom-node status-${node.status}`} transform={`translate(${point.x} ${point.y})`}>
                  <circle className="node-halo" r="38" />
                  <circle className="node-core" r="7" />
                  <text className="node-zone" y="-17" textAnchor="middle">{node.zone}</text>
                  <text className="node-label" y="25" textAnchor="middle">{node.label}</text>
                  <text className="node-meta" y="43" textAnchor="middle">{node.load_band} · {node.activity_band ?? `${Math.round(node.activity_rate ?? 0)}/m`}</text>
                </g>
              )
            })}
          </svg>
          <div
            className="mt-4 flex flex-wrap justify-center gap-6 border-t border-line pt-4 font-mono text-[11px] tracking-[0.1em] text-ink-faint uppercase"
            aria-label="Signal classes"
          >
            {LEGEND.map((entry) => (
              <span key={entry.label} className="inline-flex items-center gap-2">
                <i
                  aria-hidden="true"
                  className="inline-block h-1.5 w-1.5"
                  style={{ background: entry.color }}
                />
                {entry.label}
              </span>
            ))}
          </div>
        </div>
      )}
    </section>
  )
}
