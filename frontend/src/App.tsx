import { useMemo, useState } from 'react'
import type { KeyboardEvent } from 'react'
import { narrate } from '@shared/narrate'
import { describeAgent, describeNode } from '@shared/vocabulary'
import { shortBuildValue } from '@shared/build'
import { useFleet } from './hooks/useFleet'
import { useBuildIdentity } from './hooks/useBuildIdentity'
import { useLiveTelemetry } from './hooks/useLiveTelemetry'
import { useMossSnapshot } from './hooks/useMossSnapshot'
import { usePublicWidgets } from './hooks/usePublicWidgets'
import {
  formatAge,
  formatClockTime,
  formatCount,
  formatObservedAt,
  NOT_OBSERVED,
} from './desk/format'
import type {
  FleetCounts,
  FleetData,
  LiveEvent,
  LiveSnapshot,
  MossSnapshot,
  PublicWidgets,
} from './types'

type EvidenceTone = 'current' | 'held' | 'degraded' | 'unknown'

interface EvidenceSegment {
  id: string
  label: string
  value: string
  source: string
  observedAt: string
  freshness: string
  authority: string
  uncertainty: string
  tone: EvidenceTone
}

interface AttentionItem {
  label: string
  detail: string
  tone: EvidenceTone
}

const SECTIONS = [
  { href: '#thesis', label: 'Thesis' },
  { href: '#attention', label: 'Attention' },
  { href: '#timeline', label: 'Changed' },
  { href: '#evidence', label: 'Evidence' },
]
const RUNTIME_TTL_SECONDS = 180
const RESEARCH_TTL_MS = 24 * 60 * 60 * 1000

function words(value: string | null | undefined) {
  return value ? value.replace(/_/g, ' ') : NOT_OBSERVED
}

function observedTime(value: string | null | undefined) {
  return formatObservedAt(value)
}

function isFleetCounts(fleet: FleetData | FleetCounts): fleet is FleetCounts {
  return !('counts' in fleet)
}

function fleetCount(fleet: FleetData | FleetCounts | null, key: 'leases' | 'gates') {
  if (
    !fleet ||
    fleet.snapshot_age_s == null ||
    fleet.snapshot_age_s > RUNTIME_TTL_SECONDS
  ) return null
  if (isFleetCounts(fleet)) return key === 'leases' ? fleet.leases : fleet.gates_open
  return key === 'leases' ? fleet.counts.leases : fleet.counts.gates_open
}

function toneForValue(value: string | null | undefined): EvidenceTone {
  const normalized = String(value ?? '').toLowerCase()
  if (!normalized || normalized === NOT_OBSERVED || normalized === 'unknown') return 'unknown'
  if (['halted', 'off', 'gated', 'disarmed', 'read-only'].includes(normalized)) return 'held'
  if (['stale', 'delayed', 'degraded', 'down', 'offline', 'failed'].includes(normalized)) {
    return 'degraded'
  }
  if (['live', 'current', 'healthy', 'verified', 'working', 'recovered', 'observed'].includes(normalized)) {
    return 'current'
  }
  return 'unknown'
}

function percent(value: number | null | undefined, digits = 0) {
  return value == null ? NOT_OBSERVED : `${(value * 100).toFixed(digits)}%`
}

function currentResearch(snapshot: LiveSnapshot | null, liveError: string) {
  if (
    liveError ||
    snapshot?.status !== 'live' ||
    snapshot.freshness_s == null ||
    snapshot.freshness_s > RUNTIME_TTL_SECONDS ||
    !snapshot.research
  ) {
    return null
  }
  const observedAt = Date.parse(snapshot.research.observed_at)
  const ageMs = Date.now() - observedAt
  if (!Number.isFinite(observedAt) || ageMs < 0 || ageMs > RESEARCH_TTL_MS) return null
  return snapshot.research
}

const STORY_PAGES = [
  { href: '/dashboard/', label: 'Overview', key: 'overview' },
  { href: '/dashboard/architecture', label: 'Architecture', key: 'architecture' },
  { href: '/dashboard/pipeline', label: 'Request flow', key: 'pipeline' },
  { href: '/dashboard/models', label: 'Models', key: 'models' },
  { href: '/dashboard/ai-today', label: 'AI today', key: 'ai-today' },
] as const

type StoryPage = (typeof STORY_PAGES)[number]['key']

const SYSTEM_LAYERS = [
  {
    number: '01',
    title: 'One private doorway',
    label: 'Telegram',
    detail: 'A direct conversation with one verified owner. No public command surface.',
  },
  {
    number: '02',
    title: 'One conductor',
    label: 'OpenClaw',
    detail: 'Holds the conversation, chooses tools, keeps schedules, and reports back.',
  },
  {
    number: '03',
    title: 'The right engine',
    label: 'Local + cloud models',
    detail: 'Routes private, fast, or difficult work to the model that fits the job.',
  },
  {
    number: '04',
    title: 'Durable memory',
    label: 'Knowledge vault',
    detail: 'Research, decisions, and receipts remain useful after a chat window closes.',
  },
  {
    number: '05',
    title: 'A visible result',
    label: 'Briefs + dashboard',
    detail: 'The owner gets a concise update, with evidence and the next decision attached.',
  },
] as const

const REQUEST_STEPS = [
  {
    number: '01',
    title: 'Ask naturally',
    copy: 'The owner sends a message, forwards an idea, or lets a scheduled brief begin on time.',
    output: 'A single admitted request',
  },
  {
    number: '02',
    title: 'Understand the job',
    copy: 'OpenClaw loads the relevant context, identifies the outcome, and separates research from action.',
    output: 'A bounded plan',
  },
  {
    number: '03',
    title: 'Choose the engine',
    copy: 'Private or routine work can stay local. Harder reasoning can use a frontier model when the boundary allows it.',
    output: 'A deliberate model route',
  },
  {
    number: '04',
    title: 'Research and verify',
    copy: 'Tools gather current primary sources, compare claims, and save durable evidence instead of a loose chat summary.',
    output: 'Cited findings + receipts',
  },
  {
    number: '05',
    title: 'Pause before impact',
    copy: 'Messages, releases, money, credentials, and machine changes stop at a clear owner-controlled boundary.',
    output: 'Approval when it matters',
  },
  {
    number: '06',
    title: 'Report back',
    copy: 'The assistant returns the outcome first: what changed, what proves it, what is blocked, and what comes next.',
    output: 'A useful personal update',
  },
] as const

const MODEL_LANES = [
  {
    label: 'Conductor',
    title: 'OpenClaw',
    badge: 'Framework',
    copy: 'The persistent agent layer. It owns the conversation, schedules, tool use, memory handoff, and the return path to Telegram.',
    note: 'The conductor stays stable while model engines can change.',
  },
  {
    label: 'Home compute',
    title: 'Ollama + open-weight models',
    badge: 'Private lane',
    copy: 'Routine triage and sensitive context can run on the Windows GPU without sending the prompt to a model provider.',
    note: 'Qwen, Nemotron, GLM, and North Mini variants have been evaluated locally; evaluation is not the same as production admission.',
  },
  {
    label: 'Frontier reasoning',
    title: 'Codex + selected APIs',
    badge: 'Capability lane',
    copy: 'Complex coding, planning, and multimodal work can use a frontier service when the task benefits and the data boundary permits it.',
    note: 'Cloud capability is a route, not the operating system.',
  },
  {
    label: 'Long-lived context',
    title: 'The knowledge vault',
    badge: 'Memory layer',
    copy: 'Curated notes, research, decisions, and source trails give each engine the same durable institutional memory.',
    note: 'Memory is retrieved for a job; the public dashboard never exposes the private vault.',
  },
] as const

const AI_PATTERNS = [
  {
    category: 'Automation',
    title: 'Briefs are becoming scheduled services',
    copy: 'An assistant can wake on a schedule or event, gather the right context, complete a bounded job, and return with the result.',
  },
  {
    category: 'Tool use',
    title: 'Models increasingly act through software',
    copy: 'The useful shift is from answering a prompt to navigating tools, checking work, and producing a durable artifact.',
  },
  {
    category: 'Coordination',
    title: 'Parallel work is becoming visible',
    copy: 'Large tasks can be divided among focused workers, reconciled against one plan, and returned as a single understandable outcome.',
  },
  {
    category: 'Context',
    title: 'Memory now outlives a chat window',
    copy: 'Long-lived context and retrieval let an assistant reuse research, preferences, and decisions without asking the owner to start over.',
  },
  {
    category: 'Deployment',
    title: 'Open-weight models strengthen the private lane',
    copy: 'More capable models can run on owner-controlled hardware, making privacy, cost, and fallback real architectural choices.',
  },
  {
    category: 'Governance',
    title: 'Action boundaries matter more as autonomy grows',
    copy: 'The strongest systems separate automatic preparation from consequential actions that still require explicit human authority.',
  },
] as const

function pageFromPath(pathname: string): StoryPage {
  const normalized = pathname.replace(/\/+$/, '') || '/dashboard'
  const matched = STORY_PAGES.find((page) => page.href.replace(/\/+$/, '') === normalized)
  return matched?.key ?? 'overview'
}

function StoryHeader({ active }: { active: StoryPage }) {
  return (
    <header className="story-header">
      <a className="story-brand" href="/" aria-label="Sapphire Alpha home">
        <span className="story-mark" aria-hidden="true">S</span>
        <span>
          <b>Sapphire</b>
          <small>System story</small>
        </span>
      </a>
      <nav aria-label="Dashboard pages">
        {STORY_PAGES.map((page) => (
          <a
            key={page.key}
            href={page.href}
            aria-current={active === page.key ? 'page' : undefined}
          >
            {page.label}
          </a>
        ))}
      </nav>
      <span className="story-readonly"><i aria-hidden="true" /> Read-only</span>
    </header>
  )
}

function PageIntro({ eyebrow, title, copy }: { eyebrow: string; title: string; copy: string }) {
  return (
    <section className="page-intro">
      <p className="story-eyebrow">{eyebrow}</p>
      <h1>{title}</h1>
      <p>{copy}</p>
    </section>
  )
}

function OverviewPage({ status, statusDetail }: { status: string; statusDetail: string }) {
  return (
    <>
      <section className="story-hero">
        <div className="story-hero-copy">
          <p className="story-eyebrow">A private AI operating system, explained</p>
          <h1>One conversation.<br /><em>An entire system</em><br />behind it.</h1>
          <p className="story-deck">
            This is not a chatbot collection. It is one personal assistant that can listen,
            research, remember, use the right model, and return with a useful update—while
            consequential actions stay under human control.
          </p>
          <div className="story-actions">
            <a className="story-button story-button--primary" href="/dashboard/architecture">See the architecture <span>→</span></a>
            <a className="story-button" href="/dashboard/pipeline">Follow a request</a>
          </div>
        </div>
        <div className="story-orbit" aria-label="System relationship diagram">
          <div className="orbit-ring orbit-ring--outer" aria-hidden="true" />
          <div className="orbit-ring orbit-ring--inner" aria-hidden="true" />
          <div className="orbit-core"><span>OpenClaw</span><small>one conductor</small></div>
          <div className="orbit-node orbit-node--message"><span>Telegram</span><small>conversation</small></div>
          <div className="orbit-node orbit-node--models"><span>Models</span><small>reasoning</small></div>
          <div className="orbit-node orbit-node--vault"><span>Vault</span><small>memory</small></div>
          <div className="orbit-node orbit-node--tools"><span>Tools</span><small>action</small></div>
        </div>
      </section>

      <section className="live-ribbon" aria-label="Public system observation">
        <span><i aria-hidden="true" /> Public observation</span>
        <strong>{status}</strong>
        <p>{statusDetail}</p>
        <a href="/api/v1/live">Inspect source →</a>
      </section>

      <section className="story-section system-at-glance">
        <div className="section-lead">
          <p className="story-eyebrow">The whole system in one line</p>
          <h2>From a message to a trusted result.</h2>
          <p>The technical stack is deliberately hidden behind a human-sized experience.</p>
        </div>
        <ol className="glance-flow">
          {SYSTEM_LAYERS.map((layer) => (
            <li key={layer.number}>
              <span className="flow-number">{layer.number}</span>
              <div><small>{layer.title}</small><h3>{layer.label}</h3><p>{layer.detail}</p></div>
              <span className="flow-arrow" aria-hidden="true">→</span>
            </li>
          ))}
        </ol>
      </section>

      <section className="story-principles">
        <article><span>01</span><h3>Private by default</h3><p>Local compute and an owner-only channel keep sensitive work close to home.</p></article>
        <article><span>02</span><h3>Evidence over theater</h3><p>A result carries sources, freshness, and receipts. Missing evidence stays visibly missing.</p></article>
        <article><span>03</span><h3>Human at the boundary</h3><p>The assistant can prepare deeply; releases, messages, credentials, and capital wait for the owner.</p></article>
      </section>

      <section className="story-section explore-grid-section">
        <div className="section-lead section-lead--row">
          <div><p className="story-eyebrow">Explore the system</p><h2>Four views. No jargon required.</h2></div>
          <p>Each page answers one practical question about how the assistant works.</p>
        </div>
        <div className="explore-grid">
          {[
            ['/dashboard/architecture', 'Architecture', 'What lives where—and why?', 'A map of the private doorway, conductor, engines, memory, and proof.'],
            ['/dashboard/pipeline', 'Request flow', 'What happens after I ask?', 'Six plain-English steps from intent to an owner-ready update.'],
            ['/dashboard/models', 'Models', 'Why use more than one model?', 'The framework stays stable while local and cloud engines compete for each job.'],
            ['/dashboard/ai-today', 'AI today', 'What pattern is emerging?', 'A concise map of the capabilities reshaping personal assistants.'],
          ].map(([href, label, title, copy], index) => (
            <a href={href} key={href}>
              <span>0{index + 1} · {label}</span><h3>{title}</h3><p>{copy}</p><b>Open page →</b>
            </a>
          ))}
        </div>
      </section>
    </>
  )
}

function ArchitecturePage() {
  return (
    <>
      <PageIntro
        eyebrow="Architecture · the five layers"
        title="A home AI system with one front door."
        copy="Every layer has one job. That keeps the experience simple for the owner and makes failures easier to see, stop, and recover."
      />
      <section className="architecture-map" aria-label="Five-layer system architecture">
        {SYSTEM_LAYERS.map((layer, index) => (
          <article key={layer.number} className={`architecture-layer architecture-layer--${index + 1}`}>
            <span>{layer.number}</span>
            <div><p>{layer.title}</p><h2>{layer.label}</h2><p>{layer.detail}</p></div>
            <small>{['OWNER', 'ORCHESTRATION', 'INFERENCE', 'CONTEXT', 'OUTCOME'][index]}</small>
          </article>
        ))}
      </section>
      <section className="boundary-section story-section">
        <div className="section-lead"><p className="story-eyebrow">The important boundary</p><h2>Preparation can be automatic. Impact is not.</h2></div>
        <div className="boundary-grid">
          <article className="boundary-card boundary-card--go"><span>Can proceed</span><h3>Think, research, compare, draft</h3><ul><li>Read public sources</li><li>Search the private vault</li><li>Run local evaluations</li><li>Prepare code and release evidence</li><li>Draft the owner update</li></ul></article>
          <div className="boundary-gate"><span>Owner gate</span><i aria-hidden="true" /><p>A clear pause exactly where intent becomes consequence.</p></div>
          <article className="boundary-card boundary-card--stop"><span>Needs approval</span><h3>Send, release, spend, change access</h3><ul><li>Message an outside party</li><li>Cut over production</li><li>Change credentials or permissions</li><li>Move money or place an order</li><li>Start a privileged runtime</li></ul></article>
        </div>
      </section>
      <section className="story-section ownership-section"><p className="story-eyebrow">Why this shape works</p><div><h2>One owner. One poller. One source of truth.</h2><p>There is no second bot racing for messages and no hidden control panel competing with Telegram. The dashboard explains and observes; OpenClaw coordinates; the owner decides when a prepared action crosses its boundary.</p></div></section>
    </>
  )
}

function PipelinePage() {
  return (
    <>
      <PageIntro eyebrow="Request flow · six moments" title="What happens after you ask." copy="The best personal assistant feels direct, but it does not skip the work. Here is the entire journey from a plain-language request to a durable outcome." />
      <ol className="request-timeline">
        {REQUEST_STEPS.map((step) => (
          <li key={step.number}>
            <span className="timeline-number">{step.number}</span>
            <div><h2>{step.title}</h2><p>{step.copy}</p></div>
            <strong>{step.output}</strong>
          </li>
        ))}
      </ol>
      <section className="update-example story-section">
        <div className="section-lead"><p className="story-eyebrow">The return format</p><h2>An update should answer four questions.</h2></div>
        <div className="update-card">
          <div className="update-card-header"><span>Sapphire Assistant</span><time>08:00</time></div>
          <div className="update-line"><span>Outcome</span><p>The research brief is complete and saved to the vault.</p></div>
          <div className="update-line"><span>Evidence</span><p>Five primary sources checked; two claims were rejected as unverified.</p></div>
          <div className="update-line"><span>Blocker</span><p>The production change is prepared, but it still needs your approval.</p></div>
          <div className="update-line"><span>Next</span><p>Review the one-page summary; approve only if the effect matches your intent.</p></div>
        </div>
      </section>
    </>
  )
}

function ModelsPage() {
  return (
    <>
      <PageIntro eyebrow="Models · a portfolio, not a dependency" title="The conductor is not the model." copy="OpenClaw provides the durable assistant experience. Models are interchangeable engines selected for privacy, speed, capability, and cost." />
      <section className="model-stack">
        {MODEL_LANES.map((lane, index) => (
          <article key={lane.title}>
            <span className="model-index">0{index + 1}</span>
            <div className="model-title"><p>{lane.label}</p><h2>{lane.title}</h2></div>
            <span className="model-badge">{lane.badge}</span>
            <p>{lane.copy}</p>
            <small>{lane.note}</small>
          </article>
        ))}
      </section>
      <section className="model-router story-section">
        <div className="section-lead"><p className="story-eyebrow">A simple routing rule</p><h2>Use the smallest capable boundary.</h2><p>Every job starts with the most private, efficient lane likely to succeed. Escalation is explicit.</p></div>
        <div className="router-scale"><div><span>More local</span><b>Private context</b></div><i aria-hidden="true" /><div><b>Harder reasoning</b><span>More capability</span></div></div>
        <div className="router-cases"><p><span>Local</span> Summaries, classification, vault retrieval, routine drafting.</p><p><span>Hybrid</span> Research with local context and public-source tools.</p><p><span>Frontier</span> Complex code, long-horizon planning, multimodal work.</p></div>
      </section>
      <aside className="name-check compatibility-note"><span>Compatibility rule</span><div><h2>New models are candidates, not deployed capabilities.</h2><p>A model joins the personal-assistant route only after the runtime supports its real capabilities, privacy boundaries, failure paths, and rollback. A recognizable model name alone is never enough.</p></div></aside>
    </>
  )
}

function AiTodayPage() {
  return (
    <>
      <PageIntro eyebrow="AI today · current pattern map" title="Agents are becoming operating systems." copy="The market is converging on the same pattern built here locally: scheduled briefs, tool-using agents, long-lived context, visible workflows, and human-controlled action boundaries." />
      <aside className="verification-note"><span>Public research boundary</span><div><h2>Patterns here; named source trails stay private.</h2><p>This anonymous view publishes analytical lenses and evidence standards, not the owner's source list, vendor ranking, or research-input hierarchy.</p></div></aside>
      <section className="brief-grid" aria-label="Current AI market pattern map">
        {AI_PATTERNS.map((item, index) => (
          <article key={item.category}>
            <div className="brief-meta"><span>0{index + 1}</span><time>Current lens</time><b>{item.category}</b></div>
            <h2>{item.title}</h2><p>{item.copy}</p>
          </article>
        ))}
      </section>
      <section className="story-section convergence-section"><p className="story-eyebrow">What matters</p><h2>The headline is not one model. It is the pattern.</h2><div><p><span>Then</span>A user opened a chat, supplied context again, and carried the result elsewhere.</p><p><span>Now</span>An agent wakes on schedule, gathers context, uses tools, keeps a record, and returns when the work is done.</p><p><span>Here</span>The same pattern runs through a private owner channel, local compute, a durable vault, and explicit approval gates.</p></div></section>
    </>
  )
}

function StoryFooter({ build }: { build: ReturnType<typeof useBuildIdentity> }) {
  return (
    <footer className="story-footer">
      <div><span className="story-mark" aria-hidden="true">S</span><p><b>Sapphire System Story</b><small>One assistant. Many engines. Human authority.</small></p></div>
      <p>Anonymous · read-only · no private vault contents</p>
      <p>{build ? <>Build {shortBuildValue(build.source_sha)} · <a href="/api/build">provenance</a></> : <>Build not yet attributed · <a href="/api/build">inspect</a></>}</p>
    </footer>
  )
}

export default function App(
  props: {
    initialPath?: string
    initialWidgets?: PublicWidgets
    initialSnapshot?: LiveSnapshot
    initialLiveError?: string
  } = {},
) {
  const { initialPath, initialSnapshot, initialLiveError } = props
  const build = useBuildIdentity()
  const { snapshot: polledSnapshot, error: polledError, loading } = useLiveTelemetry()
  const snapshot = initialSnapshot ?? polledSnapshot
  const error = initialLiveError ?? polledError
  const pathname = initialPath ?? (typeof window === 'undefined' ? '/dashboard/' : window.location.pathname)
  const active = pageFromPath(pathname)
  const status = error
    ? 'Public evidence unavailable'
    : snapshot?.status === 'live'
      ? 'Latest public snapshot is current'
      : loading
        ? 'Checking the latest public snapshot'
        : 'No current public snapshot'
  const statusDetail = error
    ? 'The last value is not promoted to a live claim.'
    : snapshot?.status === 'live'
      ? `Observed ${formatAge(snapshot.freshness_s)}. This page cannot start or stop the system.`
      : 'Absence is shown honestly; it is never translated into healthy.'

  return (
    <div className="story-shell">
      <div className="story-grid" aria-hidden="true" />
      <StoryHeader active={active} />
      <main className="story-main">
        {active === 'overview' ? <OverviewPage status={status} statusDetail={statusDetail} /> : null}
        {active === 'architecture' ? <ArchitecturePage /> : null}
        {active === 'pipeline' ? <PipelinePage /> : null}
        {active === 'models' ? <ModelsPage /> : null}
        {active === 'ai-today' ? <AiTodayPage /> : null}
      </main>
      <StoryFooter build={build} />
    </div>
  )
}

export function LegacyObservatory(
  {
    initialWidgets,
    initialSnapshot,
    initialLiveError,
  }: {
    initialWidgets?: PublicWidgets
    initialSnapshot?: LiveSnapshot
    initialLiveError?: string
  } = {},
) {
  const build = useBuildIdentity()
  const { snapshot: polledSnapshot, error: polledLiveError, loading } = useLiveTelemetry()
  const error = initialLiveError ?? polledLiveError
  const snapshot = initialSnapshot ?? polledSnapshot
  const { snapshot: moss, error: mossError } = useMossSnapshot()
  const { fleet, error: fleetError } = useFleet()
  const { widgets: polledWidgets, error: widgetsError } = usePublicWidgets()
  const widgets = initialWidgets ?? polledWidgets

  const execution =
    snapshot?.status === 'live'
      ? snapshot?.desk?.execution ?? snapshot?.markets.execution ?? null
      : null
  const status = error ? 'unavailable' : (snapshot?.status ?? (loading ? 'warming' : 'not observed'))
  const narration = useMemo(() => (snapshot ? narrate(snapshot) : null), [snapshot])
  const gateCount = fleetCount(fleet, 'gates')
  const leaseCount = fleetCount(fleet, 'leases')
  const epistemics =
    !error && snapshot?.status === 'live' && snapshot.desk?.epistemics?.fresh
      ? snapshot.desk.epistemics
      : null
  const research = currentResearch(snapshot, error)
  const thesis =
    snapshot?.status === 'live' && !error
      ? research?.thesis ?? epistemics?.thesis
      : null

  const segments = useMemo(
    () =>
      buildEvidenceSegments({
        snapshot,
        widgets,
        moss,
        fleet,
        execution,
        errors: { live: error, widgets: widgetsError, fleet: fleetError, moss: mossError },
      }),
    [snapshot, widgets, moss, fleet, execution, error, widgetsError, fleetError, mossError],
  )
  const [activeId, setActiveId] = useState('snapshot')
  const activeEvidence = segments.find((segment) => segment.id === activeId) ?? segments[0]

  const attention = useMemo(
    () =>
      buildAttention({
        snapshot,
        widgets,
        execution,
        error,
        widgetsError,
        fleetError,
        mossError,
        gateCount,
      }),
    [
      snapshot,
      widgets,
      execution,
      error,
      widgetsError,
      fleetError,
      mossError,
      gateCount,
    ],
  )

  const attentionCount = attention.length
    ? formatCount(attention.length)
    : snapshot?.observed_at
      ? '0'
      : NOT_OBSERVED

  const decision = deriveCurrentDecision({
    snapshot,
    widgets,
    execution,
    error,
    attention,
  })

  return (
    <div className="observatory-shell" data-execution={execution ?? 'unknown'}>
      <div className="observatory-glow" aria-hidden="true" />

      <header className="observatory-header">
        <a className="observatory-brand" href="/">
          <span aria-hidden="true">◇</span>
          Sapphire <b>Mission Control</b>
        </a>
        <nav aria-label="Observatory sections">
          {SECTIONS.map((section) => (
            <a href={section.href} key={section.href}>
              {section.label}
            </a>
          ))}
        </nav>
        <div className="observatory-header-state">
          <span className={`state-dot state-dot--${toneForValue(status)}`} aria-hidden="true" />
          <span>{status}</span>
          <time>{error && snapshot ? `last report ${formatAge(snapshot.freshness_s)}` : formatAge(snapshot?.freshness_s)}</time>
        </div>
      </header>

      <main className="observatory-main">
        <RuntimeStrip snapshot={snapshot} error={error} />

        <section
          className="current-decision-band"
          aria-labelledby="current-decision-title"
          data-decision={decision.verb}
        >
          <p className="observatory-kicker">CURRENT DECISION</p>
          <h1 id="current-decision-title">
            <span className="current-decision-verb">{decision.verb}</span>
            <span className="current-decision-detail">{decision.summary}</span>
          </h1>
          <div className="current-decision-grid" role="group" aria-label="Decision factors">
            <div>
              <span>Pause + authority</span>
              <strong data-tone={decision.pauseTone}>{decision.pause}</strong>
            </div>
            <div>
              <span>Evidence freshness</span>
              <strong data-tone={decision.freshnessTone}>{decision.freshness}</strong>
            </div>
            <div>
              <span>Exact next gate</span>
              <strong data-tone={decision.nextTone}>{decision.nextGate}</strong>
            </div>
          </div>
          <p className="current-decision-thesis">
            Thesis: {thesis?.claim ?? 'No thesis observed.'}
            {' · '}
            Attention items: {attentionCount}
          </p>
        </section>

        <section className="observatory-opening" aria-labelledby="observatory-title">
          <div>
            <p className="observatory-kicker">Operator desk · read-only view</p>
            <h2 id="observatory-title">{thesis?.claim ?? 'No thesis observed.'}</h2>
            <p className="observatory-lede">
              What is true, what is stale, what is blocked, and what exact attended action
              is next — without presenting absence as health.
            </p>
          </div>

          <div className="observatory-opening-facts" aria-label="Current thesis summary">
            <div>
              <span>Probability</span>
              <strong>{percent(thesis?.probability)}</strong>
            </div>
            <div>
              <span>Stance</span>
              <strong>{words(thesis?.stance)}</strong>
            </div>
            <div>
              <span>Horizon</span>
              <strong>{thesis ? `${thesis.horizon_days} days` : NOT_OBSERVED}</strong>
            </div>
            <div>
              <span>Needs attention</span>
              <strong>{attentionCount}</strong>
            </div>
          </div>
        </section>

        <ThesisPulse
          snapshot={snapshot}
          execution={execution}
          error={error}
        />

        <EvidenceHorizon
          segments={segments}
          active={activeEvidence}
          onSelect={setActiveId}
        />

        <div className="observatory-decision-grid">
          <section id="attention" className="attention-panel" aria-labelledby="attention-title">
            <div className="section-heading">
              <p>02 · Needs attention</p>
              <h2 id="attention-title">The shortest path to a truthful state.</h2>
            </div>
            {attention.length ? (
              <ol className="attention-list">
                {attention.map((item, index) => (
                  <li key={`${item.label}-${index}`} data-tone={item.tone}>
                    <span>{String(index + 1).padStart(2, '0')}</span>
                    <div>
                      <strong>{item.label}</strong>
                      <p>{item.detail}</p>
                    </div>
                  </li>
                ))}
              </ol>
            ) : (
              <div className="timeline-empty">
                <span>{snapshot?.observed_at ? 'No urgent exception observed' : 'No report yet'}</span>
                <p>
                  {snapshot?.observed_at
                    ? 'This is bounded to the current snapshot; it is not a claim that every subsystem is healthy.'
                    : 'Waiting for the first report before counting exceptions.'}
                </p>
              </div>
            )}
            <p className="attention-boundary">
              This page observes the desk. Start/stop, policy changes, custody, and orders
              remain isolated control surfaces.
            </p>
          </section>

          <section id="timeline" className="timeline-panel" aria-labelledby="timeline-title">
            <div className="section-heading">
              <p>03 · What changed</p>
              <h2 id="timeline-title">Observed events, newest first.</h2>
            </div>
            <EventTimeline snapshot={snapshot} fallback={narration?.text} />
          </section>
        </div>

        <section id="evidence" className="evidence-ledger" aria-labelledby="evidence-title">
          <div className="section-heading section-heading--wide">
            <div>
              <p>04 · Evidence</p>
              <h2 id="evidence-title">The details stay available, not dominant.</h2>
            </div>
            <p>
              Open a ledger only when the decision needs it. The top of the page stays
              reserved for thesis, revision triggers, and execution availability.
            </p>
          </div>

          <div className="evidence-disclosures">
            <ResearchDisclosure snapshot={snapshot} widgets={widgets} error={error} />
            <SystemDisclosure snapshot={snapshot} leaseCount={leaseCount} />
            <AssetDisclosure
              status={moss?.status}
              funding={moss?.usdm_band}
              authority={moss?.authority}
            />
          </div>
        </section>

        <section className="measurement-contract" aria-label="Measurement contract">
          <p>Measurement contract</p>
          <h2>A number is observed, or it is absent.</h2>
          <div>
            <p>
              Every figure is tied to the report that supplied it. Missing source,
              freshness, or authority makes the value unknown—not zero, safe, or live.
            </p>
            <p>
              Capital remains banded. Identities, addresses, holdings, orders, and machine
              names never enter this anonymous surface.
            </p>
          </div>
        </section>
      </main>

      <footer className="observatory-footer">
        <span>Sapphire Alpha · conviction under revision</span>
        {build ? (
          <span>
            Build {shortBuildValue(build.source_sha)} ·{' '}
            {shortBuildValue(build.build_id, 16)} · {build.runtime_revision} ·{' '}
            {build.surfaces.operator.asset_count + build.surfaces.public.asset_count} files ·{' '}
            {shortBuildValue(build.surfaces.operator.manifest_sha256, 8)}/
            {shortBuildValue(build.surfaces.public.manifest_sha256, 8)} ·{' '}
            {build.complete ? 'attributed' : 'incomplete'} ·{' '}
            <a href="/api/build">manifest</a>
          </span>
        ) : (
          <span>
            Build not verified · <a href="/api/build">inspect manifest</a>
          </span>
        )}
        <span>Anonymous · read-only view · controls isolated</span>
      </footer>
    </div>
  )
}

function RuntimeStrip({
  snapshot,
  error,
}: {
  snapshot: LiveSnapshot | null
  error: string
}) {
  const reportCurrent = snapshot?.status === 'live' && !error
  const currentComponents = reportCurrent
    ? snapshot.nodes.filter(
        (node) => node.status === 'healthy' && node.freshness_s <= RUNTIME_TTL_SECONDS,
      ).length
    : null
  const homeCompute = reportCurrent
    ? snapshot.nodes.find((node) => node.id === 'win-workhorse')
    : null

  return (
    <section className="runtime-strip" aria-labelledby="runtime-strip-title">
      <p id="runtime-strip-title">SYSTEM NOW</p>
      <div className="runtime-strip-grid">
        <div>
          <span>Snapshot</span>
          <strong>
            {snapshot
              ? error
                ? `poll failed · last report ${formatAge(snapshot.freshness_s)}`
                : `${snapshot.status} · ${formatAge(snapshot.freshness_s)}`
              : NOT_OBSERVED}
          </strong>
        </div>
        <div>
          <span>Market activity</span>
          <strong>
            {reportCurrent && snapshot.markets.events_per_min != null
              ? `${formatCount(snapshot.markets.events_per_min)} / min`
              : NOT_OBSERVED}
          </strong>
        </div>
        <div>
          <span>Current components</span>
          <strong>
            {currentComponents != null
              ? `${formatCount(currentComponents)} / ${formatCount(snapshot?.nodes.length)}`
              : NOT_OBSERVED}
          </strong>
        </div>
        <div>
          <span>Home compute</span>
          <strong>
            {homeCompute
              ? `${homeCompute.status} · ${formatAge(homeCompute.freshness_s)}`
              : NOT_OBSERVED}
          </strong>
        </div>
      </div>
    </section>
  )
}

function ThesisPulse({
  snapshot,
  execution,
  error,
}: {
  snapshot: LiveSnapshot | null
  execution: string | null
  error: string
}) {
  const runtimeCurrent = snapshot?.status === 'live' && !error
  const epistemics =
    runtimeCurrent && snapshot.desk?.epistemics?.fresh
      ? snapshot.desk.epistemics
      : null
  const projectedThesis = currentResearch(snapshot, error)?.thesis
  const legacyThesis = epistemics?.thesis
  const thesis = projectedThesis ?? legacyThesis
  const regime = epistemics?.regime
  const learning = epistemics?.learning
  const falsifier = epistemics?.falsifiers?.[0]
  const autonomy = runtimeCurrent ? snapshot.desk?.autonomy : null
  const floor = runtimeCurrent ? snapshot.desk?.safety_floor : null
  const floorChecks = floor
    ? [floor.gate_valid, floor.pause_clear, floor.ledger === 'reconciled', floor.bounded_policy]
    : []
  const floorReady = floorChecks.length === 4 && floorChecks.every(Boolean)

  const stages = [
    {
      id: 'claim',
      eyebrow: 'Claim',
      title: 'Thesis now',
      value: thesis?.claim ?? 'No thesis observed.',
      meta: thesis
        ? legacyThesis && thesis === legacyThesis
          ? `${percent(thesis.probability)} probability · ${words(legacyThesis.confidence)} confidence`
          : `${percent(thesis.probability)} probability · ${words(thesis.stance)} · ${thesis.horizon_days} days`
        : 'Waiting for a versioned claim.',
      tone: thesis ? 'current' : 'unknown',
    },
    {
      id: 'regime',
      eyebrow: 'Context',
      title: 'Narrative & regime',
      value: regime?.label ? words(regime.label) : NOT_OBSERVED,
      meta: regime?.drivers?.length
        ? regime.drivers.slice(0, 2).join(' · ')
        : `Fit ${percent(regime?.fit)} · quality ${percent(regime?.data_quality)}`,
      tone: regime?.label && regime.label !== 'unknown' ? 'current' : 'unknown',
    },
    {
      id: 'falsifier',
      eyebrow: 'Revision trigger',
      title: 'What would change the view',
      value: falsifier?.condition ?? legacyThesis?.falsifier ?? NOT_OBSERVED,
      meta: falsifier ? `Status: ${words(falsifier.status)}` : 'No falsifier observed.',
      tone: falsifier?.status === 'triggered'
        ? 'degraded'
        : falsifier?.status === 'watch'
          ? 'held'
          : falsifier
            ? 'current'
            : 'unknown',
    },
    {
      id: 'learning',
      eyebrow: 'Outcomes',
      title: 'Learning loop',
      value: learning
        ? `${formatCount(learning.open)} open · ${formatCount(learning.resolved)} resolved`
        : NOT_OBSERVED,
      meta: learning
        ? `Brier ${learning.mean_brier == null ? NOT_OBSERVED : learning.mean_brier.toFixed(3)} · ${formatCount(learning.lessons)} lessons`
        : 'No outcome calibration observed.',
      tone: learning?.status === 'learning'
        ? 'current'
        : learning?.status === 'bootstrapping'
          ? 'held'
          : 'unknown',
    },
    {
      id: 'execution',
      eyebrow: 'Availability',
      title: 'Execution floor',
      value: floor ? (floorReady ? 'Ready' : 'Waiting') : NOT_OBSERVED,
      meta: floor
        ? `${floor.ledger} ledger · ${autonomy?.new_entries ?? 'waiting'} entries · execution ${words(execution)}`
        : 'Gate, pause, ledger, and bounded policy are not observed.',
      tone: floorReady && autonomy?.active ? 'current' : floor ? 'held' : 'unknown',
    },
  ] as const

  return (
    <section id="thesis" className="thesis-pulse" aria-labelledby="thesis-pulse-title">
      <div className="thesis-pulse-heading">
        <div>
          <p>01 · Thesis pulse</p>
          <h2 id="thesis-pulse-title">One view. Five revision points.</h2>
        </div>
        <p>
          {autonomy
            ? `Autonomy desired ${autonomy.desired}; effective ${autonomy.active ? 'on' : 'off'} — ${autonomy.reason}.`
            : 'Autonomy state has not been observed.'}
        </p>
      </div>
      <ol className="thesis-pulse-track">
        {stages.map((stage, index) => (
          <li key={stage.id} data-tone={stage.tone}>
            <span className="thesis-pulse-index">{String(index + 1).padStart(2, '0')}</span>
            <div>
              <p>{stage.eyebrow}</p>
              <h3>{stage.title}</h3>
              <strong>{stage.value}</strong>
              <small>{stage.meta}</small>
            </div>
          </li>
        ))}
      </ol>
    </section>
  )
}

function EvidenceHorizon({
  segments,
  active,
  onSelect,
}: {
  segments: EvidenceSegment[]
  active: EvidenceSegment
  onSelect: (id: string) => void
}) {
  function moveFocus(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    const keyOffsets: Record<string, number> = {
      ArrowRight: 1,
      ArrowDown: 1,
      ArrowLeft: -1,
      ArrowUp: -1,
    }
    let nextIndex = index
    if (event.key === 'Home') nextIndex = 0
    else if (event.key === 'End') nextIndex = segments.length - 1
    else if (event.key in keyOffsets) {
      nextIndex = (index + keyOffsets[event.key] + segments.length) % segments.length
    } else {
      return
    }
    event.preventDefault()
    onSelect(segments[nextIndex].id)
    document.getElementById(`evidence-tab-${segments[nextIndex].id}`)?.focus()
  }

  return (
    <section className="evidence-horizon horizon-enter" aria-labelledby="horizon-title">
      <div className="evidence-horizon-heading">
        <div>
          <p>Evidence horizon</p>
          <h2 id="horizon-title">Freshness and authority share one line.</h2>
        </div>
        <span>Focus a segment for provenance</span>
      </div>

      <div className="evidence-horizon-track" role="tablist" aria-label="Evidence sources">
        {segments.map((segment, index) => (
          <button
            key={segment.id}
            id={`evidence-tab-${segment.id}`}
            type="button"
            role="tab"
            aria-selected={segment.id === active.id}
            aria-controls="evidence-horizon-detail"
            tabIndex={segment.id === active.id ? 0 : -1}
            data-tone={segment.tone}
            data-evidence-state={
              segment.tone === 'current'
                ? 'observed'
                : segment.tone === 'degraded'
                  ? 'stale'
                  : segment.tone === 'held'
                    ? 'paused'
                    : segment.value === NOT_OBSERVED
                      ? 'unavailable'
                      : 'source-only'
            }
            onClick={() => onSelect(segment.id)}
            onFocus={() => onSelect(segment.id)}
            onKeyDown={(event) => moveFocus(event, index)}
          >
            <span>{segment.label}</span>
            <strong>{segment.value}</strong>
          </button>
        ))}
      </div>

      <div
        id="evidence-horizon-detail"
        role="tabpanel"
        aria-labelledby={`evidence-tab-${active.id}`}
        aria-live="polite"
      >
        <dl className="evidence-horizon-detail">
          <div>
            <dt>Source</dt>
            <dd>{active.source}</dd>
          </div>
          <div>
            <dt>Observed</dt>
            <dd>{active.observedAt}</dd>
          </div>
          <div>
            <dt>Freshness</dt>
            <dd>{active.freshness}</dd>
          </div>
          <div>
            <dt>Authority</dt>
            <dd>{active.authority}</dd>
          </div>
          <div>
            <dt>Uncertainty</dt>
            <dd>{active.uncertainty}</dd>
          </div>
        </dl>
      </div>
    </section>
  )
}

function EventTimeline({
  snapshot,
  fallback,
}: {
  snapshot: LiveSnapshot | null
  fallback: string | undefined
}) {
  const events = recentEvents(snapshot?.events ?? []).slice(0, 5)

  if (!events.length) {
    return (
      <div className="timeline-empty">
        <span>{snapshot?.observed_at ? 'No events in this report' : 'No event report yet'}</span>
        <p>{fallback ?? 'Waiting for the first observed event.'}</p>
      </div>
    )
  }

  return (
    <ol className="event-timeline">
      {events.map((event) => (
        <li key={event.id} data-tone={toneForValue(event.status)}>
          <time>{formatClockTime(event.observed_at)}</time>
          <div>
            <strong>{event.label}</strong>
            <span>
              {words(event.source)} → {words(event.target)}
            </span>
          </div>
          <b>{event.status}</b>
        </li>
      ))}
    </ol>
  )
}

function ResearchDisclosure({
  snapshot,
  widgets,
  error,
}: {
  snapshot: LiveSnapshot | null
  widgets: PublicWidgets | null
  error: string
}) {
  const projection = currentResearch(snapshot, error)
  const clips = widgets?.research.clips ?? []
  return (
    <details>
      <summary>
        <span>Research record</span>
        <strong>
          {projection ? '1 current thesis' : clips.length ? `${clips.length} unverified` : NOT_OBSERVED}
        </strong>
      </summary>
      <div className="disclosure-body">
        {projection ? (
          <ol className="plain-ledger">
            <li>
              <time>{observedTime(projection.observed_at)}</time>
              <strong>{projection.thesis.claim}</strong>
            </li>
          </ol>
        ) : clips.length ? (
          <ol className="plain-ledger">
            {clips.slice(0, 6).map((clip) => (
              <li key={clip.id}>
                <time>{observedTime(clip.observed_at)}</time>
                <strong>{clip.title}</strong>
              </li>
            ))}
          </ol>
        ) : (
          <p>No analyst input has been published in this observation.</p>
        )}
        <p className="disclosure-note">
          {projection
            ? 'Read-only daily projection · one ordered thesis · no execution authority'
            : <>Unverified advisory input · distinct-input floor:{' '}
                {formatCount(widgets?.research.policy.minimum_distinct_inputs)} ·
                single-input cap:{' '}
                {widgets ? `${Math.round(widgets.research.policy.single_input_cap * 100)}%` : NOT_OBSERVED}{' '}
                · review status: {widgets ? words(widgets.research.policy.review_status) : NOT_OBSERVED}</>}
        </p>
      </div>
    </details>
  )
}

function SystemDisclosure({
  snapshot,
  leaseCount,
}: {
  snapshot: LiveSnapshot | null
  leaseCount: number | null
}) {
  const agents = [...(snapshot?.agents ?? [])].sort(
    (left, right) => Date.parse(right.updated_at) - Date.parse(left.updated_at),
  )
  return (
    <details>
      <summary>
        <span>System record</span>
        <strong>
          {snapshot?.observed_at
            ? `${snapshot.nodes.length} components · ${formatCount(leaseCount)} repo holds`
            : NOT_OBSERVED}
        </strong>
      </summary>
      <div className="disclosure-body disclosure-columns">
        <div>
          <h3>Components</h3>
          <ol className="plain-ledger">
            {(snapshot?.nodes ?? []).slice(0, 8).map((node) => (
              <li key={node.id}>
                <span>{formatAge(node.freshness_s)}</span>
                <strong>{describeNode(node.id).plainName}</strong>
                <b>{node.status}</b>
              </li>
            ))}
          </ol>
          {!snapshot?.nodes.length ? <p>No component report has arrived yet.</p> : null}
        </div>
        <div>
          <h3>Recent agent state</h3>
          <ol className="plain-ledger">
            {agents.slice(0, 8).map((agent) => (
              <li key={agent.id}>
                <time>{observedTime(agent.updated_at)}</time>
                <strong>{describeAgent(agent.id).plainName}</strong>
                <b>{agent.state}</b>
              </li>
            ))}
          </ol>
          {!agents.length ? <p>No agent report has arrived yet.</p> : null}
        </div>
      </div>
    </details>
  )
}

function AssetDisclosure({
  status,
  funding,
  authority,
}: {
  status: string | undefined
  funding: string | undefined
  authority: string | undefined
}) {
  return (
    <details>
      <summary>
        <span>On-chain observation</span>
        <strong>{status ?? NOT_OBSERVED}</strong>
      </summary>
      <dl className="disclosure-body disclosure-stats">
        <div>
          <dt>Funding</dt>
          <dd>{funding ?? NOT_OBSERVED}</dd>
        </div>
        <div>
          <dt>Authority</dt>
          <dd>{authority ?? NOT_OBSERVED}</dd>
        </div>
        <div>
          <dt>Disclosure</dt>
          <dd>Banded only</dd>
        </div>
      </dl>
    </details>
  )
}

function deriveCurrentDecision({
  snapshot,
  widgets,
  execution,
  error,
  attention,
}: {
  snapshot: LiveSnapshot | null
  widgets: PublicWidgets | null
  execution: string | null
  error: string
  attention: AttentionItem[]
}): {
  verb: string
  summary: string
  pause: string
  pauseTone: EvidenceTone
  freshness: string
  freshnessTone: EvidenceTone
  nextGate: string
  nextTone: EvidenceTone
} {
  const pauseUnknown =
    widgets?.gate.pause_state === 'unknown' ||
    widgets?.gate.killswitch == null ||
    widgets == null
  const killswitch = widgets?.gate.killswitch === true
  const paused =
    killswitch ||
    ['halted', 'off', 'gated', 'paused'].includes(String(execution ?? '').toLowerCase())
  const stale = snapshot?.status === 'stale' || Boolean(error)
  const unobserved = !snapshot?.observed_at && !error

  let verb = 'HOLD'
  let summary = 'No attended action is admitted until evidence and pause truth are current.'
  if (unobserved && !widgets) {
    verb = 'REFUSE'
    summary = 'No persisted observation yet — refuse present-tense claims.'
  } else if (pauseUnknown) {
    verb = 'REFUSE'
    summary = 'Pause state unavailable — no runtime or entry claim is admitted.'
  } else if (killswitch) {
    verb = 'HOLD'
    summary = 'Kill switch engaged — entry remains ineligible until approved resume.'
  } else if (paused) {
    verb = 'HOLD'
    summary = 'Execution is held — no order path from this read-only surface.'
  } else if (stale) {
    verb = 'HOLD'
    summary = 'Evidence is stale or poll-failed — do not act on present-tense values.'
  } else if (attention.length > 0) {
    verb = 'ATTENDED ACTION'
    summary = attention[0].detail
  } else if (snapshot?.status === 'live') {
    verb = 'HOLD'
    summary = 'Observation current; no automatic action is authorized from this desk.'
  }

  const pauseLabel = pauseUnknown
    ? 'unavailable'
    : killswitch
      ? 'kill switch engaged'
      : paused
        ? words(execution) || 'paused'
        : widgets?.gate.pause_state
          ? words(widgets.gate.pause_state)
          : 'not observed'

  const freshnessLabel = error
    ? snapshot
      ? `poll failed · last report ${formatAge(snapshot.freshness_s)}`
      : 'unavailable'
    : formatAge(snapshot?.freshness_s)

  const nextGate = pauseUnknown
    ? 'Restore both pause sources before any readiness claim'
    : killswitch
      ? 'Separate approved resume transition required'
      : attention[0]?.label ??
        (snapshot?.status === 'live'
          ? 'No open gate observed on this surface'
          : 'Wait for a current admitted snapshot')

  return {
    verb,
    summary,
    pause: pauseLabel,
    pauseTone: pauseUnknown ? 'unknown' : killswitch || paused ? 'held' : 'current',
    freshness: freshnessLabel,
    freshnessTone: error || snapshot?.status === 'stale' ? 'degraded' : toneForValue(snapshot?.status),
    nextGate,
    nextTone: pauseUnknown || killswitch || attention.length ? 'held' : 'unknown',
  }
}

export function buildEvidenceSegments({
  snapshot,
  widgets,
  moss,
  fleet,
  execution,
  errors,
}: {
  snapshot: LiveSnapshot | null
  widgets: PublicWidgets | null
  moss: MossSnapshot | null
  fleet: FleetData | FleetCounts | null
  execution: string | null
  errors: { live: string; widgets: string; fleet: string; moss: string }
}): EvidenceSegment[] {
  const observed = observedTime(snapshot?.observed_at)
  const freshness = formatAge(snapshot?.freshness_s)
  const parentCurrent = snapshot?.status === 'live'
  const marketFreshness = formatAge(
    parentCurrent ? snapshot?.markets.feed_age_s : snapshot?.freshness_s,
  )
  const nestedUnavailable = snapshot?.status === 'stale' ? 'stale' : NOT_OBSERVED
  const liveTone = (value: string | null | undefined) =>
    errors.live ? 'degraded' as const : toneForValue(value)
  const fleetObservedAt =
    fleet && !isFleetCounts(fleet) ? observedTime(fleet.generated_at) : NOT_OBSERVED
  const fleetFreshness = formatAge(fleet?.snapshot_age_s)
  const fleetCurrent =
    fleet?.snapshot_age_s != null && fleet.snapshot_age_s <= RUNTIME_TTL_SECONDS
  const leaseCount = fleetCount(fleet, 'leases')
  const gateCount = fleetCount(fleet, 'gates')
  const projectedResearch = currentResearch(snapshot, errors.live)
  const widgetResearchObservedAt = widgets?.research.clips
    .map((clip) => clip.observed_at)
    .filter((value) => !Number.isNaN(Date.parse(value)))
    .sort((left, right) => Date.parse(right) - Date.parse(left))[0]
  const widgetResearchAge = widgets?.research.clips
    .map((clip) => clip.age_s)
    .filter((value) => Number.isFinite(value) && value >= 0)
    .sort((left, right) => left - right)[0]

  return [
    {
      id: 'snapshot',
      label: 'Snapshot',
      value: snapshot?.status ?? NOT_OBSERVED,
      source: '/api/v1/live',
      observedAt: observed,
      freshness,
      authority: 'read only',
      uncertainty: errors.live
        ? snapshot
          ? 'poll failed; value is from the last report'
          : 'poll failed; no observation'
        : snapshot
          ? 'schema-validated projection'
          : 'no observation',
      tone: liveTone(snapshot?.status),
    },
    {
      id: 'market',
      label: 'Market feed',
      value: parentCurrent ? snapshot?.markets.status ?? NOT_OBSERVED : nestedUnavailable,
      source: '/api/v1/live · markets',
      observedAt: observed,
      freshness: marketFreshness,
      authority: 'evidence only',
      uncertainty: errors.live
        ? snapshot
          ? 'poll failed; value is from the last report'
          : 'poll failed; no market observation'
        : snapshot?.markets.events_per_min == null
          ? 'rate not measured'
          : 'rate measured',
      tone: liveTone(parentCurrent ? snapshot?.markets.status : snapshot?.status),
    },
    {
      id: 'decisions',
      label: 'Decision gate',
      value: parentCurrent ? snapshot?.markets.decision_gate ?? NOT_OBSERVED : 'unknown',
      source: '/api/v1/live · desk',
      observedAt: observedTime(snapshot?.desk?.updated_at ?? snapshot?.observed_at),
      freshness,
      authority: 'execution control',
      uncertainty: errors.live
        ? snapshot?.desk
          ? 'poll failed; value is from the last report'
          : 'poll failed; no desk observation'
        : snapshot?.desk
          ? 'bounded public counts'
          : 'no desk observation',
      tone: liveTone(parentCurrent ? snapshot?.markets.decision_gate : snapshot?.status),
    },
    {
      id: 'execution',
      label: 'Execution',
      value: parentCurrent ? words(execution) : 'unknown',
      source: '/api/v1/live · execution',
      observedAt: observed,
      freshness,
      authority: ['halted', 'off', 'gated'].includes(String(execution))
        ? 'no execution permitted'
        : 'not established',
      uncertainty: errors.live
        ? execution
          ? 'poll failed; value is from the last report'
          : 'poll failed; no execution observation'
        : execution
          ? 'reported state'
          : 'no execution observation',
      tone: liveTone(parentCurrent ? execution : snapshot?.status),
    },
    {
      id: 'research',
      label: 'Research',
      value: projectedResearch
        ? '1 current thesis'
        : widgetResearchObservedAt
          ? `${formatCount(widgets.research.clips.length)} unverified`
        : NOT_OBSERVED,
      source: projectedResearch ? '/api/v1/live · research' : '/api/v1/widgets · research',
      observedAt: observedTime(projectedResearch?.observed_at ?? widgetResearchObservedAt),
      freshness: projectedResearch
        ? formatAge(
            Math.max(0, Date.now() - Date.parse(projectedResearch.observed_at)) / 1000,
          )
        : widgetResearchObservedAt
          ? formatAge(widgetResearchAge)
          : NOT_OBSERVED,
      authority: 'unverified advisory input',
      uncertainty: projectedResearch
        ? 'allowlisted thesis fields only; no execution authority'
        : errors.widgets
        ? 'poll failed; value is from the last report'
        : widgetResearchObservedAt
          ? 'bounded timestamped analyst text; review and primary-source provenance are not attested'
          : 'no persisted research observation',
      tone: projectedResearch ? 'current' : errors.widgets ? 'degraded' : 'unknown',
    },
    {
      id: 'fleet',
      label: 'Coordination',
      value: fleetCurrent && leaseCount != null && gateCount != null
        ? `${formatCount(leaseCount)} holds · ${formatCount(gateCount)} gates`
        : NOT_OBSERVED,
      source: '/api/fleet',
      observedAt: fleetObservedAt,
      freshness: fleetFreshness,
      authority: 'coordination only',
      uncertainty: errors.fleet
        ? 'poll failed; value is from the last report'
        : fleet?.snapshot_age_s != null
          ? !fleetCurrent
            ? 'snapshot expired; counts withdrawn'
            : isFleetCounts(fleet)
              ? 'counts-only projection; observation time absent'
              : 'sanitized fleet projection'
          : 'no timed fleet observation',
      tone: errors.fleet
        ? 'degraded'
        : fleetCurrent
          ? 'current'
          : fleet?.snapshot_age_s != null
            ? 'degraded'
            : 'unknown',
    },
    {
      id: 'moss',
      label: 'On-chain',
      value: moss?.status ?? NOT_OBSERVED,
      source: '/api/v1/moss',
      observedAt: observedTime(moss?.observed_at),
      freshness: formatAge(moss?.freshness_s),
      authority: moss?.authority ?? 'not established',
      uncertainty: errors.moss
        ? 'poll failed; value is from the last report'
        : moss
          ? 'banded public observation'
          : 'no on-chain observation',
      tone: errors.moss ? 'degraded' : toneForValue(moss?.status),
    },
  ]
}

function buildAttention({
  snapshot,
  widgets,
  execution,
  error,
  widgetsError,
  fleetError,
  mossError,
  gateCount,
}: {
  snapshot: LiveSnapshot | null
  widgets: PublicWidgets | null
  execution: string | null
  error: string
  widgetsError: string
  fleetError: string
  mossError: string
  gateCount: number | null
}): AttentionItem[] {
  const items: AttentionItem[] = []

  if (error) {
    items.push({
      label: 'Live telemetry is unavailable',
      detail: 'Keep the last observed state visible, but do not describe it in the present tense.',
      tone: 'degraded',
    })
  } else if (snapshot?.status === 'stale') {
    items.push({
      label: `Snapshot is ${formatAge(snapshot.freshness_s)}`,
      detail: 'Every value below describes that older observation.',
      tone: 'degraded',
    })
  }

  if (
    widgets?.gate.pause_state === 'unknown' ||
    widgets?.gate.killswitch == null
  ) {
    items.push({
      label: 'Pause state is unavailable',
      detail: 'No runtime or entry claim is admitted until both persisted pause sources are current.',
      tone: 'degraded',
    })
  } else if (widgets.gate.killswitch) {
    items.push({
      label: 'Kill switch is engaged',
      detail: 'Any entry path remains ineligible until a separate approved resume transition.',
      tone: 'held',
    })
  } else if (['halted', 'off', 'gated'].includes(String(execution))) {
    items.push({
      label: 'Execution is held',
      detail: 'No order path is permitted from this read-only surface.',
      tone: 'held',
    })
  }

  const blocked =
    snapshot?.status === 'live' ? snapshot.desk?.decisions.blocked : null
  if (blocked != null && blocked > 0) {
    items.push({
      label: `${blocked} ${blocked === 1 ? 'decision is' : 'decisions are'} policy-blocked`,
      detail: 'A prior approval does not override the current policy state.',
      tone: 'degraded',
    })
  }

  if (gateCount != null && gateCount > 0) {
    items.push({
      label: `${gateCount} ${gateCount === 1 ? 'gate is' : 'gates are'} open`,
      detail: 'Age and subject live in the fleet record; this page cannot clear them.',
      tone: 'held',
    })
  }

  const peripheralErrors = [widgetsError, fleetError, mossError].filter(Boolean)
  if (peripheralErrors.length) {
    items.push({
      label: `${peripheralErrors.length} supporting ${peripheralErrors.length === 1 ? 'feed is' : 'feeds are'} unavailable`,
      detail: 'The missing feeds remain unknown and do not inherit freshness from live telemetry.',
      tone: 'degraded',
    })
  }

  return items.slice(0, 4)
}

export function recentEvents(events: LiveEvent[]) {
  return [...events]
    .sort((left, right) => Date.parse(right.observed_at) - Date.parse(left.observed_at))
    .slice(0, 9)
}
