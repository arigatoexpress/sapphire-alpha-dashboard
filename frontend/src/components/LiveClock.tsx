import { useEffect, useState } from 'react'

export function LiveClock() {
  const [now, setNow] = useState(new Date())

  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000)
    return () => clearInterval(id)
  }, [])

  return (
    <time className="live-clock" dateTime={now.toISOString()}>
      {now.toLocaleTimeString(undefined, { hour12: false })}
    </time>
  )
}
