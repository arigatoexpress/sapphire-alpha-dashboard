import { formatClockTime, NOT_OBSERVED } from '../desk/format'
import type {
  PublicResearchClip,
  PublicServiceHealth,
  PublicSignal,
  PublicWidgets,
} from '../types'

function displayStatus(value: string | null | undefined) {
  if (!value) return NOT_OBSERVED
  const labels: Record<string, string> = {
    ok: 'Current',
    current: 'Current',
    disarmed: 'Disarmed',
    armed: 'Armed',
    killswitch: 'Stopped',
    not_observed: 'Not observed',
    not_configured: 'Not configured',
    unreachable: 'Unavailable',
    timeout: 'Delayed',
    degraded: 'Degraded',
    protected: 'Protected',
    standby: 'Standby',
    offline: 'Offline',
  }
  return labels[value] ?? value.replace(/_/g, ' ')
}

function statusTone(value: string | null | undefined) {
  if (value === 'ok' || value === 'current') return 'watch-current'
  if (value === 'disarmed' || value === 'protected' || value === 'standby') {
    return 'watch-protected'
  }
  if (value === 'unreachable' || value === 'timeout' || value === 'degraded') {
    return 'watch-warning'
  }
  if (value === 'killswitch' || value === 'offline') return 'watch-stopped'
  return 'watch-unknown'
}

function policyPercent(value: number) {
  return `${Math.round(value * 100)}%`
}

function EvidenceReel({ clips }: { clips: PublicResearchClip[] }) {
  return (
    <div className="evidence-reel">
      <div className="evidence-subhead">
        <span>Reviewed evidence</span>
        <strong>{clips.length ? `${clips.length} current notes` : 'No current notes'}</strong>
      </div>
      {clips.length ? (
        <ol>
          {clips.slice(0, 6).map((clip, index) => (
            <li key={clip.id}>
              <span>{String(index + 1).padStart(2, '0')}</span>
              <time dateTime={clip.observed_at}>{formatClockTime(clip.observed_at)}</time>
              <strong>{clip.title}</strong>
            </li>
          ))}
        </ol>
      ) : (
        <p className="evidence-empty">
          No reviewed evidence has been published yet. The desk keeps its existing
          posture until checked evidence arrives.
        </p>
      )}
    </div>
  )
}

function SignalTape({ signals }: { signals: PublicSignal[] }) {
  return (
    <div className="signal-tape">
      <span>Recent signal record</span>
      {signals.length ? (
        <ol>
          {signals.slice(0, 4).map((signal) => (
            <li key={signal.id}>
              <time dateTime={signal.timestamp}>{formatClockTime(signal.timestamp)}</time>
              <strong>{signal.instrument}</strong>
              <b>{signal.side}</b>
            </li>
          ))}
        </ol>
      ) : (
        <p>No signal record is available. Nothing is inferred from the absence.</p>
      )}
    </div>
  )
}

function service(
  services: PublicServiceHealth[],
  name: string,
): PublicServiceHealth | undefined {
  return services.find((item) => item.name === name)
}

export function EvidenceWatch({
  widgets,
  error,
}: {
  widgets: PublicWidgets | null
  error: string
}) {
  const clips = widgets?.research.clips ?? []
  const signals = widgets?.recent_signals ?? []
  const services = widgets?.business_health.services ?? []
  const gate = widgets?.gate.state
  const executor = widgets
    ? widgets.gate.executor_alive
      ? 'current'
      : gate === 'armed'
        ? 'offline'
        : 'protected'
    : undefined
  const watch = [
    { label: 'Trading gate', value: widgets?.gate.label ?? NOT_OBSERVED, state: gate },
    {
      label: 'Execution process',
      value: widgets ? (widgets.gate.executor_alive ? 'Running' : 'Stopped') : NOT_OBSERVED,
      state: executor,
    },
    {
      label: 'Decision relay',
      value: displayStatus(widgets?.system_health.telegram),
      state: widgets?.system_health.telegram,
    },
    {
      label: 'Signal intake',
      value: displayStatus(widgets?.tradingview.status),
      state: widgets?.tradingview.status,
    },
    {
      label: 'Primary compute',
      value: displayStatus(service(services, 'gpu_gateway')?.status),
      state: service(services, 'gpu_gateway')?.status,
    },
    {
      label: 'Control plane',
      value: displayStatus(service(services, 'ops_server')?.status),
      state: service(services, 'ops_server')?.status,
    },
  ]
  const policy = widgets?.research.policy

  return (
    <section
      id="evidence"
      aria-labelledby="evidence-watch-title"
      className="evidence-watch scroll-mt-24"
    >
      <header className="evidence-watch-head">
        <div>
          <span>Evidence watch</span>
          <h2 id="evidence-watch-title">What changed around the desk.</h2>
        </div>
        <p>
          Reviewed notes and signal observations can challenge the posture.
          The watchboard beside them shows whether the operating rail is reachable.
        </p>
      </header>

      <div className="evidence-watch-body">
        <div>
          <EvidenceReel clips={clips} />
          <SignalTape signals={signals} />
        </div>

        <aside className="system-watch" aria-label="System watch">
          <div className="evidence-subhead">
            <span>System watch</span>
            <strong>
              {widgets?.rendered_at
                ? `Observed ${formatClockTime(widgets.rendered_at)}`
                : NOT_OBSERVED}
            </strong>
          </div>
          <dl>
            {watch.map((item) => (
              <div key={item.label}>
                <dt>{item.label}</dt>
                <dd className={statusTone(item.state)}>
                  <i aria-hidden="true" />
                  {item.value}
                </dd>
              </div>
            ))}
          </dl>
        </aside>
      </div>

      <div className="evidence-policy" aria-label="Evidence authority limits">
        <div>
          <span>Corroboration</span>
          <strong>
            {policy
              ? `${policy.minimum_independent_checks} independent checks`
              : NOT_OBSERVED}
          </strong>
        </div>
        <div>
          <span>Concentration</span>
          <strong>{policy ? `${policyPercent(policy.single_input_cap)} input cap` : NOT_OBSERVED}</strong>
        </div>
        <div>
          <span>Conviction</span>
          <strong>
            {policy
              ? policy.can_set_conviction
                ? 'May influence'
                : 'Cannot set conviction'
              : NOT_OBSERVED}
          </strong>
        </div>
        <div>
          <span>Execution</span>
          <strong>
            {policy
              ? policy.can_authorize_execution
                ? 'May authorize'
                : 'Cannot authorize execution'
              : NOT_OBSERVED}
          </strong>
        </div>
      </div>

      {error ? (
        <p className="evidence-watch-error">
          Watchboard unavailable: {error}. The last received reading remains visible.
        </p>
      ) : null}
    </section>
  )
}
