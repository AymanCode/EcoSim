// Read-side helpers over arms from session.js: align towns by tick and look
// values up "as of" a tick (the last recorded tick at or before it). An arm's
// inner arrays are shared and append-only (see session.js): these helpers only
// read them.
import { DEFAULT_POLICY } from '../catalog.js'

// Index of the last entry in the ascending `ticks` that is <= tick, or -1.
function indexAtOrBefore(ticks, tick) {
  let lo = 0
  let hi = ticks.length - 1
  let found = -1
  while (lo <= hi) {
    const mid = (lo + hi) >> 1
    if (ticks[mid] <= tick) {
      found = mid
      lo = mid + 1
    } else {
      hi = mid - 1
    }
  }
  return found
}

export function commonTicks(arms) {
  if (!arms?.length) return []
  const [first, ...rest] = arms
  const others = rest.map(arm => new Set(arm.ticks))
  return first.ticks.filter(tick => others.every(set => set.has(tick)))
}

export function valueAt(arm, key, tick) {
  const index = indexAtOrBefore(arm?.ticks ?? [], tick)
  if (index < 0) return null
  return arm.series?.[key]?.[index] ?? null
}

export function snapshotAt(arm, tick) {
  const index = indexAtOrBefore(arm?.ticks ?? [], tick)
  if (index < 0) return null
  return arm.snapshots?.[arm.ticks[index]] ?? null
}

// [{ tick, value }] through `tick`; a missing value stays null.
export function seriesUpTo(arm, key, tick) {
  const index = indexAtOrBefore(arm?.ticks ?? [], tick)
  const values = arm?.series?.[key] ?? []
  const points = []
  for (let i = 0; i <= index; i += 1) points.push({ tick: arm.ticks[i], value: values[i] ?? null })
  return points
}

export function compareAt(arms, key, tick) {
  const first = arms?.length ? valueAt(arms[0], key, tick) : null
  return (arms ?? []).map((arm, i) => {
    const value = valueAt(arm, key, tick)
    const deltaVsFirst = i === 0 || value == null || first == null ? null : value - first
    return { label: arm.label, color: arm.color, value, deltaVsFirst }
  })
}

// Index in `arm.ticks` of the last recorded week at or before `tick`, or -1.
export function tickIndexAt(arm, tick) {
  return indexAtOrBefore(arm?.ticks ?? [], tick)
}

// Index in `arm.events` (tick order) of the newest event at or before `tick`, or -1.
export function eventIndexAt(arm, tick) {
  const events = arm?.events ?? []
  let lo = 0
  let hi = events.length - 1
  let last = -1
  while (lo <= hi) {
    const mid = (lo + hi) >> 1
    if (events[mid].tick <= tick) {
      last = mid
      lo = mid + 1
    } else {
      hi = mid - 1
    }
  }
  return last
}

// Events at or before `tick`, newest first; `limit` caps the count.
export function eventsUpTo(arm, tick, limit = Infinity) {
  const events = arm?.events ?? []
  const out = []
  for (let i = eventIndexAt(arm, tick); i >= 0 && out.length < limit; i -= 1) out.push(events[i])
  return out
}

// A policy change's value arrives as text ("wage_tax_rate=0.2"): a lever whose
// schema value is a number reads it back as one.
function leverValue(lever, value) {
  if (typeof DEFAULT_POLICY[lever] !== 'number' || typeof value === 'number') return value
  const number = Number(value)
  return String(value).trim() !== '' && Number.isFinite(number) ? number : value
}

const sameValue = (a, b) => (typeof a === 'number' && typeof b === 'number' ? Math.abs(a - b) < 1e-9 : String(a) === String(b))

// The rules a town has in force at `tick`: DEFAULT_POLICY, then the rules it
// was set up with, then every change the town hall made up to that week.
export function rulesAt(arm, tick) {
  const rules = { ...DEFAULT_POLICY }
  for (const [lever, value] of Object.entries(arm?.setup?.initial_policy ?? {})) {
    if (value !== undefined && value !== null) rules[lever] = leverValue(lever, value)
  }
  for (const change of arm?.policyChanges ?? []) {
    if (change.tick > tick) break
    rules[change.policy] = leverValue(change.policy, change.value)
  }
  return rules
}

// The levers of `rules` whose value differs from `base` (DEFAULT_POLICY by
// default), with the value from `rules`.
export function rulesDiff(rules, base = DEFAULT_POLICY) {
  const diff = {}
  for (const [lever, value] of Object.entries(rules ?? {})) {
    if (!sameValue(value, base?.[lever])) diff[lever] = value
  }
  return diff
}

// A tracked household's situation: 'home' (lost their home), 'work', 'look'
// (able to work, no job) or 'idle' (not able to work).
export function householdState(subject) {
  if (subject?.housingSecurity === false) return 'home'
  if (subject?.isEmployed) return 'work'
  if (subject?.canWork) return 'look'
  return 'idle'
}

// The newest event about one household at or before `tick`, or null.
export function latestEventFor(arm, householdId, tick) {
  const events = arm?.events ?? []
  for (let i = events.length - 1; i >= 0; i -= 1) {
    const event = events[i]
    if (event.tick <= tick && event.householdId === householdId) return event
  }
  return null
}
