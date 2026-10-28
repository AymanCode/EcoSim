import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeAll, beforeEach, expect, test, vi } from 'vitest'
import NumbersSheet from '../numbers/NumbersSheet.jsx'
import { COPY, METRICS } from '../catalog.js'
import { demoArms } from './fixture.js'

let arms
beforeAll(() => { arms = demoArms() })
beforeEach(() => {
  vi.useFakeTimers()
  vi.stubGlobal('matchMedia', () => ({ matches: false }))
})
afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
  vi.useRealTimers()
})

const row = key => document.querySelector(`.nx-number-row[data-metric="${key}"]`)
const rowButton = key => row(key).querySelector('button')
const foldButtonName = COPY.numbers.fold.show(METRICS.bankActiveLoans.name)
const unavailable = node => node.closest('[inert], [aria-hidden="true"]')
const advance = milliseconds => act(() => vi.advanceTimersByTime(milliseconds))
const townsWith = (key, valueAt) => arms.map((arm, index) => ({
  ...arm,
  series: { ...arm.series, [key]: arm.ticks.map(week => valueAt(week, index)) },
}))

function mount(towns, tick, playing = false) {
  const view = (at, running) => <div className="nx"><NumbersSheet arms={towns} tick={at} playing={running} onClose={() => {}} /></div>
  const result = render(view(tick, playing))
  return (at, running = false) => result.rerender(view(at, running))
}

// JSDOM permits focus inside inert trees. Record the real target's accessibility
// at the instant focus is attempted so these tests also catch premature calls.
function recordFocus() {
  const calls = []
  const nativeFocus = HTMLElement.prototype.focus
  vi.spyOn(HTMLElement.prototype, 'focus').mockImplementation(function (options) {
    calls.push({ node: this, unavailable: unavailable(this) })
    nativeFocus.call(this, options)
  })
  return calls
}

test('automatic folding keeps the focused row accessible until its fold button takes focus', () => {
  const towns = townsWith('bankActiveLoans', (week, index) => week === 31 && index ? 2 : 1)
  const update = mount(towns, 31, true)
  const source = rowButton('bankActiveLoans')
  source.focus()
  const calls = recordFocus()

  update(32)
  expect(source).toHaveFocus()
  expect(unavailable(source)).toBeNull()
  advance(200)
  expect(source).toHaveFocus()
  expect(unavailable(source)).toBeNull()
  advance(220)

  const destination = screen.getByRole('button', { name: foldButtonName })
  expect(destination).toHaveFocus()
  expect(unavailable(destination)).toBeNull()
  expect(unavailable(source)).not.toBeNull()
  expect(calls.filter(call => call.node === destination)).toEqual([{ node: destination, unavailable: null }])
})

test('playing promotion transfers fold-button focus to the accessible row and only pause folds it back', () => {
  const towns = townsWith('bankActiveLoans', (week, index) => week === 31 && index ? 2 : 1)
  const update = mount(towns, 30)
  const source = screen.getByRole('button', { name: foldButtonName })
  source.focus()
  const calls = recordFocus()

  update(31, true)
  expect(source).toHaveFocus()
  expect(unavailable(source)).toBeNull()
  advance(80)
  expect(source).toHaveFocus()
  expect(unavailable(source)).toBeNull()
  advance(80)

  const destination = rowButton('bankActiveLoans')
  expect(destination).toHaveFocus()
  expect(unavailable(destination)).toBeNull()
  expect(calls.filter(call => call.node === destination)).toEqual([{ node: destination, unavailable: null }])
  advance(420)
  update(32, true)
  expect(destination).toHaveFocus()
  expect(unavailable(destination)).toBeNull()
  expect(screen.queryByRole('button', { name: foldButtonName })).toBeNull()

  update(32)
  advance(420)
  expect(screen.getByRole('button', { name: foldButtonName })).toHaveFocus()
})

test('a verdict jump during the fold-entry fade focuses an expanded non-inert row', () => {
  const towns = townsWith('gini', (week, index) => week >= 35 && index ? 0.6 : 0.4)
  const update = mount(towns, 30)
  update(35, true)
  advance(80)
  const target = rowButton('gini')
  expect(unavailable(target)).not.toBeNull()
  const calls = recordFocus()

  fireEvent.click(screen.getByRole('link', { name: 'gap between rich and poor' }))

  expect(target).toHaveAttribute('aria-expanded', 'true')
  expect(target).toHaveFocus()
  expect(unavailable(target)).toBeNull()
  expect(calls.filter(call => call.node === target)).toEqual([{ node: target, unavailable: null }])
  advance(580)
  expect(target).toHaveFocus()
  expect(unavailable(target)).toBeNull()
})

test('reduced motion still transfers focus in both fold directions immediately', () => {
  vi.stubGlobal('matchMedia', () => ({ matches: true }))
  const towns = townsWith('bankActiveLoans', (week, index) => week === 31 && index ? 2 : 1)
  const update = mount(towns, 31)
  rowButton('bankActiveLoans').focus()
  const calls = recordFocus()

  update(32)
  const folded = screen.getByRole('button', { name: foldButtonName })
  expect(folded).toHaveFocus()
  expect(unavailable(folded)).toBeNull()
  update(31, true)
  expect(rowButton('bankActiveLoans')).toHaveFocus()
  expect(unavailable(rowButton('bankActiveLoans'))).toBeNull()
  expect(calls.every(call => call.unavailable === null)).toBe(true)
})
