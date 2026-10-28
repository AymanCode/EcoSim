import fs from 'node:fs'
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { parse } from 'postcss'
import { afterEach, beforeAll, expect, test, vi } from 'vitest'
import NumbersSheet from '../numbers/NumbersSheet.jsx'
import { COPY, METRICS, TOWN_COLORS } from '../catalog.js'
import { fixtureArm } from './fixture.js'

const here = import.meta.url
const focusCss = parse(fs.readFileSync(new URL('../next.css', here), 'utf8'))
const foldCss = parse(fs.readFileSync(new URL('../numbers/numbersSheet.css', here), 'utf8'))
const declarations = rule => Object.fromEntries(rule.nodes.filter(node => node.type === 'decl').map(node => [node.prop, node.value]))
let arms
beforeAll(() => {
  // Two equal prices provide a real multi-entry fold without unrelated chart
  // histories. Focus mechanics need only one measured week.
  const source = fixtureArm()
  const snapshot = { ...source, ticks: source.ticks.slice(-1), series: { priceHousing: [5], priceHealthcare: [10] } }
  arms = ['Town A', 'Town B', 'Town C', 'Town D'].map((label, index) => ({ ...snapshot, label, color: TOWN_COLORS[index] }))
})
afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  vi.useRealTimers()
})

test('the folded button focus outline fits inside its animation clip in either motion mode', () => {
  // jsdom cannot paint clipping. Guard the geometry-producing declarations;
  // headless screenshots cover the complete visible ring in the real browser.
  const inherited = declarations(focusCss.nodes.find(rule => rule.selector === '.nx button:focus-visible'))
  const rule = foldCss.nodes.find(rule => rule.selector === '.nx .nx-fold-entry button:focus-visible')
  expect(rule, 'fold entries need their own focus treatment outside motion media queries').toBeDefined()
  const focused = { ...inherited, ...declarations(rule) }
  const width = Number.parseFloat(focused['outline-width'] ?? focused.outline)
  expect(width).toBeGreaterThanOrEqual(2)
  expect(focused.outline).toContain('solid var(--nx-a)')
  expect(Number.parseFloat(focused['outline-offset'])).toBeLessThanOrEqual(-width)
})

test('fold separators keep their spaces inside the clip without spreading button names or values', () => {
  const entry = declarations(foldCss.nodes.find(rule => rule.selector === '.nx .nx-fold-entry > span'))
  expect(entry['white-space']).toBe('pre-wrap')
  expect(Number.parseFloat(entry['word-spacing'])).toBeGreaterThanOrEqual(4)
  const content = declarations(foldCss.nodes.find(rule => rule.selector === '.nx .nx-fold-entry > span > *'))
  expect(content['word-spacing']).toBe('normal')
})

test.each([
  { towns: 2, reduced: false },
  { towns: 2, reduced: true },
  { towns: 3, reduced: false },
  { towns: 3, reduced: true },
  { towns: 4, reduced: false },
  { towns: 4, reduced: true },
])('Enter returns focus to a usable fold entry at arrival and rest: $towns towns, reduced motion $reduced', ({ towns, reduced }) => {
  vi.useFakeTimers()
  vi.stubGlobal('matchMedia', () => ({ matches: reduced }))
  const compared = arms.slice(0, towns)
  render(<div className="nx"><NumbersSheet arms={compared} tick={compared[0].ticks[0]} onClose={() => {}} /></div>)
  const name = COPY.numbers.fold.show(METRICS.priceHousing.name)
  const original = screen.getByRole('button', { name })
  const fold = original.closest('.nx-number-fold')
  expect(fold).toHaveTextContent(COPY.numbers.fold.equal(towns))
  const entries = [...fold.querySelectorAll('.nx-fold-entry')]
  expect(entries.length).toBeGreaterThan(1)
  expect(entries.slice(1).map(entry => entry.firstElementChild.firstChild.textContent)).toEqual(Array(entries.length - 1).fill(COPY.numbers.fold.join))
  act(() => original.focus())
  fireEvent.click(original)

  const open = screen.getByRole('button', { name: METRICS.priceHousing.name })
  expect(open).toHaveFocus()
  expect(open).toHaveAttribute('aria-expanded', 'true')
  if (!reduced) act(() => vi.advanceTimersByTime(420))
  fireEvent.keyDown(open, { key: 'Enter' })
  expect(open).toHaveAttribute('aria-expanded', 'false')
  if (!reduced) {
    expect(open).toHaveFocus()
    act(() => vi.advanceTimersByTime(420))
  }

  const folded = screen.getByRole('button', { name })
  expect(folded).toHaveFocus()
  expect(folded.closest('[inert], [aria-hidden="true"]')).toBeNull()
  expect(folded.closest('.nx-fold-entry')).toHaveAttribute('data-state', reduced ? 'folded' : 'entering-entry')
  if (!reduced) act(() => vi.advanceTimersByTime(160))
  expect(folded).toHaveFocus()
  expect(folded.closest('.nx-fold-entry')).toHaveAttribute('data-state', 'folded')
})
