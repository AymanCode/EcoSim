import { describe, expect, test } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import RunScreen from '../RunScreen.jsx'
import { leadSentence, verdict } from '../narration.js'
import { fixtureArm, TOWN_A, TOWN_B } from './fixture.js'

function townB() {
  const b = fixtureArm(TOWN_B)
  b.series.peopleOutOfWorkPer100 = b.series.peopleOutOfWorkPer100.map(v => v + 3)
  b.setup = { ...b.setup, initial_policy: { minimum_wage_policy: 'high' } }
  return b
}

const weekShown = container => container.querySelector('.nx-clock .nx-week').textContent

describe('RunScreen', () => {
  test('two towns: two matching columns, the lead sentence and the verdict', () => {
    const arms = [fixtureArm(TOWN_A), townB()]
    const { container } = render(<div className="nx"><RunScreen arms={arms} /></div>)
    const columns = container.querySelectorAll('.nx-col')
    expect(columns).toHaveLength(2)
    expect(columns[0]).toHaveTextContent('Town A')
    expect(columns[0]).toHaveTextContent('no changes')
    expect(columns[1]).toHaveTextContent('Town B')
    expect(columns[1]).toHaveTextContent('a higher minimum wage')
    columns.forEach(column => {
      expect(column.querySelector('.nx-townc')).toBeInTheDocument()
      expect(column.querySelector('.nx-biz')).toBeInTheDocument()
      expect(column.querySelector('.nx-hh')).toBeInTheDocument()
    })
    expect(container.querySelector('.nx-lead')).toHaveTextContent(leadSentence(arms, 1))
    const shown = container.querySelector('.nx-verdict').textContent
    expect(shown).toBe(verdict(arms, 1))
    expect(shown.endsWith('?')).toBe(true)
    expect(container.querySelectorAll('.nx-stats .nx-stat')).toHaveLength(4)
    expect(container.querySelectorAll('path.nx-line')).toHaveLength(2)
    expect(screen.getByRole('heading', { name: "What's happening newest first" })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'How to read this for first-timers' })).toBeInTheDocument()
  })

  test('scrubbing the timeline moves every panel to that week', () => {
    const arms = [fixtureArm(TOWN_A), townB()]
    const { container } = render(<div className="nx"><RunScreen arms={arms} /></div>)
    expect(weekShown(container)).toBe('Year 1, week 1')
    fireEvent.change(screen.getByRole('slider', { name: 'Week of the run' }), { target: { value: '20' } })
    expect(weekShown(container)).toBe('Year 1, week 20')
    expect(container.querySelector('.nx-lead')).toHaveTextContent(leadSentence(arms, 20))
    expect(container.querySelector('.nx-verdict').textContent).toBe(verdict(arms, 20))
  })

  test('the chart follows the metric chips', () => {
    render(<div className="nx"><RunScreen arms={[fixtureArm(TOWN_A), townB()]} /></div>)
    fireEvent.click(screen.getByRole('button', { name: 'Typical weekly pay' }))
    expect(screen.getByRole('button', { name: 'Typical weekly pay' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('heading', { level: 3, name: 'Typical weekly pay' })).toBeInTheDocument()
  })

  test('one town: one column and a summary instead of a question', () => {
    const arms = [fixtureArm(TOWN_A)]
    const { container } = render(<div className="nx"><RunScreen arms={arms} /></div>)
    expect(container.querySelectorAll('.nx-col')).toHaveLength(1)
    expect(container.querySelector('.nx-cols')).toHaveClass('is-single')
    fireEvent.change(screen.getByRole('slider', { name: 'Week of the run' }), { target: { value: '12' } })
    const shown = container.querySelector('.nx-verdict').textContent
    expect(shown).toBe(verdict(arms, 12))
    expect(shown).not.toContain('?')
    expect(container.querySelectorAll('path.nx-line')).toHaveLength(1)
  })
})
