import Link from 'next/link'
import { ROUTES } from './Nav'
import { MEASURED_AT, MEASURED_SHA } from '@/data/metrics'
import BuildStamp from './BuildStamp'

export default function Footer() {
  return (
    <footer className="site-footer">
      <div className="site-footer__inner">
        <div className="site-footer__lead">
          <p>SAPPHIRE<span> / ALPHA</span></p>
          <h2>Research at machine speed.<br /><em>Evidence at human standards.</em></h2>
          <p className="site-footer__copy">
            A sovereign market laboratory for onchain intelligence, autonomous research,
            and decisions that can explain themselves.
          </p>
          <BuildStamp />
        </div>

        <nav aria-label="Footer" className="site-footer__nav">
          <p>Explore</p>
          <ul>
            {ROUTES.map((route) => (
              <li key={route.href}>
                <Link href={route.href}>{route.label}</Link>
              </li>
            ))}
            <li><Link href="/dashboard">Mission control</Link></li>
          </ul>
        </nav>

        <div className="site-footer__provenance">
          <p>Provenance</p>
          <dl>
            <div><dt>measured</dt><dd>{MEASURED_AT}</dd></div>
            <div><dt>metrics SHA</dt><dd>{MEASURED_SHA}</dd></div>
            <div><dt>public state</dt><dd>read only</dd></div>
          </dl>
        </div>
      </div>

      <div className="site-footer__bottom">
        <p>© {new Date().getFullYear()} Sapphire Alpha</p>
        <p>Inventory is reproducible. Evidence projections are hash-checked and scoped.</p>
      </div>
    </footer>
  )
}
