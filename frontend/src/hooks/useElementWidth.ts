import { useEffect, useRef, useState } from 'react'

/**
 * Measure an element's width so the loom can lay itself out in real pixels.
 *
 * `@shared/loomLayout` guarantees non-overlapping labels *for the width it is
 * given*. Handing it a made-up width would throw that guarantee away, which is
 * exactly the class of bug this rebuild exists to remove — so the width comes
 * from the element, and the layout is recomputed when the element changes size.
 *
 * The fallback is used before the first measurement and in any environment
 * without `ResizeObserver` (the server-rendered tests, for instance).
 */
export function useElementWidth<T extends Element>(fallback: number) {
  const ref = useRef<T | null>(null)
  const [width, setWidth] = useState(fallback)

  useEffect(() => {
    const element = ref.current
    if (!element || typeof ResizeObserver === 'undefined') return
    const observer = new ResizeObserver((entries) => {
      const measured = entries[0]?.contentRect.width
      if (measured && measured > 0) setWidth(measured)
    })
    observer.observe(element)
    return () => observer.disconnect()
  }, [])

  return { ref, width }
}
