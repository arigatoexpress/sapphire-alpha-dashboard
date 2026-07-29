import { MESH, MESH_LINKS, PIPELINE, RH_CHAIN, STRATEGIES } from '@/data/mesh'

/**
 * A single-glance diagram of the Sapphire compute mesh, the agents that watch
 * markets on top of it, and the four-stage pipeline that separates evidence
 * from execution. Pure server-renderable JSX — no `useEffect`, no `window`.
 * Motion is CSS keyframes on `stroke-dashoffset`, so the reduced-motion query
 * in globals.css disables it cleanly.
 *
 * Two variants:
 *   `full`    — used by `/architecture/`. Shows the diagram, the node cards,
 *               the strategy list, and the chain block.
 *   `compact` — used by the homepage. Just the diagram and one plain-English
 *               caption; deeper reading lives on `/architecture/`.
 */

type Variant = 'full' | 'compact'

// SVG geometry. All positions are in a 1400×720 viewBox so the same numbers
// mean the same thing whether the container is 640px wide on a phone or the
// site's 1280px cap on a desktop.
const VIEW = { w: 1400, h: 720 }
const ZONE = {
  mesh: { x: 40, y: 60, w: 420, h: 600 },
  agents: { x: 520, y: 60, w: 380, h: 600 },
  pipeline: { x: 960, y: 60, w: 400, h: 600 },
} as const

function nodeCentre(id: (typeof MESH)[number]['id']) {
  const n = MESH.find((m) => m.id === id)!
  return {
    x: ZONE.mesh.x + (n.x / 100) * ZONE.mesh.w,
    y: ZONE.mesh.y + (n.y / 100) * ZONE.mesh.h,
  }
}

function ZoneLabel({
  x,
  y,
  index,
  title,
  sub,
}: {
  x: number
  y: number
  index: string
  title: string
  sub: string
}) {
  return (
    <g className="mesh-zone-label">
      <text x={x} y={y} className="mesh-zone-index">
        {index}
      </text>
      <text x={x} y={y + 22} className="mesh-zone-title">
        {title}
      </text>
      <text x={x} y={y + 44} className="mesh-zone-sub">
        {sub}
      </text>
    </g>
  )
}

function MeshZone() {
  const cx = ZONE.mesh.x + ZONE.mesh.w / 2
  return (
    <g aria-label="Compute mesh">
      <ZoneLabel
        x={ZONE.mesh.x}
        y={ZONE.mesh.y - 14}
        index="01 · MESH"
        title="Four machines that watch"
        sub="Fully connected over Tailscale. Every node can reach every node."
      />

      {MESH_LINKS.map(([a, b], i) => {
        const pa = nodeCentre(a)
        const pb = nodeCentre(b)
        return (
          <g key={`${a}-${b}`}>
            <line
              x1={pa.x}
              y1={pa.y}
              x2={pb.x}
              y2={pb.y}
              className="mesh-link"
            />
            <line
              x1={pa.x}
              y1={pa.y}
              x2={pb.x}
              y2={pb.y}
              className="mesh-link-flow"
              style={{ animationDelay: `${i * -0.6}s` }}
            />
          </g>
        )
      })}

      {MESH.map((n, i) => {
        const p = nodeCentre(n.id)
        const isCore = n.id === 'mac' || n.id === 'win'
        const rx = isCore ? 74 : 60
        const ry = isCore ? 40 : 34
        return (
          <g
            key={n.id}
            className="mesh-node"
            style={{ animationDelay: `${180 + i * 90}ms` }}
          >
            <rect
              x={p.x - rx}
              y={p.y - ry}
              width={rx * 2}
              height={ry * 2}
              className={`mesh-node-box ${isCore ? 'is-core' : 'is-edge'}`}
            />
            <text x={p.x} y={p.y - 8} className="mesh-node-role">
              {n.role.toUpperCase()}
            </text>
            <text x={p.x} y={p.y + 12} className="mesh-node-host">
              {n.hostname}
            </text>
            <text x={p.x} y={p.y + 28} className="mesh-node-hw">
              {n.hardware}
            </text>
            <circle
              cx={p.x + rx - 10}
              cy={p.y - ry + 10}
              r={3.5}
              className="mesh-node-dot"
              style={{ animationDelay: `${i * 300}ms` }}
            />
          </g>
        )
      })}

      <text
        x={cx}
        y={ZONE.mesh.y + ZONE.mesh.h + 34}
        className="mesh-zone-caption"
      >
        Signals cross the mesh in milliseconds. No one node holds all the truth.
      </text>
    </g>
  )
}

function AgentsZone() {
  const gap = 12
  const rowH = (ZONE.agents.h - (STRATEGIES.length - 1) * gap - 60) / STRATEGIES.length
  return (
    <g aria-label="Trading agents">
      <ZoneLabel
        x={ZONE.agents.x}
        y={ZONE.agents.y - 14}
        index="02 · AGENTS"
        title="Five strategies, always in paper"
        sub="Each proposes; none may execute without a human tap."
      />

      {STRATEGIES.map((s, i) => {
        const y = ZONE.agents.y + 40 + i * (rowH + gap)
        return (
          <g
            key={s.name}
            className="mesh-agent"
            style={{ animationDelay: `${420 + i * 100}ms` }}
          >
            <rect
              x={ZONE.agents.x}
              y={y}
              width={ZONE.agents.w}
              height={rowH}
              className="mesh-agent-box"
            />
            <circle
              cx={ZONE.agents.x + 24}
              cy={y + rowH / 2}
              r={5}
              className="mesh-agent-dot"
              style={{ animationDelay: `${i * 240}ms` }}
            />
            <text
              x={ZONE.agents.x + 44}
              y={y + 26}
              className="mesh-agent-name"
            >
              {s.name}
            </text>
            <text
              x={ZONE.agents.x + 44}
              y={y + 48}
              className="mesh-agent-thesis"
            >
              {s.thesis}
            </text>
            <text
              x={ZONE.agents.x + ZONE.agents.w - 14}
              y={y + 26}
              className="mesh-agent-mode"
              textAnchor="end"
            >
              PAPER
            </text>
            <text
              x={ZONE.agents.x + ZONE.agents.w - 14}
              y={y + 48}
              className="mesh-agent-cite"
              textAnchor="end"
            >
              strategies.py:{s.line}
            </text>
          </g>
        )
      })}
    </g>
  )
}

function PipelineZone() {
  const rowH = (ZONE.pipeline.h - 90) / PIPELINE.length
  return (
    <g aria-label="Evidence pipeline">
      <ZoneLabel
        x={ZONE.pipeline.x}
        y={ZONE.pipeline.y - 14}
        index="03 · GATE"
        title="Evidence, then a single tap"
        sub="Every stage hands a signed record to the next."
      />

      <line
        x1={ZONE.pipeline.x + 32}
        y1={ZONE.pipeline.y + 40}
        x2={ZONE.pipeline.x + 32}
        y2={ZONE.pipeline.y + 40 + rowH * PIPELINE.length}
        className="mesh-pipe-spine"
      />

      {PIPELINE.map((stage, i) => {
        const y = ZONE.pipeline.y + 40 + i * rowH
        const isGate = stage.title === 'Gate'
        return (
          <g
            key={stage.index}
            className="mesh-stage"
            style={{ animationDelay: `${560 + i * 110}ms` }}
          >
            <circle
              cx={ZONE.pipeline.x + 32}
              cy={y + rowH / 2}
              r={isGate ? 9 : 6}
              className={`mesh-stage-node ${isGate ? 'is-gate' : ''}`}
            />
            {isGate && (
              <circle
                cx={ZONE.pipeline.x + 32}
                cy={y + rowH / 2}
                r={16}
                className="mesh-stage-halo"
              />
            )}
            <text
              x={ZONE.pipeline.x + 60}
              y={y + rowH / 2 - 14}
              className="mesh-stage-index"
            >
              {stage.index}
            </text>
            <text
              x={ZONE.pipeline.x + 60}
              y={y + rowH / 2 + 6}
              className="mesh-stage-title"
            >
              {stage.title}
            </text>
            <text
              x={ZONE.pipeline.x + 60}
              y={y + rowH / 2 + 26}
              className="mesh-stage-plain"
            >
              {stage.plain}
            </text>
            <text
              x={ZONE.pipeline.x + 60}
              y={y + rowH / 2 + 42}
              className="mesh-stage-tech"
            >
              {stage.technical}
            </text>
          </g>
        )
      })}
    </g>
  )
}

function InterZoneFlow() {
  const meshExit = { x: ZONE.mesh.x + ZONE.mesh.w - 20, y: ZONE.mesh.y + ZONE.mesh.h / 2 }
  const agentsEnter = { x: ZONE.agents.x, y: ZONE.agents.y + ZONE.agents.h / 2 }
  const agentsExit = { x: ZONE.agents.x + ZONE.agents.w, y: ZONE.agents.y + ZONE.agents.h / 2 }
  const pipeEnter = { x: ZONE.pipeline.x + 32, y: ZONE.pipeline.y + 60 }

  return (
    <g className="mesh-interzone">
      <line
        x1={meshExit.x}
        y1={meshExit.y}
        x2={agentsEnter.x}
        y2={agentsEnter.y}
        className="mesh-interzone-line"
      />
      <line
        x1={meshExit.x}
        y1={meshExit.y}
        x2={agentsEnter.x}
        y2={agentsEnter.y}
        className="mesh-interzone-flow"
      />
      <path
        d={`M ${agentsExit.x} ${agentsExit.y} Q ${(agentsExit.x + pipeEnter.x) / 2} ${agentsExit.y} ${pipeEnter.x} ${pipeEnter.y}`}
        className="mesh-interzone-line"
        fill="none"
      />
      <path
        d={`M ${agentsExit.x} ${agentsExit.y} Q ${(agentsExit.x + pipeEnter.x) / 2} ${agentsExit.y} ${pipeEnter.x} ${pipeEnter.y}`}
        className="mesh-interzone-flow"
        fill="none"
      />
    </g>
  )
}

export default function ArchitectureMesh({ variant = 'full' }: { variant?: Variant }) {
  return (
    <div className={`mesh mesh--${variant}`}>
      <header className="mesh-head">
        <p className="mesh-eyebrow">The system, in one view</p>
        <h2 className="mesh-title">
          Four machines watch. Five agents propose.
          <span> A human decides.</span>
        </h2>
        <p className="mesh-lede">
          Sapphire runs on a small mesh of computers you can point at. They
          observe markets around the clock, five strategies form claims, and a
          single Telegram tap is the only way capital moves. Nothing on this
          diagram is decorative; every label refers to a file you can read.
        </p>
      </header>

      <div className="mesh-canvas">
        <svg
          viewBox={`0 0 ${VIEW.w} ${VIEW.h}`}
          role="img"
          aria-labelledby="mesh-diagram-title mesh-diagram-desc"
          preserveAspectRatio="xMidYMid meet"
          className="mesh-svg"
        >
          <title id="mesh-diagram-title">Sapphire compute mesh, agents, and gate</title>
          <desc id="mesh-diagram-desc">
            Four networked machines feed five paper-trading strategies which propose
            trades through a four-stage evidence pipeline. Execution requires a human
            approval at the gate.
          </desc>
          <defs>
            <linearGradient id="mesh-panel-glow" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--color-raised)" stopOpacity="0.55" />
              <stop offset="100%" stopColor="var(--color-void)" stopOpacity="0" />
            </linearGradient>
          </defs>

          <rect
            x="20"
            y="20"
            width={VIEW.w - 40}
            height={VIEW.h - 40}
            className="mesh-frame"
          />

          <line
            x1={ZONE.mesh.x + ZONE.mesh.w + 30}
            y1="40"
            x2={ZONE.mesh.x + ZONE.mesh.w + 30}
            y2={VIEW.h - 40}
            className="mesh-divider"
          />
          <line
            x1={ZONE.agents.x + ZONE.agents.w + 30}
            y1="40"
            x2={ZONE.agents.x + ZONE.agents.w + 30}
            y2={VIEW.h - 40}
            className="mesh-divider"
          />

          <InterZoneFlow />
          <MeshZone />
          <AgentsZone />
          <PipelineZone />
        </svg>
      </div>

      {variant === 'full' && (
        <div className="mesh-legend">
          <div className="mesh-legend-col">
            <p className="mesh-legend-eyebrow">Where the numbers come from</p>
            <ul className="mesh-legend-list">
              <li>
                Mesh &amp; roles ·{' '}
                <code>Sapphire/infra/tailscale-acl.json</code>
              </li>
              <li>
                Strategy set ·{' '}
                <code>Sapphire/lib/analytics/strategies.py</code>
              </li>
              <li>
                Gate &amp; caps ·{' '}
                <code>lib/core/confirmation_firewall.py</code>
              </li>
            </ul>
          </div>
          <div className="mesh-legend-col">
            <p className="mesh-legend-eyebrow">Settlement rail</p>
            <p className="mesh-legend-body">
              Robinhood Chain, an {RH_CHAIN.family}. Mainnet {RH_CHAIN.mainnet},
              testnet {RH_CHAIN.testnet}, live since {RH_CHAIN.liveSince}. Three
              contracts:{' '}
              <code>{RH_CHAIN.contracts.join(', ')}</code>. Public wallet{' '}
              <code>
                {RH_CHAIN.publicWallet.slice(0, 6)}…{RH_CHAIN.publicWallet.slice(-4)}
              </code>
              ; keys never enter this repo.
            </p>
          </div>
          <div className="mesh-legend-col">
            <p className="mesh-legend-eyebrow">Non-technical read</p>
            <p className="mesh-legend-body">
              The system watches markets 24/7 from four small computers on the
              same private network. It writes down what it thinks — with the
              source and what would prove it wrong — and only asks to trade
              after that record is complete. A trade waits for one tap on a
              phone before any money moves.
            </p>
          </div>
        </div>
      )}
    </div>
  )
}
