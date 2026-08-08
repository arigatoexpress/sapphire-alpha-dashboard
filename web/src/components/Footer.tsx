import Link from 'next/link'
import { ROUTES } from './Nav'
import { MEASURED_AT, MEASURED_SHA } from '@/data/metrics'
import BuildStamp from './BuildStamp'

export default function Footer() {
  return (
    <footer className="mt-24 border-t border-line bg-skywash/40">
      <div className="mx-auto grid max-w-6xl gap-10 px-6 py-14 md:grid-cols-[1.4fr_1fr_1fr]">
        <div>
          <p className="font-mono text-[13px] tracking-[0.18em] text-observatory-ink uppercase">
            Sapphire<span className="text-atlas-blue"> / Evidence Intelligence</span>
          </p>
          <p className="mt-3 max-w-xs text-sm leading-relaxed text-ink-dim">
            Agent-native market intelligence where every claim carries source, age,
            falsifier, and authority.
          </p>
          <BuildStamp />
        </div>

        <nav aria-label="Footer">
          <p className="font-mono text-[11px] tracking-[0.16em] text-ink-faint uppercase">
            Pages
          </p>
          <ul className="mt-4 space-y-2.5">
            {ROUTES.map((route) => (
              <li key={route.href}>
                <Link
                  href={route.href}
                  className="underline-grow text-sm text-ink-dim transition-colors hover:text-observatory-ink"
                >
                  {route.label}
                </Link>
              </li>
            ))}
            <li>
              <Link
                href="/dashboard"
                className="underline-grow text-sm text-ink-dim transition-colors hover:text-observatory-ink"
              >
                Live desk
              </Link>
            </li>
          </ul>
        </nav>

        <div>
          <p className="font-mono text-[11px] tracking-[0.16em] text-ink-faint uppercase">
            Provenance
          </p>
          <dl className="mt-4 space-y-2.5 font-mono text-[12px]">
            <div className="flex justify-between gap-4">
              <dt className="text-ink-faint">measured</dt>
              <dd className="tnum text-ink-dim">{MEASURED_AT}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-ink-faint">metrics SHA</dt>
              <dd className="tnum text-ink-dim">{MEASURED_SHA}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-ink-faint">status</dt>
              <dd className="text-atlas-blue">declared contracts</dd>
            </div>
          </dl>
        </div>
      </div>

      <div className="border-t border-line">
        <div className="mx-auto flex max-w-6xl flex-col gap-2 px-6 py-6 font-mono text-[11px] text-ink-faint sm:flex-row sm:items-center sm:justify-between">
          <p>© {new Date().getFullYear()} Sapphire Alpha. All rights reserved.</p>
          <p>Inventory is reproducible. Evidence projections are hash-checked and scoped.</p>
        </div>
      </div>
    </footer>
  )
}
