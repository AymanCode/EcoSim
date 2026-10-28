import { afterEach, describe, expect, test, vi } from 'vitest'
import { act, render, screen, within } from '@testing-library/react'
import StoryChart from '../components/StoryChart.jsx'
import { TOWN_COLORS } from '../catalog.js'
import { fixtureArm } from './fixture.js'

const OUT = 'peopleOutOfWorkPer100'
function towns(count) {
  return TOWN_COLORS.slice(0, count).map((color, i) => ({
    ...fixtureArm({ label: `Town ${String.fromCharCode(65 + i)}`, color }),
    policyChanges: [],
  }))
}

function measureAt(width) {
  return vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockReturnValue({
    width, height: 320, top: 0, left: 0, right: width, bottom: 320,
  })
}

function draw(arms, props = {}) {
  return render(<StoryChart arms={arms} metricKey={OUT} tick={24} horizon={52} {...props} />)
}

function plotWidth(container) {
  const gridLine = container.querySelector('.nx-yaxis line')
  return Number(gridLine.getAttribute('x2')) - Number(gridLine.getAttribute('x1'))
}

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

describe('StoryChart phone layout', () => {
  test.each([2, 3, 4])('%i towns retain text identities while the plot gets most of a 305px chart', count => {
    measureAt(305)
    const arms = towns(count)
    const { container } = draw(arms)
    expect(container.querySelector('svg')).toHaveAttribute('width', '305')
    expect(plotWidth(container)).toBeGreaterThanOrEqual(305 * 0.6)
    expect(container.querySelector('svg > .nx-ann.is-bold')).toHaveAttribute('x', '0')

    const labels = [...container.querySelectorAll('.nx-endl')]
    expect(labels.map(label => label.textContent).sort()).toEqual(['A', 'B', 'C', 'D'].slice(0, count))
    const positions = labels.map(label => Number(label.getAttribute('y'))).sort((a, b) => a - b)
    for (let i = 1; i < positions.length; i += 1) {
      expect(positions[i] - positions[i - 1]).toBeGreaterThanOrEqual(18)
    }

    // The SVG is decorative; the existing table keeps full town names and readings.
    const table = screen.getByRole('table')
    expect(within(table).getAllByRole('columnheader').map(cell => cell.textContent))
      .toEqual(['Week', ...arms.map(arm => arm.label)])
    expect(within(table).getAllByRole('row').at(-1)).toHaveTextContent('in 100')
  })

  test('a week-2 rule-change label sits above the phone plot while its dated marker remains', () => {
    measureAt(305)
    const arms = towns(4)
    arms[3].policyChanges = [{ id: 'tax', tick: 2, policy: 'wage_tax_rate', value: '0.3' }]
    const { container, rerender } = draw(arms, { tick: 1 })
    expect(container.querySelector('.nx-phone-rules')).toBeNull()

    rerender(<StoryChart arms={arms} metricKey={OUT} tick={24} horizon={52} />)
    const annotation = container.querySelector('.nx-phone-rules')
    expect(annotation).toHaveTextContent('Town D switched to')
    expect(annotation).toHaveTextContent('30%')
    expect(annotation.compareDocumentPosition(container.querySelector('.nx-chart')) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(container.querySelectorAll('.nx-marker text')).toHaveLength(0)
    expect(container.querySelectorAll('.nx-marker path')).toHaveLength(1)
    expect(container.querySelectorAll('.nx-rules line')).toHaveLength(1)
  })

  test('long money readings do not take width away from the phone plot', () => {
    measureAt(305)
    const arms = towns(4)
    arms.forEach(arm => { arm.series.typicalWeeklyPay = arm.ticks.map(() => 123456) })
    const { container } = draw(arms, { metricKey: 'typicalWeeklyPay' })
    expect(plotWidth(container)).toBeGreaterThanOrEqual(305 * 0.6)
    expect([...container.querySelectorAll('.nx-endl')].map(label => label.textContent).sort()).toEqual(['A', 'B', 'C', 'D'])
  })

  test.each([400, 480])('a %ipx chart retains two-line town and value labels', width => {
    measureAt(width)
    const { container } = draw(towns(2), { tick: 11 })
    expect([...container.querySelectorAll('.nx-endl')].map(label => [...label.querySelectorAll('tspan')].map(span => span.textContent)))
      .toEqual([['Town A', '42 in 100'], ['Town B', '42 in 100']])
    expect(container.querySelector('.nx-phone-rules')).toBeNull()
  })

  test('a wide chart retains full direct labels and the original right margin', () => {
    measureAt(720)
    const { container } = draw(towns(2), { tick: 11 })
    expect([...container.querySelectorAll('.nx-endl')].map(label => label.textContent))
      .toEqual(['Town A  42 in 100', 'Town B  42 in 100'])
    expect(container.querySelector('.nx-yaxis line')).toHaveAttribute('x2', '564')
  })

  test('ResizeObserver switches label mode when a chart grows past the phone width', () => {
    measureAt(305)
    let resize
    vi.stubGlobal('ResizeObserver', class {
      constructor(callback) { resize = callback }
      observe() {}
      disconnect() {}
    })
    const { container } = draw(towns(2), { tick: 11 })
    expect([...container.querySelectorAll('.nx-endl')].map(label => label.textContent)).toEqual(['A', 'B'])
    act(() => resize([{ contentRect: { width: 480, height: 320 } }]))
    expect([...container.querySelectorAll('.nx-endl')].map(label => [...label.querySelectorAll('tspan')].map(span => span.textContent)))
      .toEqual([['Town A', '42 in 100'], ['Town B', '42 in 100']])
    expect(container.querySelector('svg')).toHaveAttribute('width', '480')
  })

  test('a policy annotation preserves the measured plot node through phone and wider layouts', () => {
    measureAt(305)
    let resize
    let observed
    vi.stubGlobal('ResizeObserver', class {
      constructor(callback) { resize = callback }
      observe(node) { observed = node }
      disconnect() {}
    })
    const arms = towns(4)
    arms[3].policyChanges = [{ id: 'tax', tick: 2, policy: 'wage_tax_rate', value: '0.3' }]
    const { container, rerender } = draw(arms, { tick: 1 })
    const plot = container.querySelector('.nx-chart')
    expect(observed).toBe(plot)
    expect(container.querySelector('.nx-phone-rules')).toBeNull()

    rerender(<StoryChart arms={arms} metricKey={OUT} tick={24} horizon={52} />)
    expect(container.querySelector('.nx-phone-rules')).toBeInTheDocument()
    expect(container.querySelector('.nx-chart')).toBe(plot)

    for (const width of [480, 305]) {
      act(() => resize([{ target: observed, contentRect: { width, height: 320 } }]))
      expect(container.querySelector('.nx-chart')).toBe(plot)
      expect(container.querySelector('svg')).toHaveAttribute('width', String(width))
    }
    expect(container.querySelector('.nx-phone-rules')).toBeInTheDocument()
  })
})
