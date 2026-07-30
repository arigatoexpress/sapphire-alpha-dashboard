import Link from 'next/link'

/** The single-page site has five anchored sections. `href` is the fragment so
 *  smooth-scroll works everywhere and the URL stays canonical (`/#system`). */
export const SECTIONS = [
  { href: '/#system', label: 'System' },
  { href: '/#intelligence', label: 'Intelligence' },
  { href: '/#research', label: 'Research' },
  { href: '/#proof', label: 'Proof' },
  { href: '/#about', label: 'About' },
] as const

export default function Nav() {
  return (
    <header className="site-nav">
      <nav aria-label="Primary" className="site-nav-inner">
        <Link href="/" className="site-nav-mark">
          <svg width="18" height="18" viewBox="0 0 16 16" aria-hidden="true">
            <path d="M8 0.5 15.5 6 8 15.5 0.5 6Z" className="site-nav-mark-outline" />
            <path d="M8 0.5 8 15.5M0.5 6 15.5 6" className="site-nav-mark-inner" />
          </svg>
          <span>
            Sapphire<span className="site-nav-mark-accent">Alpha</span>
          </span>
        </Link>

        <div className="site-nav-links">
          {SECTIONS.map((section) => (
            <a key={section.href} href={section.href} className="site-nav-link">
              {section.label}
            </a>
          ))}
          <Link href="/dashboard" className="site-nav-cta">
            Observatory
          </Link>
        </div>

        <Link href="/dashboard" className="site-nav-cta site-nav-cta--mobile">
          Observe
        </Link>
      </nav>
    </header>
  )
}
