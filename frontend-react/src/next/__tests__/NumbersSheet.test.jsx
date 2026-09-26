import fs from 'node:fs'
import { afterEach, beforeAll, describe, expect, test, vi } from 'vitest'
import { act, fireEvent, render, screen, within } from '@testing-library/react'
import NumbersSheet from '../numbers/NumbersSheet.jsx'
import { COPY, NUMBER_GROUPS, TOWN_COLORS } from '../catalog.js'
import { demoArms } from './fixture.js'

// See fixture.js: keep import.meta.url in a variable so Vite leaves it a file: URL.
const here = import.meta.url
const CSS = fs.readFileSync(new URL('../next.css', here), 'utf8')

let arms
beforeAll(() => { arms = demoArms() })

function sheet(props = {}) {
  return render(<div className="nx"><NumbersSheet arms={arms} tick={72} onClose={() => {}} {...props} /></div>)
}

const GROUP_TITLES = NUMBER_GROUPS.map(group => COPY.numbers.groups[group.id].title)

// The rules table and the glance scoreboard; the special visuals' text
// alternatives are visually hidden tables of their own.
const shownTables = () => screen.getAllByRole('table').filter(table => !table.closest('.nx-sr'))
// The two shares are drawn together, as "Who holds the savings".
const TOGETHER = { bottomHalfShare: 'topTenthShare' }

describe('NumbersSheet', () => {
  afterEach(() => { delete globalThis.IntersectionObserver })

  test('a dialog titled "All the numbers" that names the week and each town\'s rules', () => {
    sheet()
    const dialog = screen.getByRole('dialog', { name: 'All the numbers' })
    expect(dialog).toHaveTextContent('Everything we measure in both towns, in Year 2, week 20.')
    const chips = within(dialog).getAllByRole('listitem').filter(item => item.classList.contains('nx-tchip'))
    expect(chips.map(chip => chip.textContent)).toEqual(['Town ANo changes', 'Town BA higher minimum wage'])
  })

  test('the two top sections, then one card per group, each under its heading', () => {
    sheet()
    const headings = screen.getAllByRole('heading', { level: 3 }).map(heading => heading.textContent)
    expect(headings).toEqual(['Rules in force', 'This week at a glance', ...GROUP_TITLES])
    NUMBER_GROUPS.forEach(group => {
      const card = screen.getByRole('region', { name: COPY.numbers.groups[group.id].title })
      expect(card).toHaveTextContent(COPY.numbers.groups[group.id].blurb)
      const cards = within(card).getAllByRole('article')
      // Every number has its card: a tile, or the special visual that draws it.
      group.keys.forEach(key => {
        const drawnBy = TOGETHER[key] ?? key
        expect(cards.some(node => node.dataset.metric === drawnBy), key).toBe(true)
      })
      expect(cards.length).toBe(group.keys.filter(key => !TOGETHER[key]).length + (group.extras ?? []).length)
    })
  })

  test('focus moves to the heading on open and back to the opener when it closes', () => {
    const opener = document.createElement('button')
    document.body.appendChild(opener)
    opener.focus()
    const { unmount } = sheet()
    expect(screen.getByRole('heading', { level: 2, name: 'All the numbers' })).toHaveFocus()
    unmount()
    expect(opener).toHaveFocus()
    opener.remove()
  })

  test('Escape and "Back to the towns" call onClose', () => {
    const onClose = vi.fn()
    sheet({ onClose })
    fireEvent.keyDown(document.activeElement, { key: 'Escape' })
    expect(onClose).toHaveBeenCalledTimes(1)
    // One way back at a time: the bar's button waits until the header's scrolls away.
    const backs = screen.getAllByRole('button', { name: 'Back to the towns' })
    expect(backs).toHaveLength(1)
    fireEvent.click(backs[0])
    expect(onClose).toHaveBeenCalledTimes(2)
  })

  test('the sticky bar shows its own way back once the header has scrolled away', () => {
    const observers = []
    globalThis.IntersectionObserver = class {
      constructor(callback) { this.callback = callback; observers.push(this) }
      observe(target) { this.target = target }
      disconnect() {}
    }
    sheet()
    expect(observers).toHaveLength(1)
    expect(observers[0].target).toBe(screen.getByRole('button', { name: 'Back to the towns' }))
    act(() => observers[0].callback([{ isIntersecting: false }]))
    const nav = screen.getByRole('navigation', { name: 'Jump to a group' })
    expect(within(nav).getByRole('button', { name: 'Back to the towns' })).toBeVisible()
    act(() => observers[0].callback([{ isIntersecting: true }]))
    expect(screen.getAllByRole('button', { name: 'Back to the towns' })).toHaveLength(1)
  })

  test('the way back hides behind the bar above: the jump bar sticks at `top` and the observer insets the view by it', () => {
    const observers = []
    globalThis.IntersectionObserver = class {
      constructor(callback, options) { this.callback = callback; this.options = options; observers.push(this) }
      observe(target) { this.target = target }
      disconnect() { this.disconnected = true }
    }
    const { rerender } = render(<div className="nx"><NumbersSheet id="numbers" arms={arms} tick={72} onClose={() => {}} top={64} /></div>)
    const dialog = screen.getByRole('dialog', { name: 'All the numbers' })
    expect(dialog).toHaveAttribute('id', 'numbers')
    expect(dialog.style.getPropertyValue('--nx-sheet-top')).toBe('64px')
    expect(observers.at(-1).options.rootMargin).toBe('-64px 0px 0px 0px')
    // The bar above wraps to a new height: both follow it.
    rerender(<div className="nx"><NumbersSheet id="numbers" arms={arms} tick={72} onClose={() => {}} top={131} /></div>)
    expect(dialog.style.getPropertyValue('--nx-sheet-top')).toBe('131px')
    expect(observers.at(-2).disconnected).toBe(true)
    expect(observers.at(-1).options.rootMargin).toBe('-131px 0px 0px 0px')
    // With nothing above it, nothing hides it.
    rerender(<div className="nx"><NumbersSheet id="numbers" arms={arms} tick={72} onClose={() => {}} /></div>)
    expect(dialog.style.getPropertyValue('--nx-sheet-top')).toBe('0px')
    expect(observers.at(-1).options.rootMargin).toBe('0px 0px 0px 0px')
  })

  test('jump chips name every section and take the reader to it', () => {
    const scroll = vi.fn()
    Element.prototype.scrollIntoView = scroll
    try {
      sheet()
      const nav = screen.getByRole('navigation', { name: 'Jump to a group' })
      const links = within(nav).getAllByRole('link')
      expect(links.map(link => link.textContent)).toEqual(['Rules in force', 'This week', ...GROUP_TITLES])
      links.forEach(link => expect(document.getElementById(link.getAttribute('href').slice(1))).toBeInTheDocument())
      fireEvent.click(within(nav).getByRole('link', { name: 'Prices' }))
      expect(scroll).toHaveBeenCalledTimes(1)
      expect(screen.getByRole('heading', { name: 'Prices' })).toHaveFocus()
    } finally {
      delete Element.prototype.scrollIntoView
    }
  })

  test('a chart key explains the setting-up band, this week and the weeks to come', () => {
    sheet()
    const key = screen.getByRole('list', { name: 'How to read the charts' })
    expect(within(key).getAllByRole('listitem').map(item => item.textContent))
      .toEqual(['Setting up: weeks 1 to 10', 'This week', 'Weeks still to come'])
  })

  test('the sheet follows the clock', () => {
    const { rerender } = sheet()
    rerender(<div className="nx"><NumbersSheet arms={arms} tick={30} onClose={() => {}} /></div>)
    expect(screen.getByRole('dialog')).toHaveTextContent('Everything we measure in both towns, in Year 1, week 30.')
    expect(screen.getByText(/^Eight headline numbers for Year 1, week 30\./)).toBeInTheDocument()
  })

  test('a tile opens it big; Escape comes back to the numbers and to that tile', () => {
    const onClose = vi.fn()
    sheet({ onClose })
    const work = screen.getByRole('region', { name: 'Work and pay' })
    const tile = within(work).getByRole('article', { name: 'People out of work' })
    fireEvent.click(tile)
    expect(screen.getByRole('button', { name: 'Back to all the numbers' })).toHaveFocus()
    expect(screen.getByRole('heading', { level: 3, name: 'People out of work' })).toBeInTheDocument()
    expect(screen.queryByRole('region', { name: 'Work and pay' })).toBeNull()
    expect(screen.queryByRole('navigation', { name: 'Jump to a group' })).toBeNull()
    fireEvent.keyDown(document.activeElement, { key: 'Escape' })
    expect(onClose).not.toHaveBeenCalled()
    expect(screen.queryByRole('button', { name: 'Back to all the numbers' })).toBeNull()
    expect(screen.getByRole('region', { name: 'Work and pay' })).toBeInTheDocument()
    expect(tile).toHaveFocus()
    fireEvent.keyDown(document.activeElement, { key: 'Escape' })
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  test('a town lost in a live run keeps its numbers and says when it lost its connection', () => {
    sheet({
      live: {
        phase: 'lost',
        towns: [{ label: 'Town A', status: 'stopped', lastTick: 72 }, { label: 'Town B', status: 'lost', lastTick: 40 }],
      },
    })
    const note = 'lost its connection in Year 1, week 40'
    const chips = screen.getAllByRole('listitem').filter(item => item.classList.contains('nx-tchip'))
    expect(chips[1]).toHaveTextContent(note)
    expect(chips[0]).not.toHaveTextContent('lost')
    shownTables().forEach(table => {
      expect(within(table).getAllByRole('columnheader').find(head => head.textContent.startsWith('Town B'))).toHaveTextContent(note)
    })
  })

  test('four towns: the rules table and the glance table each scroll sideways inside their own card', () => {
    const four = [
      ...arms,
      { ...arms[0], label: 'Town C', color: TOWN_COLORS[2] },
      { ...arms[1], label: 'Town D', color: TOWN_COLORS[3] },
    ]
    const style = document.createElement('style')
    style.textContent = CSS
    document.head.appendChild(style)
    try {
      render(<div className="nx"><NumbersSheet arms={four} tick={72} onClose={() => {}} /></div>)
      const tables = shownTables()
      expect(tables).toHaveLength(2)
      for (const table of tables) {
        const heads = within(table).getAllByRole('columnheader').map(head => head.textContent)
        expect(heads).toEqual(expect.arrayContaining(['Town A', 'Town B', 'Town C', 'Town D']))
        let scroller = table
        while (scroller && getComputedStyle(scroller).overflowX !== 'auto') scroller = scroller.parentElement
        expect(scroller, 'an ancestor that scrolls sideways').toBeTruthy()
        // It holds the hidden text inside too (toggle names, track sentences),
        // which would otherwise widen the page past the phone's edge.
        expect(getComputedStyle(scroller).position).toBe('relative')
        // It sits inside the table's own card, not around the page.
        expect(scroller.closest('section.nx-nsec')).toBe(table.closest('section.nx-nsec'))
        expect(scroller.closest('section.nx-nsec')).not.toBeNull()
      }
    } finally {
      style.remove()
    }
  })

  test('many towns at phone width: the lines that span a table stay in its visible box; values get room', () => {
    const four = [
      ...arms,
      { ...arms[0], label: 'Town C', color: TOWN_COLORS[2] },
      { ...arms[1], label: 'Town D', color: TOWN_COLORS[3] },
    ]
    const style = document.createElement('style')
    style.textContent = CSS
    document.head.appendChild(style)
    try {
      // jsdom does no layout, so the guard is the stylesheet: the scroll box is
      // a size container, and the full-width lines stick to its left edge at
      // most its width wide, so they wrap in view while the town columns scroll.
      const rules = [...style.sheet.cssRules]
      const top = rules.filter(rule => rule.selectorText)
      const narrow = rules.filter(rule => rule.media?.mediaText.includes('max-width: 900px')).flatMap(rule => [...rule.cssRules])
      const find = (list, selector) => list.find(rule => rule.selectorText === selector)
      expect(find(top, '.nx .nx-scroll').style.getPropertyValue('container-type')).toBe('inline-size')
      const pinned = rule => {
        expect(rule, 'a pinned rule').toBeTruthy()
        expect(rule.style.getPropertyValue('position')).toBe('sticky')
        expect(rule.style.getPropertyValue('left')).toMatch(/^0(px)?$/)
        expect(rule.style.getPropertyValue('max-width')).toContain('100cqi')
      }
      pinned(find(top, '.nx .nx-rg-sum'))
      pinned(find(narrow, '.nx .nx-glance .nx-sname, .nx .nx-glance .nx-db'))
      // On wider screens the scoreboard keeps a width for every town and
      // scrolls in its card before a value can run into the next column.
      expect(find(top, '.nx .nx-glance').style.getPropertyValue('min-width')).toContain('var(--nx-towns')
      expect(find(top, '.nx .nx-sv').style.getPropertyValue('white-space')).not.toBe('nowrap')

      render(<div className="nx"><NumbersSheet arms={four} tick={72} onClose={() => {}} /></div>)
      const [rulesBox, glanceBox] = document.querySelectorAll('.nx-scroll')
      expect(rulesBox.querySelector('table')).not.toBeNull()
      expect(rulesBox.querySelectorAll('.nx-rg-sum')).toHaveLength(5)
      const rows = [...glanceBox.querySelectorAll('.nx-glance > .nx-srow:not(.is-head)')]
      expect(rows).toHaveLength(8)
      rows.forEach(row => {
        expect(row.querySelector(':scope > .nx-sname')).not.toBeNull()
        expect(row.querySelector(':scope > .nx-db')).not.toBeNull()
      })
    } finally {
      style.remove()
    }
  })

  test('at phone width a glance dot at either end stays in view; pinned names cover what scrolls under them', () => {
    const style = document.createElement('style')
    style.textContent = CSS
    document.head.appendChild(style)
    try {
      const rules = [...style.sheet.cssRules]
      const top = rules.filter(rule => rule.selectorText)
      const narrow = rules.filter(rule => rule.media?.mediaText.includes('max-width: 900px')).flatMap(rule => [...rule.cssRules])
      const find = (list, selector) => list.find(rule => rule.selectorText === selector)
      // A dot is 12px wide and centred on its place, so 0% and 100% need 6px each side.
      const track = find(narrow, '.nx .nx-glance .nx-dbt')
      expect(track, 'an inset track under 900px').toBeTruthy()
      for (const side of ['margin-left', 'margin-right']) expect(parseFloat(track.style.getPropertyValue(side))).toBeGreaterThanOrEqual(6)
      // The pinned name cells are opaque and end in a divider line.
      const names = find(top, '.nx .nx-rules thead th:first-child, .nx .nx-rrow > th, .nx .nx-rhelp > td')
      expect(names.style.getPropertyValue('background')).toBe('var(--nx-panel)')
      expect(names.style.getPropertyValue('box-shadow')).toContain('var(--nx-line)')
      // The glance's name column also covers the 18px gap beside it, with the divider at its edge.
      const glance = find(top, '.nx .nx-glance .nx-sname')
      expect(glance.style.getPropertyValue('background')).toBe('var(--nx-panel)')
      expect(glance.style.getPropertyValue('box-shadow')).toMatch(/17px 0(px)? 0(px)? var\(--nx-panel\), 18px 0(px)? 0(px)? var\(--nx-line\)/)
      // Stacked at phone width the name spans the row, so no divider there.
      expect(find(narrow, '.nx .nx-glance .nx-sname').style.getPropertyValue('box-shadow')).toBe('none')
    } finally {
      style.remove()
    }
  })
})
