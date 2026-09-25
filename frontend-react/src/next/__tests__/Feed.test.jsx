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

  test('collapses repeats of one kind within a week into a counted line', () => {
    const arm = fixtureArm(TOWN_A)
    const inWeek8 = arm.events.filter(event => event.tick === 8)
    const hiring = inWeek8.filter(event => event.type === 'regime' && event.text === 'failed_hiring')
    expect(hiring).toHaveLength(3)

    const { container } = render(<Feed arms={[arm]} tick={8} limit={50} />)
    const rows = [...container.querySelectorAll('.nx-feed li')].filter(row => row.dataset.tick === '8')
    const counted = rows.filter(row => row.textContent.includes("3 businesses couldn't fill their open jobs."))
    expect(counted).toHaveLength(1)
    expect(rows.some(row => row.textContent.includes("couldn't fill its open jobs."))).toBe(false)
    const kinds = new Set(inWeek8.map(event => `${event.type}|${event.text}`))
    expect(rows).toHaveLength(kinds.size)
  })

  test('the limit counts lines, not events', () => {
    const arm = fixtureArm(TOWN_A)
    const { container } = render(<Feed arms={[arm]} tick={24} limit={30} />)
    const rows = [...container.querySelectorAll('.nx-feed li')]
    expect(rows.length).toBeLessThan(arm.events.length)
    const lines = rows.map(row => `${row.dataset.tick}|${row.querySelector('div').lastChild.textContent}`)
    expect(new Set(lines).size).toBe(lines.length)
  })

  test('says so when nothing has happened yet', () => {
    render(<Feed arms={[fixtureArm()]} tick={0} />)
    expect(screen.getByText('Nothing has happened yet.')).toBeInTheDocument()
  })
})
