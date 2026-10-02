import { describe, expect, test } from 'vitest'
import { createArm, ingest } from '../data/session.js'
import { mulberry32 } from '../town/geometry.js'
import { houseRank, houseStates, houseWeeks } from '../town/houses.js'
import { demoArms } from './fixture.js'

const OUT = 'peopleOutOfWorkPer100'
const HOMELESS = 'homelessHouseholds'
const TOTAL = 'householdsTotal'

// The house states the arm's own series give for one recorded week.
function statesAt(arm, tick, rank) {
  const i = arm.ticks.indexOf(tick)
  return houseStates({ out: arm.series[OUT][i], homeless: arm.series[HOMELESS][i], total: arm.series[TOTAL][i] }, rank).states
}

// An arm built the way the app builds it, one frame per week through `ingest`,
// so a repeated or out-of-order week behaves exactly as it does live.
const frame = (tick, out, homeless = 0, total = 500) => ({
  tick, metrics: {}, curated: { [OUT]: out, [HOMELESS]: homeless, [TOTAL]: total },
})
function liveArm(weeks) {
  const arm = createArm({ label: 'Town', color: '#000' })
  for (const week of weeks) ingest(arm, frame(...week))
  return arm
}

// The same answer with nothing cached: the arm's weeks copied onto fresh arrays.
function fresh(arm) {
  return { ...arm, ticks: [...arm.ticks], series: Object.fromEntries(Object.entries(arm.series).map(([key, values]) => [key, [...values]])) }
}

describe('houses', () => {
  test('the rank is a fixed shuffle of 0..99 per seed', () => {
    const rank = houseRank(1337)
    expect([...rank].sort((x, y) => x - y)).toEqual(Array.from({ length: 100 }, (_, i) => i))
    expect(houseRank(1337)).toEqual(rank)
    expect(houseRank(7)).not.toEqual(rank)
  })

  test('the lowest ranks lose their homes, the next look for work', () => {
    const rank = houseRank(1)
    const { states, counts } = houseStates({ out: 30, homeless: 10, total: 500 }, rank)
    expect(counts).toEqual({ home: 2, look: 30, work: 68 })
    states.forEach((state, i) => {
      if (rank[i] < 2) expect(state).toBe('home')
      else if (rank[i] < 32) expect(state).toBe('look')
      else expect(state).toBe('work')
    })
  })

  test('missing figures mean everyone works', () => {
    expect(houseStates({ out: null, homeless: null, total: null }, houseRank(1)).counts).toEqual({ home: 0, look: 0, work: 100 })
  })

  test('counts how long each house has been in its state', () => {
    const [arm] = demoArms()
    const rank = houseRank(arm.setup.seed)
    const at40 = houseWeeks(arm, 40, rank)
    const at41 = houseWeeks(arm, 41, rank)
    expect(at40).toHaveLength(100)
    const out40 = statesAt(arm, 40, rank)
    const out41 = statesAt(arm, 41, rank)
    for (let h = 0; h < 100; h += 1) expect(at41[h]).toBe(out40[h] === out41[h] ? at40[h] + 1 : 1)
  })
})

describe('houseWeeks when the weeks change', () => {
  const rank = houseRank(1)

  test('a week that arrives after the first answer extends it', () => {
    const arm = liveArm([[1, 0], [2, 0]])
    expect(houseWeeks(arm, 2, rank)).toEqual(new Array(100).fill(2))
    ingest(arm, frame(3, 10))
    const weeks = houseWeeks(arm, 3, rank)
    for (let h = 0; h < 100; h += 1) expect(weeks[h]).toBe(rank[h] < 10 ? 1 : 3)
    expect(houseWeeks(arm, 2, rank)).toEqual(new Array(100).fill(2))
  })

  test('a repeated last week, overwritten in place, is counted again', () => {
    const arm = liveArm([[1, 0], [2, 0]])
    expect(houseWeeks(arm, 2, rank)).toEqual(new Array(100).fill(2))
    ingest(arm, frame(2, 10))
    const weeks = houseWeeks(arm, 2, rank)
    for (let h = 0; h < 100; h += 1) expect(weeks[h]).toBe(rank[h] < 10 ? 1 : 2)
    expect(weeks).toEqual(houseWeeks(fresh(arm), 2, rank))
  })

  test('a repeated week in the middle, overwritten in place, is counted again', () => {
    const arm = liveArm([[1, 0], [2, 0], [3, 0]])
    expect(houseWeeks(arm, 3, rank)).toEqual(new Array(100).fill(3))
    ingest(arm, frame(2, 10))
    const weeks = houseWeeks(arm, 3, rank)
    // Week 2 sent ten houses looking for work; by week 3 they are back at work, so their count starts over.
    for (let h = 0; h < 100; h += 1) expect(weeks[h]).toBe(rank[h] < 10 ? 1 : 3)
    expect(weeks).toEqual(houseWeeks(fresh(arm), 3, rank))
  })

  test('a changed homeless or household figure is counted again too', () => {
    const arm = liveArm([[1, 0, 0, 500], [2, 0, 0, 500], [3, 0, 0, 500]])
    expect(houseWeeks(arm, 3, rank)).toEqual(new Array(100).fill(3))
    ingest(arm, frame(2, 0, 50, 500))
    const weeks = houseWeeks(arm, 3, rank)
    // Fifty homeless in 500 households is ten houses, the lowest ranks, back to work by week 3.
    for (let h = 0; h < 100; h += 1) expect(weeks[h]).toBe(rank[h] < 10 ? 1 : 3)
    expect(weeks).toEqual(houseWeeks(fresh(arm), 3, rank))
    ingest(arm, frame(2, 0, 0, 0))
    expect(houseWeeks(arm, 3, rank)).toEqual(new Array(100).fill(3))
  })

  test('a week that arrives late and lands in the middle is counted in order', () => {
    const arm = liveArm([[1, 0], [3, 0]])
    expect(houseWeeks(arm, 3, rank)).toEqual(new Array(100).fill(2))
    ingest(arm, frame(2, 10))
    const weeks = houseWeeks(arm, 3, rank)
    for (let h = 0; h < 100; h += 1) expect(weeks[h]).toBe(rank[h] < 10 ? 1 : 3)
    expect(weeks).toEqual(houseWeeks(fresh(arm), 3, rank))
  })

  test('a different seed gives its own houses, and the first one again on return', () => {
    const arm = liveArm([[1, 0], [2, 0], [3, 10]])
    const other = houseRank(7)
    const first = houseWeeks(arm, 3, rank)
    const second = houseWeeks(arm, 3, other)
    expect(second).toEqual(houseWeeks(fresh(arm), 3, other))
    expect(second).not.toEqual(first)
    expect(houseWeeks(arm, 3, rank)).toEqual(first)
  })

  test('matches a count with nothing cached after any mix of new, late and repeated weeks', () => {
    const rand = mulberry32(2024)
    const arm = createArm({ label: 'Town', color: '#000' })
    for (let step = 0; step < 60; step += 1) {
      const tick = 1 + Math.floor(rand() * 9)
      ingest(arm, frame(tick, Math.floor(rand() * 40), rand() < 0.3 ? 25 : 0, 500))
      const at = arm.ticks[Math.floor(rand() * arm.ticks.length)]
      expect(houseWeeks(arm, at, rank)).toEqual(houseWeeks(fresh(arm), at, rank))
    }
  })
})
