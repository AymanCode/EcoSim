import { act, render } from '@testing-library/react'
import { beforeEach, afterEach, describe, expect, test, vi } from 'vitest'
import ChartTile from './ChartTile.jsx'
import StatTile from './StatTile.jsx'

vi.mock('../charts/useMeasured.js', () => ({ default: () => [{ current: null }, { width: 300, height: 150 }] }))

describe('StatTile', () => {
  beforeEach(() => { vi.useFakeTimers(); let t = 0; vi.spyOn(window, 'requestAnimationFrame').mockImplementation(cb => setTimeout(() => cb(t += 100), 16)) })
  afterEach(() => vi.restoreAllMocks())
  test('counts up to the value and shows a delta and sparkline', () => {
    const history = [{ tick: 1, value: 50000 }, { tick: 25, value: 52000 }]
    const { container } = render(<StatTile label="GDP output" value={55100} format={v => `$${(v / 1000).toFixed(1)}K`} history={history} caption="per tick" />)
    act(() => { vi.advanceTimersByTime(1000) })
    expect(container.querySelector('.tile .v').textContent).toBe('$55.1K')
    expect(container.querySelector('.delta').textContent).toMatch(/▲ 6\.0%/)
    expect(container.querySelector('svg path')).toBeTruthy()
  })
  test('tone recolours the tile', () => {
    const { container } = render(<StatTile label="Unemployment" value={28.8} format={v => `${v}%`} tone="warn" upBad />)
    expect(container.querySelector('.tile')).toHaveClass('warn')
  })
  test('retargets from the currently displayed number when value changes', () => {
    const { container, rerender } = render(<StatTile label="GDP" value={100} />)
    act(() => { vi.advanceTimersByTime(1000) })
    expect(container.querySelector('.tile .v').textContent).toBe('100')

    rerender(<StatTile label="GDP" value={200} />)
    act(() => { vi.advanceTimersByTime(60) })
    const displayed = parseFloat(container.querySelector('.tile .v').textContent)
    expect(displayed).toBeGreaterThanOrEqual(100)
    expect(displayed).toBeLessThan(200)

    act(() => { vi.advanceTimersByTime(1000) })
    expect(container.querySelector('.tile .v').textContent).toBe('200')
  })
  test('lands on the target even when rAF is paused', () => {
    vi.useFakeTimers()
    vi.spyOn(window, 'requestAnimationFrame').mockImplementation(() => 1)
    const { container, rerender } = render(<StatTile value={100} format={v => String(Math.round(v))} />)
    act(() => { vi.advanceTimersByTime(600) })
    expect(container.querySelector('.v').textContent).toBe('100')

    rerender(<StatTile value={200} format={v => String(Math.round(v))} />)
    act(() => { vi.advanceTimersByTime(600) })
    expect(container.querySelector('.v').textContent).toBe('200')
  })
})

describe('ChartTile', () => {
  test('defaults chart tone to accent when untoned', () => {
    const { container } = render(
      <ChartTile
        label="Revenue"
        value={48200}
        format={v => String(v)}
        history={[{ tick: 1, value: 40000 }, { tick: 25, value: 45000 }]}
      />
    )
    expect(container.innerHTML).not.toContain('--undefined')
  })
})

