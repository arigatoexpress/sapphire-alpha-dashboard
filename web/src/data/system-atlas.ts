export type AtlasStage = {
  id: 'observe' | 'research' | 'agents' | 'policy' | 'record'
  index: string
  title: string
  plain: string
  technical: string
  source: string
  authority: 'none'
  position: { x: number; y: number }
}

/**
 * Static public architecture contract.
 *
 * These records describe intended information boundaries, not runtime health.
 * Runtime state belongs to admitted, timestamped API observations.
 */
export const SYSTEM_ATLAS_STAGES: readonly AtlasStage[] = [
  {
    id: 'observe',
    index: '01',
    title: 'Observe',
    plain: 'Collect evidence. If a source is missing, keep it missing.',
    technical:
      'Persisted observations carry their own source timestamp; response time never replaces it.',
    source: '/api/v1/live · observed_at contract',
    authority: 'none',
    position: { x: 10, y: 56 },
  },
  {
    id: 'research',
    index: '02',
    title: 'Research',
    plain: 'Turn observations into cited claims with a written way to prove them wrong.',
    technical:
      'Research artifacts separate event probability, path scenarios, falsifiers, and later scoring.',
    source: '/research · timestamped artifact contract',
    authority: 'none',
    position: { x: 27, y: 23 },
  },
  {
    id: 'agents',
    index: '03',
    title: 'Agent market',
    plain: 'Specialist roles propose, forecast, and challenge. Evidence wins; no role gets authority.',
    technical:
      'Researcher, forecaster, and critic are proposal-only roles. Runtime status is not asserted.',
    source: 'static role contract · no worker heartbeat',
    authority: 'none',
    position: { x: 50, y: 56 },
  },
  {
    id: 'policy',
    index: '04',
    title: 'Policy boundary',
    plain: 'A separate boundary decides whether a proposal may move any farther.',
    technical:
      'Pause, expiry, limits, and owner approval are execution-side concerns, not website controls.',
    source: 'fail-closed policy contract · no runtime state',
    authority: 'none',
    position: { x: 73, y: 23 },
  },
  {
    id: 'record',
    index: '05',
    title: 'Public record',
    plain: 'Publish the evidence, limits, age, and result so readers can check the work.',
    technical:
      'Static research and build provenance are public; private identities and exact balances are not.',
    source: '/research · /api/build',
    authority: 'none',
    position: { x: 90, y: 56 },
  },
] as const

export const AGENT_MARKET_ROLES = [
  {
    role: 'Researcher',
    job: 'forms a sourced claim',
  },
  {
    role: 'Forecaster',
    job: 'states uncertainty',
  },
  {
    role: 'Critic',
    job: 'searches for failure',
  },
] as const
