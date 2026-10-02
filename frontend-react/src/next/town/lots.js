// Where each firm stands on the island. A firm takes the first free lot
// (nearest the crossing first) in the week it is first seen and keeps it until
// it leaves the server's closed list, about a year after closing; the lot is
// then free for a later firm. With every lot taken, a new firm gets null and is
// counted, never drawn on top of another; it stays null, since it was never
// drawn in the weeks before a lot freed up. A firm that held a lot and comes
// back after a gap takes the first free lot again, because its old one may
// have gone to someone else meanwhile.
//
// The answer is replayed over the arm's weeks in order and cached on the arm's
// shared `ticks` array. Weeks that arrive at the end extend the replay and
// leave earlier answers as they were. If anything earlier changes, so a week
// lands in the middle, a repeated tick replaces a week's snapshot in place, or
// the capacity differs, the replay starts over from the first week and
// earlier answers may change: this is the answer for the arm as it stands.
// Each call checks the arm's weeks against the ones it replayed (a cheap pass,
// no replay), so a stale answer is never returned.
import { LOT_CAPACITY } from './geometry.js'

const cache = new WeakMap()

const freshState = capacity => ({ capacity, weeks: [], lotOf: new Map(), holder: new Array(capacity).fill(null) })

// True when every week replayed so far is still the same week, with the same snapshot, in the arm.
function replayHolds(state, arm, ticks) {
  if (state.weeks.length > ticks.length) return false
  return state.weeks.every((week, i) => week.tick === ticks[i] && week.snapshot === arm.snapshots?.[ticks[i]])
}

export function lotAssignment(arm, capacity = LOT_CAPACITY) {
  const ticks = arm?.ticks ?? []
  let state = cache.get(ticks)
  if (!state || state.capacity !== capacity || !replayHolds(state, arm, ticks)) state = freshState(capacity)
  for (let i = state.weeks.length; i < ticks.length; i += 1) {
    const snapshot = arm.snapshots?.[ticks[i]]
    const present = new Set([...(snapshot?.firms ?? []), ...(snapshot?.firmsClosed ?? [])].map(firm => firm.id))
    state.holder.forEach((id, lot) => { if (id != null && !present.has(id)) state.holder[lot] = null })
    for (const id of [...present].sort((a, b) => a - b)) {
      const held = state.lotOf.get(id)
      // Still on its own lot, or counted and never drawn: nothing to do.
      if (state.lotOf.has(id) && (held === null || state.holder[held] === id)) continue
      const lot = state.holder.indexOf(null)
      state.lotOf.set(id, lot >= 0 ? lot : null)
      if (lot >= 0) state.holder[lot] = id
    }
    state.weeks.push({ tick: ticks[i], snapshot })
  }
  if (ticks.length) cache.set(ticks, state)
  return state.lotOf
}
