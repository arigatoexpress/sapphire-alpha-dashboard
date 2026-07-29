/**
 * The Sapphire compute mesh, its agents, and the pipeline they feed.
 *
 * Same rule as `metrics.ts`: every value here is a claim that must be
 * checkable. Nodes and roles are drawn from `Sapphire/infra/tailscale-acl.json`
 * and `Sapphire/CLAUDE.md`; strategies from `Sapphire/lib/analytics/strategies.py`;
 * the chain block from `Sapphire/lib/chain/robinhood_chain.py` and the deployed
 * contract set. Any figure that isn't reproducible from those files does not
 * ship on the page.
 *
 * This is the *compute* view of the mesh — the four machines that observe
 * markets and hold the models. It is deliberately separate from the deployment
 * view in `NODES` (which describes where the site itself is served from).
 * Both views are true; conflating them was the mistake we would have made.
 */

export type MeshNode = {
  /** Stable id used to draw connections in the SVG. */
  id: 'mac' | 'win' | 'pi1' | 'pi2'
  /** Hostname as it appears in Tailscale. */
  hostname: string
  /** One-word role, mono-cased in the diagram. */
  role: string
  /** Hardware, exactly as reported by the machine. */
  hardware: string
  /** What this node actually does in the loop. */
  duty: string
  /** Position on the SVG grid (0-100 in both axes). */
  x: number
  y: number
}

export const MESH: MeshNode[] = [
  {
    id: 'mac',
    hostname: 'macbook-pro-8',
    role: 'Commander',
    hardware: 'Apple M4 Pro · 24 GB',
    duty: 'Orchestration, gate enforcement, human-approval rail.',
    x: 50,
    y: 22,
  },
  {
    id: 'win',
    hostname: 'desktop-hfck6u9',
    role: 'GPU executor',
    hardware: 'NVIDIA RTX 5070 Ti · 16 GB',
    duty: 'Model inference, order placement inside caps.',
    x: 82,
    y: 62,
  },
  {
    id: 'pi1',
    hostname: 'rari1',
    role: 'Edge sensor',
    hardware: 'Raspberry Pi',
    duty: 'Small-model probes, always-on collectors.',
    x: 18,
    y: 62,
  },
  {
    id: 'pi2',
    hostname: 'rari2',
    role: 'Edge sensor',
    hardware: 'Raspberry Pi',
    duty: 'Redundant collector, event-bus shadow.',
    x: 50,
    y: 88,
  },
]

/** All node pairs, drawn as hairlines. The mesh is fully connected on Tailscale. */
export const MESH_LINKS: Array<[MeshNode['id'], MeshNode['id']]> = [
  ['mac', 'win'],
  ['mac', 'pi1'],
  ['mac', 'pi2'],
  ['win', 'pi1'],
  ['win', 'pi2'],
  ['pi1', 'pi2'],
]

export type Strategy = {
  /** Class name in `lib/analytics/strategies.py`. Displayed verbatim. */
  name: string
  /** Line number in the source. */
  line: number
  /** One-sentence description of what it does. */
  thesis: string
  /** Everything ships as paper-only until an explicit Telegram approval. */
  mode: 'paper' | 'live'
}

/**
 * Source: `Sapphire/lib/analytics/strategies.py`. All five classes ship in
 * paper mode; the Hyperliquid live executor is a separate rail and gated
 * per CLAUDE.md.
 */
export const STRATEGIES: Strategy[] = [
  {
    name: 'RegimeAwareRSI',
    line: 178,
    thesis: 'RSI mean-reversion, gated by the BTC 20-day regime state.',
    mode: 'paper',
  },
  {
    name: 'MultiTFMomentum',
    line: 323,
    thesis: 'RSI(7), 20-SMA, and 5-day return must all agree before entry.',
    mode: 'paper',
  },
  {
    name: 'CorrelationBreakout',
    line: 275,
    thesis: 'Fires when BTC↔SPY correlation breaks down and RSI is oversold.',
    mode: 'paper',
  },
  {
    name: 'FundingRateContrarian',
    line: 237,
    thesis: 'Fades 3-day momentum as a proxy for one-sided funding.',
    mode: 'paper',
  },
  {
    name: 'SapphireComposite',
    line: 372,
    thesis: '0–100 score across all four; quarter-Kelly position sizing.',
    mode: 'paper',
  },
]

export type PipelineStage = {
  /** Mono kicker: 01 / 02 / 03 / 04. */
  index: string
  /** Display title. */
  title: string
  /** Plain-English clause for civilians. */
  plain: string
  /** Technical detail for engineers. */
  technical: string
}

/**
 * The observation → decision pipeline. Same five verbs already used on the
 * homepage method rail; here we surface the plumbing behind each verb.
 */
export const PIPELINE: PipelineStage[] = [
  {
    index: '01',
    title: 'Observe',
    plain: 'Watch markets, chains, and threat feeds around the clock.',
    technical: 'coinglass · dune · whale_alert · glassnode · openbb · eth/sol nodes',
  },
  {
    index: '02',
    title: 'Form',
    plain: 'Turn the noise into one probability with a stated source and age.',
    technical: 'Kronos ML + 6-factor TA reconciled to AGREE_BULL / AGREE_BEAR / CONTRADICT',
  },
  {
    index: '03',
    title: 'Falsify',
    plain: 'Write down what would prove the claim wrong before the market answers.',
    technical: 'signals/*.jsonl · Redis event bus · falsifier recorded with the claim',
  },
  {
    index: '04',
    title: 'Gate',
    plain: 'A trade only leaves the machine after one Telegram tap from a human.',
    technical: 'kill_switch · confirmation_firewall · caps: $5/order · 3× lev · $25/day loss',
  },
]

/**
 * Robinhood Chain — the settlement rail. Public wallet only; keys never
 * appear in this repo per CLAUDE.md invariant #3.
 */
export const RH_CHAIN = {
  mainnet: 4663,
  testnet: 46630,
  family: 'Arbitrum Orbit L3',
  liveSince: '2026-07-01',
  publicWallet: '0xc2B59C45d188862659B3b9a51ad04BA07f55c9EB',
  contracts: [
    'SapphireSignalVerifier',
    'SapphirePaymentGate',
    'SapphireSentinelRegistry',
  ],
} as const

/**
 * The security score is a formula, not a stored constant. We surface the
 * formula and today's inputs rather than a lonely number, so a reader can
 * decide if they trust the weights.
 *
 * Source: `Sapphire/services/dashboard/app.py:8348-8393`, current input from
 * `Sapphire/data/security/2026-07-29/pipeline.json` (posture.score = 70).
 */
export const SECURITY_SCORE = {
  aggregate: 70,
  grade: 'C',
  observedAt: '2026-07-29',
  formula: 'deps · 0.35 + models · 0.35 + network · 0.30',
  components: [
    { key: 'deps', label: 'Dependency CVEs', source: 'OSV.dev + CycloneDX SBOM' },
    { key: 'models', label: 'Model integrity', source: 'Ollama blob SHA-256 audit' },
    { key: 'network', label: 'Network posture', source: 'Tailscale topology + trust zone' },
  ],
} as const
