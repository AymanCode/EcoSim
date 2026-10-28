import { describe, expect, test, vi } from 'vitest'
import { fireEvent, render, within } from '@testing-library/react'
import RunScreen from '../RunScreen.jsx'
import { fixtureArm, WHOLE_SCREEN_MS } from './fixture.js'

// Drawing geometry is checked in headless Chrome. Keep the real card,
// header, facts and focus controls without rendering thousands of SVG nodes.
vi.mock('../town/Diorama.jsx', () => ({ default: () => null }))
vi.mock('../town/MainStreetCard.jsx', () => ({ default: () => null }))

const COLORS = ['#2E6FE0', '#E0762C', '#199E70', '#9085E9']
const armsFor = count => COLORS.slice(0, count).map((color, i) => fixtureArm({ label: `Town ${'ABCD'[i]}`, color }))
const props = { tick: 20, maxTick: 24, playing: false, onToggle() {}, onScrub() {}, speed: 1, onSpeed() {} }

describe('Run town comparison layout', { timeout: WHOLE_SCREEN_MS }, () => {
  test.each([1, 2, 3, 4])('%i towns keep one shared key beside the comparison', count => {
    const { container } = render(<div className="nx"><RunScreen arms={armsFor(count)} {...props} /></div>)
    const grid = container.querySelector('.lt-towns')
    const legends = container.querySelectorAll('.lt-legend')
    expect(grid).toHaveClass(`is-${count}`)
    expect(grid.querySelectorAll('.lt-card')).toHaveLength(count)
    expect(legends).toHaveLength(1)
    // One and two towns retain their existing order. Longer comparisons
    // expose the key before the cards, including on a stacked phone layout.
    expect(Boolean(grid.compareDocumentPosition(legends[0]) & Node.DOCUMENT_POSITION_PRECEDING)).toBe(count > 2)
    expect(Boolean(grid.compareDocumentPosition(legends[0]) & Node.DOCUMENT_POSITION_FOLLOWING)).toBe(count <= 2)
  })

  test.each([3, 4])('%i towns can still enlarge one drawing and restore every card', count => {
    const { container } = render(<div className="nx"><RunScreen arms={armsFor(count)} {...props} /></div>)
    const grid = container.querySelector('.lt-towns')
    const cards = [...grid.querySelectorAll('.lt-card')]
    const chosen = cards.at(-1)
    const legend = container.querySelector('.lt-legend')

    fireEvent.click(within(chosen).getByRole('button', { name: 'Enlarge' }))
    expect(grid).toHaveClass('is-focus')
    expect([...grid.querySelectorAll('.lt-card')]).toEqual(cards)
    expect([...grid.querySelectorAll('.lt-card:not([hidden])')]).toEqual([chosen])
    expect(chosen.querySelectorAll('.lt-facts > div')).toHaveLength(4)
    expect(container.querySelectorAll('.lt-legend')).toHaveLength(1)
    expect(container.querySelector('.lt-legend')).toBe(legend)

    fireEvent.click(within(chosen).getByRole('button', { name: 'Show all' }))
    expect(grid).not.toHaveClass('is-focus')
    expect([...grid.querySelectorAll('.lt-card:not([hidden])')]).toEqual(cards)
    expect(container.querySelectorAll('.lt-legend')).toHaveLength(1)
    expect(container.querySelector('.lt-legend')).toBe(legend)
    expect(Boolean(grid.compareDocumentPosition(legend) & Node.DOCUMENT_POSITION_PRECEDING)).toBe(true)
  })
})
