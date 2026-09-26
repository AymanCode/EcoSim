import { beforeAll, describe, expect, test } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import AtAGlance from '../numbers/AtAGlance.jsx'
import { GLANCE_KEYS, METRICS, formatEndLabel, formatMetric } from '../catalog.js'
import { rangeSoFar, valueAt } from '../data/derive.js'
import { differencePhrase } from '../narration.js'
import { demoArms, fixtureArm, TOWN_A, TOWN_B } from './fixture.js'

const OUT = 'peopleOutOfWorkPer100'

let arms
beforeAll(() => { arms = demoArms() })

function draw(props = {}) {
  return render(<div className="nx"><AtAGlance arms={arms} tick={72} {...props} /></div>)
}

const rowOf = key => screen.getByRole('rowheader', { name: new RegExp(`^${METRICS[key].name}`) }).closest('[role="row"]')

describe('AtAGlance', () => {
  test('eight rows, one per headline number, with its name and meaning', () => {
    draw()
    expect(screen.getByRole('heading', { name: 'This week at a glance' })).toBeInTheDocument()
    expect(screen.getByText(/^Eight headline numbers for Year 2, week 20\. Town B's differences are counted from Town A, the town with no changes\.$/)).toBeInTheDocument()
    const table = screen.getByRole('table', { name: 'This week at a glance' })
    const names = within(table).getAllByRole('rowheader')
    expect(names).toHaveLength(8)
    GLANCE_KEYS.forEach((key, i) => {
      expect(names[i]).toHaveTextContent(METRICS[key].name)
      expect(names[i]).toHaveTextContent(METRICS[key].meaning)
    })
    const heads = within(table).getAllByRole('columnheader').map(cell => cell.textContent)
    expect(heads.slice(1)).toEqual(['Town A', 'Town B', 'Where this week sits, from the lowest to the highest either town has seen'])
  })

  test('each town\'s value; under Town B, a neutral difference from Town A', () => {
    draw()
    const cells = within(rowOf(OUT)).getAllByRole('cell')
    const [a, b] = arms.map(arm => valueAt(arm, OUT, 72))
    expect(cells[0]).toHaveTextContent(formatMetric(OUT, a))
    expect(cells[1]).toHaveTextContent(formatMetric(OUT, b))
    const phrase = differencePhrase(OUT, b, a, { tick: 72, baseLabel: 'Town A' })
    expect(phrase).toMatch(/^(\d+ (fewer|more) in 100 than Town A|about the same as Town A)$/)
    const diff = cells[1].querySelector('.nx-diff')
    expect(diff).toHaveTextContent(phrase)
    // Neutral: no colour of its own, and nothing under the first town.
    expect(diff.getAttribute('style')).toBeNull()
    expect(diff.className).toBe('nx-diff')
    expect(cells[0].querySelector('.nx-diff')).toBeNull()
  })

  test('town hall cash in debt reads "owes" and compares as a debt', () => {
    draw()
    const cells = within(rowOf('townHallCash')).getAllByRole('cell')
    const [a, b] = arms.map(arm => valueAt(arm, 'townHallCash', 72))
    expect(cells[1]).toHaveTextContent(formatMetric('townHallCash', b))
    expect(cells[1]).toHaveTextContent(differencePhrase('townHallCash', b, a, { tick: 72, baseLabel: 'Town A' }))
  })

  test('a dot track with one dot per town, placed within the range seen so far', () => {
    draw()
    const track = rowOf(OUT).querySelector('.nx-dbt')
    const dots = [...track.querySelectorAll('.nx-dot')]
    expect(dots).toHaveLength(2)
    expect(dots.map(dot => dot.style.background)).toEqual(['rgb(46, 111, 224)', 'rgb(224, 118, 44)'])
    const range = rangeSoFar(arms, OUT, 72)
    arms.forEach((arm, i) => {
      const expected = ((valueAt(arm, OUT, 72) - range.min) / (range.max - range.min)) * 100
      expect(parseFloat(dots[i].style.left)).toBeCloseTo(expected, 1)
    })
    const ends = rowOf(OUT).querySelector('.nx-dbe').textContent
    expect(ends).toContain(formatEndLabel(OUT, range.min))
    expect(ends).toContain(formatEndLabel(OUT, range.max))
    // Its text alternative names the same range.
    expect(within(rowOf(OUT)).getByText(new RegExp(`lowest so far is ${formatEndLabel(OUT, range.min)}`))).toHaveClass('nx-sr')
  })

  test('the gap between rich and poor says when it was last counted', () => {
    draw()
    expect(rowOf('gini')).toHaveTextContent('Counted every 5 weeks; last count Year 2, week 18.')
  })

  test('in the setting-up weeks there is no difference and no track yet', () => {
    draw({ tick: 5 })
    const row = rowOf(OUT)
    expect(within(row).getAllByRole('cell')[1]).toHaveTextContent('still being set up')
    expect(row.querySelector('.nx-dot')).toBeNull()
    expect(row).toHaveTextContent('Shown once the towns are set up.')
  })

  test('a number this recording never carried says "Not measured in this run", never a zero', () => {
    render(<div className="nx"><AtAGlance arms={[fixtureArm(TOWN_A), fixtureArm(TOWN_B)]} tick={20} /></div>)
    for (const key of ['happiness', 'salesExceptRentThisWeek']) {
      const row = rowOf(key)
      expect(row).toHaveTextContent('Not measured in this run')
      expect(row.querySelector('.nx-dot')).toBeNull()
      expect(row.querySelector('.nx-diff')).toBeNull()
      expect(row.textContent).not.toMatch(/\b0 of 100|\$0\b/)
    }
  })

  test('a note under a town\'s column head, such as a lost connection', () => {
    draw({ notes: [null, 'lost its connection in Year 1, week 40'] })
    const heads = within(screen.getByRole('table')).getAllByRole('columnheader')
    expect(heads[2]).toHaveTextContent('lost its connection in Year 1, week 40')
  })
})
