import { describe, expect, test, vi } from 'vitest'
import { act, fireEvent, render, renderHook, screen, within } from '@testing-library/react'
import SetupScreen from '../setup/SetupScreen.jsx'
import useSetup from '../setup/useSetup.js'
import { COPY, DEFAULT_POLICY, LEVERS, TOWN_COLORS } from '../catalog.js'

// A fixed random sequence: rollSeed(0.5) = 50000, rollSeed(0.1) = 10000, rollSeed(0.25) = 25000.
const sequence = values => {
  let i = 0
  return () => values[i++ % values.length]
}

function Harness({ random, ...props }) {
  const setup = useSetup({ random })
  return <SetupScreen setup={setup} {...props} />
}

// The sequence is made once per screen, so every roll reads the next value.
function screenWith(props = {}) {
  const handlers = { onStart: vi.fn(), onWatchExample: vi.fn() }
  const random = sequence([0.5, 0.1, 0.25])
  const view = render(<Harness random={random} problem={null} {...handlers} {...props} />)
  return { ...view, ...handlers }
}

const tiles = () => screen.getAllByRole('button', { name: /^Change rules for/ })
const households = () => screen.getByRole('slider', { name: 'Households per town' })

describe('SetupScreen', () => {
  test('1. defaults: the minimum wage question, two towns, 1,000 households, five years', () => {
    screenWith()
    expect(screen.getByRole('heading', { level: 1, name: 'What do you want to find out?' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Compare policies' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: 'What happens if we raise the minimum wage?' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: 'Do generous benefits keep people out of work?' })).toHaveAttribute('aria-pressed', 'false')
    expect(screen.getByRole('button', { name: 'Build my own' })).toHaveAttribute('aria-pressed', 'false')

    expect(tiles()).toHaveLength(2)
    expect(screen.getByRole('heading', { name: 'Your towns' })).toBeInTheDocument()
    expect(within(screen.getByRole('listitem', { name: 'Town A' })).getByText(COPY.setup.control)).toBeInTheDocument()
    expect(within(screen.getByRole('listitem', { name: 'Town B' })).getByText('A higher minimum wage.')).toBeInTheDocument()

    expect(households()).toHaveValue('1000')
    expect(households()).toHaveAttribute('max', '5000')
    expect(screen.getByText('up to 5,000 with 2 towns')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '5 years' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: '1 year' })).toHaveAttribute('aria-pressed', 'false')

    expect(screen.getByText('Town #50000')).toBeInTheDocument()
    expect(screen.queryByRole('spinbutton', { name: 'Town number' })).toBeNull()
    // The size is part of what makes the town: the same number at another size is another town.
    expect(screen.getByText(/^The same town number and size always build the same town/)).toBeInTheDocument()

    expect(screen.getByText('Two towns, 1,000 households each, five years.')).toBeInTheDocument()
    expect(screen.getByText('About a minute.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Start the experiment' })).toBeEnabled()
    expect(screen.queryByRole('alert')).toBeNull()
  })

  test('the question cards show each town\'s rules as a chip', () => {
    screenWith()
    const card = screen.getByRole('button', { name: 'Do generous benefits keep people out of work?' })
    expect(within(card).getByText('No changes')).toBeInTheDocument()
    expect(within(card).getByText('More help for people out of work')).toBeInTheDocument()
    expect(card).toHaveAccessibleDescription(/Does it help them or make work less tempting\?/)
    fireEvent.click(card)
    expect(card).toHaveAttribute('aria-pressed', 'true')
    expect(within(screen.getByRole('listitem', { name: 'Town B' })).getByText('More help for people out of work.')).toBeInTheDocument()
  })

  test('2. just play: one town, no question step, up to 10,000 households', () => {
    screenWith()
    fireEvent.click(screen.getByRole('button', { name: 'Just play' }))
    expect(screen.getByRole('button', { name: 'Just play' })).toHaveAttribute('aria-pressed', 'true')
    expect(tiles()).toHaveLength(1)
    expect(screen.queryByRole('heading', { name: 'Choose a question' })).toBeNull()
    expect(screen.getByRole('heading', { name: 'Your town' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Add a town' })).toBeNull()
    expect(households()).toHaveAttribute('max', '10000')
    expect(screen.getByText('up to 10,000 with 1 town')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Start playing' })).toBeInTheDocument()
    expect(screen.getByText('One town, 1,000 households, five years.')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Compare policies' }))
    expect(tiles()).toHaveLength(2)
    expect(screen.getByRole('button', { name: 'What happens if we raise the minimum wage?' })).toHaveAttribute('aria-pressed', 'true')
  })

  test('3. adding a town clamps households to the new cap', () => {
    screenWith()
    fireEvent.change(households(), { target: { value: '5000' } })
    expect(households()).toHaveValue('5000')
    fireEvent.click(screen.getByRole('button', { name: 'Add a town' }))
    expect(tiles()).toHaveLength(3)
    expect(households()).toHaveValue('3300')
    expect(households()).toHaveAttribute('max', '3300')
    expect(screen.getByText('Three towns, 3,300 households each, five years.')).toBeInTheDocument()
    expect(screen.getByText('About 4 minutes.')).toBeInTheDocument()
    // Town C copies Town A's rules and can be removed; A and B cannot.
    expect(within(screen.getByRole('listitem', { name: 'Town C' })).getByText(COPY.setup.control)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Remove Town B' })).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Add a town' }))
    expect(tiles()).toHaveLength(4)
    expect(screen.queryByRole('button', { name: 'Add a town' })).toBeNull()
    expect(households()).toHaveValue('2500')
    fireEvent.click(screen.getByRole('button', { name: 'Remove Town C' }))
    expect(tiles()).toHaveLength(3)
    expect(screen.getByRole('listitem', { name: 'Town C' })).toBeInTheDocument()
    expect(screen.queryByRole('listitem', { name: 'Town D' })).toBeNull()
  })

  test('4. build my own shows the town number, and a different town rolls a new one', () => {
    screenWith()
    expect(screen.queryByRole('spinbutton', { name: 'Town number' })).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Build my own' }))
    expect(screen.getByRole('button', { name: 'Build my own' })).toHaveAttribute('aria-pressed', 'true')
    const input = screen.getByRole('spinbutton', { name: 'Town number' })
    expect(input).toHaveValue(50000)
    // Build my own keeps the towns it had.
    expect(within(screen.getByRole('listitem', { name: 'Town B' })).getByText('A higher minimum wage.')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Try a different town' }))
    expect(screen.getByText('Town #10000')).toBeInTheDocument()
    expect(input).toHaveValue(10000)

    fireEvent.change(input, { target: { value: '4242' } })
    expect(screen.getByText('Town #4242')).toBeInTheDocument()
  })

  test('5. changing a town\'s rules makes the question custom', () => {
    screenWith()
    fireEvent.click(screen.getByRole('button', { name: 'Change rules for Town B' }))
    const panel = screen.getByRole('region', { name: 'Town B\'s rules' })
    const benefits = within(panel).getByRole('group', { name: 'Help for people out of work' })
    fireEvent.click(within(benefits).getByRole('button', { name: 'high' }))
    expect(screen.getByRole('button', { name: 'Build my own' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: 'What happens if we raise the minimum wage?' })).toHaveAttribute('aria-pressed', 'false')
    expect(within(screen.getByRole('listitem', { name: 'Town B' }))
      .getByText('More help for people out of work and a higher minimum wage.')).toBeInTheDocument()
    expect(screen.getByRole('spinbutton', { name: 'Town number' })).toBeInTheDocument()
    fireEvent.click(within(panel).getByRole('button', { name: 'Done' }))
    expect(screen.queryByRole('region', { name: 'Town B\'s rules' })).toBeNull()
  })

  test('6. start sends the plan', () => {
    const { onStart } = screenWith()
    fireEvent.click(screen.getByRole('button', { name: '2 years' }))
    fireEvent.change(households(), { target: { value: '1500' } })
    fireEvent.click(screen.getByRole('button', { name: 'Start the experiment' }))
    expect(onStart).toHaveBeenCalledTimes(1)
    expect(onStart.mock.calls[0][0]).toEqual({
      mode: 'compare',
      questionId: 'minimum-wage',
      towns: [
        { label: 'Town A', color: TOWN_COLORS[0], policy: DEFAULT_POLICY },
        { label: 'Town B', color: TOWN_COLORS[1], policy: { ...DEFAULT_POLICY, minimum_wage_policy: 'high' } },
      ],
      households: 1500,
      years: 2,
      seed: 50000,
    })
  })

  test('7. an unreachable simulation shows the start command and the recorded example', () => {
    const { onWatchExample } = screenWith({ problem: { kind: 'unreachable', message: '' } })
    const alert = screen.getByRole('alert')
    expect(alert).toHaveTextContent(COPY.setup.problems.unreachable)
    expect(within(alert).getByText('python -m uvicorn backend.server:app --port 8002').tagName).toBe('CODE')
    fireEvent.click(within(alert).getByRole('button', { name: 'Watch the recorded example instead' }))
    expect(onWatchExample).toHaveBeenCalledTimes(1)
    fireEvent.click(screen.getByRole('button', { name: 'Or watch a recorded example first' }))
    expect(onWatchExample).toHaveBeenCalledTimes(2)
  })

  test('other problems say what happened, with the server\'s detail', () => {
    screenWith({ problem: { kind: 'full', message: 'Maximum active simulation sessions (8) reached' } })
    const alert = screen.getByRole('alert')
    expect(alert).toHaveTextContent(COPY.setup.problems.full)
    expect(alert).toHaveTextContent('Maximum active simulation sessions (8) reached')
    expect(within(alert).queryByRole('button')).toBeNull()
  })

  test('8. the AI mayor card is disabled', () => {
    screenWith()
    const card = screen.getByRole('button', { name: 'Test an AI mayor' })
    expect(card).toBeDisabled()
    expect(within(card).getByText('Coming soon')).toBeInTheDocument()
  })

  test('a server that stopped answering while it built the towns says so, without the start command', () => {
    screenWith({ problem: { kind: 'dropped', message: '' } })
    const alert = screen.getByRole('alert')
    expect(alert).toHaveTextContent('The simulation stopped answering while it built the towns. Press Start to try again.')
    expect(alert).not.toHaveTextContent("isn't running")
    expect(within(alert).queryByText('python -m uvicorn backend.server:app --port 8002')).toBeNull()
  })

  test('rules that do not fit together disable Start until they are fixed', () => {
    const { onStart } = screenWith()
    fireEvent.click(screen.getByRole('button', { name: 'Change rules for Town B' }))
    const panel = screen.getByRole('region', { name: 'Town B\'s rules' })
    fireEvent.click(within(within(panel).getByRole('group', { name: 'The business subsidy' })).getByRole('button', { name: '10%' }))
    expect(within(panel).getByText(COPY.levers.rules.sector_subsidy)).toHaveAttribute('role', 'status')
    const start = screen.getByRole('button', { name: 'Start the experiment' })
    expect(start).toBeDisabled()
    expect(screen.getByText(COPY.setup.fixFirst(['Town B']))).toBeInTheDocument()
    fireEvent.click(start)
    expect(onStart).not.toHaveBeenCalled()
    fireEvent.click(within(within(panel).getByRole('group', { name: 'The subsidy target' })).getByRole('button', { name: 'food firms' }))
    expect(start).toBeEnabled()
  })
})

describe('useSetup', () => {
  const setupHook = () => renderHook(() => useSetup({ random: sequence([0.5, 0.1]) }))

  test('the plan follows the state', () => {
    const { result } = setupHook()
    expect(result.current.state).toMatchObject({ mode: 'compare', questionId: 'minimum-wage', households: 1000, years: 5, seed: 50000, editing: null })
    expect(result.current.plan).toEqual({
      mode: 'compare',
      questionId: 'minimum-wage',
      towns: result.current.state.towns,
      households: 1000,
      years: 5,
      seed: 50000,
    })
    act(() => result.current.actions.setMode('play'))
    expect(result.current.plan.mode).toBe('play')
    expect(result.current.plan.questionId).toBeNull()
    expect(result.current.plan.towns).toEqual([{ label: 'Town A', color: TOWN_COLORS[0], policy: DEFAULT_POLICY }])
  })

  test('households are clamped and rounded to the step', () => {
    const { result } = setupHook()
    act(() => result.current.actions.setHouseholds(1234))
    expect(result.current.state.households).toBe(1200)
    act(() => result.current.actions.setHouseholds(9999))
    expect(result.current.state.households).toBe(5000)
    act(() => result.current.actions.setHouseholds(10))
    expect(result.current.state.households).toBe(100)
    act(() => result.current.actions.setHouseholds(Number.NaN))
    expect(result.current.state.households).toBe(100)
  })

  test('years take only the offered lengths, and the seed stays in range', () => {
    const { result } = setupHook()
    act(() => result.current.actions.setYears(3))
    expect(result.current.state.years).toBe(5)
    act(() => result.current.actions.setYears(10))
    expect(result.current.state.years).toBe(10)
    act(() => result.current.actions.setSeed(-5))
    expect(result.current.state.seed).toBe(0)
    act(() => result.current.actions.setSeed(9e12))
    expect(result.current.state.seed).toBe(2147483647)
    act(() => result.current.actions.setSeed(12.7))
    expect(result.current.state.seed).toBe(12)
  })

  test('a reroll never lands on the same town', () => {
    const { result } = renderHook(() => useSetup({ random: () => 0.5 }))
    expect(result.current.state.seed).toBe(50000)
    act(() => result.current.actions.rerollSeed())
    expect(result.current.state.seed).not.toBe(50000)
  })

  test('removing a town relabels the rest and keeps the open editor on its town', () => {
    const { result } = setupHook()
    act(() => result.current.actions.addTown())
    act(() => result.current.actions.addTown())
    act(() => result.current.actions.setTownPolicy(3, { ...DEFAULT_POLICY, public_works: 'on' }))
    act(() => result.current.actions.editTown(3))
    act(() => result.current.actions.removeTown(2))
    const { towns, editing, questionId } = result.current.state
    expect(questionId).toBe('custom')
    expect(towns.map(town => town.label)).toEqual(['Town A', 'Town B', 'Town C'])
    expect(towns.map(town => town.color)).toEqual(TOWN_COLORS.slice(0, 3))
    expect(towns[2].policy.public_works).toBe('on')
    expect(editing).toBe(2)
    act(() => result.current.actions.removeTown(2))
    act(() => result.current.actions.removeTown(1))
    expect(result.current.state.towns).toHaveLength(2)
    expect(result.current.state.editing).toBeNull()
  })

  test('a new town copies Town A, and there are never more than four', () => {
    const { result } = setupHook()
    act(() => result.current.actions.setTownPolicy(0, { ...DEFAULT_POLICY, wage_tax_rate: 0.3 }))
    act(() => result.current.actions.addTown())
    expect(result.current.state.towns[2].policy.wage_tax_rate).toBe(0.3)
    act(() => result.current.actions.addTown())
    act(() => result.current.actions.addTown())
    expect(result.current.state.towns).toHaveLength(4)
  })

  test('picking a question sets its towns over the usual rules', () => {
    const { result } = setupHook()
    act(() => result.current.actions.pickQuestion('benefits'))
    expect(result.current.state.questionId).toBe('benefits')
    expect(result.current.state.towns.map(town => town.policy)).toEqual([DEFAULT_POLICY, { ...DEFAULT_POLICY, benefit_level: 'high' }])
    expect(Object.keys(LEVERS).every(lever => lever in result.current.state.towns[1].policy)).toBe(true)
  })
})
