/**
 * Visual execution pipeline for the trading page. Replaces the earlier
 * shell-transcript Terminal block with a legible ladder: signal sources on
 * the left feed a proposal that must pass every gate; each gate carries its
 * evidence state so a non-technical reader can see, in one glance, exactly
 * where and why the flow stops.
 *
 * The whole diagram is a semantic ordered list of stages, styled with grid.
 * No JS, no interaction, no runtime data — the design contract is inert by
 * construction and the trading page test forbids <button|input|form>.
 */

type GateState = 'ok' | 'unavailable' | 'paused'

const SIGNALS = [
  { label: 'Research', hint: 'daily conjecture' },
  { label: 'VPIN', hint: 'flow toxicity' },
  { label: 'TA', hint: 'technical alerts' },
  { label: 'TV', hint: 'TradingView hooks' },
]

const GATES: Array<{ index: string; label: string; body: string; state: GateState }> = [
  {
    index: '01',
    label: 'Pause sources',
    body: 'Two canonical pause observations must be current.',
    state: 'unavailable',
  },
  {
    index: '02',
    label: 'Broker rail',
    body: 'Reconciliation, session, and rate-limit evidence.',
    state: 'unavailable',
  },
  {
    index: '03',
    label: 'Credentials',
    body: 'Enrollment and rotation evidence on the executor.',
    state: 'unavailable',
  },
  {
    index: '04',
    label: 'Runtime',
    body: 'Installed executor, current health, capacity budget.',
    state: 'unavailable',
  },
]

const STATE_LABEL: Record<GateState, string> = {
  ok: 'observed',
  paused: 'paused',
  unavailable: 'unavailable',
}

/** Blocked outcome derives from the gate row — if any gate is not `ok`,
 *  the proposal is held. Held is not a failure; it is the design working. */
function outcome(): { label: string; body: string; tone: 'held' | 'fill' } {
  const anyClosed = GATES.some((g) => g.state !== 'ok')
  return anyClosed
    ? {
        label: 'Held · no order emitted',
        body: 'The design refuses to admit an action when any required observation is missing, stale, or unverifiable.',
        tone: 'held',
      }
    : {
        label: 'Fill on designated rail',
        body: 'Bounded fill goes only to the designated agentic account within the daily envelope.',
        tone: 'fill',
      }
}

export function ExecutionPipeline() {
  const end = outcome()
  return (
    <div className="exec-pipeline" aria-label="Execution flow — inert design">
      <div className="exec-pipeline__head">
        <p className="exec-pipeline__title">Execution flow</p>
        <p className="exec-pipeline__note">Inert design contract · not runtime telemetry</p>
      </div>

      <div className="exec-pipeline__stage">
        <p className="exec-pipeline__label">01 · Signal</p>
        <ul className="exec-pipeline__signals">
          {SIGNALS.map((s) => (
            <li key={s.label}>
              <strong>{s.label}</strong>
              <span>{s.hint}</span>
            </li>
          ))}
        </ul>
      </div>

      <div className="exec-pipeline__connector" aria-hidden="true" />

      <div className="exec-pipeline__stage">
        <p className="exec-pipeline__label">02 · Proposal</p>
        <div className="exec-pipeline__proposal">
          A proposal is not an order. Every proposal carries its evidence sources and
          must clear the gates below.
        </div>
      </div>

      <div className="exec-pipeline__connector" aria-hidden="true" />

      <div className="exec-pipeline__stage">
        <p className="exec-pipeline__label">03 · Gate ladder</p>
        <ol className="exec-pipeline__gates">
          {GATES.map((g) => (
            <li key={g.index} data-gate-state={g.state}>
              <div className="exec-pipeline__gate-index">{g.index}</div>
              <div className="exec-pipeline__gate-body">
                <strong>{g.label}</strong>
                <p>{g.body}</p>
              </div>
              <div className="exec-pipeline__gate-state" aria-label={`gate ${STATE_LABEL[g.state]}`}>
                <span className="exec-pipeline__gate-dot" aria-hidden="true" />
                {STATE_LABEL[g.state]}
              </div>
            </li>
          ))}
        </ol>
      </div>

      <div className="exec-pipeline__connector" aria-hidden="true" />

      <div className="exec-pipeline__outcome" data-outcome-tone={end.tone}>
        <p className="exec-pipeline__label">04 · Outcome</p>
        <strong>{end.label}</strong>
        <p>{end.body}</p>
      </div>
    </div>
  )
}
