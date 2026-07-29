import type { CSSProperties } from 'react'
import { AGENT_MARKET_ROLES, SYSTEM_ATLAS_STAGES } from '@/data/system-atlas'

type AtlasStyle = CSSProperties & {
  '--atlas-x': number
  '--atlas-y': number
}

export default function SystemAtlas() {
  return (
    <section className="system-atlas" aria-labelledby="system-atlas-title">
      <header className="system-atlas__header">
        <div>
          <p className="public-kicker">Architecture · agent market · research</p>
          <h2 id="system-atlas-title">See the whole system in one orbit.</h2>
        </div>
        <div className="system-atlas__intro">
          <strong>In plain language</strong>
          <p>
            Think of Sapphire as a newsroom joined to a laboratory. It gathers evidence,
            lets specialist roles challenge one another, records what survives, and stops
            at a separate policy boundary. Nothing on this page can approve or place a trade.
          </p>
        </div>
      </header>

      <figure className="system-atlas__figure">
        <figcaption>
          <span>Static architecture contract</span>
          <span>runtime evidence: none</span>
          <span>authority: none</span>
        </figcaption>

        <div className="system-atlas__map">
          <svg
            className="system-atlas__routes"
            viewBox="0 0 1200 620"
            preserveAspectRatio="none"
            aria-hidden="true"
          >
            <path
              className="system-atlas__orbit"
              d="M60 345 C170 85 340 80 455 310 C540 485 665 485 748 310 C860 80 1030 85 1140 345"
            />
            <path
              className="system-atlas__route"
              d="M60 345 C170 85 340 80 455 310 C540 485 665 485 748 310 C860 80 1030 85 1140 345"
            />
            <ellipse className="system-atlas__ring" cx="605" cy="327" rx="160" ry="146" />
            <ellipse className="system-atlas__ring system-atlas__ring--outer" cx="605" cy="327" rx="260" ry="224" />
          </svg>

          <div className="system-atlas__authority" aria-hidden="true">
            <span>Public authority</span>
            <strong>NONE</strong>
          </div>

          <ol className="system-atlas__path" aria-label="System path in plain language">
            {SYSTEM_ATLAS_STAGES.map((stage) => (
              <li
                key={stage.id}
                className={`system-atlas__stage system-atlas__stage--${stage.id}`}
                data-atlas-stage={stage.id}
                style={
                  {
                    '--atlas-x': stage.position.x,
                    '--atlas-y': stage.position.y,
                  } as AtlasStyle
                }
              >
                <span className="system-atlas__index">{stage.index}</span>
                <h3>{stage.title}</h3>
                <p>{stage.plain}</p>
                {stage.id === 'agents' ? (
                  <ul className="system-atlas__agents" aria-label="Proposal-only agent roles">
                    {AGENT_MARKET_ROLES.map((agent) => (
                      <li key={agent.role}>
                        <strong>{agent.role}</strong>
                        <span>{agent.job}</span>
                      </li>
                    ))}
                  </ul>
                ) : null}
                <span className="system-atlas__state">
                  {stage.id === 'agents' ? 'proposal-only' : 'contract only'}
                </span>
              </li>
            ))}
          </ol>
        </div>
      </figure>

      <details className="system-atlas__technical">
        <summary>
          <span>Technical contract</span>
          <small>Sources, state semantics, and authority</small>
        </summary>
        <dl>
          {SYSTEM_ATLAS_STAGES.map((stage) => (
            <div key={stage.id} data-atlas-stage={stage.id}>
              <dt>
                <span>{stage.index}</span>
                {stage.title}
              </dt>
              <dd>
                <p>{stage.technical}</p>
                <code>source: {stage.source}</code>
                <code>authority: {stage.authority}</code>
              </dd>
            </div>
          ))}
        </dl>
      </details>
    </section>
  )
}
