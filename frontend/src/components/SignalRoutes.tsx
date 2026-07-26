import { describeLink, describeNode } from '@shared/vocabulary'
import { linkId, type LiveLink, type LiveNode, type SignalClass } from '@shared/telemetry'
import { formatAge, formatLatency, formatRate } from '../desk/format'

const SIGNAL_LABELS: Record<SignalClass, string> = {
  network: 'network',
  agent: 'agent work',
  market: 'market data',
  archive: 'archive',
  reliability: 'health check',
}

export function SignalRoutes({
  nodes,
  links,
  status,
}: {
  nodes: LiveNode[]
  links: LiveLink[]
  status: string
}) {
  const nodeById = new Map(nodes.map((node) => [node.id, node]))
  const drawable = links.filter(
    (link) => nodeById.has(link.source) && nodeById.has(link.target),
  )
  const timed = drawable.filter(
    (link) => link.latency_ms !== null && link.latency_ms !== undefined,
  )

  return (
    <section className="border border-line bg-raised/50" aria-labelledby="routes-title">
      <div className="grid gap-5 border-b border-line px-5 py-5 md:grid-cols-[1fr_auto] md:items-end md:px-7">
        <div>
          <p className="font-mono text-[11px] tracking-[0.18em] text-sapphire uppercase">
            Live architecture
          </p>
          <h2
            id="routes-title"
            className="mt-2 font-display text-2xl font-semibold tracking-[-0.025em] text-ink"
          >
            Signal paths
          </h2>
          <p className="mt-2 max-w-2xl text-sm leading-relaxed text-ink-dim">
            A route ledger: what moved, where it went, and the measurement behind it.
            No crossing lines, inferred distance, or decorative motion.
          </p>
        </div>
        <div className="flex gap-5 font-mono text-[11px] text-ink-faint">
          <span>{nodes.length} reporting nodes</span>
          <span>
            {timed.length} of {drawable.length} timed
          </span>
        </div>
      </div>

      {nodes.length === 0 ? (
        <div className="px-5 py-10 md:px-7">
          <strong className="font-display text-base font-semibold text-ink-dim">
            {status === 'warming'
              ? 'Waiting for the first report to arrive'
              : 'The home machines are not reporting'}
          </strong>
          <p className="mt-2 text-sm text-ink-faint">
            No node or route is rendered until an observed snapshot arrives.
          </p>
        </div>
      ) : (
        <>
          <div className="grid bg-void sm:grid-cols-2 xl:grid-cols-4">
            {nodes.map((node) => {
              const described = describeNode(node.id)
              return (
                <article
                  key={node.id}
                  data-node={node.id}
                  className="min-w-0 border-r border-b border-line bg-void px-5 py-4"
                >
                  <div className="flex items-center justify-between gap-3">
                    <strong className="truncate font-display text-sm font-semibold text-ink">
                      {described.plainName}
                    </strong>
                    <span
                      role="img"
                      aria-label={`${described.plainName} status: ${node.status}`}
                      className={`route-status status-${node.status}`}
                    />
                  </div>
                  <p className="mt-2 truncate font-mono text-[10px] tracking-[0.08em] text-ink-faint uppercase">
                    {node.load} load · {formatRate(node.activity_rate)} · {formatAge(node.freshness_s)}
                  </p>
                </article>
              )
            })}
          </div>

          <div className="border-t border-line">
            {drawable.map((link) => (
              <RouteRow
                key={linkId(link)}
                link={link}
                source={nodeById.get(link.source)!}
                target={nodeById.get(link.target)!}
              />
            ))}
          </div>
        </>
      )}
    </section>
  )
}

function RouteRow({
  link,
  source,
  target,
}: {
  link: LiveLink
  source: LiveNode
  target: LiveNode
}) {
  const described = describeLink(link)
  const sourceName = describeNode(source.id).plainName
  const targetName = describeNode(target.id).plainName

  return (
    <article
      data-route={linkId(link)}
      className={`route-row signal-${link.signal_class} status-${link.status}`}
    >
      <div className="route-endpoint">
        <span className="route-kicker">from</span>
        <strong>{sourceName}</strong>
      </div>

      <div className="min-w-0">
        <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
          <strong className="font-display text-sm font-semibold text-ink">
            {described.plainName}
          </strong>
          <span className="font-mono text-[10px] tracking-[0.1em] text-ink-faint uppercase">
            {SIGNAL_LABELS[link.signal_class]}
          </span>
        </div>
        <div className="route-track" aria-hidden="true">
          <span />
        </div>
        <div className="mt-2 flex flex-wrap justify-between gap-x-4 gap-y-1 font-mono text-[11px]">
          <span className="text-ink-dim">{formatRate(link.event_rate)}</span>
          <span
            className={
              link.latency_ms === null || link.latency_ms === undefined
                ? 'text-ink-faint italic'
                : 'text-ink'
            }
          >
            {formatLatency(link.latency_ms)}
          </span>
        </div>
      </div>

      <div className="route-endpoint route-endpoint-target">
        <span className="route-kicker">to</span>
        <strong>{targetName}</strong>
      </div>
    </article>
  )
}
