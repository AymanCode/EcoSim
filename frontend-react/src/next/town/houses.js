// The 100 houses each stand for 1/100 of the town's households. Each house has
// a fixed rank from the town's seed (the same shuffle the old town drawing
// used): the lowest ranks lose their homes first, the next look for work, so
// when a figure moves only the houses at the edge change.
import { valueAt } from '../data/derive.js'
import { HOUSES, mulberry32 } from './geometry.js'

const clamp = (value, lo, hi) => Math.min(hi, Math.max(lo, value))
const ranks = new Map()

export function houseRank(seed) {
  const key = Number(seed) || 0
  if (ranks.has(key)) return ranks.get(key)
  const rand = mulberry32(key)
  const order = Array.from({ length: HOUSES }, (_, i) => i)
  for (let i = HOUSES - 1; i > 0; i -= 1) {
    const j = Math.floor(rand() * (i + 1))
    ;[order[i], order[j]] = [order[j], order[i]]
  }
  const rank = new Array(HOUSES)
  order.forEach((house, position) => { rank[house] = position })
  ranks.set(key, rank)
  return rank
}

export function houseStates({ out, homeless, total }, rank) {
  const home = total > 0 ? clamp(Math.round((100 * (homeless ?? 0)) / total), 0, HOUSES) : 0
  const look = clamp(Math.round(out ?? 0), 0, HOUSES - home)
  const states = rank.map(r => (r < home ? 'home' : r < home + look ? 'look' : 'work'))
  return { states, counts: { home, look, work: HOUSES - home - look } }
}

// Weeks each house has been in its current state, per recorded week, cached
// on the arm's shared `ticks` array and extended as weeks arrive.
const runs = new WeakMap()

export function houseWeeks(arm, tick, rank) {
  const ticks = arm?.ticks ?? []
  let state = runs.get(ticks)
  const stale = !state || state.rank !== rank || state.rows.length > ticks.length || (state.rows.length > 0 && ticks[state.rows.length - 1] !== state.lastTick)
  if (stale) state = { rank, rows: [], prev: null, lastTick: null }
  for (let i = state.rows.length; i < ticks.length; i += 1) {
    const at = ticks[i]
    const { states } = houseStates({
      out: valueAt(arm, 'peopleOutOfWorkPer100', at),
      homeless: valueAt(arm, 'homelessHouseholds', at),
      total: valueAt(arm, 'householdsTotal', at),
    }, rank)
    const prevRow = state.rows[i - 1]
    state.rows.push(states.map((s, h) => (state.prev && state.prev[h] === s ? prevRow[h] + 1 : 1)))
    state.prev = states
    state.lastTick = at
  }
  if (ticks.length) runs.set(ticks, state)
  let index = -1
  for (let i = ticks.length - 1; i >= 0; i -= 1) if (ticks[i] <= tick) { index = i; break }
  return index < 0 ? new Array(HOUSES).fill(1) : state.rows[index]
}
