import Link from 'next/link'
import { SECTIONS } from './Nav'
import { MEASURED_AT, MEASURED_SHA } from '@/data/metrics'
import BuildStamp from './BuildStamp'

export default function Footer() {
  return (
    <footer className="site-foot">
      <div className="site-foot-grid">
        <div>
          <p className="site-foot-mark">
            Sapphire<span>Alpha</span>
          </p>
          <p className="site-foot-body">
            Market research and bounded agent infrastructure, built so its claims
            can be checked rather than believed.
          </p>
          <BuildStamp />
        </div>

        <nav aria-label="Footer sections">
          <p className="site-foot-eyebrow">Sections</p>
          <ul className="site-foot-list">
            {SECTIONS.map((section) => (
              <li key={section.href}>
                <a href={section.href}>{section.label}</a>
              </li>
            ))}
            <li>
              <Link href="/dashboard">Operator observatory</Link>
            </li>
          </ul>
        </nav>

        <div>
          <p className="site-foot-eyebrow">Provenance</p>
          <dl className="site-foot-provenance">
            <div>
              <dt>measured</dt>
              <dd className="tnum">{MEASURED_AT}</dd>
            </div>
            <div>
              <dt>metrics SHA</dt>
              <dd className="tnum">{MEASURED_SHA}</dd>
            </div>
            <div>
              <dt>status</dt>
              <dd className="site-foot-verified">reproducible</dd>
            </div>
          </dl>
        </div>
      </div>

      <div className="site-foot-rule">
        <div>
          <p>© {new Date().getFullYear()} Sapphire Alpha. All rights reserved.</p>
          <p>
            Figures on this site are measured, not estimated. <span>Run the commands.</span>
          </p>
        </div>
      </div>
    </footer>
  )
}
