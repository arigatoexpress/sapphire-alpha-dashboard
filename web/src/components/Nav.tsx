import Link from 'next/link'

export const ROUTES = [
  { href: '/architecture/', label: 'Architecture' },
  { href: '/trading/', label: 'Trading' },
  { href: '/security/', label: 'Security' },
  { href: '/proof/', label: 'Proof' },
  { href: '/onchain/', label: 'On-Chain' },
  { href: '/research/', label: 'Research' },
  { href: '/about/', label: 'About' },
] as const

export default function Nav() {
  return (
    <header className="sticky top-0 z-50 border-b border-line bg-void/85 backdrop-blur-sm">
      <nav
        aria-label="Primary"
        className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-6 px-6"
      >
        <Link
          href="/"
          className="group flex items-center gap-2.5 font-mono text-[13px] tracking-[0.18em] text-ink uppercase"
        >
          {/* Mark: a sapphire cut down to two facets. Sharp, not a logo blob. */}
          <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true" className="shrink-0">
            <path d="M8 0.5 15.5 6 8 15.5 0.5 6Z" className="fill-none stroke-sapphire" strokeWidth="1.2" />
            <path d="M8 0.5 8 15.5M0.5 6 15.5 6" className="stroke-sapphire/45" strokeWidth="1" />
          </svg>
          Sapphire<span className="text-sapphire">Alpha</span>
        </Link>

        <div className="hidden items-center gap-6 lg:flex">
          {ROUTES.map((route) => (
            <Link
              key={route.href}
              href={route.href}
              className="underline-grow font-mono text-[12px] tracking-[0.1em] text-ink-dim uppercase transition-colors hover:text-ink"
            >
              {route.label}
            </Link>
          ))}
          <Link
            href="/dashboard"
            className="border border-sapphire/45 px-3 py-1.5 font-mono text-[12px] tracking-[0.1em] text-sapphire uppercase transition-colors hover:bg-sapphire hover:text-void"
          >
            Live&nbsp;desk
          </Link>
        </div>

        {/* Small screens: the live desk is the one action worth keeping. */}
        <Link
          href="/dashboard"
          className="border border-sapphire/45 px-3 py-1.5 font-mono text-[11px] tracking-[0.1em] text-sapphire uppercase lg:hidden"
        >
          Desk
        </Link>
      </nav>
    </header>
  )
}
