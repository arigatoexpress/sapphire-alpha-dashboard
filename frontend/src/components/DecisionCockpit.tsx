import type { LiveDesk } from '../types'
import { NOT_OBSERVED } from '../desk/format'

const POSTURES: Record<LiveDesk['posture'], string> = {
  capital_preservation: 'Capital preservation',
  selective_risk: 'Selective risk',
  risk_seeking: 'Risk seeking',
  neutral: 'Neutral',
  unknown: NOT_OBSERVED,
}

function ratio(part: number | null, total: number | null, suffix = '') {
  if (part === null || total === null) return NOT_OBSERVED
  return `${part} / ${total}${suffix}`
}

function headline(desk: LiveDesk | null) {
  if (!desk || desk.execution === 'unknown') return 'Waiting for desk state.'
  if (desk.execution === 'halted') return 'The desk is protected.'
  if ((desk.decisions.pending ?? 0) > 0) return 'A decision needs review.'
  if (desk.leader === 'none') return 'No result has earned authority.'
  return 'Evidence is aligned.'
}

export function DecisionCockpit({ desk }: { desk: LiveDesk | null }) {
  const cells = [
    { label: 'Posture', value: desk ? POSTURES[desk.posture] : NOT_OBSERVED },
    {
      label: 'Credible leader',
      value: desk?.leader === 'credible' ? 'Present' : desk?.leader === 'none' ? 'None' : NOT_OBSERVED,
    },
    {
      label: 'OOS validation',
      value: desk ? ratio(desk.validation.oos_pass, desk.validation.oos_total, ' pass') : NOT_OBSERVED,
    },
    {
      label: 'Validation conflicts',
      value: desk?.validation.conflicts ?? NOT_OBSERVED,
    },
    {
      label: 'Decisions waiting',
      value: desk?.decisions.pending ?? NOT_OBSERVED,
    },
    {
      label: 'Execution',
      value: desk?.execution === 'unknown' || !desk ? NOT_OBSERVED : desk.execution,
      critical: desk?.execution === 'halted',
    },
    {
      label: 'Strategy feeds',
      value: desk ? ratio(desk.feeds.fresh, desk.feeds.total, ' current') : NOT_OBSERVED,
    },
  ]

  return (
    <section
      id="decisions"
      aria-labelledby="decision-title"
      className="decision-cockpit scroll-mt-24"
    >
      <div className="decision-head">
        <div>
          <span className="decision-index">01 / DECISION STATE</span>
          <h2 id="decision-title">{headline(desk)}</h2>
        </div>
        <p>
          The mandate is the prior. Independent evidence can challenge it, change
          sizing, or stop action—it cannot silently replace it.
        </p>
      </div>
      <div className="decision-tape" aria-label="Current desk conclusions">
        {cells.map((cell, index) => (
          <div key={cell.label} className={cell.critical ? 'is-protected' : undefined}>
            <span>{String(index + 1).padStart(2, '0')} · {cell.label}</span>
            <strong>{cell.value}</strong>
          </div>
        ))}
      </div>
      <div className="decision-boundary">
        <span>Research informs</span>
        <i aria-hidden="true" />
        <strong>Risk gates decide whether action is allowed</strong>
      </div>
    </section>
  )
}
