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
    const follow = screen.getAllByRole('button', { name: /^Follow / })[2]
    const name = follow.getAttribute('aria-label')
    expect(follow).toHaveAttribute('aria-pressed', 'false')
    fireEvent.click(follow)
    expect(cardNames(container)[0]).toBe(third)
    // The label stays put; the pressed state carries the change.
    const pinned = screen.getByRole('button', { name })
    expect(pinned).toHaveAttribute('aria-pressed', 'true')
    expect(pinned).toHaveTextContent(/^Follow$/)
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

describe('HouseholdCards evictions', () => {
  function withEviction(housingSecurity) {
    const arm = fixtureArm()
    const subject = arm.snapshots[24].subjects[0]
    arm.snapshots[24] = {
      ...arm.snapshots[24],
      subjects: [{ ...subject, housingSecurity }, ...arm.snapshots[24].subjects.slice(1)],
    }
    arm.events = [...arm.events, { id: 'evict', tick: 24, type: 'regime', text: 'eviction', householdId: subject.id, firmId: null, firmName: null, sector: null, value: null }]
    return { arm, subject }
  }

  test('a household that still has a home "had to move"', () => {
    const { arm, subject } = withEviction(true)
    const { container } = render(<HouseholdCards arm={arm} tick={24} />)
    const card = container.querySelector('.nx-hc')
    expect(card.querySelector('.ev')).toHaveTextContent(`${householdName(subject.id)} had to move after falling behind on rent.`)
    expect(card).not.toHaveTextContent('lost their home')
  })

  test('a household with no home now "lost their home"', () => {
    const { arm, subject } = withEviction(false)
    const { container } = render(<HouseholdCards arm={arm} tick={24} />)
    expect(container.querySelector('.nx-hc .ev')).toHaveTextContent(`${householdName(subject.id)} lost their home.`)
  })
})
