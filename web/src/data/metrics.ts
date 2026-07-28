/**
 * Single source of truth for every number rendered on the marketing site.
 *
 * House rule: a figure only ships if it carries the command that reproduces it.
 * `verify` is displayed to the reader, not just kept as a comment — the site's
 * whole argument is "run it yourself." If you cannot write the one-liner, the
 * number does not belong on the page.
 *
 * Re-measure with `scripts/measure.sh` and update `MEASURED_AT` / `MEASURED_SHA`
 * in the same commit. Never hand-edit a value without re-running the command.
 */

/** Commit of the `Sapphire` monorepo these figures were measured against. */
export const MEASURED_SHA = 'f27122ab'
/** ISO date of measurement. Rendered next to the metrics so staleness is visible. */
export const MEASURED_AT = '2026-07-25'

export type Metric = {
  /** Short label, rendered in mono uppercase. */
  label: string
  /** The figure itself. Strings so we control grouping and units precisely. */
  value: string
  /** What the number actually counts — precision matters more than impressiveness. */
  detail: string
  /** Shell one-liner that reproduces `value`. Shown to the reader on demand. */
  verify: string
}

/**
 * Headline figures. Deliberately literal: "test functions defined" is a claim
 * that survives scrutiny; "7,695 tests passing" would not, because this counts
 * definitions rather than a green run.
 */
export const CORE_METRICS: Metric[] = [
  {
    label: 'Test functions',
    value: '7,695',
    detail: 'Test functions defined across 484 test modules.',
    verify: "git ls-files '*.py' | xargs grep -h '^\\s*\\(async \\)\\?def test_' | wc -l",
  },
  {
    label: 'HTTP routes',
    value: '182',
    detail: 'Declared FastAPI route handlers across every service.',
    verify: "git ls-files '*.py' | xargs grep -ho '@[a-z_]*\\.\\(get\\|post\\|put\\|delete\\|patch\\|head\\|options\\|websocket\\)(' | wc -l",
  },
  {
    label: 'Source modules',
    value: '900',
    detail: 'Python modules excluding tests. 1,384 including them.',
    verify: "git ls-files '*.py' | grep -vc '^tests/'",
  },
  {
    label: 'Compute nodes',
    value: '4',
    detail: 'Mac control plane, Windows GPU executor, GCP VM, Cloud Run.',
    verify: 'tailscale status --json | jq \'.Peer | length\'',
  },
]

/** Secondary figures used on interior pages. */
export const DETAIL_METRICS: Metric[] = [
  {
    label: 'Test modules',
    value: '484',
    detail: 'Files under tests/ holding the executable specification.',
    verify: "git ls-files '*.py' | grep -c '^tests/'",
  },
  {
    label: 'Solidity contracts',
    value: '5',
    detail: 'On-chain surface. Small on purpose — most logic stays off-chain.',
    verify: "git ls-files '*.sol' | wc -l",
  },
  {
    label: 'Python modules',
    value: '1,384',
    detail: 'Total tracked Python files, tests included.',
    verify: "git ls-files '*.py' | wc -l",
  },
]

/** Robinhood Chain (Arbitrum Orbit L2) — the settlement rail. */
export const CHAIN = {
  id: 4663,
  name: 'RH-CHAIN',
  family: 'Arbitrum Orbit L2',
  /** Where the chain id is pinned in the test suite, so the claim is checkable. */
  verify: "grep -rn '4663' tests/test_rail_rh_l2.py",
} as const

export type Node = {
  id: string
  role: string
  hardware: string
  duty: string
}

/** The four machines. Named by role, never by address — see the security page. */
export const NODES: Node[] = [
  {
    id: 'control',
    role: 'Control plane',
    hardware: 'Apple M4 Pro · 24 GB',
    duty: 'Orchestration, CI, gate enforcement, human approval rail.',
  },
  {
    id: 'executor',
    role: 'GPU executor',
    hardware: 'NVIDIA RTX 5070 Ti · 16 GB',
    duty: 'Intended inference and bounded-execution host; runtime unavailable.',
  },
  {
    id: 'offload',
    role: 'Offload VM',
    hardware: 'GCP Compute Engine',
    duty: 'Long-running batch work and scheduled collectors.',
  },
  {
    id: 'edge',
    role: 'Public edge',
    hardware: 'Cloud Run · us-central1',
    duty: 'This site, the public telemetry API, and privacy-bounded capital summaries.',
  },
]
