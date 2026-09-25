import { describe, expect, test } from 'vitest'
import { render, screen } from '@testing-library/react'
import HowToRead from '../components/HowToRead.jsx'
import { fixtureArm, TOWN_A, TOWN_B } from './fixture.js'

function town(meta, { households, policy } = {}) {
  const arm = fixtureArm(meta)
  if (households) arm.series.householdsTotal = arm.series.householdsTotal.map(() => households)
  if (policy) arm.setup = { ...arm.setup, initial_policy: policy }
  return arm
}

describe('HowToRead', () => {
  test('four first-timer notes for two towns', () => {
    const { container } = render(<HowToRead arms={[town(TOWN_A), town(TOWN_B)]} tick={11} />)
    expect(screen.getByRole('heading', { name: /How to read this/ })).toBeInTheDocument()
    expect(container.querySelectorAll('li')).toHaveLength(4)
    expect(container).toHaveTextContent('Both towns')
    expect(container.querySelector('li b')).toHaveTextContent('tick')
  })

  test('says how many households each house stands for', () => {
    const { container, rerender } = render(<HowToRead arms={[town(TOWN_A, { households: 500 }), town(TOWN_B, { households: 500 })]} tick={11} />)
    expect(container).toHaveTextContent('Every house stands for 5 households.')
    rerender(<HowToRead arms={[town(TOWN_A), town(TOWN_B)]} tick={11} />)
    expect(container).toHaveTextContent('Every house stands for about 1 household.')
  })

  test('amber houses are the share of working-age people looking for work', () => {
    const { container } = render(<HowToRead arms={[town(TOWN_A), town(TOWN_B)]} tick={11} />)
    expect(container).toHaveTextContent('the share of working-age people looking for work')
  })

  test('describes the first town from its own rules', () => {
    const { container, rerender } = render(<HowToRead arms={[town(TOWN_A), town(TOWN_B)]} tick={5} />)
    expect(container).toHaveTextContent('The first town keeps the usual rules.')
    rerender(<HowToRead arms={[town(TOWN_A, { policy: { minimum_wage_policy: 'high' } }), town(TOWN_B)]} tick={5} />)
    expect(container).toHaveTextContent('The first town runs with a higher minimum wage.')
  })

  test('names the rules in force at the week shown, and what the towns test is where they differ', () => {
    // The recording's town hall raised help for people out of work in week 7.
    const { container } = render(<HowToRead arms={[town(TOWN_A), town(TOWN_B)]} tick={11} />)
    expect(container).toHaveTextContent('The first town runs with more help for people out of work.')
    expect(container).toHaveTextContent(
      "The rules each town has in force are named under its title; where they differ from the first town's, that difference is what the towns are testing.",
    )
    expect(container).not.toHaveTextContent('The second changes')
  })

  test('adapted for one town', () => {
    const { container } = render(<HowToRead arms={[town(TOWN_A)]} tick={11} />)
    expect(container.querySelectorAll('li')).toHaveLength(4)
    expect(container).not.toHaveTextContent('Both towns')
  })
})
