import { useMemo, useState, type CSSProperties } from 'react'
import { DEFAULT_LOOM_METRICS } from '@shared/loomLayout'
import { describeLink, describeNode } from '@shared/vocabulary'
import { linkId, type LiveLink, type LiveNode, type SignalClass } from '@shared/telemetry'
import { useElementWidth } from '../hooks/useElementWidth'
import { leaderPath, loomCurve, loomGeometry } from '../desk/loomGeometry'
import { flowProfile, formatLatency, formatRate } from '../desk/format'

/** Width assumed before the container has been measured, and in the tests. */
const FALLBACK_WIDTH = 900

const SIGNAL_CLASSES: Array<{ id: SignalClass; label: string }> = [
  { id: 'network', label: 'machines talking' },
  { id: 'agent', label: 'agent work' },
  { id: 'market', label: 'market data' },
  { id: 'archive', label: 'writing things down' },
  { id: 'reliability', label: 'health checks' },
]

export function SignalLoom({
  nodes,
  links,
  status,
}: {
  nodes: LiveNode[]
  links: LiveLink[]
  status: string
}) {
  const { ref, width } = useElementWidth<HTMLDivElement>(FALLBACK_WIDTH)
  const [hot, setHot] = useState<string | null>(null)

  const geometry = useMemo(() => loomGeometry(nodes, { width }), [nodes, width])

  /* Every link that joins two nodes we actually placed. A link naming a node the
     snapshot did not declare is dropped rather than drawn to the origin. */
  const drawable = links.filter((link) => geometry.points[link.source] && geometry.points[link.target])

  return (
    <section className="border border-line bg-raised/60" aria-labelledby="loom-title">
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
        <p className="max-w-sm text-right font-mono text-[11px] leading-relaxed text-ink-faint">
          Each line moves at the rate its edge actually reports. An edge carrying nothing
          is drawn still.
        </p>
      </div>

      {nodes.length === 0 ? (
        <div className="flex flex-col items-center gap-3 px-6 py-24 text-center">
          <span aria-hidden="true" className="h-10 w-10 border border-dashed border-line-lit" />
          <strong className="font-display text-base font-semibold text-ink-dim">
            {status === 'warming'
              ? 'Waiting for the first report to arrive'
              : 'The home machines are not reporting'}
          </strong>
          <span className="font-mono text-[11px] text-ink-faint">
            Nothing is drawn until a signed snapshot arrives. There is no placeholder view.
          </span>
        </div>
      ) : (
        <>
          <div ref={ref} className="px-6 py-5">
            <svg
              className="loom"
              viewBox={`0 0 ${geometry.width} ${geometry.height}`}
              style={{ height: geometry.height }}
              role="img"
              aria-label="Live map of the machines, what each one is doing, and the measured flow between them"
            >
              <defs>
                <marker
                  id="arrow"
                  viewBox="0 0 10 10"
                  refX="8"
                  refY="5"
                  markerWidth="5"
                  markerHeight="5"
                  orient="auto-start-reverse"
                >
                  <path d="M 0 0 L 10 5 L 0 10 z" />
                </marker>
              </defs>

              {/* Leader lines first, so they sit under everything they connect. */}
              {geometry.boxes.map((box) =>
                box.anchor ? (
                  <path
                    key={`leader-${box.id}`}
                    className={`loom-leader ${heat(hot, box.id)}`}
                    d={leaderPath(box.anchor, box)}
                  />
                ) : null,
              )}

              {drawable.map((link) => {
                const id = linkId(link)
                const from = geometry.points[link.source]
                const to = geometry.points[link.target]
                const flow = flowProfile(link.event_rate)
                const described = describeLink(link)
                const style = {
                  '--flow-duration': `${flow.durationS}s`,
                  '--flow-width': flow.strokeWidth,
                } as CSSProperties
                return (
                  <g
                    key={id}
                    className={`loom-link signal-${link.signal_class} status-${link.status} ${
                      flow.moving ? 'is-moving' : 'is-still'
                    } ${heat(hot, link.source, link.target)}`}
                    style={style}
                  >
                    <path className="link-bed" d={loomCurve(from, to)} />
                    <path className="link-current" d={loomCurve(from, to)} markerEnd="url(#arrow)" />
                    <title>
                      {`${described.plainName} — ${described.oneLiner} Carrying ${formatRate(
                        link.event_rate,
                      )}; round trip ${formatLatency(link.latency_ms)}.`}
                    </title>
                  </g>
                )
              })}

              {geometry.placements.map(({ node, point }) => (
                <g
                  key={node.id}
                  className={`loom-node status-${node.status} ${heat(hot, node.id)}`}
                  transform={`translate(${point.x} ${point.y})`}
                  aria-label={`${describeNode(node.id).plainName}: ${describeNode(node.id).oneLiner}`}
                  onMouseEnter={() => setHot(node.id)}
                  onMouseLeave={() => setHot(null)}
                >
                  <circle className="node-halo" r={geometry.haloRadius} />
                  <circle className="node-core" r={geometry.nodeRadius} />
                  <title>{`${describeNode(node.id).plainName} — ${describeNode(node.id).oneLiner}`}</title>
                </g>
              ))}

              {/* Labels. Every coordinate below comes from @shared/loomLayout;
                  nothing here nudges a box, which is what keeps the
                  non-overlap guarantee true at every width. */}
              {geometry.boxes.map((box) => (
                <g
                  key={`box-${box.id}`}
                  className={`loom-box ${heat(hot, box.id)}`}
                  aria-label={`${describeNode(box.id).plainName} readings`}
                  onMouseEnter={() => setHot(box.id)}
                  onMouseLeave={() => setHot(null)}
                >
                  <rect x={box.x} y={box.y} width={box.width} height={box.height} rx={0} />
                  {box.lines.map((line, index) => (
                    <text
                      key={`${box.id}-${index}`}
                      className={line.kind === 'label' ? 'box-label' : 'box-sub'}
                      x={box.x + DEFAULT_LOOM_METRICS.paddingXPx}
                      y={box.y + line.y + line.height * 0.75}
                    >
                      {line.text}
                    </text>
                  ))}
                </g>
              ))}
            </svg>

            <div
              className="mt-5 flex flex-wrap justify-center gap-x-7 gap-y-3 border-t border-line pt-4 font-mono text-[11px] tracking-[0.08em] text-ink-faint"
              aria-label="What the colours mean"
            >
              {SIGNAL_CLASSES.map((entry) => (
                <span key={entry.id} className="inline-flex items-center gap-2">
                  <svg
                    aria-hidden="true"
                    className={`legend-swatch signal-${entry.id}`}
                    viewBox="0 0 18 4"
                  >
                    <path className="link-current" d="M 0 2 L 18 2" />
                  </svg>
                  {entry.label}
                </span>
              ))}
            </div>
          </div>

          <LinkLedger links={drawable} nodeCount={nodes.length} />
        </>
      )}
    </section>
  )
}

/** Dim everything that is not the thing under the cursor. */
function heat(hot: string | null, ...ids: string[]): string {
  if (hot === null) return ''
  return ids.includes(hot) ? 'is-hot' : 'is-dim'
}

/**
 * The numbers behind the picture, one row per edge.
 *
 * This table is where the honesty constraint bites hardest: `latency_ms` is
 * `null` on every link in production today, so the latency column is a column
 * of "not measured". It stays that way — no zero, no dash pretending to be a
 * reading, no shimmer standing in for a number — and lights up on its own the
 * moment a probe starts reporting.
 */
function LinkLedger({ links, nodeCount }: { links: LiveLink[]; nodeCount: number }) {
  const measured = links.filter((link) => link.latency_ms !== null && link.latency_ms !== undefined)

  return (
    <div className="border-t border-line">
      <div className="flex flex-wrap items-baseline justify-between gap-3 px-6 pt-5 pb-3">
        <p className="font-mono text-[11px] tracking-[0.2em] text-sapphire uppercase">
          Every connection, measured
        </p>
        <p className="font-mono text-[11px] text-ink-faint">
          {measured.length} of {links.length} report a round-trip time
        </p>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[640px] border-collapse text-left">
          <thead>
            <tr className="border-y border-line font-mono text-[10px] tracking-[0.14em] text-ink-faint uppercase">
              <th scope="col" className="px-6 py-2.5 font-normal">
                What is happening
              </th>
              <th scope="col" className="px-3 py-2.5 font-normal">
                From
              </th>
              <th scope="col" className="px-3 py-2.5 font-normal">
                To
              </th>
              <th scope="col" className="px-3 py-2.5 text-right font-normal">
                Events
              </th>
              <th scope="col" className="px-6 py-2.5 text-right font-normal">
                Round trip
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {links.map((link) => {
              const described = describeLink(link)
              const latency = formatLatency(link.latency_ms)
              const unmeasured = link.latency_ms === null || link.latency_ms === undefined
              return (
                <tr key={linkId(link)}>
                  <td className="px-6 py-3">
                    <strong className="block font-display text-[13px] font-semibold text-ink">
                      {described.plainName}
                    </strong>
                    <span className="block text-[12px] text-ink-faint">{described.oneLiner}</span>
                  </td>
                  <td className="px-3 py-3 text-[12px] text-ink-dim">
                    {describeNode(link.source).plainName}
                  </td>
                  <td className="px-3 py-3 text-[12px] text-ink-dim">
                    {describeNode(link.target).plainName}
                  </td>
                  <td className="tnum px-3 py-3 text-right font-mono text-[12px] text-ink">
                    {formatRate(link.event_rate)}
                  </td>
                  <td
                    className={`tnum px-6 py-3 text-right font-mono text-[12px] ${
                      unmeasured ? 'text-ink-faint italic' : 'text-ink'
                    }`}
                  >
                    {latency}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      <p className="border-t border-line px-6 py-4 text-[12px] leading-relaxed text-ink-faint">
        “{formatLatency(null)}” means exactly that: nothing times this hop yet, so there is
        no number to print. {nodeCount} machines are reporting.
      </p>
    </div>
  )
}
