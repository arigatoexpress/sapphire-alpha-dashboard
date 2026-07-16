import { motion } from 'framer-motion'
import type { ReactNode } from 'react'

interface StatusTileProps {
  title: string
  status: 'ok' | 'warn' | 'danger' | 'neutral'
  value: ReactNode
  subtitle?: ReactNode
  icon?: ReactNode
  accent: string
  pulse?: boolean
  delay?: number
}

const statusMap = { ok: 'ok', warn: 'warn', danger: 'danger', neutral: 'muted' }

export function StatusTile({
  title,
  status,
  value,
  subtitle,
  icon,
  accent,
  pulse,
  delay = 0,
}: StatusTileProps) {
  return (
    <motion.div
      className={`status-tile status-${status}`}
      style={{ '--tile-accent': accent } as React.CSSProperties}
      initial={{ opacity: 0, y: 20, scale: 0.96 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.5, delay, ease: 'easeOut' }}
      whileHover={{ y: -4 }}
    >
      <div className="tile-glow" />
      <div className="tile-header">
        <span className="tile-icon" aria-hidden="true">
          {icon}
        </span>
        <span className="tile-title">{title}</span>
      </div>
      <div className="tile-body">
        <div className="tile-value">
          <span className={`status-dot ${statusMap[status]} ${pulse ? 'pulse' : ''}`} />
          <span>{value}</span>
        </div>
        {subtitle && <div className="tile-subtitle">{subtitle}</div>}
      </div>
    </motion.div>
  )
}
