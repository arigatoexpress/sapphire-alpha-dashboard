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
    <section className="loom-panel" aria-labelledby="loom-title">
      <div className="section-heading loom-heading">
        <div>
          <p className="eyebrow">Live architecture</p>
          <h2 id="loom-title">Signal Loom</h2>
        </div>
        <p className="section-note">Motion is measured. Quiet systems stay quiet.</p>
      </div>
      {nodes.length === 0 ? (
        <div className="loom-empty">
          <span className="empty-orbit" aria-hidden="true" />
          <strong>{status === 'warming' ? 'Building the delayed public view' : 'Home telemetry not observed'}</strong>
          <span>The display will animate only after a signed snapshot arrives.</span>
        </div>
      ) : (
        <div className="loom-wrap">
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
          <div className="loom-legend" aria-label="Signal classes">
            <span><i className="legend-network" /> network</span>
            <span><i className="legend-agent" /> intelligence</span>
            <span><i className="legend-market" /> markets</span>
            <span><i className="legend-archive" /> archive</span>
          </div>
        </div>
      )}
    </section>
  )
}
