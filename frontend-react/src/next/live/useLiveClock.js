import { useCallback, useMemo, useState } from 'react'

// The week the live Run screen shows. It follows the live week (the lowest
// week every town has reached) until the viewer scrubs back; then it holds
// that week while the towns run on, until a scrub to the live week or
// follow() picks the live week up again.
export function useLiveClock(liveTick) {
  const live = Math.max(0, Math.floor(Number(liveTick) || 0))
  const [held, setHeld] = useState(null)
  const following = held == null || held >= live
  const tick = following ? live : held

  const scrub = useCallback(value => {
    const week = Math.round(Number(value))
    if (!Number.isFinite(week)) return
    setHeld(week >= live ? null : Math.max(1, week))
  }, [live])
  const follow = useCallback(() => setHeld(null), [])

  return useMemo(() => ({ tick, following, scrub, follow }), [tick, following, scrub, follow])
}

export default useLiveClock
