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
// Numeric IDs may be reused while an earlier closure is still archived. The
// replay tracks observable open/closed lifetimes and stores each week's lots
// and birth weeks. Active IDs win over archived closures; a reopened lifetime
// takes a free lot afresh and starts at age zero.
import { LOT_CAPACITY } from './geometry.js'

const cache = new WeakMap()

const freshState = capacity => ({ capacity, weeks: [], lotOf: new Map(), lives: new Map(), births: new Map(), holder: new Array(capacity).fill(null) })

// True when every week replayed so far is still the same week, with the same snapshot, in the arm.
function replayHolds(state, arm, ticks) {
  if (state.weeks.length > ticks.length) return false
  return state.weeks.every((week, i) => week.tick === ticks[i] && week.snapshot === arm.snapshots?.[ticks[i]])
}

function replay(arm, capacity) {
  const ticks = arm?.ticks ?? []
  let state = cache.get(ticks)
  if (!state || state.capacity !== capacity || !replayHolds(state, arm, ticks)) state = freshState(capacity)
  for (let i = state.weeks.length; i < ticks.length; i += 1) {
    const snapshot = arm.snapshots?.[ticks[i]]
    const tick = ticks[i]
    const open = new Map((snapshot?.firms ?? []).map(firm => [firm.id, firm]))
    const closed = new Map()
    const closures = new Map()
    for (const firm of snapshot?.firmsClosed ?? []) {
      if (Number.isFinite(firm.closedTick)) closures.set(firm.id, Math.max(closures.get(firm.id) ?? -Infinity, firm.closedTick))
      if (open.has(firm.id)) continue
      // After a reopening, an older archive record can still arrive. It no
      // longer describes this ID's current lifetime, even if the open sample
      // has since dropped it. Prefer the newest closure if several survive.
      const birth = state.births.get(firm.id)
      if (birth != null && firm.closedTick < birth) continue
      if (!closed.has(firm.id) || firm.closedTick > closed.get(firm.id).closedTick) closed.set(firm.id, firm)
    }
    const present = new Set([...open.keys(), ...closed.keys()])
    const next = new Map()
    for (const id of present) {
      const previous = state.lives.get(id)
      const isOpen = open.has(id)
      const closure = closed.get(id)?.closedTick
      const lastClosure = Math.max(previous?.lastClosure ?? -Infinity, closures.get(id) ?? -Infinity)
      // Exit and entry can happen within one server tick: no closed-only
      // snapshot need exist. A newly archived closure of the previous open
      // lifetime is still evidence that this active ID has been reopened.
      const reopened = previous?.open && lastClosure >= previous.first && lastClosure > previous.lastClosure
      const continues = previous && (isOpen ? previous.open && !reopened : previous.open || previous.closedTick === closure)
      if (continues) next.set(id, { ...previous, open: isOpen, closedTick: closure, lastClosure })
      else {
        // The same numeric ID returning from a closure or gap is a new
        // lifetime. Release its old reservation and reset overflow and age.
        next.set(id, { first: tick, open: isOpen, closedTick: closure, lot: null, lastClosure })
        if (isOpen) state.births.set(id, tick)
        const held = state.lives.get(id)?.lot
        if (held != null) state.holder[held] = null
      }
    }
    state.holder.forEach((id, lot) => { if (id != null && !present.has(id)) state.holder[lot] = null })
    for (const id of [...present].sort((a, b) => a - b)) {
      const life = next.get(id)
      const previous = state.lives.get(id)
      // A continuous overflow lifetime stays undrawn until it ends.
      if (previous && life.first === previous.first) continue
      const lot = state.holder.indexOf(null)
      life.lot = lot >= 0 ? lot : null
      if (lot >= 0) state.holder[lot] = id
    }
    state.lives = next
    for (const [id, life] of next) state.lotOf.set(id, life.lot)
    state.weeks.push({ tick, snapshot, lives: next })
  }
  if (ticks.length) cache.set(ticks, state)
  return state
}

// Legacy callers ask for the latest assignment, including departed IDs.
export function lotAssignment(arm, capacity = LOT_CAPACITY) {
  return replay(arm, capacity).lotOf
}

// The model asks for the lifetimes at the week it draws, so later reuse does
// not change a historical lot or the first week of that earlier business.
export function firmLifetimesAt(arm, tick, capacity = LOT_CAPACITY) {
  const weeks = replay(arm, capacity).weeks
  for (let i = weeks.length - 1; i >= 0; i -= 1) if (weeks[i].tick <= tick) return weeks[i].lives
  return new Map()
}
