import { beforeAll, describe, expect, test } from 'vitest'
import { fireEvent, render, screen, within } from '@testing-library/react'
import RulesInForce from '../numbers/RulesInForce.jsx'
import { TOWN_COLORS } from '../catalog.js'
import { createArm, ingest } from '../data/session.js'
import { demoArms, fixtureArm, TOWN_A, TOWN_B } from './fixture.js'

let arms
beforeAll(() => { arms = demoArms() })

function draw(props = {}) {
  return render(<div className="nx"><RulesInForce arms={arms} tick={72} {...props} /></div>)
}

// The group whose toggle is named `title` ("Show Taxes" / "Hide Taxes"): its
// row group in the table.
const group = title => screen.getByRole('button', { name: new RegExp(`^(Show|Hide) ${title}$`) }).closest('tbody')
const row = name => screen.getByRole('rowheader', { name: new RegExp(`^${name}`) }).closest('tr')

describe('RulesInForce', () => {
  test('a table with the towns as columns, under a heading that names the difference', () => {
    draw()
    expect(screen.getByRole('heading', { name: 'Rules in force' })).toBeInTheDocument()
    expect(screen.getByText(/The towns differ in one rule: the minimum wage\./)).toBeInTheDocument()
    const table = screen.getByRole('table')
    const heads = within(table).getAllByRole('columnheader').map(cell => cell.textContent)
    expect(heads).toEqual(['Rule', 'Town A', 'Town B'])
  })

  test('a group with no differences is collapsed to "Same in both towns"', () => {
    draw()
    const toggle = screen.getByRole('button', { name: 'Show Taxes' })
    expect(toggle).toHaveAttribute('aria-expanded', 'false')
    const taxes = group('Taxes')
    expect(taxes).toHaveTextContent('Same in both towns:')
    expect(taxes).toHaveTextContent('Tax on wages: 15%')
    expect(within(taxes).queryByRole('rowheader', { name: /^Tax on wages/ })).toBeNull()
  })

  test('the minimum wage row shows "high" for Town B, in its colour, with "different from Town A"', () => {
    draw()
    const toggle = screen.getByRole('button', { name: 'Hide Families and work' })
    expect(toggle).toHaveAttribute('aria-expanded', 'true')
    expect(group('Families and work')).toHaveTextContent('1 rule is different')
    const cells = within(row('Minimum wage')).getAllByRole('cell')
    expect(cells[0]).toHaveTextContent(/^normal$/)
    expect(cells[1]).toHaveTextContent('high')
    expect(cells[1]).toHaveTextContent('different from Town A')
    expect(cells[1].style.color).toBe('var(--nx-b-text)')
    expect(cells[0].style.color).toBe('')
    // A row that differs says what the rule does, under its name.
    const help = screen.getByText('Sets the lowest weekly wage a business is allowed to pay.')
    expect(help.closest('tr').previousElementSibling).toBe(row('Minimum wage'))
  })

  test('each value is headed by its rule and its town alone, not by the group line', () => {
    draw()
    const table = screen.getByRole('table')
    expect(within(table).getAllByRole('columnheader').map(cell => cell.textContent)).toEqual(['Rule', 'Town A', 'Town B'])
    // Only the open group's rules head rows; the help sentence is not part of a header.
    expect(within(table).getAllByRole('rowheader').map(cell => cell.textContent))
      .toEqual(['Minimum wage', 'Help for people out of work', 'Grocery benefit', 'Grocery benefit weekly cap', 'Social spending'])
    // The group lines are plain cells, with the group's name as a heading.
    for (const title of ['Taxes', 'Families and work']) {
      expect(group(title).querySelector('th')?.textContent ?? '').not.toContain(title)
      expect(within(group(title)).getByRole('heading', { level: 4, name: title })).toBeInTheDocument()
    }
  })

  test('compares the recorded grocery caps in dollars and does not invent earlier values', () => {
    const towns = [
      createArm({ ...TOWN_A, setup: { payment_sequence: 'income_first' } }),
      createArm({ ...TOWN_B, setup: { payment_sequence: 'income_first' } }),
    ]
    ingest(towns[0], { tick: 1, metrics: { governmentPolicy: { food_credit_policy: 'on', food_credit_weekly_budget: 500 } } })
    ingest(towns[1], { tick: 1, metrics: { governmentPolicy: { food_credit_policy: 'on', food_credit_weekly_budget: 0 } } })
    const { rerender } = draw({ arms: towns, tick: 1 })
    expect(within(row('Grocery benefit$')).getAllByRole('cell').map(cell => cell.textContent)).toEqual(['on', 'on'])
    let cells = within(row('Grocery benefit weekly cap')).getAllByRole('cell')
    expect(cells[0]).toHaveTextContent('$500.00')
    expect(cells[1]).toHaveTextContent('$0.00')
    expect(cells[1]).toHaveTextContent('different from Town A')
    expect(screen.getByText(/Each eligible household can receive up to \$2.50/)).toBeInTheDocument()

    ingest(towns[1], { tick: 2, metrics: { governmentPolicy: { food_credit_policy: 'on', food_credit_weekly_budget: 123.45 } } })
    rerender(<div className="nx"><RulesInForce arms={towns} tick={2} /></div>)
    cells = within(row('Grocery benefit weekly cap')).getAllByRole('cell')
    expect(cells[1]).toHaveTextContent('$123.45')
    ingest(towns[1], { tick: 3, metrics: { governmentPolicy: { food_credit_policy: 'off', food_credit_weekly_budget: 123.45 } } })
    rerender(<div className="nx"><RulesInForce arms={towns} tick={3} /></div>)
    expect(within(row('Grocery benefit$')).getAllByRole('cell')[1]).toHaveTextContent('off')
    rerender(<div className="nx"><RulesInForce arms={towns} tick={0} /></div>)
    fireEvent.click(screen.getByRole('button', { name: 'Show Families and work' }))
    expect(within(row('Grocery benefit weekly cap')).getAllByRole('cell').map(cell => cell.textContent)).toEqual(['not recorded', 'not recorded'])
  })

  test('a town with an older frame has an unrecorded cap beside a recorded value', () => {
    const towns = [createArm(TOWN_A), createArm(TOWN_B)]
    ingest(towns[0], { tick: 1, metrics: { governmentPolicy: { food_credit_weekly_budget: 20.5 } } })
    ingest(towns[1], { tick: 1, metrics: { governmentPolicy: {} } })
    draw({ arms: towns, tick: 1 })
    const cells = within(row('Grocery benefit weekly cap')).getAllByRole('cell')
    expect(cells[0]).toHaveTextContent('$20.50')
    expect(cells[1]).toHaveTextContent('not recorded')
    expect(cells[1]).not.toHaveTextContent('different from Town A')
    expect(screen.getAllByText(/Some settings were not recorded in every town/).length).toBeGreaterThan(0)
    expect(screen.queryByText(/Both towns run the same rules/)).toBeNull()
  })

  test('"Show" expands a collapsed group and "Hide" folds it again', () => {
    draw()
    fireEvent.click(screen.getByRole('button', { name: 'Show Taxes' }))
    const toggle = screen.getByRole('button', { name: 'Hide Taxes' })
    expect(toggle).toHaveAttribute('aria-expanded', 'true')
    expect(document.getElementById(toggle.getAttribute('aria-controls'))).toBe(group('Taxes'))
    const cells = within(row('Tax on wages')).getAllByRole('cell')
    expect(cells.map(cell => cell.textContent)).toEqual(['15%', '15%'])
    fireEvent.click(toggle)
    expect(screen.getByRole('button', { name: 'Show Taxes' })).toHaveAttribute('aria-expanded', 'false')
    expect(screen.queryByRole('rowheader', { name: /^Tax on wages/ })).toBeNull()
  })

  test('a change during the run shows in that town\'s column once its week is reached', () => {
    const changed = [arms[0], { ...arms[1], policyChanges: [{ id: 'c1', tick: 30, policy: 'benefit_level', value: 'high' }] }]
    const { rerender } = draw({ arms: changed, tick: 40 })
    expect(screen.getByText(/The towns differ in two rules: the minimum wage and help for people out of work\./)).toBeInTheDocument()
    const cells = within(row('Help for people out of work')).getAllByRole('cell')
    expect(cells[0]).toHaveTextContent(/^normal$/)
    expect(cells[1]).toHaveTextContent('high')
    expect(cells[1]).toHaveTextContent('changed in Year 1, week 30 (was normal)')
    rerender(<div className="nx"><RulesInForce arms={changed} tick={20} /></div>)
    expect(within(row('Help for people out of work')).getAllByRole('cell').map(cell => cell.textContent)).toEqual(['normal', 'normal'])
    expect(screen.queryByText(/changed in/)).toBeNull()
  })

  test('a change made while the towns were being set up says so, and opens its group', () => {
    render(<div className="nx"><RulesInForce arms={[fixtureArm(TOWN_A), fixtureArm(TOWN_B)]} tick={24} /></div>)
    expect(screen.getByRole('button', { name: 'Hide Families and work' })).toHaveAttribute('aria-expanded', 'true')
    const cells = within(row('Help for people out of work')).getAllByRole('cell')
    cells.forEach(cell => {
      expect(cell).toHaveTextContent('high')
      expect(cell).toHaveTextContent('changed in Year 1, week 7, while the towns were being set up (was normal)')
    })
    expect(screen.getByText(/Both towns run the same rules\./)).toBeInTheDocument()
  })

  test('three or more towns: "Same in every town"; one town: the rules alone', () => {
    const three = [...arms, { ...arms[0], label: 'Town C', color: TOWN_COLORS[2] }]
    const { unmount } = draw({ arms: three })
    expect(group('Taxes')).toHaveTextContent('Same in every town:')
    unmount()
    draw({ arms: [arms[0]] })
    expect(screen.getByText("The town hall's rules this week.")).toBeInTheDocument()
    expect(group('Taxes')).toHaveTextContent('Tax on wages: 15%')
    expect(group('Taxes')).not.toHaveTextContent('Same in')
  })

  test('a note under a town\'s column head, such as a lost connection', () => {
    draw({ notes: [null, 'lost its connection in Year 1, week 40'] })
    const heads = within(screen.getByRole('table')).getAllByRole('columnheader')
    expect(heads[2]).toHaveTextContent('Town B')
    expect(heads[2]).toHaveTextContent('lost its connection in Year 1, week 40')
  })
})
