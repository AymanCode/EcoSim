import { describe, expect, test, vi } from 'vitest'
import { fireEvent, render, screen, within } from '@testing-library/react'
import LeverEditor from '../components/LeverEditor.jsx'
import { COPY, DEFAULT_POLICY, LEVER_GROUPS, LEVERS } from '../catalog.js'

function editor(props = {}) {
  const onChange = vi.fn()
  const view = render(<LeverEditor value={DEFAULT_POLICY} base={DEFAULT_POLICY} onChange={onChange} idPrefix="town-b" {...props} />)
  return { ...view, onChange }
}

describe('LeverEditor', () => {
  test('all 17 levers render inside 5 fieldsets, in the catalog groups', () => {
    const { container } = editor()
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
    const { onChange, rerender } = editor()
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

  test('a broken group rule shows an alert under its group', () => {
    const { container } = editor({ value: { ...DEFAULT_POLICY, sector_subsidy_level: 10 } })
    const alert = screen.getByRole('alert')
    expect(alert).toHaveTextContent(COPY.levers.rules.sector_subsidy)
    const business = container.querySelectorAll('fieldset')[LEVER_GROUPS.findIndex(group => group.id === 'business')]
    expect(business).toContainElement(alert)
  })

  test('no alert when the rules fit together', () => {
    editor()
    expect(screen.queryByRole('alert')).toBeNull()
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
