import { useEffect, useRef, useState } from 'react'

type Money = {
  amount_minor: number
  currency: string
  scale: number
}

type Parameter = {
  name: string
  value: string | number
  unit: string
}

type Financial = {
  account: string
  symbol: string
  asset: string
  side: string
  quantity: { value: number; unit: string } | null
  max_notional: Money | null
  order_type: string
  limit_price: Money | null
  stop_price: Money | null
  time_in_force: string
  estimated_fees: Money
  max_slippage_bps: number
  market_hours_policy: string
}

export const RENDERED_ACTION_FIELDS = [
  'action_id',
  'action_kind',
  'atomic_group',
  'environment',
  'account',
  'destination',
  'parameters',
  'units',
  'max_cost',
  'max_slippage_bps',
  'target_revision_sha256',
  'idempotency_key',
  'preconditions',
  'expected_effects',
  'verification',
  'rollback',
  'kill_switch',
  'residual_risks',
  'financial',
] as const

export const RENDERED_FINANCIAL_FIELDS = [
  'account',
  'symbol',
  'asset',
  'side',
  'quantity',
  'max_notional',
  'order_type',
  'limit_price',
  'stop_price',
  'time_in_force',
  'estimated_fees',
  'max_slippage_bps',
  'market_hours_policy',
] as const

export const RENDERED_REVIEW_FIELDS = [
  'reviewer',
  'reviewer_class',
  'verdict',
  'reviewed_at',
  'candidate_sha256',
  'artifact_sha256',
] as const

export type ApprovalAction = {
  action_id: string
  action_kind: string
  atomic_group: string
  environment: string
  account: string
  destination: string
  parameters: Parameter[]
  units: string
  max_cost: Money
  max_slippage_bps: number
  target_revision_sha256: string
  idempotency_key: string
  preconditions: string[]
  expected_effects: string[]
  verification: string[]
  rollback: string[]
  kill_switch: string
  residual_risks: string[]
  financial: Financial | null
}

export type ApprovalBundleDTO = {
  schema_version: string
  bundle_id: string
  canonical_sha256: string
  rev: number
  status: string
  created_at: string
  compiled_at: string
  compile_receipt_sha256: string
  expires_at: string
  server_time: string
  creator: string
  purpose_class: string
  scope: {
    environment: string
    account: string
    destination: string
  }
  actions: ApprovalAction[]
  execution_policy: {
    failure_mode: string
    atomic_groups: string[]
  }
  partial_outcome_semantics: string
  independent_review: {
    reviewer: string
    reviewer_class: string
    verdict: string
    reviewed_at: string
    candidate_sha256: string
    artifact_sha256: string
  }
  approval_statement: string
  approval_policy: {
    approver_identity: string
    approver_class: string
  }
  dependency_pins: {
    pin_set_sha256: string
    compiler_candidate_commit: string
    compiler_candidate_tree: string
    compiler_result_sha256: string
    compiler_review_sha256: string
    fleet_lease_commit: string
    fleet_lease_tree: string
    fleet_lease_result_sha256: string
    fleet_lease_review_sha256: string
    fleet_lease_version: string
    approval_schema_version: string
    approval_source_sha256: string
    fleet_core_source_sha256: string
    approval_harness_commit: string
    approval_harness_tree: string
    consumer_commit: string
    consumer_tree: string
    consumer_result_sha256: string
    consumer_review_sha256: string
    consumer_source_sha256: string
    production_execution_available: number
  }
  eligibility: {
    eligible: boolean
    reason_code: string
  }
  consumer_state: 'DISARMED'
  etag: string
}

export type Challenge = {
  csrf_challenge: string
  expires_at: string
}

type ApprovalViewProps = {
  bundle: ApprovalBundleDTO
  challenge: Challenge | null
  busy: boolean
  message: string
  onReauthenticate: () => void
  onDecision: (decision: 'APPROVE' | 'REFUSE') => void
}

const REASON_COPY: Record<string, string> = {
  ELIGIBLE: 'Every server-side precondition is current.',
  READ_ONLY_BOOTSTRAP:
    'This rail is installed inertly. A separate legacy attended enablement is still required.',
  BUNDLE_EXPIRED: 'The exact bundle expired. Create and independently review a new bundle.',
  BUNDLE_CHANGED: 'The digest or revision changed. This browser snapshot has no authority.',
  BUNDLE_INCOMPLETE: 'The authoritative bundle is incomplete.',
  BUNDLE_INVALID: 'The registry chain did not reconstruct exactly.',
  INDEPENDENT_REVIEW_INVALID: 'The independent review is absent, stale, or invalid.',
  OWNER_POLICY_MISMATCH: 'The authenticated owner does not match the exact approver policy.',
  CONTROL_PLANE_SELF_MODIFICATION:
    'This bundle could modify the approval rail or its authority boundary.',
  ALREADY_DECIDED: 'A terminal decision or lifecycle transition is already recorded.',
  DEPENDENCY_MISMATCH: 'An accepted source, package, schema, or review identity changed.',
  SERVER_STATE_STALE:
    'The last server projection is stale or internally inconsistent. Refresh before deciding.',
}

const MAX_SERVER_STATE_AGE_MS = 5_000

export function groupDigest(digest: string): string {
  return digest.match(/.{1,8}/g)?.join(' ') ?? digest
}

export function countdownLabel(expiresAt: string, now = new Date()): string {
  const remaining = Math.max(
    0,
    Math.floor((new Date(expiresAt).getTime() - now.getTime()) / 1000),
  )
  if (remaining === 0) return 'Expired'
  if (remaining < 60) return `Expires in ${remaining} second${remaining === 1 ? '' : 's'}`
  const minutes = Math.ceil(remaining / 60)
  return `Expires in ${minutes} minute${minutes === 1 ? '' : 's'}`
}

export function serverNowFromMonotonic(
  serverTime: string,
  anchorMonotonicMs: number,
  currentMonotonicMs: number,
): Date {
  return new Date(
    new Date(serverTime).getTime() +
      Math.max(0, currentMonotonicMs - anchorMonotonicMs),
  )
}

export function serverAuthorityCurrent(
  serverTime: string,
  bundleExpiresAt: string,
  challengeExpiresAt: string | null,
  now: Date,
): boolean {
  const serverTimeMs = Date.parse(serverTime)
  const bundleExpiresMs = Date.parse(bundleExpiresAt)
  const challengeExpiresMs =
    challengeExpiresAt === null ? null : Date.parse(challengeExpiresAt)
  const nowMs = now.getTime()
  return (
    Number.isFinite(serverTimeMs) &&
    Number.isFinite(bundleExpiresMs) &&
    Number.isFinite(nowMs) &&
    bundleExpiresMs > serverTimeMs &&
    nowMs >= serverTimeMs &&
    nowMs - serverTimeMs <= MAX_SERVER_STATE_AGE_MS &&
    nowMs < bundleExpiresMs &&
    (challengeExpiresMs === null ||
      (Number.isFinite(challengeExpiresMs) &&
        challengeExpiresMs > nowMs &&
        challengeExpiresMs <= bundleExpiresMs))
  )
}

function EvidenceList({ title, values }: { title: string; values: string[] }) {
  return (
    <section className="evidence-list">
      <h4>{title}</h4>
      <ul>
        {values.map((value) => (
          <li key={value}>{value}</li>
        ))}
      </ul>
    </section>
  )
}

function MoneyValue({ value }: { value: Money | null }) {
  if (value === null) return <span>Not applicable</span>
  return (
    <span className="mono">
      {value.amount_minor} minor {value.currency} · scale {value.scale}
    </span>
  )
}

function ActionLedger({ action, index }: { action: ApprovalAction; index: number }) {
  return (
    <details className="action-ledger" open>
      <summary>
        <span className="action-ordinal">{String(index + 1).padStart(2, '0')}</span>
        <span>
          <strong>{action.action_id}</strong>
          <small>
            {action.action_kind} · group {action.atomic_group}
          </small>
        </span>
      </summary>

      <div className="action-body">
        <dl className="evidence-grid">
          <div>
            <dt>Environment</dt>
            <dd className="mono">{action.environment}</dd>
          </div>
          <div>
            <dt>Account</dt>
            <dd className="mono">{action.account}</dd>
          </div>
          <div>
            <dt>Destination</dt>
            <dd className="mono">{action.destination}</dd>
          </div>
          <div>
            <dt>Target revision</dt>
            <dd className="mono">{action.target_revision_sha256}</dd>
          </div>
          <div>
            <dt>One-use action key</dt>
            <dd className="mono">{action.idempotency_key}</dd>
          </div>
          <div>
            <dt>Action units</dt>
            <dd className="mono">{action.units}</dd>
          </div>
          <div>
            <dt>Bound cost</dt>
            <dd>
              <MoneyValue value={action.max_cost} />
            </dd>
          </div>
          <div>
            <dt>Slippage cap</dt>
            <dd className="mono">{action.max_slippage_bps} bps</dd>
          </div>
        </dl>

        <section className="parameters">
          <h4>Exact parameters</h4>
          <dl>
            {action.parameters.map((parameter) => (
              <div key={parameter.name}>
                <dt>{parameter.name}</dt>
                <dd className="mono">
                  {String(parameter.value)} · {parameter.unit}
                </dd>
              </div>
            ))}
          </dl>
        </section>

        {action.financial ? (
          <section className="financial-terms">
            <h4>Financial terms</h4>
            <dl className="evidence-grid">
              <div>
                <dt>Side / quantity</dt>
                <dd className="mono">
                  {action.financial.side} {action.financial.quantity?.value}{' '}
                  {action.financial.quantity?.unit}
                </dd>
              </div>
              <div>
                <dt>Order / time</dt>
                <dd className="mono">
                  {action.financial.order_type} · {action.financial.time_in_force}
                </dd>
              </div>
              <div>
                <dt>Symbol</dt>
                <dd className="mono">{action.financial.symbol}</dd>
              </div>
              <div>
                <dt>Financial account</dt>
                <dd className="mono">{action.financial.account}</dd>
              </div>
              <div>
                <dt>Asset</dt>
                <dd className="mono">{action.financial.asset}</dd>
              </div>
              <div>
                <dt>Limit</dt>
                <dd>
                  <MoneyValue value={action.financial.limit_price} />
                </dd>
              </div>
              <div>
                <dt>Maximum notional</dt>
                <dd>
                  <MoneyValue value={action.financial.max_notional} />
                </dd>
              </div>
              <div>
                <dt>Stop</dt>
                <dd>
                  <MoneyValue value={action.financial.stop_price} />
                </dd>
              </div>
              <div>
                <dt>Estimated fees</dt>
                <dd>
                  <MoneyValue value={action.financial.estimated_fees} />
                </dd>
              </div>
              <div>
                <dt>Financial slippage cap</dt>
                <dd className="mono">{action.financial.max_slippage_bps} bps</dd>
              </div>
              <div>
                <dt>Market hours</dt>
                <dd>{action.financial.market_hours_policy}</dd>
              </div>
            </dl>
          </section>
        ) : null}

        <div className="action-evidence">
          <EvidenceList title="Preconditions" values={action.preconditions} />
          <EvidenceList title="Expected effects" values={action.expected_effects} />
          <EvidenceList title="Verification" values={action.verification} />
          <EvidenceList title="Rollback / cancellation" values={action.rollback} />
          <EvidenceList title="Residual risks" values={action.residual_risks} />
          <section className="evidence-list">
            <h4>Kill switch</h4>
            <p>{action.kill_switch}</p>
          </section>
        </div>
      </div>
    </details>
  )
}

function HashRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="hash-row">
      <dt>{label}</dt>
      <dd className="mono">{value}</dd>
    </div>
  )
}

export function ApprovalView({
  bundle,
  challenge,
  busy,
  message,
  onReauthenticate,
  onDecision,
}: ApprovalViewProps) {
  const anchorMonotonic = useRef(performance.now())
  const [now, setNow] = useState(() => new Date(bundle.server_time))
  const resultHeading = useRef<HTMLHeadingElement>(null)

  useEffect(() => {
    anchorMonotonic.current = performance.now()
    setNow(new Date(bundle.server_time))
    const interval = window.setInterval(
      () =>
        setNow(
          serverNowFromMonotonic(
            bundle.server_time,
            anchorMonotonic.current,
            performance.now(),
          ),
        ),
      250,
    )
    return () => window.clearInterval(interval)
  }, [bundle.server_time])

  useEffect(() => {
    if (message) resultHeading.current?.focus()
  }, [message])

  const serverCurrent = serverAuthorityCurrent(
    bundle.server_time,
    bundle.expires_at,
    challenge?.expires_at ?? null,
    now,
  )
  const eligible = bundle.eligibility.eligible && serverCurrent
  const challengeCurrent =
    challenge !== null &&
    serverCurrent &&
    new Date(challenge.expires_at).getTime() > now.getTime()
  const canDecide = eligible && challengeCurrent && !busy
  const effectiveReason = serverCurrent
    ? bundle.eligibility.reason_code
    : 'SERVER_STATE_STALE'
  const reasonCopy =
    REASON_COPY[effectiveReason] ??
    'The server refused this exact decision state.'

  return (
    <main className="approval-shell">
      <header className="rail-header">
        <div>
          <p className="eyebrow">Sapphire owner rail · local attended boundary</p>
          <h1>One exact decision.</h1>
        </div>
        <div className="header-state">
          <span className={`state-mark ${eligible ? 'state-mark--verified' : ''}`}>
            {effectiveReason}
          </span>
          <span className="mono">rev {bundle.rev}</span>
        </div>
      </header>

      {message ? (
        <section className="decision-result" aria-live="polite">
          <h2 ref={resultHeading} tabIndex={-1}>
            {message}
          </h2>
        </section>
      ) : null}

      <section className="hash-spine" aria-labelledby="exact-bundle-heading">
        <div>
          <p className="eyebrow">Exact bundle</p>
          <h2 id="exact-bundle-heading">{bundle.bundle_id}</h2>
        </div>
        <div className="digest-band">
          <span className="sr-only">
            Full canonical SHA-256: {bundle.canonical_sha256}
          </span>
          <code aria-hidden="true">{groupDigest(bundle.canonical_sha256)}</code>
          <button
            type="button"
            className="copy-digest"
            aria-label="Copy full canonical bundle SHA-256"
            onClick={() => void navigator.clipboard.writeText(bundle.canonical_sha256)}
          >
            Copy full digest
          </button>
        </div>
      </section>

      <div className="rail-columns">
        <aside className="bundle-evidence" aria-label="Bundle evidence">
          <section>
            <p className="eyebrow">Authority object</p>
            <dl className="stacked-definitions">
              <div>
                <dt>Status</dt>
                <dd>{bundle.status}</dd>
              </div>
              <div>
                <dt>Purpose</dt>
                <dd>{bundle.purpose_class}</dd>
              </div>
              <div>
                <dt>Creator</dt>
                <dd>{bundle.creator}</dd>
              </div>
              <div>
                <dt>Display schema</dt>
                <dd className="mono">{bundle.schema_version}</dd>
              </div>
              <div>
                <dt>Created</dt>
                <dd>
                  <time dateTime={bundle.created_at}>{bundle.created_at}</time>
                </dd>
              </div>
              <div>
                <dt>Compiled</dt>
                <dd>
                  <time dateTime={bundle.compiled_at}>{bundle.compiled_at}</time>
                </dd>
              </div>
              <div>
                <dt>Expires</dt>
                <dd>
                  <time dateTime={bundle.expires_at}>{bundle.expires_at}</time>
                </dd>
              </div>
            </dl>
          </section>

          <section>
            <h3>Exact scope</h3>
            <dl className="stacked-definitions">
              <HashRow label="Environment" value={bundle.scope.environment} />
              <HashRow label="Account" value={bundle.scope.account} />
              <HashRow label="Destination" value={bundle.scope.destination} />
            </dl>
          </section>

          <section>
            <h3>Review trace</h3>
            <dl className="stacked-definitions">
              <div>
                <dt>Verdict</dt>
                <dd>{bundle.independent_review.verdict}</dd>
              </div>
              <div>
                <dt>Reviewer</dt>
                <dd>{bundle.independent_review.reviewer}</dd>
              </div>
              <div>
                <dt>Reviewer class</dt>
                <dd>{bundle.independent_review.reviewer_class}</dd>
              </div>
              <div>
                <dt>Reviewed</dt>
                <dd>
                  <time dateTime={bundle.independent_review.reviewed_at}>
                    {bundle.independent_review.reviewed_at}
                  </time>
                </dd>
              </div>
              <HashRow
                label="Candidate"
                value={bundle.independent_review.candidate_sha256}
              />
              <HashRow
                label="Review artifact"
                value={bundle.independent_review.artifact_sha256}
              />
              <HashRow
                label="Compile receipt"
                value={bundle.compile_receipt_sha256}
              />
              <HashRow
                label="Dependency pin set"
                value={bundle.dependency_pins.pin_set_sha256}
              />
              <HashRow
                label="Compiler candidate commit"
                value={bundle.dependency_pins.compiler_candidate_commit}
              />
              <HashRow
                label="Compiler candidate tree"
                value={bundle.dependency_pins.compiler_candidate_tree}
              />
              <HashRow
                label="Compiler result"
                value={bundle.dependency_pins.compiler_result_sha256}
              />
              <HashRow
                label="Compiler review"
                value={bundle.dependency_pins.compiler_review_sha256}
              />
              <HashRow
                label="Installed fleet-lease commit"
                value={bundle.dependency_pins.fleet_lease_commit}
              />
              <HashRow
                label="Installed fleet-lease tree"
                value={bundle.dependency_pins.fleet_lease_tree}
              />
              <HashRow
                label="Installed package result"
                value={bundle.dependency_pins.fleet_lease_result_sha256}
              />
              <HashRow
                label="Installed package review"
                value={bundle.dependency_pins.fleet_lease_review_sha256}
              />
              <HashRow
                label="Approval source"
                value={bundle.dependency_pins.approval_source_sha256}
              />
              <HashRow
                label="Fleet core source"
                value={bundle.dependency_pins.fleet_core_source_sha256}
              />
              <HashRow
                label="Approval harness commit"
                value={bundle.dependency_pins.approval_harness_commit}
              />
              <HashRow
                label="Approval harness tree"
                value={bundle.dependency_pins.approval_harness_tree}
              />
              <HashRow
                label="Consumer commit"
                value={bundle.dependency_pins.consumer_commit}
              />
              <HashRow
                label="Consumer tree"
                value={bundle.dependency_pins.consumer_tree}
              />
              <HashRow
                label="Consumer result"
                value={bundle.dependency_pins.consumer_result_sha256}
              />
              <HashRow
                label="Consumer review"
                value={bundle.dependency_pins.consumer_review_sha256}
              />
              <HashRow
                label="Consumer source"
                value={bundle.dependency_pins.consumer_source_sha256}
              />
              <div>
                <dt>Installed package / schema</dt>
                <dd className="mono">
                  fleet-lease {bundle.dependency_pins.fleet_lease_version} · approval{' '}
                  {bundle.dependency_pins.approval_schema_version}
                </dd>
              </div>
              <div>
                <dt>Production execution</dt>
                <dd className="mono">
                  {bundle.dependency_pins.production_execution_available === 0
                    ? 'UNAVAILABLE'
                    : 'UNEXPECTEDLY AVAILABLE'}
                </dd>
              </div>
            </dl>
          </section>
        </aside>

        <section className="ordered-actions" aria-labelledby="ordered-actions-heading">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Immutable source order</p>
              <h2 id="ordered-actions-heading">Ordered action ledger</h2>
            </div>
            <span className="mono">{bundle.actions.length} exact actions</span>
          </div>

          <div className="policy-strip">
            <strong>{bundle.execution_policy.failure_mode}</strong>
            <span>
              {bundle.partial_outcome_semantics} Atomic groups:{' '}
              {bundle.execution_policy.atomic_groups.join(', ')}
            </span>
          </div>

          {bundle.actions.map((action, index) => (
            <ActionLedger key={action.action_id} action={action} index={index} />
          ))}
        </section>

        <aside className="decision-well" aria-labelledby="attended-decision-heading">
          <p className="eyebrow">Attended decision</p>
          <h2 id="attended-decision-heading">Approval is not execution.</h2>
          <p className="decision-statement">{bundle.approval_statement}</p>
          <dl className="stacked-definitions">
            <div>
              <dt>Approver identity</dt>
              <dd className="mono">{bundle.approval_policy.approver_identity}</dd>
            </div>
            <div>
              <dt>Approver class</dt>
              <dd className="mono">{bundle.approval_policy.approver_class}</dd>
            </div>
            <HashRow label="Projection ETag" value={bundle.etag} />
          </dl>

          <div className="consumer-state">
            <span>Consumer {bundle.consumer_state.toLowerCase()}</span>
            <strong>{countdownLabel(bundle.expires_at, now)}</strong>
          </div>

          <div
            className={`eligibility-banner ${eligible ? 'eligibility-banner--verified' : ''}`}
            role="status"
          >
            <strong>{effectiveReason}</strong>
            <span>{reasonCopy}</span>
          </div>

          {!challengeCurrent && eligible ? (
            <section className="reauth-block">
              <p>
                Basic authentication verifies the configured credential. A browser
                may resend a cached credential; this is not biometric or passkey
                proof of human presence.
              </p>
              <button
                type="button"
                className="reauth-button"
                disabled={busy}
                onClick={onReauthenticate}
              >
                Re-verify owner
              </button>
            </section>
          ) : null}

          {challengeCurrent && eligible ? (
            <p className="challenge-window" aria-live="polite">
              Decision window · {countdownLabel(challenge.expires_at, now)}
            </p>
          ) : null}

          {canDecide ? (
            <div className="decision-controls">
              <button
                type="button"
                className="decision-approve"
                onClick={() => onDecision('APPROVE')}
              >
                Approve exact bundle
              </button>
              <button
                type="button"
                className="decision-refuse"
                onClick={() => onDecision('REFUSE')}
              >
                Refuse bundle
              </button>
            </div>
          ) : null}

          <p className="separation-note">
            A decision records authority only. Nothing here invokes a connector,
            deployment, order, cancellation, or external action.
          </p>
        </aside>
      </div>
    </main>
  )
}

function bundleIdFromPath(): string {
  const match = window.location.pathname.match(/^\/operator\/approvals\/([a-z0-9._:-]+)$/)
  if (!match) throw new Error('BUNDLE_PATH_INVALID')
  return match[1]
}

async function readJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as
      | { detail?: string }
      | null
    throw new Error(body?.detail ?? `HTTP_${response.status}`)
  }
  return response.json() as Promise<T>
}

export default function ApprovalApp() {
  const [bundle, setBundle] = useState<ApprovalBundleDTO | null>(null)
  const [challenge, setChallenge] = useState<Challenge | null>(null)
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const errorHeading = useRef<HTMLHeadingElement>(null)
  const bundleId = bundleIdFromPath()
  const endpoint = `/api/operator/v1/approval-bundles/${encodeURIComponent(bundleId)}`

  async function load(): Promise<void> {
    const current = await readJson<ApprovalBundleDTO>(
      await fetch(endpoint, {
        credentials: 'same-origin',
        cache: 'no-store',
        headers: { Accept: 'application/json' },
      }),
    )
    setBundle(current)
    setError('')
  }

  useEffect(() => {
    void load().catch((reason: unknown) => {
      setError(reason instanceof Error ? reason.message : 'BUNDLE_LOAD_FAILED')
    })
  }, [])

  useEffect(() => {
    const refresh = () => {
      void load().catch((reason: unknown) => {
        setChallenge(null)
        setError(reason instanceof Error ? reason.message : 'BUNDLE_REFRESH_FAILED')
      })
    }
    const interval = window.setInterval(refresh, 2_000)
    window.addEventListener('focus', refresh)
    document.addEventListener('visibilitychange', refresh)
    return () => {
      window.clearInterval(interval)
      window.removeEventListener('focus', refresh)
      document.removeEventListener('visibilitychange', refresh)
    }
  }, [])

  useEffect(() => {
    if (error) errorHeading.current?.focus()
  }, [error])

  async function reauthenticate(): Promise<void> {
    setBusy(true)
    setError('')
    try {
      const issued = await readJson<Challenge>(
        await fetch(`${endpoint}/reauth`, {
          method: 'POST',
          credentials: 'same-origin',
          cache: 'no-store',
          headers: { 'Content-Type': 'application/json' },
          body: '{}',
        }),
      )
      setChallenge(issued)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'REAUTH_FAILED')
    } finally {
      setBusy(false)
    }
  }

  async function decide(decision: 'APPROVE' | 'REFUSE'): Promise<void> {
    if (!bundle || !challenge) return
    setBusy(true)
    setError('')
    try {
      const result = await readJson<{ message: string }>(
        await fetch(`${endpoint}/decision`, {
          method: 'POST',
          credentials: 'same-origin',
          cache: 'no-store',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            decision,
            canonical_sha256: bundle.canonical_sha256,
            expected_rev: bundle.rev,
            csrf_challenge: challenge.csrf_challenge,
          }),
        }),
      )
      setChallenge(null)
      setMessage(result.message)
      await load()
    } catch (reason) {
      setChallenge(null)
      setError(reason instanceof Error ? reason.message : 'DECISION_REFUSED')
      await load().catch(() => undefined)
    } finally {
      setBusy(false)
    }
  }

  if (error && !bundle) {
    return (
      <main className="approval-load-state" role="alert">
        <p className="eyebrow">Owner rail unavailable</p>
        <h1 ref={errorHeading} tabIndex={-1}>
          {error}
        </h1>
        <p>No private bundle details were loaded.</p>
      </main>
    )
  }

  if (!bundle) {
    return (
      <main className="approval-load-state" aria-live="polite">
        <p className="eyebrow">Local owner rail</p>
        <h1>Reconstructing the exact bundle…</h1>
      </main>
    )
  }

  return (
    <>
      {error ? (
        <section className="error-summary" role="alert">
          <h2 ref={errorHeading} tabIndex={-1}>
            Decision unavailable · {error}
          </h2>
          <p>The authoritative server state replaced the browser snapshot.</p>
        </section>
      ) : null}
      <ApprovalView
        bundle={bundle}
        challenge={challenge}
        busy={busy}
        message={message}
        onReauthenticate={() => void reauthenticate()}
        onDecision={(decision) => void decide(decision)}
      />
    </>
  )
}
