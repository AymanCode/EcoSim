import { describe, expect, test } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import BusinessList from '../components/BusinessList.jsx'
import { firmDisplayName } from '../names.js'
import { fixtureArm } from './fixture.js'

const names = container => [...container.querySelectorAll('.nx-brow .nx-bname')].map(el => el.textContent)

describe('BusinessList', () => {
  test('ranks open firms richest first with friendly names, up to max', () => {
    const arm = fixtureArm()
    const { container } = render(<BusinessList arm={arm} tick={24} />)
    const richestFirst = [...arm.snapshots[24].firms].sort((a, b) => b.cash - a.cash)
    expect(names(container)).toEqual(richestFirst.slice(0, 7).map(firmDisplayName))
    expect(names(container).some(name => name.startsWith('Baseline') || /Co\d/.test(name))).toBe(false)
  })

  test('shows sector, staff and a status tag', () => {
    const { container } = render(<BusinessList arm={fixtureArm()} tick={24} />)
    const first = container.querySelector('.nx-brow')
    expect(first).toHaveTextContent('Housing')
    expect(first).toHaveTextContent('4 staff')
    expect(first).toHaveTextContent('Steady')
    expect(first.querySelector('.bar b')).toHaveStyle({ width: '100%' })
  })

  test('"See all" toggles every firm', () => {
    const { container } = render(<BusinessList arm={fixtureArm()} tick={24} />)
    expect(container.querySelectorAll('.nx-brow')).toHaveLength(7)
    fireEvent.click(screen.getByRole('button', { name: 'See all 9' }))
    expect(container.querySelectorAll('.nx-brow')).toHaveLength(9)
    expect(screen.getByText('Struggling')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Show fewer' }))
    expect(container.querySelectorAll('.nx-brow')).toHaveLength(7)
  })

  test('lists firms closed in the last year after the open ones, faded and tagged Closed', () => {
    const arm = fixtureArm()
    arm.snapshots[24] = { ...arm.snapshots[24], firmsClosed: [{ id: 50, name: 'FoodCo9', sector: 'Food', closedTick: 20, lastStaff: 3 }] }
    const { container } = render(<BusinessList arm={arm} tick={24} max={20} />)
    const rows = container.querySelectorAll('.nx-brow')
    expect(rows).toHaveLength(10)
    expect(rows[9]).toHaveClass('is-closed')
    expect(rows[9]).toHaveTextContent('Closed')
    expect(rows[9]).toHaveTextContent(firmDisplayName({ id: 50, name: 'FoodCo9', sector: 'Food' }))
  })
})
