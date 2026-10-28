import { describe, expect, test } from 'vitest'
import { COPY, NUMBER_GROUPS, TOWN_COLORS, formatMetric } from '../catalog.js'
import {
  differenceWords, rowStatus, rowValues, shouldFold, tally, verdictParts,
} from '../numbers/compare.js'
import { demoArms } from './fixture.js'

const readings = (...values) => values.map(value => ({ value, measured: true }))
const towns = (key, a, b) => [a, b].map((value, index) => ({
  label: `Town ${index === 0 ? 'A' : 'B'}`, color: TOWN_COLORS[index],
  ticks: [20], series: { [key]: [value] }, eventCounts: {}, policyChanges: [],
}))

describe('differences use the displayed values and their displayed units', () => {
  test.each([
    ['wealthP50', 262.6, 272.2, '$263', '$272', '$9 more', 'better'],
    ['wealthP50', 262.6, 207.4, '$263', '$207', '$56 less', 'worse'],
    ['gini', 0.544, 0.528, '0.54', '0.53', '0.01 lower', 'better'],
    ['gini', 0.528, 0.544, '0.53', '0.54', '0.01 higher', 'worse'],
    ['firmsOpen', 10.49, 11.51, '10', '12', '2 more', 'better'],
    ['firmsOpen', 11.51, 10.49, '12', '10', '2 fewer', 'worse'],
    ['netJobs26', -1.49, 1.49, '-1', '+1', '2 more', 'better'],
    ['townHallCash', -263.4, 272.6, 'owes $263', '$273', '$536 more', 'different'],
    ['bottomHalfShare', 13.49, 14.51, '13%', '15%', '2 points higher', 'different'],
    ['topTenthShare', 14.51, 13.49, '15%', '13%', '2 points lower', 'different'],
    ['peopleOutOfWorkPer100', 46.49, 33.51, '46 in 100', '34 in 100', '12 fewer', 'better'],
    ['happiness', 13.49, 25.51, '13 of 100', '26 of 100', '13 points higher', 'better'],
    ['priceFood', 5.404, 6.486, '$5.40', '$6.49', '$1.09 more', 'worse'],
    ['priceServices', 10.795, 10.805, '$10.79', '$10.80', '$0.01 more', 'worse'],
  ])('%s: %s versus %s agrees with %s and %s', (key, a, b, shownA, shownB, expected, status) => {
    expect([formatMetric(key, a), formatMetric(key, b)]).toEqual([shownA, shownB])
    expect(differenceWords(key, a, b)).toBe(expected)
    expect(rowStatus(key, a, b, 20)).toBe(status)
  })

  test.each([
    ['wealthP50', 263.1, 263.4, '$263'],
    ['gini', 0.531, 0.534, '0.53'],
    ['firmsOpen', 10.1, 10.4, '10'],
    ['netJobs26', -0.49, 0.49, '+0'],
    ['townHallCash', -0.49, 0.49, '$0'],
    ['townHallCash', -1000.1, -1000.4, 'owes $1,000'],
    ['bottomHalfShare', 13.1, 13.4, '13%'],
    ['happiness', 13.1, 13.4, '13 of 100'],
    ['peopleOutOfWorkPer100', 33.1, 33.4, '33 in 100'],
    ['priceFood', 5.401, 5.404, '$5.40'],
  ])('%s: equal displayed values have no better/worse tag or nonzero difference', (key, a, b, shown) => {
    expect([formatMetric(key, a), formatMetric(key, b)]).toEqual([shown, shown])
    expect(differenceWords(key, a, b)).toBe(COPY.numbers.difference.same)
    expect(rowStatus(key, a, b, 20)).toBe('same')
    expect(shouldFold(key, readings(a, b))).toBe(key !== 'happiness')
  })

  test.each([
    ['wealthP50', 263.1, 263.4],
    ['gini', 0.531, 0.534],
    ['firmsOpen', 10.1, 10.4],
    ['townHallCash', -0.49, 0.49],
    ['bottomHalfShare', 13.1, 13.4],
  ])('%s: the tally counts rounded equality as same', (key, a, b) => {
    const arms = towns(key, a, b)
    expect(rowValues(arms, key, 20).map(reading => reading.formatted))
      .toEqual([formatMetric(key, a), formatMetric(key, b)])
    expect(tally(arms, [key], 20)).toEqual([
      { label: 'Town B', color: TOWN_COLORS[1], better: 0, worse: 0, different: 0, same: 1 },
    ])
  })

  test('output percentages preserve a visible 25% sales decrease', () => {
    expect([formatMetric('salesExceptRentThisWeek', 400.49), formatMetric('salesExceptRentThisWeek', 300.49)])
      .toEqual(['$400', '$300'])
    expect(differenceWords('salesExceptRentThisWeek', 400.49, 300.49)).toBe('25% less')
  })

  test.each([
    [100.49, 100.51, '$100', '$101', '1% more'],
    [100.51, 100.49, '$101', '$100', '1% less'],
  ])('output percentages use the displayed dollar baseline: %s versus %s', (a, b, shownA, shownB, expected) => {
    expect([formatMetric('salesExceptRentThisWeek', a), formatMetric('salesExceptRentThisWeek', b)])
      .toEqual([shownA, shownB])
    expect(differenceWords('salesExceptRentThisWeek', a, b)).toBe(expected)
  })

  test('equal displayed output never claims a percentage change', () => {
    const key = 'salesExceptRentThisWeek'
    expect([formatMetric(key, 1.49), formatMetric(key, 0.51)]).toEqual(['$1', '$1'])
    expect(differenceWords(key, 1.49, 0.51)).toBe(COPY.numbers.difference.aboutSame)
    expect(rowStatus(key, 1.49, 0.51, 20)).toBe('same')
    expect(tally(towns(key, 1.49, 0.51), [], 20)[0]).toMatchObject({ different: 0, same: 1 })
  })

  test('a whole-percent approximation does not erase visibly different output dollars from the tally', () => {
    const key = 'salesExceptRentThisWeek'
    expect([formatMetric(key, 10000), formatMetric(key, 10001)]).toEqual(['$10,000', '$10,001'])
    expect(differenceWords(key, 10000, 10001)).toBe(COPY.numbers.difference.aboutSame)
    expect(rowStatus(key, 10000, 10001, 20)).toBe('different')
    expect(tally(towns(key, 10000, 10001), [], 20)[0]).toMatchObject({
      better: 0, worse: 0, different: 1, same: 0,
    })
  })

  test.each([0, 0.49])('a displayed zero output baseline (%s raw) states the dollar difference', a => {
    expect([formatMetric('salesExceptRentThisWeek', a), formatMetric('salesExceptRentThisWeek', 0.51)])
      .toEqual(['$0', '$1'])
    expect(differenceWords('salesExceptRentThisWeek', a, 0.51)).toBe('$1 more')
  })

  test('the approved week-104 demo keeps its tally and exact verdict', () => {
    const arms = demoArms()
    const rows = NUMBER_GROUPS.flatMap(group => group.rows)
    expect(tally(arms, rows, 104)).toEqual([
      { label: 'Town B', color: TOWN_COLORS[1], better: 8, worse: 2, different: 8, same: 4 },
    ])
    expect(verdictParts(arms, rows, 104)[0].parts.map(part => part.text).join('')).toBe(
      'Town B is ahead on jobs, pay, savings and businesses, and its people feel better. '
      + 'Food and services cost more there. The gap between rich and poor is the same, '
      + 'but the poorer half holds a little less of the cash in Town B.',
    )
  })
})
