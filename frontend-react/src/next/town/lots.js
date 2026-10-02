// Where each firm stands on the island. A firm takes the first free lot
// (nearest the crossing first) in the week it is first seen and keeps it until
// it leaves the server's closed list, about a year after closing; the lot is
// then free for a later firm. With every lot taken, a new firm gets null and is
// counted, never drawn on top of another. The answer is replayed over the
// arm's weeks in order and cached on the arm's shared `ticks` array, so new
// weeks extend it and earlier answers never change.
import { LOT_CAPACITY } from './geometry.js'

const cache = new WeakMap()

export function lotAssignment(arm, capacity = LOT_CAPACITY) {
  const ticks = arm?.ticks ?? []
  let state = cache.get(ticks)
  const stale = !state || state.capacity !== capacity || state.done > ticks.length || (state.done > 0 && ticks[state.done - 1] !== state.lastTick)
  if (stale) state = { capacity, done: 0, lastTick: null, lotOf: new Map(), holder: new Array(capacity).fill(null) }
  for (let i = state.done; i < ticks.length; i += 1) {
    const snapshot = arm.snapshots?.[ticks[i]]
    const present = new Set([...(snapshot?.firms ?? []), ...(snapshot?.firmsClosed ?? [])].map(firm => firm.id))
    state.holder.forEach((id, lot) => { if (id != null && !present.has(id)) state.holder[lot] = null })
    for (const id of [...present].sort((a, b) => a - b)) {
      if (state.lotOf.has(id)) continue
      const lot = state.holder.indexOf(null)
      state.lotOf.set(id, lot >= 0 ? lot : null)
      if (lot >= 0) state.holder[lot] = id
    }
    state.done = i + 1
    state.lastTick = ticks[i]
  }
  if (ticks.length) cache.set(ticks, state)
  return state.lotOf
}
