import { describe, expect, test } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import HouseholdCards from '../components/HouseholdCards.jsx'
import { householdName } from '../names.js'
import { fixtureArm } from './fixture.js'

const cardNames = container => [...container.querySelectorAll('.nx-hc .nx-hname')].map(el => el.textContent)

describe('HouseholdCards', () => {
  test('shows four tracked households at a time', () => {
    const arm = fixtureArm()
    const { container } = render(<HouseholdCards arm={arm} tick={24} />)
    const subjects = arm.snapshots[24].subjects
    expect(container.querySelectorAll('.nx-hc')).toHaveLength(4)
    expect(cardNames(container)[0]).toBe(`${householdName(subjects[0].id)}, ${subjects[0].age}`)
  })

  test('"Show me four others" moves on through the sample', () => {
    const arm = fixtureArm()
    const { container } = render(<HouseholdCards arm={arm} tick={24} />)
    const before = cardNames(container)[0]
    fireEvent.click(screen.getByRole('button', { name: 'Show me four others' }))
    const after = cardNames(container)[0]
    expect(after).not.toBe(before)
    const fifth = arm.snapshots[24].subjects[4]
    expect(after).toBe(`${householdName(fifth.id)}, ${fifth.age}`)
  })

  test('"Follow" pins a card to the first slot', () => {
    const arm = fixtureArm()
    const { container } = render(<HouseholdCards arm={arm} tick={24} />)
    const third = cardNames(container)[2]
    const follow = screen.getAllByRole('button', { name: /^Follow/ })[2]
    fireEvent.click(follow)
    expect(cardNames(container)[0]).toBe(third)
    expect(screen.getByRole('button', { name: /^Following/ })).toHaveAttribute('aria-pressed', 'true')
    fireEvent.click(screen.getByRole('button', { name: 'Show me four others' }))
    expect(cardNames(container)[0]).toBe(third)
    expect(container.querySelectorAll('.nx-hc')).toHaveLength(4)
  })

  test('each card has a job line, savings, a status chip and a sentence', () => {
    const arm = fixtureArm()
    const { container } = render(<HouseholdCards arm={arm} tick={24} />)
    const card = container.querySelector('.nx-hc')
    expect(card.querySelector('.j').textContent.length).toBeGreaterThan(3)
    expect(card).toHaveTextContent('saved')
    expect(card.querySelector('.nx-chip')).toBeTruthy()
    expect(card.querySelector('.ev').textContent).toMatch(/\.\s|\.$/)
  })
})
