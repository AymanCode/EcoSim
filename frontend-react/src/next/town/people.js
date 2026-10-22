// Replay the whole tracked sample in week order. Continuing households keep
// their homes; departures release them that week. Returners reserve their old
// home if it is free, then newcomers probe from their ID's hash. Simultaneous
// arrivals resolve in identity order, independent of the sample's order.
// Each week's answer is separate, so later arrivals cannot move earlier pins.
import { comparePersonIds, PERSON_HOUSE_CAPACITY, personHouseStart } from './geometry.js'

const cache = new WeakMap()
const freshState = () => ({ weeks: [], keys: new Map(), current: new Map(), homes: new Map() })
const idsAt = snapshot => (snapshot?.subjects ?? []).map(subject => subject.id)

function replayHolds(state, arm, ticks) {
  if (state.weeks.length > ticks.length) return false
  return state.weeks.every((week, i) => {
    const snapshot = arm.snapshots?.[ticks[i]]
    if (week.tick !== ticks[i] || week.snapshot !== snapshot) return false
    // Also detect edits to IDs inside a doctored snapshot, not just the
    // snapshot replacements made by ingest on a repeated week.
    const subjects = snapshot?.subjects ?? []
    return week.ids.length === subjects.length && week.ids.every((id, j) => Object.is(id, subjects[j].id))
  })
}

function replay(arm) {
  const ticks = arm?.ticks ?? []
  let state = cache.get(ticks)
  if (!state || !replayHolds(state, arm, ticks)) state = freshState()
  for (let i = state.weeks.length; i < ticks.length; i += 1) {
    const tick = ticks[i], snapshot = arm.snapshots?.[tick], ids = idsAt(snapshot)
    const occurrences = new Map()
    const keys = ids.map(id => {
      const occurrence = occurrences.get(id) ?? 0
      occurrences.set(id, occurrence + 1)
      if (!state.keys.has(id)) state.keys.set(id, [])
      const known = state.keys.get(id)
      // Duplicate or missing IDs have no separate identity to follow. Give
      // each occurrence a stable key so even bad samples use distinct homes.
      known[occurrence] ??= { id, occurrence }
      return known[occurrence]
    })
    const current = new Map(), used = new Set()
    const assign = (key, house) => {
      current.set(key, house)
      used.add(house)
      state.homes.set(key, house)
    }
    for (const key of keys) {
      const house = state.current.get(key)
      if (house != null) assign(key, house)
    }
    const arriving = keys.filter(key => !current.has(key)).sort((a, b) => comparePersonIds(a.id, b.id) || a.occurrence - b.occurrence)
    for (const key of arriving) {
      const old = state.homes.get(key)
      if (old != null && !used.has(old)) assign(key, old)
    }
    for (const key of arriving) {
      if (current.has(key)) continue
      const start = personHouseStart(key.id)
      let house = null
      for (let step = 0; step < PERSON_HOUSE_CAPACITY; step += 1) {
        const candidate = (start + step) % PERSON_HOUSE_CAPACITY
        if (!used.has(candidate)) { house = candidate; break }
      }
      // More than 40 tracked households cannot all have distinct homes.
      // Leave overflow undrawn; it can take a vacancy in a later week.
      if (house == null) current.set(key, null)
      else assign(key, house)
    }
    state.current = current
    state.weeks.push({ tick, snapshot, ids, houses: keys.map(key => current.get(key)) })
  }
  if (ticks.length) cache.set(ticks, state)
  return state.weeks
}

// Aligned with snapshotAt(arm, tick).subjects, including the unpinned sample.
// Shallow live-arm copies share ticks and this cache. Each call checks replayed
// weeks; appends extend it, while splices, removals and rewrites rebuild it.
export function householdHousesAt(arm, tick) {
  const weeks = replay(arm)
  for (let i = weeks.length - 1; i >= 0; i -= 1) if (weeks[i].tick <= tick) return weeks[i].houses
  return []
}
