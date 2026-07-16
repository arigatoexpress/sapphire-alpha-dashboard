import { motion, AnimatePresence } from 'framer-motion'
import type { TradingViewAlert } from '../types'

interface AlertStreamProps {
  alerts: TradingViewAlert[]
}

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString(undefined, { hour12: false })
  } catch {
    return iso
  }
}

export function AlertStream({ alerts }: AlertStreamProps) {
  const latest = alerts.slice(0, 20)

  return (
    <div className="card alert-stream">
      <div className="card-glow" />
      <div className="alert-stream-header">
        <h2>Alert Stream</h2>
        <span className="live-badge">
          <span className="status-dot danger pulse" />
          LIVE
        </span>
      </div>
      <div className="alert-stream-scroll">
        <AnimatePresence initial={false}>
          {latest.length === 0 && (
            <motion.div
              key="empty"
              className="muted"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
            >
              no alerts yet
            </motion.div>
          )}
          {latest.map((a) => {
            const action = a.alert.action.toLowerCase()
            return (
              <motion.div
                key={a.signal_id}
                className={`alert-line ${action}`}
                initial={{ opacity: 0, x: -20, height: 0 }}
                animate={{ opacity: 1, x: 0, height: 'auto' }}
                exit={{ opacity: 0, x: 20, height: 0 }}
                transition={{ duration: 0.3 }}
              >
                <span className="alert-time">{formatTime(a.received_at)}</span>
                <span className="alert-symbol">{a.alert.symbol}</span>
                <span className={`alert-action ${action}`}>{a.alert.action}</span>
                <span className="alert-price">${a.alert.price.toFixed(2)}</span>
                <span
                  className={`status-dot ${a.published ? 'ok' : 'warn'}`}
                  title={a.published ? 'published' : 'pending'}
                />
              </motion.div>
            )
          })}
        </AnimatePresence>
      </div>
    </div>
  )
}
