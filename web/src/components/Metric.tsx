import type { Metric } from '@/data/metrics'

/**
 * A figure and what it actually counts.
 *
 * The `verify` command stays in the data file as the internal record of how the
 * number was produced, but it is not rendered — a reader should not need to
 * read shell to trust a claim. What earns trust here is precision about what is
 * being counted: "test functions defined" rather than a rounder, vaguer number.
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
    </div>
  )
}
