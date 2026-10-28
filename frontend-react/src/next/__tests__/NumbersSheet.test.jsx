import { act, fireEvent, render, screen, within } from '@testing-library/react'
import { readFileSync } from 'node:fs'
import { afterEach, beforeAll, describe, expect, test, vi } from 'vitest'
import NumbersSheet from '../numbers/NumbersSheet.jsx'
import { COPY, NUMBER_GROUPS, TOWN_COLORS } from '../catalog.js'
import { demoArms, fixtureArm } from './fixture.js'

let arms
beforeAll(() => { arms = demoArms() })
afterEach(() => { vi.unstubAllGlobals(); delete globalThis.IntersectionObserver })
const reduce = () => vi.stubGlobal('matchMedia', () => ({ matches: true }))
const sheet = (props = {}) => render(<div className="nx"><NumbersSheet arms={arms} tick={104} onClose={() => {}} {...props} /></div>)
const row = key => document.querySelector(`.nx-number-row[data-metric="${key}"]`)
const values = key => [...row(key).querySelectorAll('.nx-number-value')].map(node => node.textContent)
const here = import.meta.url
const numbersSheetCss = readFileSync(new URL('../numbers/numbersSheet.css', here), 'utf8')

describe('compact numbers sheet', () => {
  test('answer first, unique measure homes, six groups and revised equality folds', () => {
    sheet()
    const dialog = screen.getByRole('dialog', { name: COPY.numbers.title })
    expect(within(dialog).getAllByRole('heading', { level: 3 }).map(h => h.textContent)).toEqual([COPY.numbers.answer, ...NUMBER_GROUPS.map(group => COPY.numbers.groups[group.id].title)])
    expect(screen.queryByRole('navigation')).toBeNull()
    expect(dialog).not.toHaveTextContent('Everything we measure')
    expect(dialog).not.toHaveTextContent('Under 3%')
    const tally = screen.getByRole('group', { name: COPY.numbers.tally.label('Town B') })
    expect([...tally.children].map(chip => chip.textContent)).toEqual([
      '✓ 8 better in Town B', '! 2 worse', '8 different, neither better nor worse', '4 the same',
    ])
    expect(dialog.querySelector('.nx-answer-verdict').textContent).toBe('Town B is ahead on jobs, pay, savings and businesses, and its people feel better. Food and services cost more there. The gap between rich and poor is the same, but the poorer half holds a little less of the cash in Town B.')
    expect(row('publicWorksJobs')).toBeNull()
    expect(values('peopleOutOfWorkPer100')).toEqual(['46 in 100', '33 in 100'])
    expect(values('topTenthShare')).toEqual(['56%', '57%'])
    expect(values('bankActiveLoans')).toEqual(['337', '342'])
    const folded = [...dialog.querySelectorAll('.nx-row-motion[data-state="folded"]')].map(node => node.querySelector('[data-metric]').dataset.metric)
    expect(folded.sort()).toEqual(['gini','priceHousing','priceHealthcare','homelessHouseholds'].sort())
    expect(dialog.querySelectorAll('[data-hero="happiness"]')).toHaveLength(1)
    expect(row('happiness')).toBeNull()
    expect(dialog.querySelectorAll('.nx-number-chart-key')).toHaveLength(0)
  })

  test('focus goes into dialog and back; one Escape closes even with a chart open', () => {
    const opener = document.createElement('button'); document.body.appendChild(opener); opener.focus()
    const onClose = vi.fn(); const { unmount } = sheet({ onClose })
    expect(screen.getByRole('heading', { level: 2 })).toHaveFocus()
    fireEvent.keyDown(document.activeElement, { key: 'Escape' }); expect(onClose).toHaveBeenCalledOnce()
    unmount(); expect(opener).toHaveFocus(); opener.remove()
  })

  test('verdict links unfold their row, scroll and focus its button', () => {
    reduce(); const scroll = vi.fn(); Element.prototype.scrollIntoView = scroll
    try {
      sheet()
      fireEvent.click(screen.getByRole('link', { name: 'gap between rich and poor' }))
      expect(screen.getByRole('button', { name: 'Gap between rich and poor' })).toHaveFocus()
      expect(row('gini').querySelector('button')).toHaveAttribute('aria-expanded', 'true')
      expect(scroll).toHaveBeenCalledOnce()
    } finally { delete Element.prototype.scrollIntoView }
  })

  test('sticky Back and offset track the timeline', () => {
    const observers = []
    globalThis.IntersectionObserver = class { constructor(callback, options) { this.callback=callback; this.options=options; observers.push(this) } observe(node) { this.node=node } disconnect() {} }
    sheet({ id: 'numbers', top: 131 })
    expect(screen.getByRole('dialog')).toHaveAttribute('id','numbers')
    expect(screen.getByRole('dialog').style.getPropertyValue('--nx-sheet-top')).toBe('131px')
    expect(observers[0].options.rootMargin).toBe('-131px 0px 0px 0px')
    expect(screen.getAllByRole('button',{name:COPY.numbers.back})).toHaveLength(1)
    act(() => observers[0].callback([{isIntersecting:false}]))
    expect(within(screen.getByRole('group',{name:COPY.numbers.columns.label})).getByRole('button',{name:COPY.numbers.back})).toBeVisible()
  })

  test.each([1, 2, 3, 4])('sticky Back retains every column heading with %i towns', townCount => {
    const towns = Array.from({ length: townCount }, (_, index) => fixtureArm({ label: `Town ${String.fromCharCode(65 + index)}`, color: TOWN_COLORS[index] }))
    let observeHeader
    vi.stubGlobal('IntersectionObserver', class {
      constructor(callback) { observeHeader = callback }
      observe() {}
      disconnect() {}
    })
    // Vitest skips CSS imports. Apply the real sheet styles from disk so this
    // regression catches headings hidden by CSS as well as missing markup.
    const styles = document.createElement('style')
    styles.textContent = numbersSheetCss
    document.head.appendChild(styles)
    try {
      sheet({ arms: towns })
      const columns = screen.getByRole('group', { name: COPY.numbers.columns.label })
      const headings = [
        ...towns.map(town => within(columns).getByText(town.label)),
        within(columns).getByText(COPY.numbers.columns.run),
      ]
      if (townCount > 1) {
        headings.push(within(columns).getByText(townCount === 2
          ? COPY.numbers.columns.difference(towns[1].label, towns[0].label)
          : COPY.numbers.columns.differences(towns[0].label)))
      }
      expect(within(columns).queryByRole('button', { name: COPY.numbers.back })).toBeNull()
      act(() => observeHeader([{ isIntersecting: false }]))
      expect(within(columns).getByRole('button', { name: COPY.numbers.back })).toBeVisible()
      headings.forEach(heading => expect(heading).toBeVisible())
      act(() => observeHeader([{ isIntersecting: true }]))
      expect(within(columns).queryByRole('button', { name: COPY.numbers.back })).toBeNull()
      headings.forEach(heading => expect(heading).toBeVisible())
    } finally { styles.remove() }
  })

  test('sticky Back keeps its accessible name, close action and place before row controls', () => {
    let observeHeader
    vi.stubGlobal('IntersectionObserver', class {
      constructor(callback) { observeHeader = callback }
      observe() {}
      disconnect() {}
    })
    const onClose = vi.fn()
    sheet({ arms: [fixtureArm()], onClose })
    act(() => observeHeader([{ isIntersecting: false }]))
    const columns = screen.getByRole('group', { name: COPY.numbers.columns.label })
    const back = within(columns).getByRole('button', { name: COPY.numbers.back })
    const firstRow = within(row('peopleOutOfWorkPer100')).getByRole('button')
    const controls = screen.getAllByRole('button')
    expect(controls.indexOf(back)).toBeLessThan(controls.indexOf(firstRow))
    expect(back).not.toHaveAttribute('tabindex')
    expect(back.querySelector('svg')).toHaveAttribute('aria-hidden', 'true')
    back.focus()
    expect(back).toHaveFocus()
    fireEvent.keyDown(back, { key: 'Escape' })
    expect(onClose).toHaveBeenCalledOnce()
    onClose.mockClear()
    fireEvent.click(back)
    expect(onClose).toHaveBeenCalledOnce()
  })

  test('rules line excludes chip settings and retains mid-run history', () => {
    const changed = arms.map(arm => ({...arm,policyChanges:[{tick:30,policy:'benefit_level',value:'high'},{tick:40,policy:'benefit_level',value:'neutral'}]}))
    sheet({ arms:changed })
    fireEvent.click(screen.getByRole('button',{name:'Show them'}))
    const list=document.querySelector('.nx-number-rules ul')
    expect(list).not.toHaveTextContent('Minimum wage')
    expect(list).toHaveTextContent('changed in Year 1, week 40 (was high)')
    expect([...list.querySelectorAll('li')].find(li=>li.textContent.startsWith('Tax on wages')).textContent).toBe('Tax on wages: 15%')
  })

  test.each([2, 3, 4])('%s towns show values without outcome comparisons throughout warm-up, then compare in week 11', townCount => {
    reduce()
    const towns = [...arms, { ...arms[0], label: 'Town C', color: TOWN_COLORS[2] }, { ...arms[1], label: 'Town D', color: TOWN_COLORS[3] }].slice(0, townCount)
    const { container, rerender } = sheet({ arms: towns, tick: 1 })
    for (const tick of [1, 5, 10]) {
      rerender(<div className="nx"><NumbersSheet arms={towns} tick={tick} onClose={() => {}} /></div>)
      expect(screen.getByText(COPY.numbers.warmup)).toBeInTheDocument()
      expect(container.querySelector('.nx-answer-verdict,.nx-answer-tally,.nx-answer-hero-difference,.nx-answer-hero-note')).toBeNull()
      expect(container.querySelectorAll('.nx-number-tag,.nx-answer-tag,.nx-number-difference')).toHaveLength(0)
      expect([...container.querySelectorAll('.nx-number-differences')].every(cell => cell.textContent === '')).toBe(true)
      expect(container.querySelector('.nx-number-column-difference')).toBeEmptyDOMElement()
      expect(container.querySelector('.nx-number-fold')).toBeNull()
      expect(values('typicalWeeklyPay')).toHaveLength(townCount)
      expect(values('priceHousing')).toEqual(Array(townCount).fill('$5.00'))
      expect(container.querySelectorAll('.nx-answer-hero .nx-answer-reading').length).toBeGreaterThanOrEqual(2)
      expect(container.querySelectorAll('.nx-number-value.is-same-value')).toHaveLength(0)
      expect(container.querySelector('.nx-story-inline')).not.toHaveTextContent('towns start from the same place')
      expect(container.querySelector('.nx-number-rules p')).toHaveTextContent(/^Rules:\s*Show them$/)
    }
    fireEvent.click(screen.getByRole('button', { name: 'Show them' }))
    expect(container.querySelector('.nx-number-rules ul')).toBeVisible()
    expect(container.querySelector('.nx-number-rules ul')).toHaveTextContent('Tax on wages: 15%')
    rerender(<div className="nx"><NumbersSheet arms={towns} tick={11} onClose={() => {}} /></div>)
    expect(screen.queryByText(COPY.numbers.warmup)).toBeNull()
    expect(container.querySelectorAll('.nx-answer-verdict')).toHaveLength(townCount - 1)
    expect(container.querySelectorAll('.nx-answer-tally')).toHaveLength(townCount - 1)
    expect(container.querySelector('.nx-answer-hero-difference')).toBeInTheDocument()
    expect(container.querySelector('.nx-number-column-difference')).toHaveTextContent('Town A')
    expect(container.querySelector('.nx-number-difference')).toBeInTheDocument()
  }, 15_000)

  test('one town has every row and no comparisons, tally or fold line', () => {
    sheet({arms:[arms[0]]})
    expect(document.querySelectorAll('.nx-number-row')).toHaveLength(20)
    expect(document.querySelector('.nx-answer-verdict,.nx-answer-tally,.nx-number-differences,.nx-number-fold')).toBeNull()
    expect(document.querySelector('.nx-number-rules')).toHaveTextContent('17 rules, all at their usual settings.')
  })

  test('three and four towns get a value column and comparison per town', () => {
    const towns=[...arms,{...arms[0],label:'Town C',color:TOWN_COLORS[2]},{...arms[1],label:'Town D',color:TOWN_COLORS[3]}]
    sheet({arms:towns})
    expect(values('typicalWeeklyPay')).toHaveLength(4)
    expect(document.querySelectorAll('.nx-answer-tally')).toHaveLength(3)
    expect(document.querySelectorAll('.nx-answer-verdict')).toHaveLength(3)
    expect(document.querySelector('.nx-number-fold')).toHaveTextContent('Same in every town:')
  })

  test('lost notice and last-week note live beneath the town column', () => {
    sheet({live:{phase:'lost',towns:[{label:'Town A',status:'paused'},{label:'Town B',status:'lost',lastTick:40}],error:{town:'Town B',kind:'lost'}}})
    expect(screen.getByRole('status')).toHaveTextContent('Town B lost its connection')
    expect(document.querySelectorAll('.nx-number-column-town')[1]).toHaveTextContent('lost its connection in Year 1, week 40')
  })

  test('missing measurements remain rows and never read zero', () => {
    const missing=arms.map(arm=>({...arm,series:{...arm.series,priceFood:[]}}))
    sheet({arms:missing})
    expect(values('priceFood')).toEqual([COPY.numbers.notMeasured,COPY.numbers.notMeasured])
    expect(row('priceFood').closest('.nx-row-motion')).toHaveAttribute('data-state','row')
  })

  test('playing promotes equal rows once; pause recomputes equality', () => {
    reduce()
    const towns=arms.map((arm,i)=>({...arm,series:{...arm.series,bankActiveLoans:arm.ticks.map(week=>week===31&&i?2:1)}}))
    const {rerender}=sheet({arms:towns,tick:30})
    const phase=()=>row('bankActiveLoans').closest('.nx-row-motion').dataset.state
    expect(phase()).toBe('folded')
    rerender(<div className="nx"><NumbersSheet arms={towns} tick={31} playing onClose={()=>{}} /></div>)
    expect(phase()).toBe('row')
    rerender(<div className="nx"><NumbersSheet arms={towns} tick={32} playing onClose={()=>{}} /></div>)
    expect(phase()).toBe('row')
    rerender(<div className="nx"><NumbersSheet arms={towns} tick={32} onClose={()=>{}} /></div>)
    expect(phase()).toBe('folded')
  })
})
