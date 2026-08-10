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
  { href: '/proof/', label: 'Method' },
] as const

export default function Nav() {
  return (
    <header className="site-nav">
      <nav aria-label="Primary" className="site-nav__inner">
        <Link
          href="/"
          className="site-brand"
        >
          <span className="site-brand__gem" aria-hidden="true" />
          <span>Sapphire <small>Alpha</small></span>
        </Link>

        <div className="site-nav__links">
          {PRIMARY_ROUTES.map((route) => (
            <Link key={route.href} href={route.href}>
              {route.label}
            </Link>
          ))}
          <Link href="/onchain/">Onchain</Link>
        </div>

        <Link href="/dashboard" aria-label="Live desk" className="site-nav__desk">
          Mission control <span aria-hidden="true">↗</span>
        </Link>
      </nav>
    </header>
  )
}
