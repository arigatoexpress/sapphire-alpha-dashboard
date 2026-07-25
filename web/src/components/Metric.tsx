import type { Metric } from '@/data/metrics'

/**
 * A figure plus the command that reproduces it.
 *
 * The disclosure is a native <details>, not React state: it works before
 * hydration, survives a JS failure, and is keyboard-accessible for free. On a
 * statically exported page that argues for verifiability, shipping a component
 * that needs a bundle to reveal its own proof would undercut the point.
 */
export default function MetricCard({ metric, index = 0 }: { metric: Metric; index?: number }) {
  return (
    <div
      className="rise group relative border-t border-line-lit pt-5"
      style={{ animationDelay: `${index * 90}ms` }}
    >
      {/* The accent rule lights up on hover — the only motion on the card. */}
      <span className="absolute -top-px left-0 h-px w-0 bg-sapphire transition-[width] duration-500 ease-out group-hover:w-full" />

      <p className="font-mono text-[11px] tracking-[0.16em] text-ink-faint uppercase">
        {metric.label}
      </p>

      <p className="tnum mt-3 font-display text-5xl leading-none font-semibold text-ink md:text-6xl">
        {metric.value}
      </p>

      <p className="mt-3 max-w-[34ch] text-sm leading-relaxed text-ink-dim">{metric.detail}</p>

      <details className="mt-4">
        <summary className="inline-flex cursor-pointer list-none items-center gap-1.5 font-mono text-[11px] tracking-[0.12em] text-sapphire uppercase transition-opacity hover:opacity-70 [&::-webkit-details-marker]:hidden">
          Verify
          <span aria-hidden="true" className="text-[9px]">▼</span>
        </summary>
        <pre className="mt-2.5 overflow-x-auto border-l-2 border-sapphire/40 bg-sunk px-3 py-2.5 font-mono text-[11px] leading-relaxed text-ink-dim">
          <code>{metric.verify}</code>
        </pre>
      </details>
    </div>
  )
}
