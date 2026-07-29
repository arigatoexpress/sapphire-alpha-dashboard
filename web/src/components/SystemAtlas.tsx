import type { CSSProperties } from 'react'
import type { LiveLink, LiveSnapshot } from '@shared/telemetry'
import { linkId } from '@shared/telemetry'
import { AGENT_MARKET_ROLES, SYSTEM_ATLAS_STAGES } from '@/data/system-atlas'

type AtlasStyle = CSSProperties & {
  '--atlas-x': number
  '--atlas-y': number
}

type LinkStyle = CSSProperties & {
  '--atlas-flow-duration': string
}

type Point = { x: number; y: number }

type SystemAtlasProps = {
  snapshot?: LiveSnapshot | null
  sourceError?: string
}

function topologyPoint(index: number, count: number): Point {
  const angle = -Math.PI / 2 + (Math.PI * 2 * index) / Math.max(count, 1)
  return {
    x: Number((50 + Math.cos(angle) * 41).toFixed(3)),
    y: Number((50 + Math.sin(angle) * 36).toFixed(3)),
  }
}

function age(seconds: number | null | undefined) {
  if (seconds == null || !Number.isFinite(seconds)) return 'not observed'
  if (seconds < 60) return `${Math.round(seconds)}s`
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`
  return `${Math.round(seconds / 3600)}h`
}

function rate(value: number | null, unit: string, current: boolean) {
  if (!current || value == null || !Number.isFinite(value)) return 'not observed'
  return `${Math.round(value)} ${unit}`
}

function flowState(link: LiveLink, current: boolean) {
  return current &&
    link.status === 'healthy' &&
    link.event_rate != null &&
    link.event_rate > 0
    ? 'observed'
    : 'unavailable'
}

function flowDuration(eventRate: number | null) {
  if (eventRate == null || eventRate <= 0) return '7s'
  return `${Math.max(1.8, 7 - Math.log10(eventRate + 1) * 1.6).toFixed(2)}s`
}

export default function SystemAtlas({
  snapshot = null,
  sourceError = '',
}: SystemAtlasProps) {
  const current = snapshot?.status === 'live' && !sourceError
  const retained = Boolean(
    snapshot && (sourceError || snapshot.status === 'stale'),
  )
  const nodes = snapshot?.nodes ?? []
  const links = snapshot?.links ?? []
  const points = new Map(
    nodes.map((node, index) => [
      node.id,
      topologyPoint(index, nodes.length),
    ]),
  )
  const runtimeState = sourceError
    ? snapshot
      ? 'retained snapshot · poll unavailable'
      : 'not observed · poll unavailable'
    : snapshot?.status === 'stale'
      ? 'retained snapshot · stale'
      : (snapshot?.status ?? 'not observed')

  return (
    <section className="system-atlas" aria-labelledby="system-atlas-title">
      <header className="system-atlas__header">
        <div>
          <p className="public-kicker">Architecture · live telemetry · authority</p>
          <h2 id="system-atlas-title">See the whole system in one orbit.</h2>
        </div>
        <div className="system-atlas__intro">
          <strong>In plain language</strong>
          <p>
            Each card is one admitted semantic node. Each route is one reported
            dependency. Motion appears only when that route carries a measured,
            non-zero event rate. Missing measurements stay missing. Nothing on
            this page can approve or place a trade.
          </p>
        </div>
      </header>

      <figure className="system-atlas__figure" data-runtime-current={current}>
        <figcaption>
          <span>{nodes.length ? 'Live runtime topology' : 'Static architecture contract'}</span>
          <span>runtime evidence: {runtimeState}</span>
          <span>observed: {snapshot?.observed_at ?? 'not observed'}</span>
          <span>authority: none</span>
        </figcaption>

        <div className="system-atlas__map">
          {nodes.length ? (
            <>
              <svg
                className="system-atlas__routes"
                viewBox="0 0 1200 680"
                preserveAspectRatio="none"
                role="img"
                aria-label="Admitted runtime dependency routes"
              >
                <ellipse className="system-atlas__orbit" cx="600" cy="340" rx="480" ry="245" />
                {links.map((link) => {
                  const source = points.get(link.source)
                  const target = points.get(link.target)
                  if (!source || !target) return null
                  const state = flowState(link, current)
                  return (
                    <line
                      key={linkId(link)}
                      className="system-atlas__link"
                      data-atlas-link={linkId(link)}
                      data-flow={state}
                      data-status={current ? link.status : 'unknown'}
                      x1={source.x * 12}
                      y1={source.y * 6.8}
                      x2={target.x * 12}
                      y2={target.y * 6.8}
                      style={
                        {
                          '--atlas-flow-duration': flowDuration(link.event_rate),
                        } as LinkStyle
                      }
                    >
                      <title>{`${link.source} to ${link.target}: ${
                        current ? link.status : 'unknown'
                      }; ${rate(link.event_rate, 'evt/min', current)}`}</title>
                    </line>
                  )
                })}
              </svg>

              <div className="system-atlas__authority" aria-hidden="true">
                <span>Public authority</span>
                <strong>NONE</strong>
              </div>

              <ol className="system-atlas__nodes" aria-label="Admitted runtime nodes">
                {nodes.map((node, index) => {
                  const point = points.get(node.id)!
                  const measurementsCurrent =
                    current &&
                    (node.status === 'healthy' || node.status === 'degraded')
                  return (
                    <li
                      key={node.id}
                      className="system-atlas__node"
                      data-atlas-node={node.id}
                      data-status={current ? node.status : 'unknown'}
                      style={
                        {
                          '--atlas-x': point.x,
                          '--atlas-y': point.y,
                        } as AtlasStyle
                      }
                    >
                      <div className="system-atlas__node-head">
                        <span>{String(index + 1).padStart(2, '0')}</span>
                        <b>{current ? node.status : 'unknown'}</b>
                      </div>
                      <h3>{node.label}</h3>
                      <p>{node.zone}</p>
                      <dl>
                        <div>
                          <dt>age</dt>
                          <dd>{current ? age(node.freshness_s) : 'not observed'}</dd>
                        </div>
                        <div>
                          <dt>load</dt>
                          <dd>{measurementsCurrent ? node.load : 'not observed'}</dd>
                        </div>
                        <div>
                          <dt>rate</dt>
                          <dd>
                            {rate(
                              node.activity_rate,
                              'evt/min',
                              measurementsCurrent,
                            )}
                          </dd>
                        </div>
                      </dl>
                    </li>
                  )
                })}
              </ol>
            </>
          ) : (
            <div className="system-atlas__empty">
              <span>Runtime topology not observed</span>
              <p>
                Waiting for a schema-validated <code>/api/v1/live</code> report.
                The architecture contract remains available below.
              </p>
            </div>
          )}
        </div>
      </figure>

      <details className="system-atlas__technical">
        <summary>
          <span>Technical contract</span>
          <small>Sources, state semantics, and authority</small>
        </summary>
        {links.length ? (
          <ol className="system-atlas__link-ledger" aria-label="Runtime route evidence">
            {links.map((link) => (
              <li key={linkId(link)}>
                <strong>{linkId(link)}</strong>
                <span>{link.signal_class}</span>
                <span>{current ? link.status : 'unknown'}</span>
                <span>{rate(link.event_rate, 'evt/min', current)}</span>
                <span>{rate(link.latency_ms, 'ms', current)}</span>
              </li>
            ))}
          </ol>
        ) : null}
        <dl>
          {SYSTEM_ATLAS_STAGES.map((stage) => (
            <div key={stage.id} data-atlas-stage={stage.id}>
              <dt>
                <span>{stage.index}</span>
                {stage.title}
              </dt>
              <dd>
                <p>{stage.plain}</p>
                <p>{stage.technical}</p>
                {stage.id === 'agents' ? (
                  <ul aria-label="Proposal-only agent roles">
                    {AGENT_MARKET_ROLES.map((agent) => (
                      <li key={agent.role}>
                        <strong>{agent.role}</strong>: {agent.job}
                      </li>
                    ))}
                  </ul>
                ) : null}
                <code>source: {stage.source}</code>
                <code>authority: {stage.authority}</code>
              </dd>
            </div>
          ))}
        </dl>
        {retained ? (
          <p className="system-atlas__retained">
            This is a retained snapshot. Current styling, rates, latency, and
            route motion are withdrawn until a fresh report arrives.
          </p>
        ) : null}
      </details>
    </section>
  )
}
