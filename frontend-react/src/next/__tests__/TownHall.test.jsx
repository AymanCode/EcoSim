import { describe, expect, test, vi } from 'vitest'
import { fireEvent, render, screen, within } from '@testing-library/react'
import TownHall from '../components/TownHall.jsx'
import { COPY, DEFAULT_POLICY, TOWN_COLORS } from '../catalog.js'
import { addPendingConfig, createArm, failPendingConfig, ingest } from '../data/session.js'

const receipt = fields => ({
  actionId: null, status: 'sending', requested: {}, applied: {}, rejected: {}, effectiveTick: null, message: null, ...fields,
})

function towns() {
  const a = createArm({ label: 'Town A', color: TOWN_COLORS[0] })
  a.policy = { ...DEFAULT_POLICY, benefit_level: 'high' }
  const b = createArm({ label: 'Town B', color: TOWN_COLORS[1] })
  b.policy = { ...DEFAULT_POLICY }
  return [a, b]
}

function hall(arms = towns(), props = {}) {
  const onConfigure = vi.fn()
  const onClose = vi.fn()
  const view = render(<TownHall arms={arms} tick={20} onConfigure={onConfigure} onClose={onClose} {...props} />)
  const aside = screen.getByRole('complementary', { name: 'Town hall' })
  return { ...view, aside, onConfigure, onClose }
}

const pick = (aside, lever, option) => fireEvent.click(
  within(within(aside).getByRole('group', { name: new RegExp(`^${lever}`) })).getByRole('button', { name: option }),
)
const apply = aside => within(aside).getByRole('button', { name: 'Change from next week' })

describe('TownHall', () => {
  test('opens on Town A with the rules its town hall has in force', () => {
    const { aside, onClose } = hall()
    const tabs = within(aside).getByRole('group', { name: 'Which town' })
    expect(within(tabs).getAllByRole('button').map(tab => tab.textContent)).toEqual(['Town A', 'Town B'])
    expect(within(tabs).getByRole('button', { name: 'Town A' })).toHaveAttribute('aria-pressed', 'true')
    expect(within(tabs).getByRole('button', { name: 'Town B' })).toHaveAttribute('aria-pressed', 'false')
    const benefits = within(aside).getByRole('group', { name: 'Help for people out of work' })
    expect(within(benefits).getByRole('button', { name: 'high' })).toHaveAttribute('aria-pressed', 'true')
    expect(within(aside).getByText('Changes start at the next week. The other towns keep their own rules.')).toBeInTheDocument()
    fireEvent.click(within(aside).getByRole('button', { name: 'Close the town hall' }))
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  test('a town without a week yet shows its starting rules', () => {
    const b = createArm({ label: 'Town B', color: TOWN_COLORS[1], setup: { initial_policy: { minimum_wage_policy: 'high' } } })
    const { aside } = hall([b])
    const wage = within(aside).getByRole('group', { name: 'The minimum wage' })
    expect(within(wage).getByRole('button', { name: 'high' })).toHaveAttribute('aria-pressed', 'true')
    expect(within(aside).getByText('Changes start at the next week.')).toBeInTheDocument()
  })

  test('sends only the levers that changed, and the change stays shown while it is on its way', () => {
    const arms = towns()
    // As the live controller does: a 'sending' receipt for every CONFIG.
    const onConfigure = vi.fn((index, levers) => addPendingConfig(arms[index], levers))
    const { aside } = hall(arms, { onConfigure })
    expect(apply(aside)).toBeDisabled()
    pick(aside, 'The minimum wage', 'high')
    expect(apply(aside)).toBeEnabled()
    fireEvent.click(apply(aside))
    expect(onConfigure).toHaveBeenCalledWith(0, { minimum_wage_policy: 'high' })
    // No snap back to the old rules, and nothing to send twice.
    const wage = within(aside).getByRole('group', { name: 'The minimum wage' })
    expect(within(wage).getByRole('button', { name: 'high' })).toHaveAttribute('aria-pressed', 'true')
    expect(within(aside).queryByText('(changed)')).toBeNull()
    expect(apply(aside)).toBeDisabled()
  })

  test('after the town hall applies a change, its rules include it, and it can be undone at once', () => {
    const arms = towns()
    const onConfigure = vi.fn((index, levers) => addPendingConfig(arms[index], levers))
    const { aside, rerender } = hall(arms, { onConfigure })
    fireEvent.click(within(aside).getByRole('button', { name: 'Town B' }))
    pick(aside, 'The business subsidy', '25%')
    fireEvent.click(within(within(aside).getByRole('group', { name: /^The subsidy target/ })).getByRole('button', { name: 'food firms' }))
    fireEvent.click(apply(aside))
    expect(onConfigure).toHaveBeenLastCalledWith(1, { sector_subsidy_target: 'food', sector_subsidy_level: 25 })
    // Paused: CONFIG_APPLIED comes alone, and no week follows until Resume.
    ingest(arms[1], {
      type: 'CONFIG_APPLIED', actionId: 'p1', requested: { sector_subsidy_target: 'food', sector_subsidy_level: 25 },
      applied: { sector_subsidy_target: 'food', sector_subsidy_level: 25 }, rejected: {}, effectiveTick: 21,
    })
    rerender(<TownHall arms={[...arms]} tick={20} onConfigure={onConfigure} onClose={() => {}} />)
    const level = within(aside).getByRole('group', { name: 'The business subsidy' })
    expect(within(level).getByRole('button', { name: '25%' })).toHaveAttribute('aria-pressed', 'true')
    expect(apply(aside)).toBeDisabled()
    // Undo before resuming: back to no subsidy.
    pick(aside, 'The business subsidy', 'none')
    fireEvent.click(within(within(aside).getByRole('group', { name: /^The subsidy target/ })).getByRole('button', { name: 'no one' }))
    expect(apply(aside)).toBeEnabled()
    fireEvent.click(apply(aside))
    expect(onConfigure).toHaveBeenLastCalledWith(1, { sector_subsidy_target: 'none', sector_subsidy_level: 0 })
  })

  test('a change that failed shows the rules in force again', () => {
    const arms = towns()
    const onConfigure = vi.fn((index, levers) => addPendingConfig(arms[index], levers))
    const { aside, rerender } = hall(arms, { onConfigure })
    pick(aside, 'The minimum wage', 'high')
    fireEvent.click(apply(aside))
    failPendingConfig(arms[0], 'the run is finished')
    rerender(<TownHall arms={[...arms]} tick={20} onConfigure={onConfigure} onClose={() => {}} />)
    const wage = within(aside).getByRole('group', { name: 'The minimum wage' })
    expect(within(wage).getByRole('button', { name: 'normal' })).toHaveAttribute('aria-pressed', 'true')
  })

  test('focus moves to the heading only when opened from its toggle', () => {
    const { aside, unmount } = hall(towns(), { autoFocus: true })
    expect(document.activeElement).toBe(within(aside).getByRole('heading', { name: 'Town hall' }))
    unmount()
    hall(towns())
    expect(document.activeElement).toBe(document.body)
  })

  test('each town keeps its own draft', () => {
    const { aside, onConfigure } = hall()
    pick(aside, 'The minimum wage', 'high')
    fireEvent.click(within(aside).getByRole('button', { name: 'Town B' }))
    expect(within(aside).getByRole('button', { name: 'Town B' })).toHaveAttribute('aria-pressed', 'true')
    expect(apply(aside)).toBeDisabled()
    pick(aside, 'Public works jobs', 'on')
    fireEvent.click(apply(aside))
    expect(onConfigure).toHaveBeenLastCalledWith(1, { public_works: 'on' })
    fireEvent.click(within(aside).getByRole('button', { name: 'Town A' }))
    fireEvent.click(apply(aside))
    expect(onConfigure).toHaveBeenLastCalledWith(0, { minimum_wage_policy: 'high' })
  })

  test('a rule the town hall would refuse keeps the button disabled', () => {
    const { aside } = hall()
    pick(aside, 'The business subsidy', '25%')
    expect(within(aside).getByText(COPY.levers.rules.sector_subsidy)).toHaveAttribute('role', 'status')
    expect(apply(aside)).toBeDisabled()
  })

  test('receipts: waiting, applied with its week, a rejected lever and a failure', () => {
    const [a, b] = towns()
    a.receipts = [
      receipt({ actionId: 'x0', status: 'failed', message: 'the run is finished' }),
      receipt({
        actionId: 'x1', status: 'applied', applied: { minimum_wage_policy: 'high' }, rejected: { sector_subsidy_level: 'needs a target' }, effectiveTick: 60,
      }),
      receipt({ actionId: 'x2', status: 'queued' }),
    ]
    const { aside } = hall([a, b])
    const lines = within(aside).getAllByRole('listitem').map(item => item.textContent)
    expect(lines).toEqual([
      'Waiting for next week…',
      'Year 2, week 8: A higher minimum wage.The business subsidy was not changed: needs a target',
      "Couldn't change the rules: the run is finished",
    ])
  })

  test('only the newest five receipts show, newest first', () => {
    const [a, b] = towns()
    a.receipts = Array.from({ length: 7 }, (_, i) => receipt({
      actionId: `x${i}`, status: 'applied', applied: { minimum_wage_policy: 'high' }, effectiveTick: i + 1,
    }))
    const { aside } = hall([a, b])
    const lines = within(aside).getAllByRole('listitem').map(item => item.textContent)
    expect(lines).toHaveLength(5)
    expect(lines[0]).toBe('Year 1, week 7: A higher minimum wage.')
    expect(lines[4]).toBe('Year 1, week 3: A higher minimum wage.')
  })

  test('a locked town hall explains why and sends nothing', () => {
    const { aside, onConfigure } = hall(towns(), { locked: 'The run is over. Add a year to change the rules again.' })
    pick(aside, 'The minimum wage', 'high')
    expect(apply(aside)).toBeDisabled()
    expect(within(aside).getByText('The run is over. Add a year to change the rules again.')).toBeInTheDocument()
    fireEvent.click(apply(aside))
    expect(onConfigure).not.toHaveBeenCalled()
  })
})
