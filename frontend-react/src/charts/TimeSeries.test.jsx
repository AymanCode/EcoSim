import { act, render } from '@testing-library/react'
import { describe, expect, test, vi } from 'vitest'
import frame from '../test/fixtures/frame.json'
import TimeSeries, { alignByTick } from './TimeSeries.jsx'

vi.mock('./useMeasured.js', () => ({ default: () => [{ current: null }, { width: 600, height: 200 }] }))

describe('TimeSeries', () => {
  const gdp = { data: frame.metrics.gdpHistory, tone: 'acc', name: 'GDP' }
  test('renders one path per series and an end label', () => {
    const { container } = render(<div style={{ height: 200 }}><TimeSeries series={[gdp]} format={v => `$${v}`} endLabel /></div>)
    expect(container.querySelectorAll('.recharts-area').length).toBe(1)
    expect(container.textContent).toContain('GDP')
  })
  test('split mode adds the pre-change line and the shaded region', () => {
    const { container } = render(<TimeSeries series={[gdp]} format={v => v} split={{ tick: frame.metrics.gdpHistory[1].tick, color: 'var(--ai)' }} />)
    expect(container.querySelectorAll('.recharts-line').length).toBe(1)
    expect(container.querySelector('.recharts-reference-area')).toBeTruthy()
  })
  test('markers render as reference lines with labels', () => {
    const { container } = render(<TimeSeries series={[gdp]} format={v => v} markers={[{ tick: frame.metrics.gdpHistory[1].tick, label: 'Wage tax 15% → 18%', ai: false, ok: true }]} />)
    expect(container.querySelector('.recharts-reference-line')).toBeTruthy()
    expect(container.textContent).toContain('Wage tax')
  })

  test('a series missing a tick is left null in the aligned rows, not fabricated as zero', () => {
    const a = { data: [{ tick: 1, value: 1 }, { tick: 3, value: 3 }], tone: 'acc', name: 'A' }
    const b = { data: [{ tick: 2, value: 2 }], tone: 'ai', name: 'B' }
    expect(alignByTick([a, b], 250)).toEqual([
      { tick: 1, s0: 1, s1: null },
      { tick: 2, s0: null, s1: 2 },
      { tick: 3, s0: 3, s1: null },
    ])
  })

  test('two series with different tick sets each render their own area', () => {
    const a = { data: [{ tick: 1, value: 1 }, { tick: 3, value: 3 }], tone: 'acc', name: 'A' }
    const b = { data: [{ tick: 2, value: 2 }], tone: 'ai', name: 'B' }
    const { container } = render(<TimeSeries series={[a, b]} format={v => v} />)
    expect(container.querySelectorAll('.recharts-area').length).toBe(2)
  })

  test('markers stay hidden below the 470px width gate', async () => {
    vi.resetModules()
    vi.doMock('./useMeasured.js', () => ({ default: () => [{ current: null }, { width: 400, height: 200 }] }))
    const { default: NarrowTimeSeries } = await import('./TimeSeries.jsx')
    const { container } = render(
      <NarrowTimeSeries
        series={[gdp]}
        format={v => v}
        markers={[{ tick: frame.metrics.gdpHistory[1].tick, label: 'Wage tax 15% → 18%', ai: false, ok: true }]}
      />
    )
    expect(container.querySelector('.recharts-reference-line')).toBeNull()
    expect(container.textContent).not.toContain('Wage tax')
  })

  test('wrapper inline style uses min-height and not fixed height', () => {
    const { container: c1 } = render(<TimeSeries series={[gdp]} format={v => v} height={220} />)
    const chart1 = c1.querySelector('.chart')
    expect(chart1.style.minHeight).toBe('220px')
    expect(chart1.style.height).toBe('')

    const { container: c2 } = render(<TimeSeries series={[gdp]} format={v => v} />)
    const chart2 = c2.querySelector('.chart')
    expect(chart2.style.minHeight).toBe('150px')
    expect(chart2.style.height).toBe('')
  })

  test('hard-stops first-mount animation after 1500ms timeout', () => {
    vi.useFakeTimers()
    try {
      const { container } = render(<TimeSeries series={[gdp]} format={v => v} />)
      expect(container.querySelector('.chart')).toHaveAttribute('data-animating', 'true')
      act(() => {
        vi.advanceTimersByTime(1600)
      })
      expect(container.querySelector('.chart')).toHaveAttribute('data-animating', 'false')
    } finally {
      vi.useRealTimers()
    }
  })
})
