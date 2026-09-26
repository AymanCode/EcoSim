import { describe, expect, test, vi } from 'vitest'
import { fireEvent, render, screen, within } from '@testing-library/react'
import RunScreen from '../RunScreen.jsx'
import useReplay from '../useReplay.js'
import { formatMetric } from '../catalog.js'
import { commonTicks, valueAt } from '../data/derive.js'
import { leadSentence, verdict } from '../narration.js'
import { fixtureArm, TOWN_A, TOWN_B } from './fixture.js'

function townB() {
  const b = fixtureArm(TOWN_B)
  b.series.peopleOutOfWorkPer100 = b.series.peopleOutOfWorkPer100.map(v => v + 3)
  b.setup = { ...b.setup, initial_policy: { minimum_wage_policy: 'high' } }
  return b
}

// The parent owns the clock, as NextApp does.
function Clocked({ arms }) {
  const maxTick = commonTicks(arms).at(-1) ?? 1
  const clock = useReplay({ maxTick })
  return (
    <div className="nx">
      <RunScreen
        arms={arms}
        tick={clock.tick}
        maxTick={maxTick}
        playing={clock.playing}
        onToggle={clock.toggle}
        onScrub={clock.scrub}
        speed={clock.speed}
        onSpeed={clock.setSpeed}
      />
    </div>
  )
}

const weekShown = container => container.querySelector('.nx-clock .nx-week').textContent
const scrubTo = week => fireEvent.change(screen.getByRole('slider', { name: 'Week of the run' }), { target: { value: String(week) } })
// The two ways into "All the numbers": the line under the stat cards and the timeline's button.
const sheetLink = container => within(container.querySelector('.nx-side')).getByRole('button', { name: 'Show me all the numbers' })
const sheetToggle = () => within(screen.getByRole('region', { name: 'Timeline' })).getByRole('button', { name: 'Show me all the numbers' })
const sheet = () => screen.queryByRole('dialog', { name: 'All the numbers' })

describe('RunScreen', () => {
  test('two towns: two matching columns, the lead sentence and the verdict', () => {
    const arms = [fixtureArm(TOWN_A), townB()]
    const { container } = render(<Clocked arms={arms} />)
    scrubTo(20)
    const columns = container.querySelectorAll('.nx-col')
    expect(columns).toHaveLength(2)
    expect(columns[0]).toHaveTextContent('Town A')
    expect(columns[0].querySelector('.nx-colhead span')).toHaveTextContent('more help for people out of work')
    expect(columns[1]).toHaveTextContent('Town B')
    expect(columns[1]).toHaveTextContent('a higher minimum wage')
    columns.forEach(column => {
      expect(column.querySelector('.nx-townc')).toBeInTheDocument()
      expect(column.querySelector('.nx-biz')).toBeInTheDocument()
      expect(column.querySelector('.nx-hh')).toBeInTheDocument()
    })
    expect(container.querySelector('.nx-lead')).toHaveTextContent(leadSentence(arms, 20))
    const shown = container.querySelector('.nx-verdict').textContent
    expect(shown).toBe(verdict(arms, 20))
    expect(shown.endsWith('?')).toBe(true)
    expect(container.querySelectorAll('.nx-stats .nx-stat')).toHaveLength(4)
    expect(container.querySelectorAll('path.nx-line')).toHaveLength(2)
    expect(screen.getByRole('heading', { name: "What's happening newest first" })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'How to read this for first-timers' })).toBeInTheDocument()
  })

  test('scrubbing the timeline moves every panel to that week', () => {
    const arms = [fixtureArm(TOWN_A), townB()]
    const { container } = render(<Clocked arms={arms} />)
    expect(weekShown(container)).toBe('Year 1, week 1')
    expect(container.querySelector('.nx-lead')).toHaveTextContent(leadSentence(arms, 1))
    scrubTo(20)
    expect(weekShown(container)).toBe('Year 1, week 20')
    expect(container.querySelector('.nx-lead')).toHaveTextContent(leadSentence(arms, 20))
    expect(container.querySelector('.nx-verdict').textContent).toBe(verdict(arms, 20))
  })

  test('shows the week it is given and reports the viewer\'s moves to its parent', () => {
    const onScrub = vi.fn()
    const onToggle = vi.fn()
    const { container } = render(
      <div className="nx">
        <RunScreen arms={[fixtureArm(TOWN_A), townB()]} tick={17} maxTick={24} playing={false} onToggle={onToggle} onScrub={onScrub} speed={1} onSpeed={() => {}} />
      </div>,
    )
    expect(weekShown(container)).toBe('Year 1, week 17')
    scrubTo(3)
    expect(onScrub).toHaveBeenCalledWith(3)
    expect(weekShown(container)).toBe('Year 1, week 17')
    fireEvent.click(screen.getByRole('button', { name: 'Play' }))
    expect(onToggle).toHaveBeenCalledTimes(1)
  })

  test('the chart follows the metric chips', () => {
    render(<Clocked arms={[fixtureArm(TOWN_A), townB()]} />)
    fireEvent.click(screen.getByRole('button', { name: 'Typical weekly pay' }))
    expect(screen.getByRole('button', { name: 'Typical weekly pay' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('heading', { level: 3, name: 'Typical weekly pay' })).toBeInTheDocument()
  })

  test('a column head names the rules in force at the week shown, including a change the town hall made', () => {
    // The recording's town hall raised help for people out of work in week 7.
    const arms = [fixtureArm(TOWN_A), townB()]
    const { container } = render(<Clocked arms={arms} />)
    const heads = () => [...container.querySelectorAll('.nx-colhead span')].map(head => head.textContent)
    scrubTo(6)
    expect(heads()).toEqual(['no changes', 'a higher minimum wage'])
    scrubTo(7)
    expect(heads()).toEqual(['more help for people out of work', 'more help for people out of work and a higher minimum wage'])
    // A change back to the usual rules reads as no change.
    arms[0].policyChanges.push({ id: 'back', tick: 20, policy: 'benefit_level', value: 'neutral' })
    scrubTo(20)
    expect(heads()[0]).toBe('no changes')
  })

  test('one town: one column and a summary instead of a question', () => {
    const arms = [fixtureArm(TOWN_A)]
    const { container } = render(<Clocked arms={arms} />)
    expect(container.querySelectorAll('.nx-col')).toHaveLength(1)
    expect(container.querySelector('.nx-cols')).toHaveClass('is-single')
    scrubTo(18)
    const shown = container.querySelector('.nx-verdict').textContent
    expect(shown).toBe(verdict(arms, 18))
    expect(shown).not.toContain('?')
    expect(container.querySelectorAll('path.nx-line')).toHaveLength(1)
  })

  test('a line under the stat cards names more numbers and opens all of them; focus goes in and back to the link', () => {
    const arms = [fixtureArm(TOWN_A), townB()]
    const { container } = render(<Clocked arms={arms} />)
    expect(sheet()).toBeNull()
    expect(container.querySelector('.nx-side .nx-morestats')).toHaveTextContent(
      "Also: prices in every shop, savings, businesses opening and closing, the town hall's money. Show me all the numbers.",
    )
    const link = sheetLink(container)
    fireEvent.click(link)
    const dialog = sheet()
    expect(dialog).toBeInTheDocument()
    expect(within(dialog).getByRole('heading', { level: 2, name: 'All the numbers' })).toHaveFocus()
    // The sheet takes the towns' place under the timeline, which stays in view.
    expect(container.querySelector('main')).not.toBeVisible()
    expect(screen.getByRole('slider', { name: 'Week of the run' })).toBeVisible()
    expect(dialog.compareDocumentPosition(screen.getByRole('region', { name: 'Timeline' })) & Node.DOCUMENT_POSITION_PRECEDING).toBeTruthy()
    fireEvent.click(within(dialog).getByRole('button', { name: 'Back to the towns' }))
    expect(sheet()).toBeNull()
    expect(container.querySelector('main')).toBeVisible()
    expect(link).toHaveFocus()
    // The Run screen is as it was.
    expect(container.querySelectorAll('.nx-col')).toHaveLength(2)
  })

  test('opening from the stat cards scrolls to the top; closing restores the towns position', () => {
    const scroller = document.documentElement
    const original = Object.getOwnPropertyDescriptor(scroller, 'scrollTop')
    let position = 900
    const writes = []
    Object.defineProperty(scroller, 'scrollTop', {
      configurable: true, get: () => position,
      set: value => { position = value; writes.push(value) },
    })
    try {
      const { container } = render(<Clocked arms={[fixtureArm(TOWN_A), townB()]} />)
      const link = sheetLink(container)
      fireEvent.click(link)
      expect(writes).toEqual([0])
      scroller.scrollTop = 1800
      writes.length = 0
      fireEvent.click(within(sheet()).getByRole('button', { name: 'Back to the towns' }))
      expect(writes).toEqual([900])
      expect(link).toHaveFocus()
    } finally {
      if (original) Object.defineProperty(scroller, 'scrollTop', original)
      else delete scroller.scrollTop
    }
  })

  test('the timeline button opens and closes it, Escape closes it, and focus comes back to the button', () => {
    render(<Clocked arms={[fixtureArm(TOWN_A), townB()]} />)
    const toggle = sheetToggle()
    expect(toggle).toHaveAttribute('aria-pressed', 'false')
    expect(toggle).toHaveAttribute('aria-expanded', 'false')
    fireEvent.click(toggle)
    expect(toggle).toHaveAttribute('aria-pressed', 'true')
    expect(toggle).toHaveAttribute('aria-expanded', 'true')
    expect(toggle).toHaveAttribute('aria-controls', sheet().id)
    fireEvent.keyDown(document.activeElement, { key: 'Escape' })
    expect(sheet()).toBeNull()
    expect(toggle).toHaveFocus()
    expect(toggle).toHaveAttribute('aria-pressed', 'false')
    fireEvent.click(toggle)
    expect(sheet()).toBeInTheDocument()
    fireEvent.click(toggle)
    expect(sheet()).toBeNull()
    expect(toggle).toHaveFocus()
  })

  test('the sheet runs on the same clock: scrubbing while it is open moves its numbers', () => {
    const arms = [fixtureArm(TOWN_A), townB()]
    const { container } = render(<Clocked arms={arms} />)
    fireEvent.click(sheetLink(container))
    const tile = within(sheet()).getByRole('article', { name: 'People out of work' })
    const shown = () => [...tile.querySelectorAll('.nx-pv b')].map(value => value.textContent)
    const expected = week => arms.map(arm => formatMetric('peopleOutOfWorkPer100', valueAt(arm, 'peopleOutOfWorkPer100', week)))
    scrubTo(5)
    expect(shown()).toEqual(expected(5))
    scrubTo(15)
    expect(expected(15)).not.toEqual(expected(5))
    expect(shown()).toEqual(expected(15))
    expect(sheet()).toHaveTextContent('Everything we measure in both towns, in Year 1, week 15.')
    expect(weekShown(container)).toBe('Year 1, week 15')
  })

  test('the sheet\'s jump bar sticks right under the timeline, at the timeline\'s measured height', () => {
    const realObserver = globalThis.ResizeObserver
    globalThis.ResizeObserver = class {
      constructor(callback) { this.callback = callback }
      observe(node) { this.callback([{ target: node }]) }
      unobserve() {}
      disconnect() {}
    }
    const rect = vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockImplementation(function measured() {
      const height = this.classList.contains('nx-hbar') ? 131.6 : 0
      return { x: 0, y: 0, top: 0, left: 0, right: 0, bottom: height, width: 0, height }
    })
    try {
      const { container } = render(<Clocked arms={[fixtureArm(TOWN_A), townB()]} />)
      fireEvent.click(sheetLink(container))
      expect(sheet().style.getPropertyValue('--nx-sheet-top')).toBe('131px')
    } finally {
      rect.mockRestore()
      globalThis.ResizeObserver = realObserver
    }
  })
})
