import { useEffect, useRef, useState } from 'react'

// Ported from `animateNum` in docs/superpowers/specs/2026-09-06-prototype.html:
// a cubic ease-out count-up driven by requestAnimationFrame, with an
// animation id so a superseded run becomes a no-op instead of fighting a
// newer one. Unlike the prototype (which reads `performance.now()` for its
// start time), this hook takes t0 from the FIRST rAF callback timestamp —
// tests drive rAF with a mocked clock under `vi.useFakeTimers()`, and a
// `performance.now()` start would drift from that mocked clock forever,
// so progress would never reach 1.
const easeOutCubic = (k) => 1 - Math.pow(1 - k, 3)

function prefersReducedMotion() {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return false
  try {
    return window.matchMedia('(prefers-reduced-motion: reduce)').matches
  } catch {
    return false
  }
}

/**
 * @param {number} value - target number to animate toward
 * @param {{duration?: number, fromZero?: boolean}} [options]
 *   duration: animation length in ms (default 450, matching the tile
 *   count-up in the prototype). fromZero: when true, the very first mount
 *   starts from 0 instead of snapping to the value; subsequent updates always
 *   animate from the currently displayed number. Defaults to false so mount
 *   snaps to the value.
 * @returns {number} the currently displayed, eased number
 */
export default function useCountUp(value, { duration = 450, fromZero = false } = {}) {
  const to = Number(value)
  const isReduced = prefersReducedMotion()
  const initialValue = isReduced || !fromZero ? to : 0
  const curRef = useRef(initialValue)
  const mountedRef = useRef(false)
  const [display, setDisplay] = useState(initialValue)

  useEffect(() => {
    const isFirstMount = !mountedRef.current
    mountedRef.current = true
    const reduced = prefersReducedMotion()

    if (isFirstMount && (!fromZero || reduced)) {
      curRef.current = to
      setDisplay(to)
      return undefined
    }

    const from = isFirstMount ? 0 : curRef.current

    if (reduced || Math.abs(to - from) < 1e-9) {
      curRef.current = to
      setDisplay(to)
      return undefined
    }

    // Cancelling via a closure flag (rather than cancelAnimationFrame) keeps
    // this safe under mocked/fake-timer rAF implementations — like the test
    // suite's `setTimeout`-backed mock — where the real id returned by
    // `requestAnimationFrame` may not be one `cancelAnimationFrame` (real or
    // faked) knows how to cancel. A stray callback after cancellation is a
    // harmless no-op.
    let cancelled = false
    let completed = false
    let startTs = null

    const step = (ts) => {
      if (cancelled || completed) return
      if (startTs === null) startTs = ts
      const k = Math.max(0, Math.min(1, (ts - startTs) / duration))
      const next = from + (to - from) * easeOutCubic(k)
      if (k < 1) {
        curRef.current = next
        setDisplay(next)
        requestAnimationFrame(step)
      } else {
        completed = true
        curRef.current = to
        setDisplay(to)
      }
    }
    requestAnimationFrame(step)

    const timer = setTimeout(() => {
      if (cancelled || completed) return
      cancelled = true
      completed = true
      curRef.current = to
      setDisplay(to)
    }, duration)

    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [to, duration, fromZero])

  return display
}
