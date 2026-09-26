import { describe, expect, test, vi } from 'vitest'
import { fireEvent, render, screen, within } from '@testing-library/react'
import StoryChart from '../components/StoryChart.jsx'
import { METRICS, STORY_METRICS, formatMetric } from '../catalog.js'
import { countedSeriesUpTo, valueAt } from '../data/derive.js'
import { demoArms, fixtureArm, TOWN_A, TOWN_B } from './fixture.js'

const OUT = 'peopleOutOfWorkPer100'
const arms = () => [fixtureArm(TOWN_A), fixtureArm(TOWN_B)]

function draw(props = {}) {
  return render(<StoryChart arms={arms()} metricKey={OUT} tick={24} horizon={24} onMetricChange={() => {}} {...props} />)
}

describe('StoryChart', () => {
  test('draws one line per town in its colour', () => {
    const { container } = draw()
    const lines = [...container.querySelectorAll('path.nx-line')]
    expect(lines).toHaveLength(2)
    expect(lines.map(line => line.style.stroke)).toEqual(['rgb(46, 111, 224)', 'rgb(224, 118, 44)'])
  })

  test('the warm-up weeks sit in a band labelled "setting up", drawn dashed and faint', () => {
    const { container } = draw({ tick: 24 })
    const band = container.querySelector('.nx-warm')
    expect(band).toBeInTheDocument()
    expect(Number(band.getAttribute('width'))).toBeGreaterThan(0)
    expect(container.querySelector('.nx-warm-label')).toHaveTextContent('setting up')
    const warm = [...container.querySelectorAll('path.nx-warmline')]
    expect(warm).toHaveLength(2)
    // The dashed part runs to the first real week and no further; the solid part starts there.
    const points = d => d.split(/[ML]/).filter(Boolean).map(pair => Number(pair.trim().split(' ')[0]))
    const solid = container.querySelector('path.nx-line').getAttribute('d')
    expect(points(warm[0].getAttribute('d')).at(-1)).toBe(points(solid)[0])
  })

  test('during warm-up there is only the dashed line', () => {
    const { container } = draw({ tick: 6 })
    expect(container.querySelectorAll('path.nx-line')).toHaveLength(0)
    expect(container.querySelectorAll('path.nx-warmline')).toHaveLength(2)
  })

  test('the y-axis leaves out the warm-up weeks', () => {
    const arm = fixtureArm(TOWN_A)
    // A spike during warm-up must not stretch the axis.
    arm.series[OUT] = arm.series[OUT].map((v, i) => (arm.ticks[i] === 3 ? 95 : Math.min(v, 45)))
    const { container } = render(<StoryChart arms={[arm]} metricKey={OUT} tick={24} horizon={24} onMetricChange={() => {}} />)
    const top = [...container.querySelectorAll('.nx-yaxis text')].map(text => parseInt(text.textContent, 10)).at(-1)
    expect(top).toBeLessThan(60)
  })

  test('marks each policy change once the week is reached', () => {
    const { container, rerender } = draw()
    const markers = [...container.querySelectorAll('.nx-marker')]
    expect(markers).toHaveLength(2)
    expect(markers[0].querySelector('path').style.fill).toBe('rgb(46, 111, 224)')
    expect(container.querySelector('.nx-marker')).toHaveTextContent('more help for people out of work')
    rerender(<StoryChart arms={arms()} metricKey={OUT} tick={5} horizon={24} onMetricChange={() => {}} />)
    expect(container.querySelectorAll('.nx-marker')).toHaveLength(0)
  })

  test('one town hall change of several levers in one week is one marker with one phrase', () => {
    const [a, b] = arms()
    b.policyChanges = [
      { id: 'o1', tick: 15, policy: 'bailout_policy', value: 'off' },
      { id: 'o2', tick: 15, policy: 'bailout_target', value: 'none' },
      { id: 'o3', tick: 15, policy: 'bailout_budget', value: '0' },
    ]
    const { container } = render(<StoryChart arms={[a, b]} metricKey={OUT} tick={24} horizon={24} onMetricChange={() => {}} />)
    const markers = [...container.querySelectorAll('.nx-marker')].filter(marker => marker.textContent.startsWith('Town B'))
    expect(markers).toHaveLength(1)
    expect(markers[0]).toHaveTextContent('Town B switched tono bailouts')
    expect(container.querySelector('.nx-marker').textContent).not.toMatch(/bailout target|bailout budget/)
  })

  test('end labels show each town\'s value and never overlap', () => {
    const { container } = draw({ tick: 11 })
    const labels = [...container.querySelectorAll('.nx-endl')]
    expect(labels).toHaveLength(2)
    expect(labels[0]).toHaveTextContent('Town A')
    expect(labels[0]).toHaveTextContent('42 in 100')
    // The fixture towns are identical, so the labels start on top of each other.
    const ys = labels.map(label => Number(label.getAttribute('y'))).sort((a, b) => a - b)
    expect(ys[1] - ys[0]).toBeGreaterThanOrEqual(16)
  })

  test('town hall cash below zero reads "owes" at the end of the line; the axis keeps its sign', () => {
    const [a, b] = arms()
    b.series.townHallCash = b.series.townHallCash.map(() => -11276.486)
    const { container } = render(<StoryChart arms={[a, b]} metricKey="townHallCash" tick={24} horizon={24} onMetricChange={() => {}} />)
    const labels = [...container.querySelectorAll('.nx-endl')].map(label => label.textContent)
    expect(labels.find(text => text.startsWith('Town B'))).toMatch(/owes \$11k$/)
    const axis = [...container.querySelectorAll('.nx-yaxis text')].map(text => text.textContent)
    expect(axis.some(text => text.startsWith('-$'))).toBe(true)
    expect(axis.some(text => text.startsWith('owes'))).toBe(false)
  })

  test('a narrow chart puts each town and its value on two lines', () => {
    const measure = vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockReturnValue({ width: 340, height: 320, top: 0, left: 0, right: 340, bottom: 320 })
    try {
      const { container } = draw({ tick: 11 })
      const labels = [...container.querySelectorAll('.nx-endl')]
      expect(labels.map(label => [...label.querySelectorAll('tspan')].map(span => span.textContent)))
        .toEqual([['Town A', '42 in 100'], ['Town B', '42 in 100']])
      const ys = labels.map(label => Number(label.getAttribute('y'))).sort((a, b) => a - b)
      expect(ys[1] - ys[0]).toBeGreaterThanOrEqual(32)
      const plotRight = Math.max(...[...container.querySelectorAll('.nx-yaxis line')].map(line => Number(line.getAttribute('x2'))))
      expect(340 - plotRight).toBeLessThan(110)
    } finally {
      measure.mockRestore()
    }
  })

  test('shades the weeks ahead and labels the axes', () => {
    const { container } = draw({ tick: 6, horizon: 104 })
    expect(container.querySelector('.nx-future')).toBeInTheDocument()
    expect(container.querySelector('.nx-ahead')).toHaveTextContent('the weeks ahead')
    const xLabels = [...container.querySelectorAll('.nx-xaxis text')].map(text => text.textContent)
    expect(xLabels).toEqual(['Year 1', 'Year 2'])
    const yLabels = [...container.querySelectorAll('.nx-yaxis text')].map(text => text.textContent)
    expect(yLabels.length).toBeGreaterThanOrEqual(3)
    yLabels.forEach(label => expect(label).toMatch(/^\d+ in 100$/))
  })

  test('money metrics get money ticks', () => {
    const { container } = draw({ metricKey: 'typicalWeeklyPay' })
    const yLabels = [...container.querySelectorAll('.nx-yaxis text')].map(text => text.textContent)
    yLabels.forEach(label => expect(label).toMatch(/^\$[\d,.]+k?$/))
  })

  test('metric chips switch the chart', () => {
    const onMetricChange = vi.fn()
    draw({ onMetricChange })
    const group = screen.getByRole('group', { name: 'Chart a different number' })
    const chips = within(group).getAllByRole('button')
    expect(chips.map(chip => chip.textContent)).toEqual(STORY_METRICS.map(key => METRICS[key].name))
    expect(within(group).getByRole('button', { name: 'People out of work' })).toHaveAttribute('aria-pressed', 'true')
    fireEvent.click(within(group).getByRole('button', { name: 'Typical weekly pay' }))
    expect(onMetricChange).toHaveBeenCalledWith('typicalWeeklyPay')
    expect(screen.getByRole('heading', { name: 'People out of work' })).toBeInTheDocument()
  })

  test('a hidden table gives every 13th week for each town', () => {
    draw()
    const table = screen.getByRole('table')
    expect(table).toHaveClass('nx-sr')
    const headers = within(table).getAllByRole('columnheader').map(cell => cell.textContent)
    expect(headers).toEqual(['Week', 'Town A', 'Town B'])
    const rows = within(table).getAllByRole('row').slice(1)
    expect(rows.map(row => row.firstChild.textContent)).toEqual(['Year 1, week 13', 'Year 1, week 24'])
    expect(rows[0]).toHaveTextContent('in 100')
  })
})

// "See it big" in the numbers sheet: any number, its own chips, and the
// counted-every-5-weeks numbers drawn only at their counts.
describe('StoryChart for the numbers sheet', () => {
  test('metricKeys lists its own chips; the Run screen keeps STORY_METRICS by default', () => {
    const keys = ['typicalWeeklyPay', 'bankActiveLoans']
    draw({ metricKey: 'bankActiveLoans', metricKeys: keys })
    const chips = within(screen.getByRole('group', { name: 'Chart a different number' })).getAllByRole('button')
    expect(chips.map(chip => chip.textContent)).toEqual(keys.map(key => METRICS[key].name))
    expect(screen.getByRole('heading', { name: METRICS.bankActiveLoans.name })).toBeInTheDocument()
  })

  test('a single number needs no chips', () => {
    draw({ metricKey: 'bankActiveLoans', metricKeys: ['bankActiveLoans'] })
    expect(screen.queryByRole('group', { name: 'Chart a different number' })).toBeNull()
  })

  test('with countedWeeks, a counted-every-5-weeks number is drawn at its counts only', () => {
    const demo = demoArms()
    const { container } = render(<StoryChart arms={demo} metricKey="gini" tick={72} horizon={104} onMetricChange={() => {}} countedWeeks />)
    const band = container.querySelector('.nx-warm')
    const x0 = Number(band.getAttribute('x'))
    const perWeek = Number(band.getAttribute('width')) / 10
    const weekAt = px => Math.round((px - x0) / perWeek)
    const drawn = [...container.querySelectorAll('path.nx-warmline, path.nx-line')].slice(0, 2)
      .flatMap(path => path.getAttribute('d').split(/[ML]/).map(part => part.trim()).filter(Boolean).map(pair => weekAt(Number(pair.split(' ')[0]))))
    expect([...new Set(drawn)]).toEqual(countedSeriesUpTo(demo[0], 'gini', 72).map(point => point.tick))
    // Each town's dot sits on its last count (week 70), not on this week.
    container.querySelectorAll('.nx-dot').forEach(dot => expect(weekAt(Number(dot.getAttribute('cx')))).toBe(70))
    // The table gives the counts, about every 13 weeks, and the last one.
    const rows = within(screen.getByRole('table')).getAllByRole('row').slice(1).map(row => row.firstChild.textContent)
    expect(rows).toEqual(['Year 1, week 1', 'Year 1, week 15', 'Year 1, week 30', 'Year 1, week 45', 'Year 2, week 8', 'Year 2, week 18'])
  })

  test('with countedWeeks, each table row holds the count made that week, even when its frame is missing', () => {
    const demo = demoArms()
    // Week 70's frame never arrived; week 71 carries the week-70 count.
    const dropWeek = (arm, week) => {
      const keep = arm.ticks.map(t => t !== week)
      const series = Object.fromEntries(Object.entries(arm.series).map(([key, values]) => [key, values.filter((_, i) => keep[i])]))
      return { ...arm, ticks: arm.ticks.filter((_, i) => keep[i]), series }
    }
    const count70 = formatMetric('gini', valueAt(demo[0], 'gini', 70))
    const count65 = formatMetric('gini', valueAt(demo[0], 'gini', 69))
    expect(count70).not.toBe(count65)
    render(<StoryChart arms={demo.map(arm => dropWeek(arm, 70))} metricKey="gini" tick={72} horizon={104} onMetricChange={() => {}} countedWeeks />)
    const last = within(screen.getByRole('table')).getAllByRole('row').at(-1)
    expect(last.firstChild).toHaveTextContent('Year 2, week 18')
    expect(within(last).getAllByRole('cell')[0]).toHaveTextContent(count70)
  })

  test('without countedWeeks the gap between rich and poor draws as before', () => {
    const demo = demoArms()
    const { container } = render(<StoryChart arms={demo} metricKey="gini" tick={72} horizon={104} onMetricChange={() => {}} />)
    const cursor = container.querySelector('.nx-cursor').style.transform
    const cursorX = Number(cursor.match(/translateX\(([\d.]+)px\)/)[1])
    container.querySelectorAll('.nx-dot').forEach(dot => expect(Number(dot.getAttribute('cx'))).toBeCloseTo(cursorX, 1))
  })
})
