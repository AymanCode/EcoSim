import { COUNTED_EVERY_5, NUMBER_DERIVED_ROWS } from '../catalog.js'
import { tickIndexAt } from '../data/derive.js'
import { rowSeries } from './compare.js'

const histories = new WeakMap()
const counted = new Set(COUNTED_EVERY_5)
const isNumber = value => typeof value === 'number' && Number.isFinite(value)

// Live arms are shallow copies sharing append-only ticks/source arrays. Cache
// observations, not arm wrappers, and never mutate an array returned to React.
// Replacing a source or truncating a run starts a fresh history.
export function rowHistory(arm, row, tick) {
  const key = typeof row === 'string' ? row : row.key
  const ticks = arm.ticks
  if (!ticks) return []
  const definition = NUMBER_DERIVED_ROWS[key]
  const values = arm.series?.[definition?.source ?? key]
  const asOf = counted.has(key) ? arm.series?.wealthAsOfTick : undefined
  const events = definition?.kind === 'netJobs' ? arm.eventCounts : undefined
  let byKey = histories.get(ticks)
  if (!byKey) histories.set(ticks, byKey = new Map())
  let cache = byKey.get(key)
  if (!cache || cache.values !== values || cache.asOf !== asOf || cache.events !== events || ticks.length < cache.length) {
    cache = { values, asOf, events, length: ticks.length, observations: [], sum: 0, complete: true }
    byKey.set(key, cache)
  }
  cache.length = ticks.length
  const end = tickIndexAt(arm, tick)
  for (let i = cache.observations.length; i <= end; i += 1) {
    const week = ticks[i]
    const value = values?.[i] ?? null
    let point = { tick: week, value }
    if (definition?.kind === 'netJobs') {
      // Evaluate precisely the original 26-week window, once per new point.
      // In particular, keep its summation order and missing-week semantics.
      point = rowSeries({ ...arm, ticks: [week] }, row, week)[0]
    } else if (definition?.kind === 'cumulative') {
      if (!isNumber(value)) cache.complete = false
      if (cache.complete) cache.sum += value
      point = { tick: week, value: cache.complete ? cache.sum : null }
    } else if (counted.has(key)) {
      const changed = i === 0 || value !== (values?.[i - 1] ?? null) || (asOf?.[i] ?? null) !== (asOf?.[i - 1] ?? null)
      const countedWeek = isNumber(asOf?.[i]) ? asOf[i] : week
      const recovering = i > 0 && !isNumber(values?.[i - 1]) && ticks[i - 1] >= countedWeek
      point = !isNumber(value) ? { tick: week, value: null }
        : changed ? { tick: recovering ? week : countedWeek, value } : null
    }
    cache.observations.push(point)
  }
  if (cache.end === end) return cache.result
  const result = []
  for (let i = 0; i <= end; i += 1) {
    const point = cache.observations[i]
    if (!point) continue
    if (counted.has(key) && result.at(-1)?.tick === point.tick) result[result.length - 1] = point
    else result.push(point)
  }
  cache.end = end
  cache.result = result
  return result
}
