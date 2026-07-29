import Link from 'next/link'

/** Full public route inventory — footer and sitemap consumers. */
export const ROUTES = [
  { href: '/research/', label: 'Research' },
  { href: '/architecture/', label: 'Systems' },
  { href: '/trading/', label: 'Strategy' },
  { href: '/proof/', label: 'Proof' },
  { href: '/security/', label: 'Security' },
  { href: '/onchain/', label: 'On-Chain' },
  { href: '/about/', label: 'About' },
] as const

/** Primary paths for the signal-cartography header. */
export const PRIMARY_ROUTES = [
  { href: '/research/', label: 'Research' },
  { href: '/architecture/', label: 'Systems' },
] as const

export default function Nav() {
  return (
    <header className="sticky top-0 z-50 border-b border-line bg-glacier/90 backdrop-blur-sm">
      <nav
        aria-label="Primary"
        className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-6 px-6"
      >
        <Link
          href="/"
          className="group flex items-center gap-2.5 font-mono text-[13px] tracking-[0.18em] text-observatory-ink uppercase"
        >
          <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true" className="shrink-0">
            <path d="M8 0.5 15.5 6 8 15.5 0.5 6Z" className="fill-none stroke-atlas-blue" strokeWidth="1.2" />
            <path d="M8 0.5 8 15.5M0.5 6 15.5 6" className="stroke-atlas-blue/45" strokeWidth="1" />
          </svg>
          Sapphire<span className="text-atlas-blue"> / Research OS</span>
        </Link>

        <div className="hidden items-center gap-6 lg:flex">
          {PRIMARY_ROUTES.map((route) => (
            <Link
              key={route.href}
              href={route.href}
              className="underline-grow font-mono text-[12px] tracking-[0.1em] text-ink-dim uppercase transition-colors hover:text-observatory-ink"
            >
              {route.label}
            </Link>
          ))}
          <Link
            href="/dashboard"
            className="border border-atlas-blue/50 px-3 py-1.5 font-mono text-[12px] tracking-[0.1em] text-atlas-blue uppercase transition-colors hover:bg-atlas-blue hover:text-glacier"
          >
            Live truth
          </Link>
        </div>

        <Link
          href="/dashboard"
          aria-label="Live truth"
          className="border border-atlas-blue/50 px-3 py-1.5 font-mono text-[11px] tracking-[0.1em] text-atlas-blue uppercase lg:hidden"
        >
          Truth
        </Link>
      </nav>
    </header>
  )
}
