import { describe, expect, test } from 'vitest'
import { COUNTED_EVERY_5, GLANCE_KEYS, NUMBER_GROUPS, formatMetric } from '../catalog.js'
import {
  countedAt, countedSeriesUpTo, cumulativeUpTo, firmStatesAt, rangeSoFar, rulesTable, valueAt, weeklyCounts,
} from '../data/derive.js'
import { countedNote, differencePhrase } from '../narration.js'
import { demoArms, fixtureArm, TOWN_B } from './fixture.js'

// Built once: the helpers only read arms.
const [A, B] = demoArms()

// The curated keys Task H added; the older fixture has none of them.
const NEW_KEYS = ['happiness', 'salesExceptRentThisWeek', 'townHallIncome', 'familySupportPaid', 'topTenthShare', 'bottomHalfShare']

describe('counted-every-5-weeks numbers on the demo', () => {
  test('week 72 shows the week-70 count, labelled as such', () => {
    for (const key of COUNTED_EVERY_5) {
      expect(countedAt(A, key, 72), key).toEqual({ value: valueAt(A, key, 70), asOfTick: 70 })
      expect(countedAt(B, key, 72), key).toEqual({ value: valueAt(B, key, 70), asOfTick: 70 })
    }
    expect(countedNote(countedAt(A, 'gini', 72).asOfTick)).toBe('Counted every 5 weeks; last count Year 2, week 18.')
    expect(formatMetric('topTenthShare', countedAt(A, 'topTenthShare', 72).value)).toBe('42%')
  })

  test('a scrub only reaches the next count at the week it was made', () => {
    expect(countedAt(A, 'gini', 74).asOfTick).toBe(70)
    expect(countedAt(A, 'gini', 75).asOfTick).toBe(75)
    expect(countedAt(A, 'gini', 3)).toEqual({ value: valueAt(A, 'gini', 1), asOfTick: 1 })
    expect(countedAt(A, 'gini', 0)).toBeNull()
  })

  test('the counted weeks are the only points to draw', () => {
    const weeks = [1, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70]
    expect(countedSeriesUpTo(A, 'bottomHalfShare', 72).map(point => point.tick)).toEqual(weeks)
    expect(countedSeriesUpTo(A, 'bottomHalfShare', 72).at(-1).value).toBe(valueAt(A, 'bottomHalfShare', 70))
  })

  test('happiness is counted every week', () => {
    expect(COUNTED_EVERY_5).not.toContain('happiness')
    expect(countedAt(A, 'happiness', 72)).toEqual({ value: valueAt(A, 'happiness', 72), asOfTick: 72 })
    expect(countedSeriesUpTo(A, 'happiness', 72)).toHaveLength(72)
  })
})

describe('the other helpers on the demo', () => {
  test('rulesTable flags the minimum wage as the only difference', () => {
    const table = rulesTable([A, B], 72)
    expect(table.map(group => group.group)).toEqual(['taxes', 'people', 'spending', 'business', 'prices'])
    expect(table.filter(group => !group.same).map(group => group.group)).toEqual(['people'])
    const people = table.find(group => group.group === 'people')
    expect(people.rows.find(row => row.lever === 'minimum_wage_policy')).toEqual({
      lever: 'minimum_wage_policy', values: ['neutral', 'high'], differs: true, changedAt: null, was: null, changes: [null, null],
    })
    expect(people.rows.filter(row => row.differs).map(row => row.lever)).toEqual(['minimum_wage_policy'])
    expect(table.find(group => group.group === 'taxes').rows[0]).toMatchObject({ lever: 'wage_tax_rate', values: [0.15, 0.15], differs: false })
  })

  test('weeklyCounts gives the last 26 weeks, ending at the tick', () => {
    const rows = weeklyCounts(A, ['hired', 'laidOff'], 72)
    expect(rows).toHaveLength(26)
    expect(rows[0].tick).toBe(47)
    expect(rows.at(-1)).toEqual({ tick: 72, hired: 6, laidOff: 18 })
  })

  test('firmStatesAt splits the open firms by how they are doing', () => {
    const states = firmStatesAt(A, 72)
    expect(states).toEqual({ growing: 2, steady: 6, struggling: 9 })
    expect(states.growing + states.steady + states.struggling).toBe(valueAt(A, 'firmsOpen', 72))
  })

  test('cumulativeUpTo adds up the money written off so far', () => {
    const expected = A.series.bankDefaultAmountThisTick.slice(0, 72).reduce((sum, value) => sum + (value ?? 0), 0)
    expect(cumulativeUpTo(A, 'bankDefaultAmountThisTick', 72)).toBeCloseTo(expected, 6)
    expect(expected).toBeGreaterThan(0)
  })

  test('rangeSoFar spans both towns after warm-up', () => {
    const range = rangeSoFar([A, B], 'peopleOutOfWorkPer100', 72)
    const seen = [A, B].flatMap(arm => arm.series.peopleOutOfWorkPer100.slice(10, 72))
    expect(range).toEqual({ min: Math.min(...seen), max: Math.max(...seen) })
  })
})

describe('differencePhrase', () => {
  const at = { tick: 72 }

  test('phrases each format neutrally against the first town', () => {
    expect(differencePhrase('peopleOutOfWorkPer100', 31.263, 42.2, at)).toBe('11 fewer in 100 than Town A')
    expect(differencePhrase('peopleOutOfWorkPer100', 45.4, 42.2, at)).toBe('3 more in 100 than Town A')
    expect(differencePhrase('typicalWeeklyPay', 58.227, 46.449, at)).toBe('$12 more than Town A')
    expect(differencePhrase('townHallCash', -11276.486, 80602.696, at)).toBe('$91,879 less than Town A')
    expect(differencePhrase('foodSpendPerHousehold', 4.71, 4.59, at)).toBe('$0.12 more than Town A')
    expect(differencePhrase('priceFood', 4.59, 4.71, at)).toBe('$0.12 less than Town A')
    expect(differencePhrase('gini', 0.551, 0.498, at)).toBe('0.05 higher than Town A')
    expect(differencePhrase('gini', 0.44, 0.498, at)).toBe('0.06 lower than Town A')
    expect(differencePhrase('firmsOpen', 19, 17, at)).toBe('2 more than Town A')
    expect(differencePhrase('careDenials', 1200, 3, at)).toBe('1,197 more than Town A')
    expect(differencePhrase('firmsOpen', 17, 19, at)).toBe('2 fewer than Town A')
    expect(differencePhrase('happiness', 40.295, 22.345, at)).toBe('18 points higher than Town A')
    expect(differencePhrase('happiness', 22.6, 24.1, at)).toBe('1 point lower than Town A')
    expect(differencePhrase('topTenthShare', 49.715, 41.577, at)).toBe('8 percentage points higher than Town A')
    expect(differencePhrase('bottomHalfShare', 16.863, 18.4, at)).toBe('1 percentage point lower than Town A')
  })

  test('says "about the same" when the shown values tie', () => {
    expect(differencePhrase('peopleOutOfWorkPer100', 42.4, 41.6, at)).toBe('about the same as Town A')
    expect(differencePhrase('priceFood', 4.714, 4.706, at)).toBe('about the same as Town A')
    expect(differencePhrase('gini', 0.4149, 0.4051, at)).toBe('about the same as Town A')
    expect(differencePhrase('townHallCash', -0.4, 0.4, at)).toBe('about the same as Town A')
    expect(differencePhrase('topTenthShare', 41.577, 42.2, at)).toBe('about the same as Town A')
    // 10.795 is stored just below itself and shows as $10.79.
    expect(differencePhrase('priceHealthcare', 10.795, 10.79, at)).toBe('about the same as Town A')
    expect(differencePhrase('priceHealthcare', 10.8, 10.795, at)).toBe('$0.01 more than Town A')
  })

  test('names another first town when asked', () => {
    expect(differencePhrase('firmsOpen', 19, 17, { tick: 72, baseLabel: 'Town C' })).toBe('2 more than Town C')
  })

  test('says the towns are still being set up during warm-up', () => {
    expect(differencePhrase('peopleOutOfWorkPer100', valueAt(B, 'peopleOutOfWorkPer100', 5), valueAt(A, 'peopleOutOfWorkPer100', 5), { tick: 5 }))
      .toBe('still being set up')
    expect(differencePhrase('typicalWeeklyPay', 30, 21.6, { tick: 10 })).toBe('still being set up')
    expect(differencePhrase('typicalWeeklyPay', 30, 21.6, { tick: 11 })).toBe('$8 more than Town A')
  })

  test('has nothing to say when either value is missing', () => {
    expect(differencePhrase('happiness', null, 40, at)).toBeNull()
    expect(differencePhrase('happiness', 40, undefined, at)).toBeNull()
  })
})

describe('countedNote', () => {
  test('names the week of the last count', () => {
    expect(countedNote(70)).toBe('Counted every 5 weeks; last count Year 2, week 18.')
    expect(countedNote(1)).toBe('Counted every 5 weeks; last count Year 1, week 1.')
    expect(countedNote(null)).toBe('Counted every 5 weeks.')
  })
})

describe('an older recording without the new keys', () => {
  test('gives null for them, never a zero, and nothing throws', () => {
    const old = [fixtureArm(), fixtureArm(TOWN_B)]
    for (const key of NEW_KEYS) {
      expect(valueAt(old[0], key, 20), key).toBeNull()
      expect(countedAt(old[0], key, 20), key).toBeNull()
      expect(countedSeriesUpTo(old[0], key, 20), key).toEqual([])
      expect(cumulativeUpTo(old[0], key, 20), key).toBeNull()
      expect(rangeSoFar(old, key, 20), key).toBeNull()
      expect(differencePhrase(key, valueAt(old[1], key, 20), valueAt(old[0], key, 20), { tick: 20 }), key).toBeNull()
      expect(formatMetric(key, valueAt(old[0], key, 20)), key).toBe('not measured')
    }
    expect(() => rulesTable(old, 20)).not.toThrow()
    expect(() => weeklyCounts(old[0], ['hired', 'laidOff'], 20)).not.toThrow()
    for (const key of [...NUMBER_GROUPS.flatMap(group => group.keys), ...GLANCE_KEYS]) {
      expect(() => rangeSoFar(old, key, 20)).not.toThrow()
      expect(() => countedAt(old[0], key, 20)).not.toThrow()
    }
  })

  test('still counts the numbers it has', () => {
    const old = fixtureArm()
    expect(countedAt(old, 'gini', 12)).toEqual({ value: valueAt(old, 'gini', 10), asOfTick: 10 })
    expect(cumulativeUpTo(old, 'bankDefaultAmountThisTick', 20)).toBe(0)
    expect(firmStatesAt(old, 12)).toEqual({
      growing: valueAt(old, 'firmsGrowing', 12), steady: valueAt(old, 'firmsSteady', 12), struggling: valueAt(old, 'firmsStruggling', 12),
    })
  })
})
