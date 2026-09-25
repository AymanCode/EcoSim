// Read-side helpers over arms from session.js: align towns by tick and look
// values up "as of" a tick (the last recorded tick at or before it). An arm's
// inner arrays are shared and append-only (see session.js): these helpers only
// read them.
import { COUNTED_EVERY_5, DEFAULT_POLICY, LEVER_GROUPS, WARMUP_TICKS } from '../catalog.js'

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

const isNumber = value => typeof value === 'number' && Number.isFinite(value)

// Counted-every-5-weeks figures (COUNTED_EVERY_5) repeat between counts; the
// frame's `wealthAsOfTick` names the week of the count. A week is a count when
// the figure changed or `wealthAsOfTick` moved (a recount can repeat the
// value); the first recorded week is one too.
const COUNTED = new Set(COUNTED_EVERY_5)
const AS_OF = 'wealthAsOfTick'

function isCount(arm, key, index) {
  if (index === 0) return true
  const values = arm.series?.[key] ?? []
  const asOf = arm.series?.[AS_OF] ?? []
  return (values[index] ?? null) !== (values[index - 1] ?? null) || (asOf[index] ?? null) !== (asOf[index - 1] ?? null)
}

// A figure as of `tick`, with the week it describes: { value, asOfTick }. For
// a COUNTED_EVERY_5 key that is the last count at or before `tick` (at week 72,
// the week-70 count); for any other key, the last recorded week. Null when
// nothing is recorded yet or the value is missing.
export function countedAt(arm, key, tick) {
  const index = indexAtOrBefore(arm?.ticks ?? [], tick)
  if (index < 0) return null
  const value = arm.series?.[key]?.[index] ?? null
  if (value === null) return null
  let at = index
  if (COUNTED.has(key)) while (!isCount(arm, key, at)) at -= 1
  return { value, asOfTick: arm.ticks[at] }
}

// [{ tick, value }] at the weeks a figure was counted, through `tick`: what a
// chart draws. A COUNTED_EVERY_5 key has a point at each count only; any other
// key at every recorded week. A missing value is left out.
export function countedSeriesUpTo(arm, key, tick) {
  const index = indexAtOrBefore(arm?.ticks ?? [], tick)
  const values = arm?.series?.[key] ?? []
  const counted = COUNTED.has(key)
  const points = []
  for (let i = 0; i <= index; i += 1) {
    const value = values[i] ?? null
    if (value !== null && (!counted || isCount(arm, key, i))) points.push({ tick: arm.ticks[i], value })
  }
  return points
}

// { min, max } of every town's recorded values of `key` after warm-up, up to
// `tick`; null during warm-up or when none was measured.
export function rangeSoFar(arms, key, tick) {
  let min = Infinity
  let max = -Infinity
  for (const arm of arms ?? []) {
    const values = arm?.series?.[key] ?? []
    for (let i = indexAtOrBefore(arm?.ticks ?? [], tick); i >= 0 && arm.ticks[i] > WARMUP_TICKS; i -= 1) {
      if (!isNumber(values[i])) continue
      min = Math.min(min, values[i])
      max = Math.max(max, values[i])
    }
  }
  return min <= max ? { min, max } : null
}

// The sum of a weekly figure over every recorded week up to `tick` (loans
// written off so far); a missing week adds nothing. Null when no week up to
// `tick` has a value.
export function cumulativeUpTo(arm, key, tick) {
  const values = arm?.series?.[key] ?? []
  let sum = 0
  let seen = false
  for (let i = indexAtOrBefore(arm?.ticks ?? [], tick); i >= 0; i -= 1) {
    if (!isNumber(values[i])) continue
    sum += values[i]
    seen = true
  }
  return seen ? sum : null
}

// The town-wide event counts (session.js `eventCounts`) for each of the
// `weeks` weeks ending at `tick`, oldest first: [{ tick, [key]: n }]. A week
// with no counts (not recorded, or before week 1) reads null, never zero.
export function weeklyCounts(arm, keys, tick, weeks = 26) {
  const last = Math.floor(Number(tick))
  if (!(last >= 1)) return []
  const rows = []
  for (let week = Math.max(1, last - weeks + 1); week <= last; week += 1) {
    const counts = arm?.eventCounts?.[week]
    const row = { tick: week }
    for (const key of keys ?? []) row[key] = isNumber(counts?.[key]) ? counts[key] : null
    rows.push(row)
  }
  return rows
}

// The open firms by how they are doing, from the curated counts:
// { growing, steady, struggling }, or null when any count is missing.
export function firmStatesAt(arm, tick) {
  const growing = valueAt(arm, 'firmsGrowing', tick)
  const steady = valueAt(arm, 'firmsSteady', tick)
  const struggling = valueAt(arm, 'firmsStruggling', tick)
  return [growing, steady, struggling].every(isNumber) ? { growing, steady, struggling } : null
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

// Per lever, the town hall's last change up to `tick`: { changedAt, was }, the
// week and the value in force before that week. Changes of one lever in the
// same week read as one; a week that leaves the value as it was is no change.
function lastChanges(arm, tick) {
  const rules = rulesAt(arm, -Infinity)
  const history = {}
  for (const change of arm?.policyChanges ?? []) {
    if (change.tick > tick) break
    const lever = change.policy
    const value = leverValue(lever, change.value)
    const changes = history[lever] ?? (history[lever] = [])
    const last = changes[changes.length - 1]
    if (last?.changedAt === change.tick) {
      if (sameValue(value, last.was)) changes.pop()
    } else if (!sameValue(value, rules[lever])) {
      changes.push({ changedAt: change.tick, was: rules[lever] ?? null })
    }
    rules[lever] = value
  }
  const last = {}
  for (const [lever, changes] of Object.entries(history)) if (changes.length) last[lever] = changes[changes.length - 1]
  return last
}

// The rules in force at `tick` in every town, by LEVER_GROUPS group:
// [{ group, same, rows: [{ lever, values, differs, changedAt, was, changes }] }].
// `values` holds each town's value in arm order and `differs` says whether any
// town's value differs from the first town's; `same` is true when no row
// differs. `changes` holds each town's last change of the lever up to `tick`,
// { changedAt, was } or null, for its own column; `changedAt` and `was` repeat
// the latest of them (null when no town changed the lever).
export function rulesTable(arms, tick) {
  const towns = arms ?? []
  const rules = towns.map(arm => rulesAt(arm, tick))
  const changes = towns.map(arm => lastChanges(arm, tick))
  return LEVER_GROUPS.map(({ id, levers }) => {
    const rows = levers.map(lever => {
      const values = rules.map(townRules => townRules[lever])
      const own = changes.map(townChanges => townChanges[lever] ?? null)
      const latest = own.reduce((best, change) => (change && (!best || change.changedAt > best.changedAt) ? change : best), null)
      return {
        lever,
        values,
        differs: values.some(value => !sameValue(value, values[0])),
        changedAt: latest?.changedAt ?? null,
        was: latest ? latest.was : null,
        changes: own,
      }
    })
    return { group: id, same: rows.every(row => !row.differs), rows }
  })
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
