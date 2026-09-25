import { useState } from 'react'
import { describe, expect, test, vi } from 'vitest'
import { fireEvent, render, screen, within } from '@testing-library/react'
import LeverEditor from '../components/LeverEditor.jsx'
import { COPY, DEFAULT_POLICY, LEVER_GROUPS, LEVERS } from '../catalog.js'

// Rules under which every lever control shows: bailouts for one sector.
const SECTOR_BAILOUTS = { ...DEFAULT_POLICY, bailout_policy: 'sector', bailout_target: 'food', bailout_budget: 5000 }
const ANY_BAILOUTS = { ...DEFAULT_POLICY, bailout_policy: 'all', bailout_budget: 5000 }

function editor(props = {}) {
  const onChange = vi.fn()
  const view = render(<LeverEditor value={DEFAULT_POLICY} base={DEFAULT_POLICY} onChange={onChange} idPrefix="town-b" {...props} />)
  return { ...view, onChange }
}

// The editor as Set up and the Town hall hold it: every change becomes the new value.
function Held({ initial, onChange }) {
  const [value, setValue] = useState(initial)
  return <LeverEditor value={value} base={DEFAULT_POLICY} idPrefix="town-b" onChange={next => { onChange(next); setValue(next) }} />
}

function held(initial) {
  const onChange = vi.fn()
  const view = render(<Held initial={initial} onChange={onChange} />)
  return { ...view, onChange, last: () => onChange.mock.calls.at(-1)[0] }
}

const choose = (name, option) => fireEvent.click(within(screen.getByRole('group', { name })).getByRole('button', { name: option }))
const row = (container, lever) => container.querySelector(`[data-lever="${lever}"]`)

describe('LeverEditor', () => {
  test('all 17 levers render inside 5 fieldsets, in the catalog groups', () => {
    const { container } = editor({ value: SECTOR_BAILOUTS })
    const fieldsets = [...container.querySelectorAll('fieldset')]
    expect(fieldsets).toHaveLength(5)
    LEVER_GROUPS.forEach((group, i) => {
      expect(fieldsets[i].querySelector('legend')).toHaveTextContent(COPY.levers.groups[group.id].title)
      expect([...fieldsets[i].querySelectorAll('[data-lever]')].map(row => row.dataset.lever)).toEqual(group.levers)
    })
    for (const spec of Object.values(LEVERS)) expect(screen.getByText(spec.help)).toBeInTheDocument()
    expect(screen.getAllByRole('slider')).toHaveLength(3)
    // Every lever has five options or fewer, so each enum is a segmented group.
    expect(container.querySelectorAll('select')).toHaveLength(0)
    expect(container.querySelectorAll('[data-lever] [role="group"]')).toHaveLength(14)
  })

  test('a tax rate is a labelled slider shown as a percentage', () => {
    editor()
    const slider = screen.getByRole('slider', { name: 'The tax on wages' })
    expect(slider).toHaveAttribute('min', '0')
    expect(slider).toHaveAttribute('max', '0.5')
    expect(slider).toHaveAttribute('step', '0.01')
    expect(slider).toHaveValue('0.15')
    expect(slider).toHaveAttribute('aria-valuetext', '15%')
    expect(slider).toHaveAccessibleDescription(LEVERS.wage_tax_rate.help)
    expect(screen.getByRole('slider', { name: 'The tax on investment' })).toHaveAttribute('max', '0.3')
  })

  test('moving the wage tax slider sends the full vector with only that lever changed', () => {
    const { onChange } = editor()
    fireEvent.change(screen.getByRole('slider', { name: 'The tax on wages' }), { target: { value: '0.2' } })
    expect(onChange).toHaveBeenCalledTimes(1)
    expect(onChange).toHaveBeenCalledWith({ ...DEFAULT_POLICY, wage_tax_rate: 0.2 })
  })

  test('pressing "high" on the minimum wage sends it', () => {
    const { onChange } = editor()
    const group = screen.getByRole('group', { name: 'The minimum wage' })
    expect(within(group).getAllByRole('button').map(button => button.textContent)).toEqual(['low', 'normal', 'high'])
    expect(within(group).getByRole('button', { name: 'normal' })).toHaveAttribute('aria-pressed', 'true')
    expect(within(group).getByRole('button', { name: 'high' })).toHaveAttribute('aria-pressed', 'false')
    fireEvent.click(within(group).getByRole('button', { name: 'high' }))
    expect(onChange).toHaveBeenCalledWith({ ...DEFAULT_POLICY, minimum_wage_policy: 'high' })
  })

  test('numeric levers stay numbers', () => {
    const { onChange, rerender } = editor({ value: ANY_BAILOUTS, base: ANY_BAILOUTS })
    fireEvent.click(within(screen.getByRole('group', { name: 'The business subsidy' })).getByRole('button', { name: '25%' }))
    expect(onChange.mock.calls[0][0].sector_subsidy_level).toBe(25)
    fireEvent.click(within(screen.getByRole('group', { name: 'The bailout budget' })).getByRole('button', { name: '$10,000' }))
    expect(onChange.mock.calls[1][0].bailout_budget).toBe(10000)

    // Text that holds a number comes back as a number, and a partial vector comes back whole.
    rerender(<LeverEditor value={{ sector_subsidy_level: '10', sector_subsidy_target: 'food' }} base={DEFAULT_POLICY} onChange={onChange} idPrefix="town-b" />)
    expect(within(screen.getByRole('group', { name: /^The business subsidy/ })).getByRole('button', { name: '10%' }))
      .toHaveAttribute('aria-pressed', 'true')
    fireEvent.click(within(screen.getByRole('group', { name: 'The minimum wage' })).getByRole('button', { name: 'high' }))
    const sent = onChange.mock.calls[2][0]
    expect(Object.keys(sent).sort()).toEqual(Object.keys(DEFAULT_POLICY).sort())
    expect(sent).toEqual({ ...DEFAULT_POLICY, sector_subsidy_level: 10, sector_subsidy_target: 'food', minimum_wage_policy: 'high' })
  })

  test('a broken group rule shows a polite status line under its group, not an alert', () => {
    const { container } = editor({ value: { ...DEFAULT_POLICY, sector_subsidy_level: 10 } })
    const line = screen.getByText(COPY.levers.rules.sector_subsidy)
    expect(line).toHaveAttribute('role', 'status')
    expect(screen.queryByRole('alert')).toBeNull()
    const business = container.querySelectorAll('fieldset')[LEVER_GROUPS.findIndex(group => group.id === 'business')]
    expect(business).toContainElement(line)
  })

  test('no rule line when the rules fit together', () => {
    const { container } = editor()
    expect(container.querySelector('.nx-lproblem')).toBeNull()
  })

  test('a lever that differs from the base is marked as changed', () => {
    const { container } = editor({ value: { ...DEFAULT_POLICY, minimum_wage_policy: 'high' } })
    expect(screen.getAllByText('(changed)')).toHaveLength(1)
    expect(screen.getByRole('group', { name: 'The minimum wage (changed)' })).toBeInTheDocument()
    expect(container.querySelector('[data-lever="minimum_wage_policy"] .nx-ldot')).not.toBeNull()
    expect(container.querySelectorAll('.nx-ldot')).toHaveLength(1)
  })

  test('two editors on one page keep their ids apart', () => {
    const { container } = render(
      <>
        <LeverEditor value={DEFAULT_POLICY} base={DEFAULT_POLICY} onChange={() => {}} idPrefix="town-a" />
        <LeverEditor value={DEFAULT_POLICY} base={DEFAULT_POLICY} onChange={() => {}} idPrefix="town-b" />
      </>,
    )
    const ids = [...container.querySelectorAll('[id]')].map(node => node.id)
    expect(new Set(ids).size).toBe(ids.length)
  })
})

// The bailout rule of policyRules.js: off lends nothing, one sector names its
// sector, any business names none, and both need a budget.
describe('LeverEditor bailouts', () => {
  test('with bailouts off, only the bailout choice shows', () => {
    const { container } = editor()
    expect(row(container, 'bailout_policy')).not.toBeNull()
    expect(row(container, 'bailout_target')).toBeNull()
    expect(row(container, 'bailout_budget')).toBeNull()
  })

  test('choosing any business clears the sector and hides it, and keeps the budget', () => {
    const { container, last } = held(SECTOR_BAILOUTS)
    choose(/^Bailouts/, 'any business')
    expect(last()).toEqual({ ...SECTOR_BAILOUTS, bailout_policy: 'all', bailout_target: 'none' })
    expect(Object.keys(last()).sort()).toEqual(Object.keys(DEFAULT_POLICY).sort())
    expect(row(container, 'bailout_target')).toBeNull()
    expect(row(container, 'bailout_budget')).not.toBeNull()
    expect(container.querySelector('.nx-lproblem')).toBeNull()
  })

  test('choosing off resets the sector and the budget and hides both', () => {
    const { container, last } = held(SECTOR_BAILOUTS)
    choose(/^Bailouts/, 'off')
    expect(last()).toEqual(DEFAULT_POLICY)
    expect(row(container, 'bailout_target')).toBeNull()
    expect(row(container, 'bailout_budget')).toBeNull()
    expect(container.querySelector('.nx-lproblem')).toBeNull()
  })

  test('choosing one sector shows the sector choice and asks for a sector until one is picked', () => {
    const { container, last } = held(DEFAULT_POLICY)
    choose(/^Bailouts/, 'one sector only')
    expect(last()).toEqual({ ...DEFAULT_POLICY, bailout_policy: 'sector' })
    expect(row(container, 'bailout_target')).not.toBeNull()
    expect(row(container, 'bailout_budget')).not.toBeNull()
    expect(screen.getByText(COPY.levers.rules.bailout_target)).toHaveAttribute('role', 'status')

    choose(/^The bailout target/, 'food firms')
    expect(last().bailout_target).toBe('food')
    expect(screen.queryByText(COPY.levers.rules.bailout_target)).toBeNull()
    expect(screen.getByText(COPY.levers.rules.bailout_budget)).toBeInTheDocument()

    choose(/^The bailout budget/, '$5,000')
    expect(last()).toEqual(SECTOR_BAILOUTS)
    expect(container.querySelector('.nx-lproblem')).toBeNull()
  })

  test('a hidden control keeps its value, and its rule shows under the controls still in view', () => {
    const { container, onChange } = editor({ value: { ...DEFAULT_POLICY, bailout_target: 'food' } })
    expect(row(container, 'bailout_target')).toBeNull()
    const line = screen.getByText(COPY.levers.rules.bailout_off)
    expect(row(container, 'bailout_policy').nextElementSibling).toBe(line)
    fireEvent.click(within(screen.getByRole('group', { name: 'The minimum wage' })).getByRole('button', { name: 'high' }))
    expect(onChange).toHaveBeenCalledWith({ ...DEFAULT_POLICY, bailout_target: 'food', minimum_wage_policy: 'high' })
  })
})
