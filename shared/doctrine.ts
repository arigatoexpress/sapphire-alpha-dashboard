/**
 * Public presentation data for the decision framework.
 *
 * This is deliberately generic: private identity, research inputs, positions,
 * and execution policy do not belong in the public application bundle.
 */
export const PUBLIC_DOCTRINE = {
  headline: 'Preserve optionality.',
  posture: 'Late-cycle · capital preservation',
  primary: {
    name: 'Cycle model',
    scope: 'risk regime',
  },
  lenses: [
    { name: 'Liquidity', scope: 'macro conditions' },
    { name: 'Market structure', scope: 'crypto mechanics' },
    { name: 'Frontier technology', scope: 'demand signals' },
    { name: 'Fundamentals', scope: 'protocol economics' },
  ],
  inputCap: '25%',
  evidenceMinimum: '2+',
} as const
