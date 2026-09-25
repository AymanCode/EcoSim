import { describe, expect, test, vi } from 'vitest'
import { fireEvent, render, screen, within } from '@testing-library/react'
import StoryChart from '../components/StoryChart.jsx'
import { METRICS, STORY_METRICS } from '../catalog.js'
import { fixtureArm, TOWN_A, TOWN_B } from './fixture.js'

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

  test('marks each policy change once the week is reached', () => {
    const { container, rerender } = draw()
    const markers = [...container.querySelectorAll('.nx-marker')]
    expect(markers).toHaveLength(2)
    expect(markers[0].querySelector('path').style.fill).toBe('rgb(46, 111, 224)')
    expect(container.querySelector('.nx-marker')).toHaveTextContent('more help for people out of work')
    rerender(<StoryChart arms={arms()} metricKey={OUT} tick={5} horizon={24} onMetricChange={() => {}} />)
    expect(container.querySelectorAll('.nx-marker')).toHaveLength(0)
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
