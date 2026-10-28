import { beforeAll, describe, expect, test, vi } from 'vitest'
import { fireEvent, render, screen, within } from '@testing-library/react'
import AnswerCard from '../numbers/AnswerCard.jsx'
import { COPY, NUMBER_GROUPS, TOWN_COLORS } from '../catalog.js'
import { demoArms, fixtureArm, TOWN_A, TOWN_B } from './fixture.js'

const ROWS = NUMBER_GROUPS.flatMap(group => group.rows)
const APPROVED_VERDICT = 'Town B is ahead on jobs, pay, savings and businesses, and its people feel better. Food and services cost more there. The gap between rich and poor is the same, but the poorer half holds a little less of the cash in Town B.'
let arms
beforeAll(() => { arms = demoArms() })

function draw(props = {}) {
  return render(<div className="nx"><AnswerCard arms={arms} tick={104} rows={ROWS} {...props} /></div>)
}

const hero = name => screen.getByRole('article', { name })
const visibleValues = node => [...node.querySelectorAll('.nx-answer-reading')].map(value => value.textContent)

describe('AnswerCard', () => {
  test('the approved week-104 verdict stays byte-identical before the heroes and links named terms to their rows', () => {
    const onJump = vi.fn()
    const { container } = draw({ onJump })
    const answer = screen.getByRole('region', { name: COPY.numbers.answer })
    const verdict = container.querySelector('.nx-answer-verdict')
    expect(verdict.textContent).toBe(APPROVED_VERDICT)
    expect(verdict.textContent).not.toMatch(/\d/)
    expect(answer.firstElementChild).toBe(screen.getByRole('heading', { name: COPY.numbers.answer }))
    expect(verdict.nextElementSibling).toHaveClass('nx-answer-heroes')
    expect(within(verdict).getAllByRole('link').map(link => link.textContent)).toEqual([
      'jobs', 'pay', 'savings', 'businesses', 'Food', 'services', 'gap between rich and poor', 'poorer half',
    ])
    fireEvent.click(within(verdict).getByRole('link', { name: 'savings' }))
    expect(onJump).toHaveBeenCalledWith('wealthP50')
  })

  test('each headline value has one visible home, with the approved differences, notes and tally', () => {
    draw()
    expect(visibleValues(hero('Output'))).toEqual(['$22,522', '$35,726'])
    expect(visibleValues(hero('Wellbeing'))).toEqual(['13 of 100', '26 of 100'])
    expect(hero('Output')).toHaveTextContent('Town B sold 59% more.')
    expect(hero('Output')).toHaveTextContent('Prices are higher there too, so part of the gap is prices.')
    expect(hero('Output').querySelector('.nx-answer-tag')).toBeNull()
    expect(hero('Wellbeing')).toHaveTextContent('✓ better')
    expect(hero('Wellbeing')).toHaveTextContent('Town B is 13 points higher.')
    expect(hero('Wellbeing')).toHaveTextContent('Both towns started at 69.')
    const counts = screen.getByRole('group', { name: 'The comparison for Town B' })
    expect([...counts.children].map(chip => chip.textContent)).toEqual([
      '✓ 8 better in Town B', '! 2 worse', '8 different, neither better nor worse', '4 the same',
    ])
  })

  test('each hero has post-warm-up town lines and a historical table equivalent', () => {
    draw()
    for (const name of ['Output', 'Wellbeing']) {
      const card = hero(name)
      expect(card.querySelectorAll('.nx-answer-spark path')).toHaveLength(2)
      expect(card.querySelector('.nx-answer-spark text')).toBeNull()
      const table = within(card).getByRole('table', { name: `${name}, every recorded week` })
      expect(within(table).getAllByRole('columnheader').map(head => head.textContent)).toEqual(['Week', 'Town A', 'Town B'])
      const weeks = within(table).getAllByRole('rowheader')
      expect(weeks[0]).toHaveTextContent('Year 1, week 11')
      expect(weeks.at(-1)).toHaveTextContent('Year 2, week 52')
    }
  })

  test('a coincident comparison line is dashed so the control remains visible', () => {
    draw({ arms: [arms[0], { ...arms[0], label: 'Town B', color: TOWN_COLORS[1] }] })
    for (const name of ['Output', 'Wellbeing']) {
      const [control, comparison] = hero(name).querySelectorAll('.nx-answer-spark path')
      expect(control.getAttribute('d')).toBe(comparison.getAttribute('d'))
      expect(control).not.toHaveAttribute('stroke-dasharray')
      expect(comparison).toHaveAttribute('stroke-dasharray', '3 3')
      expect(control).toHaveAttribute('stroke', TOWN_COLORS[0])
      expect(comparison).toHaveAttribute('stroke', TOWN_COLORS[1])
    }
  })

  test('equal displayed hero readings appear once with every matching town swatch', () => {
    const third = { ...arms[0], label: 'Town C', color: TOWN_COLORS[2] }
    draw({ arms: [arms[0], { ...arms[0], label: 'Town B', color: TOWN_COLORS[1] }, third] })
    for (const [name, reading] of [['Output', '$22,522'], ['Wellbeing', '13 of 100']]) {
      const values = hero(name).querySelector('.nx-answer-values')
      expect(visibleValues(values)).toEqual([reading])
      expect([...values.querySelectorAll('.nx-answer-swatch')].map(swatch => swatch.title)).toEqual(['Town A', 'Town B', 'Town C'])
      expect(values.querySelector('.nx-sr')).toHaveTextContent('Town A · Town B · Town C')
    }
  })

  test('warm-up replaces the verdict, suppresses tags and tallies, and keeps both heroes', () => {
    const { container } = draw({ tick: 5 })
    expect(screen.getByText(COPY.numbers.warmup)).toBeInTheDocument()
    expect(container.querySelector('.nx-answer-verdict')).toBeNull()
    expect(container.querySelector('.nx-answer-tag')).toBeNull()
    expect(container.querySelector('.nx-answer-tally')).toBeNull()
    expect(screen.getAllByRole('article')).toHaveLength(2)
    expect(hero('Output').querySelector('.nx-answer-value')).toBeInTheDocument()
    expect(hero('Wellbeing').querySelector('.nx-answer-value')).toBeInTheDocument()
    expect(container.querySelectorAll('.nx-answer-spark path')).toHaveLength(4)
    expect([...container.querySelectorAll('.nx-answer-spark path')].every(path => !path.getAttribute('d').trim())).toBe(true)
    expect(container.querySelector('.nx-answer-hero-difference')).toBeNull()
    expect(container.querySelector('.nx-answer-hero-note')).toBeNull()
  })

  test('one town keeps two single-value heroes and drops comparison-only content', () => {
    const { container } = draw({ arms: [arms[0]] })
    expect(visibleValues(hero('Output'))).toEqual(['$22,522'])
    expect(visibleValues(hero('Wellbeing'))).toEqual(['13 of 100'])
    expect(container.querySelector('.nx-answer-verdict')).toBeNull()
    expect(container.querySelector('.nx-answer-hero-difference')).toBeNull()
    expect(container.querySelector('.nx-answer-tally')).toBeNull()
    expect(container.querySelectorAll('.nx-answer-spark path')).toHaveLength(2)
  })

  test('a single-town start note appears only when it adds a different displayed reading', () => {
    const town = {
      label: 'Town A', color: TOWN_COLORS[0], ticks: [1, 20, 30],
      series: { happiness: [69.1, 51.2, 69.4], salesExceptRentThisWeek: [100, 120, 130] },
      eventCounts: {}, policyChanges: [],
    }
    const { rerender } = draw({ arms: [town], tick: 1 })
    expect(visibleValues(hero('Wellbeing'))).toEqual(['69 of 100'])
    expect(hero('Wellbeing').querySelector('.nx-answer-hero-note')).toBeNull()
    expect(hero('Output').querySelector('.nx-answer-hero-note')).toBeNull()

    rerender(<div className="nx"><AnswerCard arms={[town]} tick={20} rows={ROWS} /></div>)
    expect(visibleValues(hero('Wellbeing'))).toEqual(['51 of 100'])
    expect(hero('Wellbeing').querySelector('.nx-answer-hero-note')).toHaveTextContent('The town started at 69.')
    expect(hero('Output').querySelector('.nx-answer-hero-note')).toBeNull()

    rerender(<div className="nx"><AnswerCard arms={[town]} tick={30} rows={ROWS} /></div>)
    expect(visibleValues(hero('Wellbeing'))).toEqual(['69 of 100'])
    expect(hero('Wellbeing').querySelector('.nx-answer-hero-note')).toBeNull()
  })

  test.each([2, 3, 4])('%s-town cards omit a repeated common start and retain it after every town moves', townCount => {
    const towns = Array.from({ length: townCount }, (_, index) => ({
      label: `Town ${String.fromCharCode(65 + index)}`, color: TOWN_COLORS[index], ticks: [1, 20],
      series: { happiness: [69.1 + index * 0.1, 50 + index] }, eventCounts: {}, policyChanges: [],
    }))
    const { rerender } = draw({ arms: towns, tick: 1 })
    expect(visibleValues(hero('Wellbeing'))).toEqual(['69 of 100'])
    expect(hero('Wellbeing').querySelector('.nx-answer-hero-note')).toBeNull()

    rerender(<div className="nx"><AnswerCard arms={towns} tick={20} rows={ROWS} /></div>)
    expect(hero('Wellbeing').querySelector('.nx-answer-hero-note')).toHaveTextContent(
      townCount === 2 ? 'Both towns started at 69.' : 'All towns started at 69.',
    )
  })

  test('three towns compare each other town with the first, with a verdict and tally for each', () => {
    const third = { ...arms[0], label: 'Town C', color: TOWN_COLORS[2] }
    const { container } = draw({ arms: [...arms, third] })
    expect(container.querySelectorAll('.nx-answer-verdict')).toHaveLength(2)
    expect(container.querySelectorAll('.nx-answer-value')).toHaveLength(4)
    expect(hero('Output').querySelector('.nx-answer-value-towns').querySelectorAll('.nx-answer-swatch')).toHaveLength(2)
    expect(container.querySelectorAll('.nx-answer-spark path')).toHaveLength(6)
    expect(screen.getByRole('group', { name: 'The comparison for Town B' })).toHaveTextContent('8 better in Town B')
    expect(screen.getByRole('group', { name: 'The comparison for Town C' })).toHaveTextContent('0 better in Town C')
    expect(hero('Output')).toHaveTextContent('Town C sold about the same.')
  })

  test.each([2, 3])('%s price-only towns visibly identify each verdict and keep its food link working', townCount => {
    const towns = [5, 6, 4].slice(0, townCount).map((price, index) => ({
      label: ['Town A', 'Town B', 'Town C'][index], color: TOWN_COLORS[index],
      ticks: [20], series: { priceFood: [price] }, eventCounts: {}, policyChanges: [],
    }))
    const onJump = vi.fn()
    const { container } = draw({ arms: towns, tick: 20, onJump })
    const verdicts = [...container.querySelectorAll('.nx-answer-verdict')]
    expect(verdicts.map(verdict => verdict.textContent)).toEqual([
      'Town B: Food costs more there.',
      ...(townCount === 3 ? ['Town C: Food costs less there.'] : []),
    ])
    verdicts.forEach(verdict => {
      fireEvent.click(within(verdict).getByRole('link', { name: 'Food' }))
      expect(onJump).toHaveBeenLastCalledWith('priceFood')
    })
    expect(onJump).toHaveBeenCalledTimes(townCount - 1)
  })

  test('headlines that were never measured say so and show no misleading differences or tags', () => {
    const { container } = draw({ arms: [fixtureArm(TOWN_A), fixtureArm(TOWN_B)], tick: 20 })
    expect(visibleValues(hero('Output'))).toEqual([COPY.numbers.notMeasured, COPY.numbers.notMeasured])
    expect(visibleValues(hero('Wellbeing'))).toEqual([COPY.numbers.notMeasured, COPY.numbers.notMeasured])
    expect(container.querySelector('.nx-answer-hero-difference')).toBeNull()
    expect(hero('Wellbeing').querySelector('.nx-answer-tag')).toBeNull()
  })

  test('scrubbing updates headline readings and the displayed comparison', () => {
    const { rerender } = draw()
    const before = visibleValues(hero('Output'))
    rerender(<div className="nx"><AnswerCard arms={arms} tick={30} rows={ROWS} /></div>)
    expect(visibleValues(hero('Output'))).not.toEqual(before)
    expect(hero('Output')).not.toHaveTextContent('Town B sold 59% more.')
    const table = within(hero('Output')).getByRole('table')
    expect(within(table).getAllByRole('rowheader').at(-1)).toHaveTextContent('Year 1, week 30')
  })
})
