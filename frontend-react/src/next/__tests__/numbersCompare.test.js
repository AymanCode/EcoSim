import { beforeAll, describe, expect, test } from 'vitest'
import { COPY, NUMBER_GROUPS, TOWN_COLORS, WARMUP_TICKS } from '../catalog.js'
import {
  differenceWords, foldLines, heroNotes, nextFoldKeys, rowDefinition, rowSeries, rowStatus,
  rowValues, shouldFold, tally, verdictParts, visibleRows,
} from '../numbers/compare.js'
import { demoArms } from './fixture.js'

const rows = NUMBER_GROUPS.flatMap(group => group.rows)
let demo
beforeAll(() => { demo = demoArms() })
const sentence = verdict => verdict.parts.map(part => part.text).join('')
const readings = (...values) => values.map(value => ({ value, measured: typeof value === 'number' }))
const arm = (series = {}, extra = {}) => ({
  label: 'Town A', color: TOWN_COLORS[0], ticks: [1, 20], series,
  eventCounts: {}, policyChanges: [], ...extra,
})
const pair = key => [
  arm({ [key]: [100, 100] }),
  arm({ [key]: [100, 110] }, { label: 'Town B', color: TOWN_COLORS[1] }),
]

describe('numbers comparison: approved recorded demo at week 104', () => {
  test.each([
    ['peopleOutOfWorkPer100', '46 in 100', '33 in 100', '13 fewer', 'better'],
    ['typicalWeeklyPay', '$49', '$61', '$12 more', 'better'],
    ['netJobs26', '+17', '+83', '66 more', 'better'],
    ['foodSpendPerHousehold', '$18.71', '$24.99', '$6.28 more', 'different'],
    ['priceFood', '$5.40', '$6.49', '$1.09 more', 'worse'],
    ['priceServices', '$24.79', '$32.20', '$7.41 more', 'worse'],
    ['wealthP50', '$85', '$131', '$46 more', 'better'],
    ['bottomHalfShare', '14%', '13%', '1 point lower', 'different'],
    ['careSoFar', '4', '1', '3 fewer', 'better'],
    ['firmsOpen', '15', '16', '1 more', 'better'],
    ['writtenOffSoFar', '$106,156', '$83,238', '$22,918 less', 'better'],
    ['townHallCash', 'owes $65,919', '$61,636', '$127,555 more', 'different'],
    ['townHallIncome', '$4,593', '$7,542', '$2,949 more', 'different'],
    ['familySupportPaid', '$8,682', '$5,408', '$3,274 less', 'different'],
  ])('%s has one row and the approved values and comparison', (key, a, b, words, status) => {
    const values = rowValues(demo, key, 104)
    expect(values.map(reading => reading.formatted)).toEqual([a, b])
    expect(differenceWords(key, values[0].value, values[1].value)).toBe(words)
    expect(rowStatus(key, values[0].value, values[1].value, 104)).toBe(status)
  })

  test('the two heroes and the tally include each measure once', () => {
    const output = rowValues(demo, 'salesExceptRentThisWeek', 104)
    expect(output.map(reading => reading.formatted)).toEqual(['$22,522', '$35,726'])
    expect(differenceWords('salesExceptRentThisWeek', output[0].value, output[1].value)).toBe('59% more')
    expect(rowStatus('salesExceptRentThisWeek', output[0].value, output[1].value)).toBe('different')
    const wellbeing = rowValues(demo, 'happiness', 104)
    expect(wellbeing.map(reading => reading.formatted)).toEqual(['13 of 100', '26 of 100'])
    expect(differenceWords('happiness', wellbeing[0].value, wellbeing[1].value)).toBe('13 points higher')
    expect(tally(demo, rows, 104)).toEqual([
      { label: 'Town B', color: TOWN_COLORS[1], better: 8, worse: 2, different: 8, same: 4 },
    ])
    expect(tally(demo, [...rows, ...rows, { key: 'happiness' }], 104)).toEqual(tally(demo, rows, 104))
  })

  test('the four exact-equality folds follow the revised owner rule; public works is hidden', () => {
    const visible = visibleRows(demo, rows, 104)
    expect(visible.map(row => row.key)).not.toContain('publicWorksJobs')
    const folded = visible.filter(row => shouldFold(row, rowValues(demo, row, 104)))
    expect(folded.map(row => row.key).sort()).toEqual([
      'gini', 'priceHousing', 'priceHealthcare', 'homelessHouseholds',
    ].sort())
    expect(shouldFold('bottomHalfShare', rowValues(demo, 'bottomHalfShare', 104))).toBe(false)
    const folds = foldLines(demo, folded, 104)
    expect(folds.map(line => line.label)).toEqual(['Same in both towns:'])
    const housing = folds[0].items.find(item => item.key === 'priceHousing')
    expect(housing.values).toEqual(['$5.00'])
    expect(shouldFold('bankActiveLoans', rowValues(demo, 'bankActiveLoans', 104))).toBe(false)
    expect(shouldFold('topTenthShare', rowValues(demo, 'topTenthShare', 104))).toBe(false)
  })

  test('the week-104 verdict stays byte-identical, links every named term, and contains no digit', () => {
    const [verdict] = verdictParts(demo, rows, 104)
    expect(sentence(verdict)).toBe('Town B is ahead on jobs, pay, savings and businesses, and its people feel better. Food and services cost more there. The gap between rich and poor is the same, but the poorer half holds a little less of the cash in Town B.')
    expect(sentence(verdict)).not.toMatch(/\d/)
    expect(verdict.parts.filter(part => part.rowId).map(part => part.rowId)).toEqual([
      'peopleOutOfWorkPer100', 'typicalWeeklyPay', 'wealthP50', 'firmsOpen',
      'priceFood', 'priceServices', 'gini', 'bottomHalfShare',
    ])
  })
})

describe('wellbeing start notes use displayed values', () => {
  test('one town omits the week-one start, keeps a moved start, and omits it when scrubbed back', () => {
    const towns = [arm({ happiness: [69.1, 51.2] })]
    expect(heroNotes(towns, 'happiness', 1)).toEqual([])
    expect(heroNotes(towns, 'happiness', 20)).toEqual(['The town started at 69.'])
    expect(heroNotes(towns, 'happiness', 1)).toEqual([])
  })

  test('a raw change that rounds to the same reading does not repeat the start', () => {
    const towns = [arm({ happiness: [69.1, 69.4] })]
    expect(rowValues(towns, 'happiness', 20)[0].formatted).toBe('69 of 100')
    expect(heroNotes(towns, 'happiness', 20)).toEqual([])
  })

  test.each([2, 3, 4])('%s towns keep their shared-start wording only once every current reading has moved', townCount => {
    const towns = Array.from({ length: townCount }, (_, index) => arm({ happiness: [69.1 + index * 0.1, 50 + index] }, {
      label: `Town ${String.fromCharCode(65 + index)}`, color: TOWN_COLORS[index],
    }))
    expect(heroNotes(towns, 'happiness', 1)).toEqual([])
    expect(heroNotes(towns, 'happiness', 20)).toEqual([
      townCount === 2 ? 'Both towns started at 69.' : 'All towns started at 69.',
    ])

    towns.forEach((town, index) => {
      const stillAtStart = towns.map((other, otherIndex) => otherIndex === index
        ? { ...town, series: { happiness: [town.series.happiness[0], 69.4] } }
        : other)
      expect(heroNotes(stillAtStart, 'happiness', 20)).toEqual([])
    })
  })

  test('different displayed starts still have no shared-start note after the towns move', () => {
    const towns = [
      arm({ happiness: [69.4, 50] }),
      arm({ happiness: [69.6, 51] }, { label: 'Town B' }),
    ]
    expect(heroNotes(towns, 'happiness', 20)).toEqual([])
  })
})

describe('numbers comparison states', () => {
  test.each([
    ['priceServices', 'services', 12, 'Services cost more there.'],
    ['priceServices', 'services', 8, 'Services cost less there.'],
    ['priceFood', 'food', 12, 'Food costs more there.'],
    ['priceFood', 'food', 8, 'Food costs less there.'],
  ])('a two-town price-only %s verdict names its town and agrees with its noun at %s', (key, verdictWord, price, expected) => {
    const towns = [
      arm({ [key]: [10, 10] }),
      arm({ [key]: [price, price] }, { label: 'Town B' }),
    ]
    expect(sentence(verdictParts(towns, [{ key, verdictWord }], 20)[0])).toBe(`Town B: ${expected}`)
  })

  test('three price-only towns identify each comparison town and preserve row links', () => {
    const towns = [5, 6, 4].map((price, index) => arm({ priceFood: [price, price] }, {
      label: ['Town A', 'Town B', 'Town C'][index], color: TOWN_COLORS[index],
    }))
    const verdicts = verdictParts(towns, rows, 20)
    expect(verdicts.map(sentence)).toEqual([
      'Town B: Food costs more there.',
      'Town C: Food costs less there.',
    ])
    verdicts.forEach(verdict => {
      expect(verdict.parts.filter(part => part.rowId).map(part => part.rowId)).toEqual(['priceFood'])
      expect(sentence(verdict)).not.toMatch(/\d/)
    })
  })

  test('unchanged headline measures do not leave mixed price clauses without a town', () => {
    const shared = { typicalWeeklyPay: [40, 40], happiness: [50, 50] }
    const towns = [
      arm({ ...shared, priceFood: [5, 5], priceServices: [10, 10] }),
      arm({ ...shared, priceFood: [6, 6], priceServices: [9, 9] }, { label: 'Town B' }),
    ]
    expect(sentence(verdictParts(towns, rows, 20)[0]))
      .toBe('Town B: Food costs more there. Services cost less there.')
  })

  test.each([3, 4])('%s-town price-led verdicts name their town before there, even when the ending names it too', townCount => {
    const towns = [10, 12, 8, 14].slice(0, townCount).map((price, index) => arm({
      priceServices: [price, price], gini: [0.5, 0.5], bottomHalfShare: [20, 20],
      typicalWeeklyPay: [40, 40], happiness: [50, 50],
    }, { label: ['Town A', 'Town B', 'Town C', 'Town D'][index], color: TOWN_COLORS[index] }))
    const verdicts = verdictParts(towns, rows, 20)
    verdicts.forEach((verdict, index) => {
      const text = sentence(verdict)
      const label = towns[index + 1].label
      expect(text.startsWith(`${label}: Services cost `)).toBe(true)
      expect(text.indexOf(label)).toBeLessThan(text.indexOf('there'))
      expect(text).toContain(`in ${label}.`)
      expect(verdict.parts.filter(part => part.rowId).map(part => part.rowId)).toEqual(['priceServices', 'gini', 'bottomHalfShare'])
    })
  })

  test('multi-town clauses name their town before its and gap-led paragraphs also identify their town first', () => {
    const towns = [
      arm({ typicalWeeklyPay: [40, 40], happiness: [50, 50], gini: [0.5, 0.5], bottomHalfShare: [20, 20] }),
      arm({ typicalWeeklyPay: [50, 50], happiness: [60, 60], gini: [0.5, 0.5], bottomHalfShare: [20, 20] }, { label: 'Town B' }),
      arm({ typicalWeeklyPay: [40, 40], happiness: [50, 50], gini: [0.6, 0.6], bottomHalfShare: [10, 10] }, { label: 'Town C' }),
    ]
    const [jobs, gap] = verdictParts(towns, rows, 20).map(sentence)
    expect(jobs.startsWith('Town B is ahead on pay')).toBe(true)
    expect(jobs.indexOf('Town B')).toBeLessThan(jobs.indexOf('its'))
    expect(gap.startsWith('Town C: The gap between rich and poor')).toBe(true)
  })

  test.each([
    [0.6, 10, 'wider', 'less', 'and'],
    [0.6, 30, 'wider', 'more', 'but'],
    [0.6, 20, 'wider', 'same', 'but'],
    [0.4, 10, 'narrower', 'less', 'but'],
    [0.4, 30, 'narrower', 'more', 'and'],
    [0.4, 20, 'narrower', 'same', 'but'],
    [0.5, 10, 'the same', 'less', 'but'],
    [0.5, 30, 'the same', 'more', 'but'],
    [0.5, 20, 'the same', 'same', 'and'],
  ])('gap %s and poorer-half share %s use %s / %s joined with %s', (gap, share, gapWords, shareWords, joiner) => {
    const towns = [
      arm({ gini: [0.5, 0.5], bottomHalfShare: [20, 20] }),
      arm({ gini: [gap, gap], bottomHalfShare: [share, share] }, { label: 'Town B' }),
    ]
    const shareClause = shareWords === 'same' ? 'the same share of the cash' : `a little ${shareWords} of the cash`
    expect(sentence(verdictParts(towns, rows, 20)[0]))
      .toBe(`The gap between rich and poor is ${gapWords}, ${joiner} the poorer half holds ${shareClause} in Town B.`)
  })

  test.each([
    [{ happiness: [50, 60] }, "Town B's people feel better."],
    [{ typicalWeeklyPay: [40, 50] }, 'Town B is ahead on pay.'],
    [{ gini: [0.5, 0.5] }, 'The gap between rich and poor is the same in Town B.'],
    [{ bottomHalfShare: [20, 20] }, 'The poorer half holds the same share of the cash in Town B.'],
  ])('an existing town-naming clause needs no lead-in: %s', (series, expected) => {
    const [verdict] = verdictParts([
      arm(Object.fromEntries(Object.entries(series).map(([key, values]) => [key, [values[0], values[0]]]))),
      arm(series, { label: 'Town B' }),
    ], rows, 20)
    expect(sentence(verdict)).toBe(expected)
  })

  test('the week-12 demo uses the plural services verb', () => {
    const text = sentence(verdictParts(demo, rows, 12)[0])
    expect(text).toContain('Services cost more there.')
    expect(text).not.toContain('Services costs')
  })

  test.each([
    [100, 99.6, 'about the same'],
    [100, 100.4, 'about the same'],
    [100, 100, 'about the same'],
    [0, 0, 'about the same'],
    [100, 99.4, '1% less'],
    [100, 100.6, '1% more'],
  ])('output %s versus %s describes the rounded percentage', (a, b, expected) => {
    expect(differenceWords('salesExceptRentThisWeek', a, b)).toBe(expected)
  })

  test('warm-up keeps readings available but has no judgment, verdict or tally', () => {
    expect(rowValues(demo, 'typicalWeeklyPay', 5).every(reading => reading.value !== null)).toBe(true)
    expect(rowStatus('typicalWeeklyPay', 30, 40, WARMUP_TICKS)).toBe('warmup')
    expect(tally(demo, rows, 5)).toEqual([])
    expect(verdictParts(demo, rows, 5)).toEqual([])
    expect(rowStatus('typicalWeeklyPay', 30, 40, WARMUP_TICKS + 1)).toBe('better')
  })

  test('one town has no comparisons or folds', () => {
    expect(rowValues([demo[0]], 'typicalWeeklyPay', 104)).toHaveLength(1)
    expect(tally([demo[0]], rows, 104)).toEqual([])
    expect(verdictParts([demo[0]], rows, 104)).toEqual([])
    expect(shouldFold('gini', rowValues([demo[0]], 'gini', 104))).toBe(false)
    expect(foldLines([demo[0]], rows, 104)).toEqual([])
  })

  test('three and four towns compare with A and require every town to pass the fold', () => {
    const third = { ...demo[0], label: 'Town C', color: TOWN_COLORS[2] }
    const fourth = { ...demo[1], label: 'Town D', color: TOWN_COLORS[3] }
    const towns = [...demo, third, fourth]
    expect(rowValues(towns, 'firmsOpen', 104).map(value => value.formatted)).toEqual(['15', '16', '15', '16'])
    const counts = tally(towns, rows, 104)
    expect(counts.map(count => count.label)).toEqual(['Town B', 'Town C', 'Town D'])
    expect(counts[1]).toMatchObject({ better: 0, worse: 0, different: 0, same: 22 })
    expect(counts[2]).toMatchObject({ better: 8, worse: 2, different: 8, same: 4 })
    expect(verdictParts(towns, rows, 104)).toHaveLength(3)
    verdictParts(towns, rows, 104).forEach(verdict => expect(sentence(verdict)).not.toMatch(/\d/))
    expect(shouldFold('bankActiveLoans', readings(1000, 990, 950))).toBe(false)
    expect(shouldFold('bankActiveLoans', readings(1000, 1000, 1000))).toBe(true)
    expect(foldLines(towns.slice(0, 3), [{ key: 'priceHousing' }], 104)[0].label).toBe('Same in every town:')
  })

  test('not measured is never zero, tagged, folded or tallied', () => {
    const missing = [arm(), arm({}, { label: 'Town B' })]
    expect(rowValues(missing, 'bankActiveLoans', 20)).toEqual(missing.map(town => ({
      label: town.label, color: town.color, value: null, formatted: COPY.numbers.notMeasured,
      measured: false, asOfTick: 20,
    })))
    expect(rowStatus('bankActiveLoans', null, 3, 20)).toBe('notMeasured')
    expect(differenceWords('bankActiveLoans', null, 3)).toBe('')
    expect(shouldFold('bankActiveLoans', rowValues(missing, 'bankActiveLoans', 20))).toBe(false)
    expect(tally(missing, [{ key: 'bankActiveLoans' }], 20)[0]).toMatchObject({ better: 0, worse: 0, different: 0, same: 0 })
    expect(sentence(verdictParts(missing, rows, 20)[0])).toBe(COPY.numbers.verdict.noComparison('Town B'))
    expect(shouldFold('bankActiveLoans', readings(0, null))).toBe(false)
    expect(foldLines(missing, [{ key: 'bankActiveLoans' }], 20)).toEqual([])
  })

  test('a missing town does not inherit another town\'s measured status', () => {
    const towns = [arm({ bankActiveLoans: [0, 0] }), arm({}, { label: 'Town B' })]
    expect(rowValues(towns, 'bankActiveLoans', 20).map(value => value.measured)).toEqual([true, false])
    expect(tally(towns, [{ key: 'bankActiveLoans' }], 20)[0].same).toBe(0)
    expect(shouldFold('bankActiveLoans', rowValues(towns, 'bankActiveLoans', 20))).toBe(false)
  })

  test('both zero and display equality fold, but open rows and heroes do not', () => {
    expect(shouldFold('bankActiveLoans', readings(0, 0))).toBe(true)
    expect(shouldFold('gini', readings(0.6301, 0.634))).toBe(true)
    expect(shouldFold('bankActiveLoans', readings(0, 0), true)).toBe(false)
    expect(shouldFold('happiness', readings(69, 69))).toBe(false)
    expect(rowStatus('gini', 0.6301, 0.634, 20)).toBe('same')
  })

  test('near values stay as rows, including negative balances', () => {
    expect(shouldFold('bankActiveLoans', readings(970, 1000))).toBe(false)
    expect(shouldFold('bankActiveLoans', readings(999, 1000))).toBe(false)
    expect(shouldFold('townHallCash', readings(-999, -1000))).toBe(false)
    expect(shouldFold('townHallCash', readings(-1000.1, -1000.2))).toBe(true)
    expect(shouldFold('townHallCash', readings(-1, 1))).toBe(false)
    const towns = [arm({ townHallCash: [-20, -20] }), arm({ townHallCash: [30, 30] }, { label: 'Town B' })]
    expect(rowValues(towns, 'townHallCash', 20).map(value => value.formatted)).toEqual(['owes $20', '$30'])
    expect(differenceWords('townHallCash', -20, 30)).toBe('$50 more')
    expect(rowStatus('townHallCash', -20, 30)).toBe('different')
  })

  test('a stale fold set never overrides the tally\'s current values', () => {
    const towns = pair('bankActiveLoans')
    const bankRow = [{ key: 'bankActiveLoans' }]
    expect(tally(towns, bankRow, 1)).toEqual([])
    expect(tally(towns, bankRow, 20)[0].different).toBe(1)
    expect(tally(towns, bankRow, 20, ['bankActiveLoans'])[0].different).toBe(1)
    expect(tally(towns, bankRow, 20, [])[0].different).toBe(1)
  })

  test('playing promotes diverging rows immediately and only pause can fold them again', () => {
    const bankRow = [{ key: 'bankActiveLoans' }]
    const towns = [
      arm({ bankActiveLoans: [100, 100, 100] }, { ticks: [11, 20, 30] }),
      arm({ bankActiveLoans: [100, 110, 100] }, { label: 'Town B', ticks: [11, 20, 30] }),
    ]
    let folded = nextFoldKeys(towns, bankRow, 11, [], false)
    expect(folded).toEqual(['bankActiveLoans'])
    folded = nextFoldKeys(towns, bankRow, 20, folded, true)
    expect(folded).toEqual([])
    expect(foldLines(towns, bankRow, 20)).toEqual([])
    expect(tally(towns, bankRow, 20)[0]).toMatchObject({ different: 1, same: 0 })
    folded = nextFoldKeys(towns, bankRow, 30, folded, true)
    expect(folded).toEqual([])
    expect(tally(towns, bankRow, 30)[0]).toMatchObject({ different: 0, same: 1 })
    folded = nextFoldKeys(towns, bankRow, 30, folded, false)
    expect(folded).toEqual(['bankActiveLoans'])
    expect(nextFoldKeys(towns, bankRow, 30, folded, true, ['bankActiveLoans'])).toEqual([])
    expect(nextFoldKeys(towns, bankRow, 30, folded, false, ['bankActiveLoans'])).toEqual([])
  })

  test('scrubbing reads only the week shown and the derived histories agree', () => {
    const source = arm({ careDenials: [null, 2, 1] }, {
      ticks: [1, 2, 27], eventCounts: { 1: { hired: 10, laidOff: 0 }, 2: { hired: 0, laidOff: 2 }, 27: { hired: 3, laidOff: 0 } },
    })
    expect(rowValues([source], 'netJobs26', 2)[0].value).toBe(8)
    expect(rowValues([source], 'netJobs26', 27)[0].value).toBe(1)
    expect(rowValues([source], 'careSoFar', 1)[0].value).toBeNull()
    expect(rowValues([source], 'careSoFar', 2)[0].value).toBe(2)
    expect(rowSeries(source, 'careSoFar', 27)).toEqual([{ tick: 1, value: null }, { tick: 2, value: 2 }, { tick: 27, value: 3 }])
    expect(rowSeries(source, 'netJobs26', 27).at(-1).value).toBe(rowValues([source], 'netJobs26', 27)[0].value)
    expect(rowSeries(demo[0], 'writtenOffSoFar', 104).at(-1).value).toBeCloseTo(rowValues(demo, 'writtenOffSoFar', 104)[0].value)
    expect(rowValues(demo, 'happiness', 30)[0].formatted).not.toBe(rowValues(demo, 'happiness', 104)[0].formatted)
  })

  test('counted metrics expose the actual count week rather than the scrub week', () => {
    const source = arm({ wealthP50: [40, 50, 50], wealthAsOfTick: [65, 70, 70] }, { ticks: [65, 70, 72] })
    expect(rowValues([source], 'wealthP50', 72)[0]).toMatchObject({ value: 50, asOfTick: 70 })
    expect(rowSeries(source, 'wealthP50', 72)).toEqual([{ tick: 65, value: 40 }, { tick: 70, value: 50 }])
    expect(rowDefinition('wealthP50')).toMatchObject({ name: 'Typical savings', sub: 'the middle household', better: 'higher' })
  })

  test('public works follows current rules including mid-run changes', () => {
    const publicRow = rows.filter(row => row.key === 'publicWorksJobs')
    const towns = [arm({}, { policyChanges: [{ tick: 15, policy: 'public_works', value: 'on' }] })]
    expect(visibleRows(towns, publicRow, 14)).toEqual([])
    expect(visibleRows(towns, publicRow, 15)).toEqual(publicRow)
  })

  test('hero notes are conditional on current prices and rounded starting values', () => {
    expect(heroNotes(demo, 'salesExceptRentThisWeek', 104)).toEqual([COPY.numbers.heroes.priceNote])
    expect(heroNotes(demo, 'happiness', 104)).toEqual(['Both towns started at 69.'])
    expect(heroNotes([demo[0]], 'salesExceptRentThisWeek', 104)).toEqual([])
    expect(heroNotes([demo[0], demo[0]], 'salesExceptRentThisWeek', 104)).toEqual([])
    const other = arm({ happiness: [70, 70] }, { label: 'Town B' })
    expect(heroNotes([demo[0], other], 'happiness', 20)).toEqual([])
    expect(heroNotes(demo, 'happiness', 0)).toEqual([])
    expect(heroNotes([...demo, { ...demo[1], label: 'Town C' }], 'salesExceptRentThisWeek', 104))
      .toEqual([COPY.numbers.heroes.priceNoteTown('Town B'), COPY.numbers.heroes.priceNoteTown('Town C')])
  })

  test.each([
    [90, 6, 12, false],
    [100.4, 4, 12, false],
    [99.6, 4, 12, false],
    [100, 4, 12, false],
    [null, 4, 12, false],
    [110, 4, 12, true],
    [110, 4, 10, false],
    [110, null, null, false],
    [110, 5.004, 10, false],
    [110, 5.006, 10, true],
  ])('output %s, food %s and services %s give a price note: %s', (output, food, services, expected) => {
    const towns = [
      arm({ salesExceptRentThisWeek: [100, 100], priceFood: [5, 5], priceServices: [10, 10] }),
      arm({ salesExceptRentThisWeek: [output, output], priceFood: [food, food], priceServices: [services, services] }, { label: 'Town B' }),
    ]
    expect(heroNotes(towns, 'salesExceptRentThisWeek', 20)).toEqual(expected ? [COPY.numbers.heroes.priceNote] : [])
  })

  test('the week-5 demo has no price note despite higher services because its output gap rounds to zero', () => {
    const output = rowValues(demo, 'salesExceptRentThisWeek', 5)
    expect(differenceWords('salesExceptRentThisWeek', output[0].value, output[1].value)).toBe(COPY.numbers.difference.aboutSame)
    const food = rowValues(demo, 'foodSpendPerHousehold', 5)
    const services = rowValues(demo, 'priceServices', 5)
    expect(food[1].value).toBeLessThan(food[0].value)
    expect(services[1].value).toBeGreaterThan(services[0].value)
    expect(heroNotes(demo, 'salesExceptRentThisWeek', 5)).toEqual([])
  })

  test('each multi-town price note independently needs higher sales and a higher included price', () => {
    const towns = [
      arm({ salesExceptRentThisWeek: [100, 100], priceServices: [10, 10], priceHousing: [10, 10] }),
      arm({ salesExceptRentThisWeek: [90, 90], priceServices: [12, 12], priceHousing: [10, 10] }, { label: 'Town B' }),
      arm({ salesExceptRentThisWeek: [110, 110], priceServices: [9, 9], priceHousing: [12, 12] }, { label: 'Town C' }),
      arm({ salesExceptRentThisWeek: [110, 110], priceServices: [12, 12], priceHousing: [10, 10] }, { label: 'Town D' }),
    ]
    expect(heroNotes(towns, 'salesExceptRentThisWeek', 20)).toEqual([COPY.numbers.heroes.priceNoteTown('Town D')])
  })

  test.each(['priceFood', 'priceServices', 'priceHealthcare'])('higher %s can explain higher dollar output after warm-up', key => {
    const towns = [
      arm({ salesExceptRentThisWeek: [100, 100], [key]: [5, 5] }),
      arm({ salesExceptRentThisWeek: [110, 110], [key]: [6, 6] }, { label: 'Town B' }),
    ]
    expect(heroNotes(towns, 'salesExceptRentThisWeek', 20)).toEqual([COPY.numbers.heroes.priceNote])
    expect(heroNotes(towns, 'salesExceptRentThisWeek', 5)).toEqual([])
  })

  test.each([90, 110])('higher housing alone never triggers a note when output is %s', output => {
    const towns = [
      arm({ salesExceptRentThisWeek: [100, 100], priceFood: [5, 5], priceServices: [10, 10], priceHealthcare: [10, 10], priceHousing: [11, 11] }),
      arm({ salesExceptRentThisWeek: [output, output], priceFood: [4, 4], priceServices: [9, 9], priceHealthcare: [10, 10], priceHousing: [12, 12] }, { label: 'Town B' }),
    ]
    expect(heroNotes(towns, 'salesExceptRentThisWeek', 20)).toEqual([])
  })

  test('a missing control output cannot support a price note', () => {
    const towns = [
      arm({ priceFood: [5, 5] }),
      arm({ salesExceptRentThisWeek: [110, 110], priceFood: [6, 6] }, { label: 'Town B' }),
    ]
    expect(heroNotes(towns, 'salesExceptRentThisWeek', 20)).toEqual([])
  })
})
