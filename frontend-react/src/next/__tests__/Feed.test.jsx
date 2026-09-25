import { describe, expect, test } from 'vitest'
import { render, screen } from '@testing-library/react'
import Feed from '../components/Feed.jsx'
import { fixtureArm, TOWN_A, TOWN_B } from './fixture.js'

describe('Feed', () => {
  test('lists events newest first across towns, up to the limit', () => {
    const { container } = render(<Feed arms={[fixtureArm(TOWN_A), fixtureArm(TOWN_B)]} tick={11} />)
    const rows = [...container.querySelectorAll('.nx-feed li')]
    expect(rows).toHaveLength(8)
    const ticks = rows.map(row => Number(row.dataset.tick))
    expect(ticks).toEqual([...ticks].sort((x, y) => y - x))
    expect(ticks[0]).toBe(11)
    expect(rows[0]).toHaveTextContent('Year 1, week 11')
    expect(rows.some(row => row.textContent.includes('Town A'))).toBe(true)
    expect(rows.some(row => row.textContent.includes('Town B'))).toBe(true)
  })

  test('says so when nothing has happened yet', () => {
    render(<Feed arms={[fixtureArm()]} tick={0} />)
    expect(screen.getByText('Nothing has happened yet.')).toBeInTheDocument()
  })
})
