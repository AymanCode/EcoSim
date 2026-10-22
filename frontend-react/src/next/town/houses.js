// The 100 houses each stand for 1/100 of the town's households. Each house has
// a fixed rank from the town's seed (the same shuffle the old town drawing
// used): the lowest ranks lose their homes first, the next look for work, so
// when a figure moves only the houses at the edge change.
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

// Weeks each house has been in its current state, per recorded week. Cached on
// the arm's shared `ticks` array: each row keeps the week and the three
// figures it was built from, and every call checks them against the arm (a
// cheap pass, no replay). Weeks that arrive at the end extend the rows; if an
// earlier week was overwritten in place (a repeated tick), a week landed in the
// middle, or the seed changed, the rows are rebuilt from the first week that
// differs.
const runs = new WeakMap()

// The series are aligned with `ticks`, so week `i` reads index `i`.
const figure = (arm, key, i) => arm.series?.[key]?.[i] ?? null

export function houseWeeks(arm, tick, rank) {
  const ticks = arm?.ticks ?? []
  let state = runs.get(ticks)
  if (!state || state.rank !== rank) state = { rank, rows: [] }
  const { rows } = state
  const inputsAt = i => ({
    out: figure(arm, 'peopleOutOfWorkPer100', i),
    homeless: figure(arm, 'homelessHouseholds', i),
    total: figure(arm, 'householdsTotal', i),
  })
  let keep = 0
  while (keep < rows.length && keep < ticks.length) {
    const row = rows[keep]
    const now = inputsAt(keep)
    if (row.tick !== ticks[keep] || !Object.is(row.out, now.out) || !Object.is(row.homeless, now.homeless) || !Object.is(row.total, now.total)) break
    keep += 1
  }
  rows.length = keep
  for (let i = keep; i < ticks.length; i += 1) {
    const inputs = inputsAt(i)
    const { states } = houseStates(inputs, rank)
    const prev = rows[i - 1]
    rows.push({
      tick: ticks[i],
      ...inputs,
      states,
      weeks: states.map((s, h) => (prev && prev.states[h] === s ? prev.weeks[h] + 1 : 1)),
    })
  }
  if (ticks.length) runs.set(ticks, state)
  let index = -1
  for (let i = ticks.length - 1; i >= 0; i -= 1) if (ticks[i] <= tick) { index = i; break }
  return index < 0 ? new Array(HOUSES).fill(1) : rows[index].weeks
}
