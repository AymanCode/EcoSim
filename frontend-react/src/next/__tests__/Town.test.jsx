import { describe, expect, test } from 'vitest'
import { render } from '@testing-library/react'
import Town from '../components/Town.jsx'
import { fixtureArm } from './fixture.js'

const housesIn = (container, state) => new Set(
  [...container.querySelectorAll('.nx-house')]
    .map((house, index) => (house.classList.contains(state) ? index : -1))
    .filter(index => index >= 0),
)

function withManyFirms(arm) {
  const snap = arm.snapshots[24]
  const extra = Array.from({ length: 12 }, (_, i) => ({
    id: 100 + i, name: `FoodProduct${100 + i}`, sector: 'Food', cash: 500, staff: 2,
    price: 5, lastRevenue: 0, lastProfit: 0, state: 'steady', isBaseline: false,
  }))
  arm.snapshots[24] = {
    ...snap,
    firms: [...snap.firms, ...extra],
    firmsClosed: [{ id: 50, name: 'FoodCo9', sector: 'Food', closedTick: 20, lastStaff: 3 }],
  }
  return arm
}

describe('Town', () => {
  test('draws 100 houses and the legend', () => {
    const { container } = render(<Town arm={fixtureArm()} tick={11} />)
    expect(container.querySelectorAll('.nx-house')).toHaveLength(100)
    const legend = container.querySelector('.nx-legend')
    expect(legend).toHaveTextContent('working')
    expect(legend).toHaveTextContent('looking for work')
    expect(legend).toHaveTextContent('lost their home')
  })

  test('colours houses from people out of work and homes lost', () => {
    const { container } = render(<Town arm={fixtureArm()} tick={11} />)
    // Week 11: 41.67 in 100 out of work, nobody homeless.
    expect(housesIn(container, 'is-look').size).toBe(42)
    expect(housesIn(container, 'is-work').size).toBe(58)
    expect(housesIn(container, 'is-home').size).toBe(0)
  })

  test('keeps houses in place so only a few change colour', () => {
    const arm = fixtureArm()
    const { container, rerender } = render(<Town arm={arm} tick={12} />)
    const before = housesIn(container, 'is-look')
    rerender(<Town arm={arm} tick={13} />)
    const after = housesIn(container, 'is-look')
    expect(before.size).toBe(18)
    expect(after.size).toBe(27)
    for (const index of before) expect(after.has(index)).toBe(true)
  })

  test('puts open firms on Main street with a flag on the struggling one', () => {
    const { container } = render(<Town arm={fixtureArm()} tick={24} />)
    expect(container.querySelectorAll('.nx-bldg')).toHaveLength(9)
    expect(container.querySelectorAll('.nx-bldg.is-struggling')).toHaveLength(1)
    expect(container.querySelector('.nx-bldg-more')).toBeNull()
  })

  test('draws at most 16 buildings, closed lots last, then a "+N more" label', () => {
    const { container } = render(<Town arm={withManyFirms(fixtureArm())} tick={24} />)
    const buildings = container.querySelectorAll('.nx-bldg')
    const more = container.querySelectorAll('.nx-bldg-more')
    expect(buildings.length + more.length).toBeLessThanOrEqual(17)
    expect(buildings).toHaveLength(16)
    expect(more[0]).toHaveTextContent('+6 more')
  })

  test('shows a closed firm as a crossed-out lot', () => {
    const arm = fixtureArm()
    arm.snapshots[24] = { ...arm.snapshots[24], firmsClosed: [{ id: 50, name: 'FoodCo9', sector: 'Food', closedTick: 20, lastStaff: 3 }] }
    const { container } = render(<Town arm={arm} tick={24} />)
    const buildings = container.querySelectorAll('.nx-bldg')
    expect(buildings).toHaveLength(10)
    expect(buildings[9]).toHaveClass('is-closed')
  })

  test('has three facts and a text alternative for the drawing', () => {
    const { container, getByText } = render(<Town arm={fixtureArm()} tick={11} />)
    expect(getByText('42 in 100')).toBeInTheDocument()
    expect(getByText('$36')).toBeInTheDocument()
    expect(getByText('9 firms')).toBeInTheDocument()
    expect(getByText('0 struggling, 0 closed')).toBeInTheDocument()
    expect(container.querySelector('svg')).toHaveAttribute('aria-hidden', 'true')
    const alt = container.querySelector('.nx-sr')
    expect(alt).toHaveTextContent('Out of every 100 households: 58 working, 42 looking for work, 0 lost their home.')
    expect(alt).toHaveTextContent('9 firms open: 0 struggling. 0 closed in the last year.')
  })
})
