import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { afterEach, beforeAll, beforeEach, expect, test, vi } from 'vitest'
import NumbersSheet from '../numbers/NumbersSheet.jsx'
import { demoArms } from './fixture.js'

const here = import.meta.url
const sheetStyles = readFileSync(fileURLToPath(new URL('../numbers/numbersSheet.css', here)), 'utf8')
let arms
beforeAll(() => { arms = demoArms() })
beforeEach(() => {
  vi.useFakeTimers()
  vi.stubGlobal('matchMedia', () => ({ matches: false }))
})
afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  vi.useRealTimers()
})

const advance = milliseconds => act(() => vi.advanceTimersByTime(milliseconds))
const row = key => document.querySelector(`.nx-row-motion[data-metric="${key}"]`)
const entry = key => document.querySelector(`.nx-fold-entry[data-metric="${key}"]`)
const unavailable = node => node.closest('[inert], [aria-hidden="true"]')
const loansTowns = () => arms.map((arm, index) => ({
  ...arm,
  series: { ...arm.series, bankActiveLoans: arm.ticks.map(week => week === 31 && index ? 2 : 1) },
}))
function mount(towns, tick, playing = false) {
  const view = (at, running) => <div className="nx"><style>{sheetStyles}</style><NumbersSheet arms={towns} tick={at} playing={running} onClose={() => {}} /></div>
  const result = render(view(tick, playing))
  return (at, running = false) => result.rerender(view(at, running))
}

test('a newly different metric has current readings in its growing row throughout the entry fade', () => {
  const update = mount(loansTowns(), 30)
  const moving = row('bankActiveLoans')
  expect(moving.dataset.state).toBe('folded')
  expect(entry('bankActiveLoans').querySelector('b')).toHaveTextContent('1')

  update(31, true)
  for (const elapsed of [0, 80, 79, 1, 260]) {
    advance(elapsed)
    const folded = entry('bankActiveLoans')
    const rowVisible = ['entering-row', 'row'].includes(moving.dataset.state)
    const foldVisible = folded && folded.dataset.state !== 'leaving-entry'
    expect(Boolean(rowVisible || foldVisible)).toBe(true)
    expect(unavailable(moving.querySelector('button'))).toBeNull()
    expect(getComputedStyle(moving).gridTemplateRows).toBe('1fr')
    expect(getComputedStyle(moving).visibility).not.toBe('hidden')
    expect([...moving.querySelectorAll('.nx-number-value')].map(node => node.textContent)).toEqual(['1', '2'])
    // The outgoing equality entry may retain its name, never the old common reading.
    expect(folded?.querySelector('b') ?? null).toBeNull()
  }
  expect(moving.dataset.state).toBe('row')
  expect(entry('bankActiveLoans')).toBeNull()
})

test('a still-painting collapse accepts a click from outside focus and reopens its row', () => {
  const update = mount(loansTowns(), 31)
  const moving = row('bankActiveLoans')
  const button = moving.querySelector('button')
  expect(screen.getByRole('heading', { level: 2 })).toHaveFocus()

  update(32)
  expect(moving.dataset.state).toBe('leaving-row')
  expect(moving).not.toHaveAttribute('inert')
  expect(moving).toHaveAttribute('aria-hidden', 'false')
  expect(unavailable(button)).toBeNull()
  advance(80)
  // fireEvent does not perform pointer focus in JSDOM; emulate that browser step.
  act(() => button.focus())
  fireEvent.click(button)
  expect(button).toHaveFocus()
  expect(button).toHaveAttribute('aria-expanded', 'true')
  expect(moving.dataset.state).toBe('entering-row')
  advance(580)
  expect(moving.dataset.state).toBe('row')
  expect(button).toHaveFocus()
  expect(entry('bankActiveLoans')).toBeNull()
})

test('the final Jobs and pay fold entry and its label leave as one fading line', () => {
  const update = mount(arms, 11)
  const folded = entry('netJobs26')
  const line = folded.closest('.nx-fold-motion')
  expect(line.querySelectorAll('.nx-fold-entry')).toHaveLength(1)
  expect(line).toHaveAttribute('data-state', 'open')

  update(12, true)
  expect(line).toHaveClass('is-leaving')
  expect(line).toHaveAttribute('data-state', 'leaving')
  expect(folded).toHaveAttribute('data-state', 'leaving-entry')
  // JSDOM exposes CSS targets, not interpolated pixels. The parent fades both
  // pieces while the retained child keeps its width and opacity inside it.
  expect(getComputedStyle(line).opacity).toBe('0')
  expect(getComputedStyle(line).gridTemplateRows).toBe('0fr')
  expect(getComputedStyle(folded).opacity).toBe('1')
  expect(getComputedStyle(folded).gridTemplateColumns).toBe('1fr')
  expect(line.querySelector('.nx-number-fold-label')).not.toBeNull()
  advance(159)
  expect(entry('netJobs26')).toBe(folded)
  expect(line).toHaveAttribute('data-state', 'leaving')
  advance(1)
  expect(entry('netJobs26')).toBeNull()
  expect(line).toHaveAttribute('data-state', 'closed')
  expect(getComputedStyle(line).opacity).toBe('0')
})

test('reduced motion promotes and recomputes the final fold line instantly', () => {
  vi.stubGlobal('matchMedia', () => ({ matches: true }))
  const update = mount(arms, 11)
  const line = entry('netJobs26').closest('.nx-fold-motion')
  update(12, true)
  expect(row('netJobs26')).toHaveAttribute('data-state', 'row')
  expect(entry('netJobs26')).toBeNull()
  expect(line).toHaveAttribute('data-state', 'closed')
  update(11, true)
  expect(row('netJobs26')).toHaveAttribute('data-state', 'row')
  update(11)
  expect(row('netJobs26')).toHaveAttribute('data-state', 'folded')
  expect(entry('netJobs26')).toHaveAttribute('data-state', 'folded')
  expect(line).toHaveAttribute('data-state', 'open')
  expect(document.querySelector('.nx-sheet [data-state^="entering"], .nx-sheet [data-state^="leaving"]')).toBeNull()
})
