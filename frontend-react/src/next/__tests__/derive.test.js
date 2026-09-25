import { describe, expect, test } from 'vitest'
import {
  commonTicks, valueAt, snapshotAt, seriesUpTo, compareAt, eventsUpTo, householdState, latestEventFor, countedAt, countedSeriesUpTo, rangeSoFar,
  cumulativeUpTo, weeklyCounts, firmStatesAt, rulesTable,
} from '../data/derive.js'
import { fixtureArm, TOWN_A, TOWN_B } from './fixture.js'

const KEY = 'peopleOutOfWorkPer100'

function twoTowns() {
  const a = fixtureArm(TOWN_A)
  const b = fixtureArm(TOWN_B)
  b.series[KEY] = b.series[KEY].map(v => v + 3)
  return [a, b]
}

describe('commonTicks', () => {
  test('keeps ticks present in every arm, ascending', () => {
    const [a, b] = twoTowns()
    expect(commonTicks([a, b])).toEqual(a.ticks)
    const shorter = { ...b, ticks: b.ticks.filter(t => t % 2 === 0 || t > 20) }
    const common = commonTicks([a, shorter])
    expect(common[0]).toBe(2)
    expect(common).toContain(21)
    expect(common).not.toContain(3)
    expect(commonTicks([])).toEqual([])
  })
})

describe('valueAt and snapshotAt', () => {
  test('are null before the first recorded tick', () => {
    const arm = fixtureArm()
    expect(valueAt(arm, KEY, 0)).toBeNull()
    expect(snapshotAt(arm, 0)).toBeNull()
  })

  test('use the last recorded tick at or before the asked tick', () => {
    const arm = fixtureArm()
    expect(valueAt(arm, KEY, 11)).toBeCloseTo(41.67, 2)
    expect(valueAt(arm, KEY, 11.5)).toBeCloseTo(41.67, 2)
    expect(valueAt(arm, KEY, 500)).toBeCloseTo(1.67, 2)
    expect(snapshotAt(arm, 13).subjects.map(s => s.id)).toContain(29)
    expect(snapshotAt(arm, 500)).toBe(arm.snapshots[24])
  })

  test('return null for an unknown key', () => {
    expect(valueAt(fixtureArm(), 'noSuchMetric', 5)).toBeNull()
  })
})

describe('seriesUpTo', () => {
  test('lists tick and value pairs through the asked tick', () => {
    const arm = fixtureArm()
    const points = seriesUpTo(arm, 'typicalWeeklyPay', 3)
    expect(points.map(p => p.tick)).toEqual([1, 2, 3])
    expect(points[0].value).toBeCloseTo(35.52, 2)
    expect(seriesUpTo(arm, KEY, 0)).toEqual([])
  })
})

describe('compareAt', () => {
  test('gives each town its value and a delta against the first town', () => {
    const rows = compareAt(twoTowns(), KEY, 11)
    expect(rows).toHaveLength(2)
    expect(rows[0]).toMatchObject({ label: 'Town A', color: TOWN_A.color, deltaVsFirst: null })
    expect(rows[1].label).toBe('Town B')
    expect(rows[1].deltaVsFirst).toBeCloseTo(3, 6)
  })

  test('has a null delta when either value is missing', () => {
    const rows = compareAt(twoTowns(), KEY, 0)
    expect(rows[1].deltaVsFirst).toBeNull()
  })
})

describe('eventsUpTo', () => {
  test('returns events up to the tick, newest first, capped by limit', () => {
    const arm = fixtureArm()
    const events = eventsUpTo(arm, 11, 5)
    expect(events).toHaveLength(5)
    expect(events[0].tick).toBe(11)
    expect(events.every(e => e.tick <= 11)).toBe(true)
    for (let i = 1; i < events.length; i += 1) expect(events[i - 1].tick).toBeGreaterThanOrEqual(events[i].tick)
  })

  test('returns every event up to the tick without a limit', () => {
    const arm = fixtureArm()
    expect(eventsUpTo(arm, 24)).toHaveLength(arm.events.length)
    expect(eventsUpTo(arm, 0)).toEqual([])
  })
})

describe('householdState', () => {
  test('reads lost home first, then work, then looking', () => {
    expect(householdState({ housingSecurity: false, isEmployed: true, canWork: true })).toBe('home')
    expect(householdState({ housingSecurity: true, isEmployed: true, canWork: true })).toBe('work')
    expect(householdState({ housingSecurity: true, isEmployed: false, canWork: true })).toBe('look')
    expect(householdState({ housingSecurity: true, isEmployed: false, canWork: false })).toBe('idle')
  })
})

describe('latestEventFor', () => {
  test('finds the newest event about a household at or before the tick', () => {
    const arm = fixtureArm()
    // Household 13 was hired in week 1 and laid off in week 11.
    expect(latestEventFor(arm, 13, 10)).toMatchObject({ type: 'hired', tick: 1 })
    expect(latestEventFor(arm, 13, 24)).toMatchObject({ type: 'laid_off', tick: 11 })
    expect(latestEventFor(arm, 13, 0)).toBeNull()
    expect(latestEventFor(arm, 9999, 24)).toBeNull()
  })
})

// A hand-built arm for weeks 60 to 72 whose gap between rich and poor was
// counted at weeks 65 and 70.
function countedArm() {
  const ticks = Array.from({ length: 13 }, (_, i) => 60 + i)
  return { ticks, series: { gini: ticks.map(t => (t < 65 ? 0.4 : t < 70 ? 0.45 : 0.5)) }, eventCounts: {} }
}

describe('countedAt', () => {
  test('gives the last count at or before the tick, with the week it was made', () => {
    const arm = countedArm()
    expect(countedAt(arm, 'gini', 72)).toEqual({ value: 0.5, asOfTick: 70 })
    expect(countedAt(arm, 'gini', 70)).toEqual({ value: 0.5, asOfTick: 70 })
    expect(countedAt(arm, 'gini', 69)).toEqual({ value: 0.45, asOfTick: 65 })
    expect(countedAt(arm, 'gini', 64)).toEqual({ value: 0.4, asOfTick: 60 })
    expect(countedAt(arm, 'gini', 59)).toBeNull()
  })

  test('a recount that repeats the value still moves the count, read from wealthAsOfTick', () => {
    const arm = countedArm()
    arm.series.gini = arm.ticks.map(() => 0.4)
    arm.series.wealthAsOfTick = arm.ticks.map(t => (t < 65 ? 60 : t < 70 ? 65 : 70))
    expect(countedAt(arm, 'gini', 72)).toEqual({ value: 0.4, asOfTick: 70 })
    expect(countedSeriesUpTo(arm, 'gini', 72)).toEqual([{ tick: 60, value: 0.4 }, { tick: 65, value: 0.4 }, { tick: 70, value: 0.4 }])
  })

  test('is null for a missing value or key', () => {
    const arm = countedArm()
    arm.series.topTenthShare = arm.ticks.map(() => null)
    expect(countedAt(arm, 'topTenthShare', 72)).toBeNull()
    expect(countedAt(arm, 'bottomHalfShare', 72)).toBeNull()
    expect(countedAt(null, 'gini', 72)).toBeNull()
  })

  test('countedSeriesUpTo keeps only the counted weeks', () => {
    expect(countedSeriesUpTo(countedArm(), 'gini', 72)).toEqual([{ tick: 60, value: 0.4 }, { tick: 65, value: 0.45 }, { tick: 70, value: 0.5 }])
    expect(countedSeriesUpTo(countedArm(), 'gini', 67)).toEqual([{ tick: 60, value: 0.4 }, { tick: 65, value: 0.45 }])
  })
})

describe('rangeSoFar', () => {
  // Weeks 1 to 14: extreme values during warm-up, the real economy after.
  const town = after => ({ ticks: Array.from({ length: 14 }, (_, i) => i + 1), series: { priceFood: [0, 100, 0, 100, 0, 100, 0, 100, 0, 100, ...after] } })
  const arms = [town([30, 40, 35, 20]), town([25, 45, null, 60])]

  test('spans every town, ignoring warm-up weeks and missing values', () => {
    expect(rangeSoFar(arms, 'priceFood', 13)).toEqual({ min: 25, max: 45 })
    expect(rangeSoFar(arms, 'priceFood', 14)).toEqual({ min: 20, max: 60 })
    expect(rangeSoFar(arms, 'priceFood', 11)).toEqual({ min: 25, max: 30 })
  })

  test('is null during warm-up or with nothing measured', () => {
    expect(rangeSoFar(arms, 'priceFood', 10)).toBeNull()
    expect(rangeSoFar(arms, 'noSuchMetric', 14)).toBeNull()
    expect(rangeSoFar([], 'priceFood', 14)).toBeNull()
  })
})

describe('cumulativeUpTo', () => {
  const arm = { ticks: [1, 2, 3, 4], series: { bankDefaultAmountThisTick: [0, 5, null, 10] } }

  test('sums the series up to the tick, skipping missing weeks', () => {
    expect(cumulativeUpTo(arm, 'bankDefaultAmountThisTick', 1)).toBe(0)
    expect(cumulativeUpTo(arm, 'bankDefaultAmountThisTick', 3)).toBe(5)
    expect(cumulativeUpTo(arm, 'bankDefaultAmountThisTick', 4)).toBe(15)
    expect(cumulativeUpTo(arm, 'bankDefaultAmountThisTick', 99)).toBe(15)
  })

  test('is null when nothing was measured', () => {
    expect(cumulativeUpTo(arm, 'bankDefaultAmountThisTick', 0)).toBeNull()
    expect(cumulativeUpTo(arm, 'noSuchMetric', 4)).toBeNull()
    expect(cumulativeUpTo({ ticks: [1], series: { x: [null] } }, 'x', 1)).toBeNull()
  })
})

describe('weeklyCounts', () => {
  test('reads each week of the window from eventCounts, oldest first', () => {
    const arm = fixtureArm()
    const rows = weeklyCounts(arm, ['hired', 'laidOff'], 24, 4)
    expect(rows.map(row => row.tick)).toEqual([21, 22, 23, 24])
    expect(rows[3]).toEqual({ tick: 24, hired: arm.eventCounts[24].hired, laidOff: arm.eventCounts[24].laidOff })
    expect(weeklyCounts(arm, ['hired'], 5)).toHaveLength(5)
    expect(weeklyCounts(arm, ['hired'], 0)).toEqual([])
  })

  test('a week without counts reads as missing, not zero', () => {
    const arm = { ticks: [1, 2], eventCounts: { 1: { hired: 2 }, 2: null } }
    expect(weeklyCounts(arm, ['hired', 'laidOff'], 3, 3)).toEqual([
      { tick: 1, hired: 2, laidOff: null },
      { tick: 2, hired: null, laidOff: null },
      { tick: 3, hired: null, laidOff: null },
    ])
  })
})

describe('firmStatesAt', () => {
  test('reads the curated firm counts, or null when one is missing', () => {
    const arm = { ticks: [1, 2], series: { firmsGrowing: [1, 2], firmsSteady: [3, 4], firmsStruggling: [0, null] } }
    expect(firmStatesAt(arm, 1)).toEqual({ growing: 1, steady: 3, struggling: 0 })
    expect(firmStatesAt(arm, 2)).toBeNull()
    expect(firmStatesAt(arm, 0)).toBeNull()
  })
})

describe('rulesTable', () => {
  // The fixture's Town A raises help for people out of work in week 7.
  function towns() {
    const a = fixtureArm(TOWN_A)
    const b = fixtureArm(TOWN_B)
    b.policyChanges = []
    return [a, b]
  }
  const row = (table, lever) => table.flatMap(group => group.rows).find(r => r.lever === lever)

  test('lists the lever groups in order and collapses the ones where the towns agree', () => {
    const table = rulesTable(towns(), 6)
    expect(table.map(group => group.group)).toEqual(['taxes', 'people', 'spending', 'business', 'prices'])
    expect(table.every(group => group.same)).toBe(true)
    expect(row(table, 'benefit_level')).toEqual({
      lever: 'benefit_level', values: ['neutral', 'neutral'], differs: false, changedAt: null, was: null, changes: [null, null],
    })
    expect(table.flatMap(group => group.rows)).toHaveLength(17)
  })

  test('reports a change made mid-run, in the town that made it', () => {
    const table = rulesTable(towns(), 10)
    expect(table.find(group => group.group === 'people').same).toBe(false)
    expect(row(table, 'benefit_level')).toEqual({
      lever: 'benefit_level',
      values: ['high', 'neutral'],
      differs: true,
      changedAt: 7,
      was: 'neutral',
      changes: [{ changedAt: 7, was: 'neutral' }, null],
    })
  })

  test('reads numbers back as numbers and ignores a change to the value already in force', () => {
    const [a, b] = towns()
    a.policyChanges = [
      { tick: 12, policy: 'social_spending', value: 'medium' },
      { tick: 12, policy: 'wage_tax_rate', value: '0.2' },
    ]
    const table = rulesTable([a, b], 20)
    expect(row(table, 'social_spending')).toMatchObject({ differs: false, changedAt: null, changes: [null, null] })
    expect(row(table, 'wage_tax_rate')).toMatchObject({ values: [0.2, 0.15], differs: true, changedAt: 12, was: 0.15 })
    expect(rulesTable([a, b], 11).find(group => group.group === 'taxes').same).toBe(true)
  })

  test('two changes of a lever in one week read as one change from the value before that week', () => {
    const [a, b] = towns()
    a.policyChanges = [
      { tick: 12, policy: 'benefit_level', value: 'high' },
      { tick: 12, policy: 'benefit_level', value: 'low' },
      { tick: 15, policy: 'bailout_budget', value: '5000' },
      { tick: 15, policy: 'bailout_budget', value: '0' },
    ]
    const table = rulesTable([a, b], 20)
    expect(row(table, 'benefit_level')).toMatchObject({ values: ['low', 'neutral'], changedAt: 12, was: 'neutral' })
    expect(row(table, 'bailout_budget')).toMatchObject({ values: [0, 0], differs: false, changedAt: null })
  })

  test('picks the latest change across towns for the row, and keeps each town\'s own', () => {
    const [a, b] = towns()
    b.policyChanges = [{ tick: 30, policy: 'benefit_level', value: 'low' }]
    expect(row(rulesTable([a, b], 40), 'benefit_level')).toMatchObject({
      values: ['high', 'low'], changedAt: 30, was: 'neutral', changes: [{ changedAt: 7, was: 'neutral' }, { changedAt: 30, was: 'neutral' }],
    })
  })

  test('one town agrees with itself', () => {
    expect(rulesTable([fixtureArm()], 10).every(group => group.same)).toBe(true)
    expect(rulesTable([], 10).every(group => group.same && group.rows.every(r => r.values.length === 0))).toBe(true)
  })
})
