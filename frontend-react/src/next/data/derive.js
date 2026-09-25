// Read-side helpers over arms from session.js: align towns by tick and look
// values up "as of" a tick (the last recorded tick at or before it).

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

// Events at or before `tick`, newest first; `limit` caps the count.
export function eventsUpTo(arm, tick, limit = Infinity) {
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
  const out = []
  for (let i = last; i >= 0 && out.length < limit; i -= 1) out.push(events[i])
  return out
}
