import { describe, expect, test } from 'vitest'
import { fireEvent, render, within } from '@testing-library/react'
import { COPY, TOWN_COLORS } from '../catalog.js'
import { countedSeriesUpTo, cumulativeUpTo } from '../data/derive.js'
import StoryChart from '../components/StoryChart.jsx'
import HiresAndLayoffs from '../numbers/HiresAndLayoffs.jsx'
import NumberRow from '../numbers/NumberRow.jsx'
import NumbersSheet from '../numbers/NumbersSheet.jsx'
import { foldLines, rowSeries, rowValues, shouldFold, tally, verdictParts } from '../numbers/compare.js'
import { rowHistory } from '../numbers/rowHistory.js'

function arm(label = 'Town A', series = {}, weeks = 40) {
  return {
    label, color: TOWN_COLORS[label === 'Town A' ? 0 : 1],
    ticks: Array.from({ length: weeks }, (_, index) => index + 1),
    series, eventCounts: {}, events: [], policyChanges: [], setup: {}, horizon: weeks,
  }
}

function employed(label) {
  const town = arm(label)
  town.eventCounts = Object.fromEntries(town.ticks.map(tick => [tick, { hired: 2, laidOff: 1 }]))
  return town
}

function countedTown(label = 'Town A', missing = []) {
  const town = arm(label)
  town.ticks = Array.from({ length: 21 }, (_, index) => index + 15)
  town.series.wealthAsOfTick = town.ticks.map(tick => Math.floor(tick / 5) * 5)
  town.series.gini = town.ticks.map((tick, index) => missing.includes(tick) ? null : town.series.wealthAsOfTick[index] / 100)
  return town
}

const tallySize = count => count.better + count.worse + count.different + count.same
const cellTexts = row => [...row.children].map(cell => cell.textContent)
const moves = path => (path.getAttribute('d').match(/M/g) ?? []).length

describe('missing event windows', () => {
  test.each(['hired', 'laidOff'])('a missing %s week invalidates the complete window and recovers only after it leaves', key => {
    const towns = [employed('Town A'), employed('Town B')]
    delete towns[1].eventCounts[12][key]
    const row = { key: 'netJobs26', verdictWord: 'jobs' }
    const readings = rowValues(towns, row, 15)
    expect(readings.map(reading => reading.value)).toEqual([15, null])
    expect(readings[1]).toMatchObject({ measured: true, formatted: COPY.numbers.missingReading })
    expect(shouldFold(row, readings)).toBe(false)
    expect(foldLines(towns, [row], 15)).toEqual([])
    expect(tallySize(tally(towns, [row], 15)[0])).toBe(0)
    expect(verdictParts(towns, [row], 15)[0].parts.some(part => part.rowId === row.key)).toBe(false)
    expect(rowValues(towns, row, 37)[1].value).toBeNull()
    expect(rowValues(towns, row, 38)[1].value).toBe(26)
    expect(rowHistory(towns[1], row, 38)).toEqual(rowSeries(towns[1], row, 38))
  })

  test.each(['hired', 'laidOff'])('the opened hires chart keeps a missing %s cell and suppresses incomplete totals', key => {
    const town = employed('Town B')
    delete town.eventCounts[12][key]
    const { container } = render(<HiresAndLayoffs arms={[town]} tick={12} inline />)
    const panel = container.querySelector('.nx-vpanel')
    expect(panel.querySelector('.nx-vhead')).toHaveTextContent(COPY.numbers.hires.thisWeekMissing)
    expect(panel.querySelector('.nx-foot')).toHaveTextContent(COPY.numbers.missingReading)
    expect(panel.querySelector('.nx-foot')).not.toHaveTextContent('In these weeks:')
    const rows = within(container.querySelector('table')).getAllByRole('row').slice(1)
    expect(cellTexts(rows[11])).toEqual([
      'Year 1, week 12', key === 'hired' ? COPY.numbers.notRecorded : '2', key === 'laidOff' ? COPY.numbers.notRecorded : '1',
    ])
  })

  test('a town with no event readings yet keeps the run-wide footer despite other-town and future counts', () => {
    const missing = arm('Town B')
    missing.eventCounts[4] = { hired: 2, laidOff: 0 }
    const { container } = render(<HiresAndLayoffs arms={[employed('Town A'), missing]} tick={3} inline />)
    const footer = container.querySelectorAll('.nx-vpanel .nx-foot')[1]
    expect(footer).toHaveTextContent(COPY.numbers.notMeasured)
    expect(footer).not.toHaveTextContent(COPY.numbers.missingReading)
  })
})

describe('missing cumulative contributions', () => {
  test.each([
    ['careSoFar', 'careDenials'],
    ['writtenOffSoFar', 'bankDefaultAmountThisTick'],
  ])('%s keeps the known prefix and stays unknown after readings resume', (key, source) => {
    const values = [0, 2, null, 3]
    const town = arm('Town A', { [source]: values }, values.length)
    const expected = [{ tick: 1, value: 0 }, { tick: 2, value: 2 }, { tick: 3, value: null }, { tick: 4, value: null }]
    expect([1, 2, 3, 4].map(tick => cumulativeUpTo(town, source, tick))).toEqual([0, 2, null, null])
    expect(rowSeries(town, key, 4)).toEqual(expected)
    expect(rowHistory(town, key, 4)).toEqual(expected)
    expect(rowHistory(town, key, 2)).toEqual(expected.slice(0, 2))
    expect(rowHistory(town, key, 4)).toEqual(expected)
    const control = arm('Town B', { [source]: [0, 2, 0, 3] }, 4)
    expect(rowValues([town, control], key, 4)[0].formatted).toBe(COPY.numbers.missingReading)
    expect(shouldFold(key, rowValues([town, control], key, 4))).toBe(false)
    expect(tallySize(tally([town, control], [key], 15)[0])).toBe(0)
  })

  test.each([
    ['careSoFar', 'careDenials', ['0', '2']],
    ['writtenOffSoFar', 'bankDefaultAmountThisTick', ['$0', '$2']],
  ])('the opened %s chart retains the measured prefix when both totals become unknown', (key, source, prefix) => {
    const towns = ['Town A', 'Town B'].map(label => arm(label, { [source]: [0, 2, null, 3] }, 4))
    const { container } = render(<NumbersSheet arms={towns} tick={4} onClose={() => {}} />)
    const row = container.querySelector(`.nx-number-row[data-metric="${key}"]`)
    fireEvent.click(row.querySelector('button[aria-expanded]'))
    const table = row.querySelector('table')
    expect(table).not.toBeNull()
    expect(within(table).getAllByRole('row').slice(1).map(cellTexts)).toEqual([
      ['Year 1, week 1', prefix[0], prefix[0]],
      ['Year 1, week 2', prefix[1], prefix[1]],
      ['Year 1, week 3', COPY.numbers.notRecorded, COPY.numbers.notRecorded],
      ['Year 1, week 4', COPY.numbers.notRecorded, COPY.numbers.notRecorded],
    ])
    expect(row.querySelectorAll('.nx-warmline')).toHaveLength(2)
    for (const path of row.querySelectorAll('.nx-warmline')) expect(path.getAttribute('d').match(/[ML]/g)).toHaveLength(2)
  })
})

describe('counted chart gaps and five-week sampling', () => {
  test('normal weekly carries retain only real counts and a continuous line', () => {
    const town = countedTown()
    const expected = [15, 20, 25, 30, 35].map(tick => ({ tick, value: tick / 100 }))
    expect(countedSeriesUpTo(town, 'gini', 35)).toEqual(expected)
    expect(rowHistory(town, 'gini', 35)).toEqual(expected)
    const { container } = render(<StoryChart arms={[town]} metricKey="gini" tick={35} horizon={40} countedWeeks inline hideEndLabels />)
    expect(moves(container.querySelector('.nx-line'))).toBe(1)
  })

  test('missing counted readings break both charts and keep the missing week in their tables', () => {
    const missing = Array.from({ length: 11 }, (_, index) => index + 20)
    const town = countedTown('Town B', missing)
    const expected = [
      { tick: 15, value: 0.15 }, ...missing.map(tick => ({ tick, value: null })),
      { tick: 31, value: 0.3 }, { tick: 35, value: 0.35 },
    ]
    expect(countedSeriesUpTo(town, 'gini', 35)).toEqual(expected)
    expect(rowHistory(town, 'gini', 35)).toEqual(expected)
    expect(rowHistory(town, 'gini', 25)).toEqual(expected.filter(point => point.tick <= 25))
    const spark = render(<NumberRow row="gini" arms={[town]} tick={35} />)
    expect(moves(spark.container.querySelector('.nx-number-spark path'))).toBe(2)
    const sparkRow = within(spark.container.querySelector('table')).getAllByRole('row').find(row => row.textContent.includes('Year 1, week 25'))
    expect(cellTexts(sparkRow)).toEqual(['Year 1, week 25', COPY.numbers.notRecorded])
    spark.unmount()
    const chart = render(<StoryChart arms={[town]} metricKey="gini" tick={35} horizon={40} countedWeeks inline hideEndLabels />)
    expect(moves(chart.container.querySelector('.nx-line'))).toBe(2)
    const chartRow = within(chart.container.querySelector('table')).getAllByRole('row').find(row => row.textContent.includes('Year 1, week 25'))
    expect(cellTexts(chartRow)).toEqual(['Year 1, week 25', COPY.numbers.notRecorded])
  })

  test('one missing carry cannot be erased by a recovery with the same count date', () => {
    const town = countedTown('Town B', [22])
    const points = countedSeriesUpTo(town, 'gini', 25)
    expect(points).toEqual([
      { tick: 15, value: 0.15 }, { tick: 20, value: 0.2 }, { tick: 22, value: null },
      { tick: 23, value: 0.2 }, { tick: 25, value: 0.25 },
    ])
    expect(rowHistory(town, 'gini', 25)).toEqual(points)
  })

  test('a recovered count dot uses its plotted recovery week and later normal counts keep their week', () => {
    const town = countedTown('Town B', Array.from({ length: 11 }, (_, index) => index + 20))
    const chart = tick => <StoryChart arms={[town]} metricKey="gini" tick={tick} horizon={40} countedWeeks inline hideEndLabels interactive />
    const { container, rerender } = render(chart(31))
    const lastPoint = () => container.querySelector('.nx-line').getAttribute('d').match(/[ML]([\d.-]+) ([\d.-]+)/g).at(-1).slice(1).split(' ').map(Number)
    expect(Number(container.querySelector('.nx-dot[r="5"]').getAttribute('cx'))).toBe(lastPoint()[0])
    expect(countedSeriesUpTo(town, 'gini', 31).at(-1).tick).toBe(31)
    const plot = container.querySelector('[tabindex="0"]')
    fireEvent.keyDown(plot, { key: 'End' })
    expect(Number(container.querySelector('.nx-crosshair .nx-dot').getAttribute('cx'))).toBe(lastPoint()[0])
    rerender(chart(35))
    expect(countedSeriesUpTo(town, 'gini', 35).at(-1).tick).toBe(35)
    expect(Number(container.querySelector('.nx-dot[r="5"]').getAttribute('cx'))).toBe(lastPoint()[0])
  })

  test('append caching and backwards scrubbing keep the same real gaps as the uncached helper', () => {
    const complete = countedTown('Town B', [20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30])
    const town = { ...complete, ticks: [], series: { gini: [], wealthAsOfTick: [] } }
    for (let index = 0; index < complete.ticks.length; index += 1) {
      town.ticks.push(complete.ticks[index])
      town.series.gini.push(complete.series.gini[index])
      town.series.wealthAsOfTick.push(complete.series.wealthAsOfTick[index])
      expect(rowHistory({ ...town }, 'gini', town.ticks[index])).toEqual(countedSeriesUpTo(town, 'gini', town.ticks[index]))
    }
    for (const tick of [15, 19, 22, 25, 30, 31, 35]) expect(rowHistory(town, 'gini', tick)).toEqual(countedSeriesUpTo(town, 'gini', tick))
  })
})

describe('selected-week missing labels', () => {
  test.each(['priceFood', 'gini'])('%s distinguishes never measured so far from an intermittent missing reading', key => {
    const town = arm('Town A', { [key]: [null, 5, null, 6], wealthAsOfTick: [1, 2, 3, 4] }, 4)
    expect(rowValues([town], key, 1)[0]).toMatchObject({ measured: false, value: null, formatted: COPY.numbers.notMeasured })
    expect(rowValues([town], key, 3)[0]).toMatchObject({ measured: true, value: null, formatted: COPY.numbers.missingReading })
    expect(rowValues([town], key, 4)[0].value).toBe(6)
  })

  test('an unknown cumulative total uses the selected-week phrase after a source reading exists', () => {
    const town = arm('Town A', { careDenials: [null, 2, null, 3] }, 4)
    expect(rowValues([town], 'careSoFar', 1)[0]).toMatchObject({ measured: false, formatted: COPY.numbers.notMeasured })
    expect(rowValues([town], 'careSoFar', 2)[0]).toMatchObject({ measured: true, value: null, formatted: COPY.numbers.missingReading })
  })

  test.each([
    ['careSoFar', 'careDenials'],
    ['writtenOffSoFar', 'bankDefaultAmountThisTick'],
  ])('%s tooltip distinguishes a missing total from a never-measured source', (key, source) => {
    const town = arm('Town A', { [source]: [null, 2, null, 3] }, 4)
    const { container } = render(<NumbersSheet arms={[town]} tick={4} onClose={() => {}} />)
    const row = container.querySelector(`.nx-number-row[data-metric="${key}"]`)
    fireEvent.click(row.querySelector('button[aria-expanded]'))
    fireEvent.keyDown(row.querySelector('[tabindex="0"]'), { key: 'End' })
    const tooltip = within(row).getByRole('tooltip')
    expect(tooltip).toHaveTextContent(COPY.numbers.column('Town A', COPY.numbers.missingReading))
    expect(tooltip).not.toHaveTextContent(COPY.numbers.notMeasured)
  })

  test('future event counts do not relabel an earlier never-measured window', () => {
    const town = arm()
    town.eventCounts = { 4: { hired: 2, laidOff: 0 } }
    expect(rowValues([town], 'netJobs26', 3)[0]).toMatchObject({ measured: false, value: null, formatted: COPY.numbers.notMeasured })
    expect(rowValues([town], 'netJobs26', 4)[0]).toMatchObject({ measured: true, value: null, formatted: COPY.numbers.missingReading })
  })

  test('a town never measured keeps the run-wide wording independently of another town', () => {
    const towns = [arm('Town A', { priceFood: [5, 6] }, 2), arm('Town B', {}, 2)]
    expect(rowValues(towns, 'priceFood', 2)[1]).toMatchObject({ measured: false, value: null, formatted: COPY.numbers.notMeasured })
  })
})
