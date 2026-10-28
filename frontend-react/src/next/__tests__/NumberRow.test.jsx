import { useState } from 'react'
import fs from 'node:fs'
import { afterEach, describe, expect, test, vi } from 'vitest'
import { act, fireEvent, render, screen, within } from '@testing-library/react'
import NumberRow from '../numbers/NumberRow.jsx'
import { COPY, NUMBER_GROUPS } from '../catalog.js'
import { weeklyCounts } from '../data/derive.js'
import { rowSeries } from '../numbers/compare.js'

vi.mock('../data/derive.js', async importOriginal => {
  const actual = await importOriginal()
  return { ...actual, weeklyCounts: vi.fn(actual.weeklyCounts) }
})
vi.mock('../numbers/compare.js', async importOriginal => {
  const actual = await importOriginal()
  return { ...actual, rowSeries: vi.fn(actual.rowSeries) }
})

afterEach(() => {
  vi.useRealTimers()
  vi.restoreAllMocks()
  vi.clearAllMocks()
})

const arm = (label, color, values) => ({ label, color, ticks: [1, 11, 20], series: { typicalWeeklyPay: values } })
const ARMS = [arm('Town A', '#2E6FE0', [20, 45, 49]), arm('Town B', '#E0762C', [20, 55, 61])]
const ROW = { key: 'typicalWeeklyPay', visual: 'chart' }
const here = import.meta.url
const ROW_CSS = fs.readFileSync(new URL('../numbers/numberRow.css', here), 'utf8')

function draw(props = {}) {
  return render(<div className="nx"><NumberRow id="pay-row" row={ROW} arms={ARMS} tick={20} {...props} /></div>)
}

function ControlledRow() {
  const [open, setOpen] = useState(false)
  return <div className="nx"><NumberRow id="pay-row" row={ROW} arms={ARMS} tick={20} open={open} onToggle={setOpen}><div data-testid="visual" /></NumberRow></div>
}

describe('NumberRow', () => {
  // The cold 520-week render draws 20 rows in JSDOM and can pass 5s under full-suite load.
  test.each([[104, 4810], [520, 26442]])('closed rows: weekly work at %i ticks', (weeks, expected) => {
    const rows = NUMBER_GROUPS.flatMap(group => group.rows).filter(row => row.key !== 'publicWorksJobs')
    expect(rows).toHaveLength(20)
    const ticks = Array.from({ length: weeks }, (_, i) => i + 1)
    const arms = ['Town A', 'Town B'].map(label => ({
      label, color: '#2E6FE0', ticks: [...ticks],
      series: Object.fromEntries(rows.map(row => [row.key, ticks.map(() => 1)])),
      eventCounts: Object.fromEntries(ticks.map(tick => [tick, { hired: 3, laidOff: 1 }])),
    }))
    const content = tick => <>{rows.map(row => <NumberRow key={row.key} row={row} arms={arms.map(arm => ({ ...arm }))} tick={tick} />)}</>
    const { rerender } = render(content(weeks))
    // Cold histories still calculate every original point, with exact values.
    expect(weeklyCounts.mock.results.reduce((sum, call) => sum + call.value.length, 0)).toBe(expected)
    vi.clearAllMocks()
    rerender(content(weeks))
    expect(rowSeries).not.toHaveBeenCalled()
    expect(weeklyCounts.mock.results.reduce((sum, call) => sum + call.value.length, 0)).toBe(52)
    for (const arm of arms) {
      arm.ticks.push(weeks + 1)
      Object.values(arm.series).forEach(values => values.push(1))
      arm.eventCounts[weeks + 1] = { hired: 4, laidOff: 1 }
    }
    vi.clearAllMocks()
    rerender(content(weeks + 1))
    expect(rowSeries).toHaveBeenCalledTimes(2)
    expect(weeklyCounts.mock.results.reduce((sum, call) => sum + call.value.length, 0)).toBe(104)
  }, 20_000)

  test('closed charts survive collapse, then unmount and stop updating', () => {
    vi.useFakeTimers()
    const visual = vi.fn(() => <div data-testid="full-chart" />)
    const { rerender } = draw({ open: true, renderVisual: visual })
    const content = (open, tick = 20) => <div className="nx"><NumberRow id="pay-row" row={ROW} arms={ARMS} tick={tick} open={open} renderVisual={visual} /></div>
    rerender(content(false))
    act(() => vi.advanceTimersByTime(419))
    expect(screen.getByTestId('full-chart')).toBeInTheDocument()
    act(() => vi.advanceTimersByTime(1))
    expect(screen.queryByTestId('full-chart')).toBeNull()
    expect(screen.getByRole('table', { name: COPY.numbers.chart.table('Typical weekly pay') })).toBeInTheDocument()
    visual.mockClear()
    rerender(content(false, 21))
    expect(visual).not.toHaveBeenCalled()
  })

  test('collapse follows the motion token and reopening cancels cleanup', () => {
    vi.useFakeTimers()
    const content = open => <div className="nx" style={{ '--nx-change': '600ms' }}><NumberRow row={ROW} arms={ARMS} tick={20} open={open}><div data-testid="full-chart" /></NumberRow></div>
    const { rerender, container, unmount } = render(content(true))
    // jsdom does not inherit custom properties; set it on the motion element.
    container.querySelector('.nx-number-expand-motion').style.setProperty('--nx-change', '600ms')
    rerender(content(false))
    act(() => vi.advanceTimersByTime(420))
    expect(screen.getByTestId('full-chart')).toBeInTheDocument()
    rerender(content(true))
    act(() => vi.advanceTimersByTime(600))
    expect(screen.getByTestId('full-chart')).toBeInTheDocument()
    rerender(content(false))
    act(() => vi.advanceTimersByTime(600))
    expect(screen.queryByTestId('full-chart')).toBeNull()
    unmount()
    expect(vi.getTimerCount()).toBe(0)
  })

  test('reduced motion unmounts a closed chart immediately', () => {
    vi.spyOn(window, 'matchMedia').mockImplementation(query => ({ matches: query.includes('prefers-reduced-motion'), addEventListener() {}, removeEventListener() {} }))
    const { rerender } = draw({ open: true, children: <div data-testid="full-chart" /> })
    rerender(<div className="nx"><NumberRow row={ROW} arms={ARMS} tick={20}><div data-testid="full-chart" /></NumberRow></div>)
    expect(screen.queryByTestId('full-chart')).toBeNull()
  })

  test('the collapse transition can release contents, ignoring child and unrelated transitions', () => {
    vi.useFakeTimers()
    const content = open => <NumberRow row={ROW} arms={ARMS} tick={20} open={open}><div data-testid="full-chart" /></NumberRow>
    const { container, rerender, unmount } = render(content(true))
    rerender(content(false))
    const motion = container.querySelector('.nx-number-expand-motion')
    const transition = (target, propertyName) => {
      const event = new Event('transitionend', { bubbles: true })
      Object.defineProperty(event, 'propertyName', { value: propertyName })
      fireEvent(target, event)
    }
    transition(screen.getByTestId('full-chart'), 'grid-template-rows')
    transition(motion, 'color')
    expect(screen.getByTestId('full-chart')).toBeInTheDocument()
    transition(motion, 'grid-template-rows')
    expect(screen.queryByTestId('full-chart')).toBeNull()
    unmount()
    expect(vi.getTimerCount()).toBe(0)
  })

  test('a folding row keeps its visible preview through the shrink phase', () => {
    const content = phase => <div className="nx-row-motion" data-state={phase} aria-hidden={phase !== 'row'} inert={phase !== 'row'}><NumberRow row={ROW} arms={ARMS} tick={20} /></div>
    const { container, rerender } = render(content('row'))
    const paths = () => [...container.querySelectorAll('.nx-number-spark path')].map(path => path.getAttribute('d'))
    const initial = paths()
    expect(initial).toHaveLength(2)
    rerender(content('leaving-row'))
    expect(paths()).toEqual(initial)
    rerender(content('entering-entry'))
    expect(container.querySelector('svg, table')).toBeNull()
  })

  test('fully folded and hidden rows build no histories, tables or visuals; unfolding restores them', () => {
    const visual = vi.fn(() => <div data-testid="full-chart" />)
    const content = (phase, hidden = false, open = false) => <div hidden={hidden}><div className="nx-row-motion" data-state={phase} aria-hidden={phase !== 'row'} inert={phase !== 'row'}><NumberRow row={{ key: 'netJobs26' }} arms={ARMS} tick={20} open={open} renderVisual={visual} /></div></div>
    const { container, rerender } = render(content('folded'))
    expect(rowSeries).not.toHaveBeenCalled()
    expect(weeklyCounts).not.toHaveBeenCalled()
    expect(container.querySelector('table, svg')).toBeNull()
    rerender(content('leaving-entry'))
    expect(weeklyCounts).not.toHaveBeenCalled()
    rerender(content('row', true, true))
    expect(weeklyCounts).not.toHaveBeenCalled()
    expect(visual).not.toHaveBeenCalled()
    rerender(content('row'))
    expect(rowSeries).toHaveBeenCalled()
    expect(container.querySelector('table')).toBeInTheDocument()
    vi.clearAllMocks()
    rerender(content('folded'))
    expect(container.querySelector('table, svg')).toBeNull()
    expect(rowSeries).not.toHaveBeenCalled()
    expect(weeklyCounts).not.toHaveBeenCalled()
    vi.clearAllMocks()
    rerender(content('folded'))
    expect(rowSeries).not.toHaveBeenCalled()
    expect(weeklyCounts).not.toHaveBeenCalled()
  })

  test('one button owns the expanded region, with current values and the difference', () => {
    draw()
    const button = screen.getByRole('button', { name: 'Typical weekly pay' })
    expect(button).toHaveAttribute('type', 'button')
    expect(button).toHaveAttribute('aria-expanded', 'false')
    expect(button).toHaveAttribute('aria-controls', 'pay-row-expanded')
    expect(button).toHaveAttribute('title', "The middle earner's weekly pay before tax.")
    expect(button).toHaveAccessibleDescription(/\$49.*\$61.*\$12 more/)
    const region = document.getElementById(button.getAttribute('aria-controls'))
    expect(region).toHaveAttribute('aria-labelledby', button.id)
    expect(region).toHaveAttribute('aria-hidden', 'true')
    expect(region).toHaveAttribute('inert')
    expect(region).toHaveAttribute('data-state', 'closed')
    expect(within(button).getByText('$49')).toBeInTheDocument()
    expect(within(button).getByText('$61')).toBeInTheDocument()
    expect(within(button).getByText(COPY.numbers.tags.better)).toBeInTheDocument()
    expect(within(button).getByText('$12 more')).toBeInTheDocument()
  })

  test('Enter, Space and a click toggle once each and preserve keyboard focus', () => {
    render(<ControlledRow />)
    const button = screen.getByRole('button', { name: 'Typical weekly pay' })
    button.focus()
    fireEvent.keyDown(button, { key: 'Enter' })
    expect(button).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByTestId('visual')).toBeVisible()
    expect(screen.getByRole('region', { name: 'Typical weekly pay' })).toHaveAttribute('data-state', 'open')
    expect(button).toHaveFocus()
    fireEvent.keyDown(button, { key: ' ' })
    expect(button).toHaveAttribute('aria-expanded', 'false')
    const closed = document.getElementById(button.getAttribute('aria-controls'))
    expect(closed).toHaveAttribute('data-state', 'closed')
    expect(closed).toHaveAttribute('aria-hidden', 'true')
    expect(closed).toHaveAttribute('inert')
    // The visual stays mounted so its height can animate all the way closed.
    expect(closed.querySelector('[data-testid="visual"]')).toBeInTheDocument()
    expect(screen.queryByRole('region')).toBeNull()
    fireEvent.keyDown(button, { key: 'a' })
    expect(button).toHaveAttribute('aria-expanded', 'false')
    fireEvent.click(button)
    expect(button).toHaveAttribute('aria-expanded', 'true')
  })

  test('opening hides the preview and renders the supplied visual before the meaning', () => {
    const renderVisual = vi.fn(() => <div data-testid="visual" />)
    const { container, rerender } = draw({ renderVisual })
    expect(container.querySelector('.nx-number-spark')).toBeVisible()
    expect(renderVisual).not.toHaveBeenCalled()
    expect(screen.getByRole('table', { name: COPY.numbers.chart.table('Typical weekly pay') })).toBeInTheDocument()
    rerender(<div className="nx"><NumberRow id="pay-row" row={ROW} arms={ARMS} tick={20} open renderVisual={renderVisual} /></div>)
    expect(container.querySelector('.nx-number-spark')).not.toBeVisible()
    const region = screen.getByRole('region', { name: 'Typical weekly pay' })
    expect(within(region).getByTestId('visual').nextElementSibling).toHaveTextContent("The middle earner's weekly pay before tax.")
    expect(renderVisual).toHaveBeenCalledWith({ row: ROW, arms: ARMS, tick: 20 })
    expect(screen.queryByRole('table')).toBeNull()
  })

  test('initially expanded rows mount open without an entering phase; reduced motion disables the transition', () => {
    draw({ open: true, children: <div data-testid="visual" /> })
    const region = screen.getByRole('region', { name: 'Typical weekly pay' })
    expect(region).toHaveAttribute('data-state', 'open')
    expect(region).toHaveAttribute('aria-hidden', 'false')
    expect(region).not.toHaveAttribute('inert')
    expect(within(region).getByTestId('visual')).toBeInTheDocument()
    expect(ROW_CSS).toMatch(/grid-template-rows:\s*0fr/)
    expect(ROW_CSS).toMatch(/\[data-state="open"\]\s*\{\s*grid-template-rows:\s*1fr/)
    expect(ROW_CSS).toMatch(/@media\s*\(prefers-reduced-motion:\s*reduce\)\s*\{\s*[^}]*\.nx-number-expand-motion\s*\{\s*transition:\s*none/)
  })

  test('not-measured values stay explicit and have no judgment', () => {
    draw({ arms: ARMS.map(town => ({ ...town, series: {} })) })
    const button = screen.getByRole('button', { name: 'Typical weekly pay' })
    expect(within(button).getAllByText(COPY.numbers.notMeasured)).toHaveLength(2)
    expect(within(button).queryByText(COPY.numbers.tags.better)).toBeNull()
    expect(within(button).queryByText(COPY.numbers.tags.worse)).toBeNull()
  })

  test('one town omits the difference column; three towns compare each with the control', () => {
    const { container, rerender } = draw({ arms: [ARMS[0]] })
    expect(container.querySelector('.nx-number-grid')).toHaveClass('is-one-town')
    expect(container.querySelector('.nx-number-differences')).toBeNull()
    const three = [...ARMS, arm('Town C', '#199E70', [20, 40, 40])]
    rerender(<div className="nx"><NumberRow row={ROW} arms={three} tick={20} /></div>)
    const differences = container.querySelector('.nx-number-differences')
    expect(differences).toHaveTextContent('Town B')
    expect(differences).toHaveTextContent('Town C')
    expect(within(differences).getByText('$12 more')).toBeInTheDocument()
    expect(within(differences).getByText('$9 less')).toBeInTheDocument()
    expect(within(differences).getByText(COPY.numbers.tags.better)).toBeInTheDocument()
    expect(within(differences).getByText(COPY.numbers.tags.worse)).toBeInTheDocument()
  })

  test('warm-up shows numeric values without relative words or judgments', () => {
    draw({ tick: 1 })
    const button = screen.getByRole('button', { name: 'Typical weekly pay' })
    expect(within(button).getAllByText('$20')).toHaveLength(2)
    expect(within(button).queryByText(COPY.numbers.sameAsTown('Town A'))).toBeNull()
    expect(button.querySelector('.nx-number-differences')).toBeEmptyDOMElement()
    expect(within(button).queryByText(COPY.numbers.tags.better)).toBeNull()
    expect(within(button).queryByText(COPY.numbers.tags.worse)).toBeNull()
  })

  test('an equal open row shows each formatted number once, referring later towns to its first occurrence', () => {
    const equal = [ARMS[0], { ...ARMS[1], series: { typicalWeeklyPay: [20, 45, 49] } }]
    const { rerender } = draw({ arms: equal, open: true })
    const button = screen.getByRole('button', { name: 'Typical weekly pay' })
    expect(within(button).getAllByText('$49')).toHaveLength(1)
    expect(within(button).getByText(COPY.numbers.sameAsTown('Town A'))).toBeInTheDocument()
    expect(button).toHaveAttribute('aria-expanded', 'true')
    const three = [...ARMS, arm('Town C', '#199E70', [20, 55, 61])]
    rerender(<div className="nx"><NumberRow row={ROW} arms={three} tick={20} open /></div>)
    const threeButton = screen.getByRole('button', { name: 'Typical weekly pay' })
    expect(within(threeButton).getAllByText('$49')).toHaveLength(1)
    expect(within(threeButton).getAllByText('$61')).toHaveLength(1)
    expect(within(threeButton).getByText(COPY.numbers.sameAsTown('Town B'))).toBeInTheDocument()
  })

  test('a counted metric includes its last count beneath the meaning', () => {
    draw({ row: { key: 'wealthP50' }, open: true, arms: ARMS.map((town, i) => ({ ...town, series: { wealthP50: [100, 80 + i * 10, 85 + i * 10], wealthAsOfTick: [1, 10, 20] } })) })
    const region = screen.getByRole('region', { name: 'Typical savings' })
    expect(region).toHaveTextContent('Counted every 5 weeks; last count Year 1, week 20.')
    expect(screen.getByRole('button', { name: 'Typical savings' })).toHaveTextContent('the middle household')
  })
})
