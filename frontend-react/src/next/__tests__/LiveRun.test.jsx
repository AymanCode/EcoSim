import { StrictMode } from 'react'
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'
import { act, fireEvent, render, screen, within } from '@testing-library/react'
import NextApp from '../NextApp.jsx'
import { createArm, ingest, isFrame, parseSession } from '../data/session.js'
import { leadSentence } from '../narration.js'
import { fakeSocketFactory } from './fakeSocket.js'
import { FIXTURE_TEXT } from './fixture.js'

// The recorded fixture's weeks, fed to every live town.
const FRAMES = parseSession(FIXTURE_TEXT).messages.filter(isFrame)

function app({ strict = false } = {}) {
  const { FakeSocket, sockets } = fakeSocketFactory()
  const tree = <NextApp search="?view=next" WebSocketImpl={FakeSocket} />
  const view = render(strict ? <StrictMode>{tree}</StrictMode> : tree)
  return { sockets, ...view }
}

// useExperiment hands state to React at most every 100 ms.
const flush = () => act(() => { vi.advanceTimersByTime(250) })
const start = (name = 'Start the experiment') => fireEvent.click(screen.getByRole('button', { name }))

// Each socket opens, gets its session, and the server confirms the SETUP it was sent.
function connect(sockets) {
  act(() => {
    sockets.forEach((socket, i) => {
      socket.open()
      socket.receive({ type: 'SESSION', sessionId: `s${i}` })
      socket.receive({ type: 'SETUP_COMPLETE', config: socket.sent[0].config })
    })
  })
  flush()
}

function run(sockets, from = 0, to = 12) {
  act(() => {
    FRAMES.slice(from, to).forEach(frame => sockets.forEach(socket => socket.receive(frame)))
  })
  flush()
}

// The arms the app should hold after `connect` and `run`, built the same way.
function expectedArms(sockets, weeks) {
  return sockets.map(socket => {
    const { config } = socket.sent[0]
    const arm = createArm({ label: config.arm_label, setup: config })
    ingest(arm, { type: 'SETUP_COMPLETE', config })
    FRAMES.slice(0, weeks).forEach(frame => ingest(arm, frame))
    return arm
  })
}

const weekShown = container => container.querySelector('.nx-clock .nx-week').textContent

describe('NextApp live', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  test('Start opens one socket per town, and the weeks fill two town columns', () => {
    const { sockets, container } = app()
    expect(screen.getByRole('heading', { level: 1, name: 'What do you want to find out?' })).toBeInTheDocument()
    expect(sockets).toHaveLength(0)
    start()
    expect(sockets).toHaveLength(2)
    expect(sockets.map(socket => socket.url)).toEqual(['ws://localhost:5173/ws', 'ws://localhost:5173/ws'])
    flush()
    expect(screen.getByText('Building the towns…')).toBeInTheDocument()
    expect(container.querySelectorAll('.nx-col')).toHaveLength(0)
    connect(sockets)
    expect(sockets.map(socket => socket.commands())).toEqual([['SETUP', 'START'], ['SETUP', 'START']])
    run(sockets)
    expect(screen.queryByText('Building the towns…')).toBeNull()
    expect(screen.getByRole('heading', { level: 1, name: 'What happens with a higher minimum wage?' })).toBeInTheDocument()
    const columns = container.querySelectorAll('.nx-col')
    expect(columns).toHaveLength(2)
    expect(columns[0]).toHaveTextContent('Town A')
    expect(columns[1]).toHaveTextContent('Town B')
    expect(container.querySelector('.nx-lead')).toHaveTextContent(leadSentence(expectedArms(sockets, 12), 12))
    expect(weekShown(container)).toBe('Year 1, week 12')
    expect(screen.queryByRole('group', { name: 'Speed' })).toBeNull()
    expect(screen.getByRole('button', { name: 'Pause' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Back to live' })).toBeNull()
  })

  test('StrictMode still opens exactly one socket per town', () => {
    const { sockets } = app({ strict: true })
    start()
    expect(sockets).toHaveLength(2)
    connect(sockets)
    expect(sockets.every(socket => socket.readyState === 1)).toBe(true)
  })

  test('no simulation running: back to Set up with the fix, and no socket left open', () => {
    const { sockets } = app()
    start()
    act(() => { sockets[0].fail() })
    flush()
    expect(screen.getByRole('heading', { level: 1, name: 'What do you want to find out?' })).toBeInTheDocument()
    expect(screen.getByRole('alert')).toHaveTextContent("The simulation isn't running on this computer.")
    expect(screen.getByText('python -m uvicorn backend.server:app --port 8002')).toBeInTheDocument()
    expect(sockets.every(socket => socket.readyState === 3)).toBe(true)
    expect(screen.getByRole('button', { name: 'Start the experiment' })).toBeEnabled()
  })

  test('the Town hall changes Town B\'s minimum wage and shows the receipt', () => {
    const { sockets } = app()
    start()
    connect(sockets)
    run(sockets)
    const toggle = screen.getByRole('button', { name: 'Town hall' })
    expect(toggle).toHaveAttribute('aria-pressed', 'false')
    fireEvent.click(toggle)
    expect(toggle).toHaveAttribute('aria-pressed', 'true')
    const hall = screen.getByRole('complementary', { name: 'Town hall' })
    fireEvent.click(within(hall).getByRole('button', { name: 'Town B' }))
    fireEvent.click(within(within(hall).getByRole('group', { name: 'The minimum wage' })).getByRole('button', { name: 'low' }))
    fireEvent.click(within(hall).getByRole('button', { name: 'Change from next week' }))
    expect(sockets[1].sent.at(-1)).toEqual({ command: 'CONFIG', config: { minimum_wage_policy: 'low' } })
    expect(sockets[0].commands()).not.toContain('CONFIG')
    flush()
    expect(within(hall).getByText('Waiting for next week…')).toBeInTheDocument()
    act(() => {
      sockets[1].receive({ type: 'CONFIG_QUEUED', actionId: 'a1', tick: 12 })
      sockets[1].receive({
        type: 'CONFIG_APPLIED', actionId: 'a1', requested: { minimum_wage_policy: 'low' }, applied: { minimum_wage_policy: 'low' }, rejected: {}, effectiveTick: 13,
      })
    })
    flush()
    expect(within(hall).getByText('Year 1, week 13: A lower minimum wage.')).toBeInTheDocument()
    fireEvent.click(within(hall).getByRole('button', { name: 'Close the town hall' }))
    expect(screen.queryByRole('complementary', { name: 'Town hall' })).toBeNull()
  })

  test('the horizon: FINISH on every town, then the end panel adds a year', () => {
    const { sockets } = app()
    start()
    connect(sockets)
    run(sockets)
    act(() => { sockets.forEach(socket => socket.receive({ type: 'HORIZON_REACHED', tick: 12 })) })
    expect(sockets.map(socket => socket.commands().at(-1))).toEqual(['FINISH', 'FINISH'])
    flush()
    expect(screen.getByRole('button', { name: 'Add a year' })).toBeDisabled()
    act(() => { sockets.forEach(socket => socket.receive({ type: 'FINISHED', tick: 12, analysisReady: true, runId: 'r', drained: 0 })) })
    flush()
    expect(screen.getByRole('heading', { name: '24 weeks are up.' })).toBeInTheDocument()
    const add = screen.getByRole('button', { name: 'Add a year' })
    expect(add).toBeEnabled()
    fireEvent.click(add)
    expect(sockets.map(socket => socket.sent.at(-1))).toEqual([{ command: 'EXTEND', ticks: 52 }, { command: 'EXTEND', ticks: 52 }])
    act(() => { sockets.forEach(socket => socket.receive({ type: 'EXTENDED', horizonTick: 76, tick: 12, resumed: true })) })
    flush()
    expect(screen.queryByRole('button', { name: 'Add a year' })).toBeNull()
    expect(screen.getByRole('button', { name: 'Pause' })).toBeInTheDocument()
  })

  test('New experiment closes every socket and goes back to the same set up', () => {
    const { sockets } = app()
    fireEvent.click(screen.getByRole('button', { name: 'Do generous benefits keep people out of work?' }))
    start()
    connect(sockets)
    run(sockets)
    fireEvent.click(screen.getByRole('button', { name: 'New experiment' }))
    expect(sockets.every(socket => socket.readyState === 3 && socket.closedWith === 1000)).toBe(true)
    expect(screen.getByRole('heading', { level: 1, name: 'What do you want to find out?' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Do generous benefits keep people out of work?' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('listitem', { name: 'Town B' })).toHaveTextContent('More help for people out of work.')
    act(() => { sockets[0].receive(FRAMES[12]) })
    flush()
    expect(screen.getByRole('heading', { level: 1, name: 'What do you want to find out?' })).toBeInTheDocument()
  })

  test('a lost town pauses the others, names the town, and can start again with the same town number', () => {
    const { sockets } = app()
    start()
    connect(sockets)
    run(sockets)
    act(() => { sockets[1].serverClose() })
    flush()
    expect(screen.getByRole('alert')).toHaveTextContent(
      'Town B lost its connection to the simulation in Year 1, week 12. The other towns are paused.',
    )
    expect(sockets[0].commands().at(-1)).toBe('STOP')
    fireEvent.click(screen.getByRole('button', { name: 'Start these towns again' }))
    expect(sockets).toHaveLength(4)
    expect(sockets[0].readyState).toBe(3)
    connect(sockets.slice(2))
    expect(sockets[2].sent[0].config.seed).toBe(sockets[0].sent[0].config.seed)
    expect(sockets[3].sent[0].config.initial_policy).toEqual({ minimum_wage_policy: 'high' })
    expect(screen.queryByRole('alert')).toBeNull()
    expect(screen.getByText('Building the towns…')).toBeInTheDocument()
  })

  test('Just play: one town, with the Town hall open from the start', () => {
    const { sockets, container } = app()
    fireEvent.click(screen.getByRole('button', { name: 'Just play' }))
    start('Start playing')
    expect(sockets).toHaveLength(1)
    expect(screen.getByRole('complementary', { name: 'Town hall' })).toBeInTheDocument()
    expect(screen.getByText('You can change the rules as soon as the run starts.')).toBeInTheDocument()
    connect(sockets)
    run(sockets)
    expect(container.querySelectorAll('.nx-col')).toHaveLength(1)
    expect(screen.getByRole('heading', { level: 1, name: 'What happens in Town A?' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Town hall' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.queryByText('You can change the rules as soon as the run starts.')).toBeNull()
  })

  test('Pause and Resume reach every town', () => {
    const { sockets } = app()
    start()
    connect(sockets)
    run(sockets)
    fireEvent.click(screen.getByRole('button', { name: 'Pause' }))
    expect(sockets.map(socket => socket.commands().at(-1))).toEqual(['STOP', 'STOP'])
    flush()
    fireEvent.click(screen.getByRole('button', { name: 'Resume' }))
    expect(sockets.map(socket => socket.commands().at(-1))).toEqual(['START', 'START'])
    flush()
    expect(screen.getByRole('button', { name: 'Pause' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Play again' })).toBeNull()
  })

  test('scrubbing back holds that week until "Back to live"', () => {
    const { sockets, container } = app()
    start()
    connect(sockets)
    run(sockets)
    const slider = screen.getByRole('slider', { name: 'Week of the run' })
    expect(slider).toHaveAttribute('max', '12')
    fireEvent.change(slider, { target: { value: '5' } })
    expect(weekShown(container)).toBe('Year 1, week 5')
    run(sockets, 12, 16)
    expect(weekShown(container)).toBe('Year 1, week 5')
    fireEvent.click(screen.getByRole('button', { name: 'Back to live' }))
    expect(weekShown(container)).toBe('Year 1, week 16')
    expect(screen.queryByRole('button', { name: 'Back to live' })).toBeNull()
  })

  test('households: "Meet other families" reshuffles and Follow pins, on that town only', () => {
    const { sockets, container } = app()
    start()
    connect(sockets)
    run(sockets)
    const townB = container.querySelectorAll('.nx-col')[1]
    fireEvent.click(within(townB).getByRole('button', { name: 'Meet other families' }))
    expect(sockets[1].sent.at(-1)).toEqual({ command: 'TRACK', action: 'reshuffle' })
    expect(sockets[0].commands()).not.toContain('TRACK')
    const follow = within(townB).getAllByRole('button', { name: /^Follow / })[1]
    fireEvent.click(follow)
    const pinned = sockets[1].sent.at(-1)
    expect(pinned).toMatchObject({ command: 'TRACK', action: 'pin' })
    expect(typeof pinned.householdId).toBe('number')
    // The server pins only a household it follows: follow it first.
    expect(sockets[1].sent.at(-2)).toEqual({ command: 'TRACK', action: 'follow', householdId: pinned.householdId })
    fireEvent.click(within(townB).getByRole('button', { name: follow.getAttribute('aria-label') }))
    expect(sockets[1].sent.at(-1)).toEqual({ command: 'TRACK', action: 'unpin', householdId: pinned.householdId })
  })

  test('"Meet other families" waits for a running town and the live week', () => {
    const { sockets, container } = app()
    start()
    connect(sockets)
    run(sockets)
    const meet = () => within(container.querySelectorAll('.nx-col')[1]).getByRole('button', { name: 'Meet other families' })
    expect(meet()).toBeEnabled()
    fireEvent.click(screen.getByRole('button', { name: 'Pause' }))
    flush()
    expect(meet()).toBeDisabled()
    fireEvent.click(meet())
    expect(sockets[1].commands()).not.toContain('TRACK')
    fireEvent.click(screen.getByRole('button', { name: 'Resume' }))
    flush()
    expect(meet()).toBeEnabled()
    fireEvent.change(screen.getByRole('slider', { name: 'Week of the run' }), { target: { value: '5' } })
    expect(meet()).toBeDisabled()
  })

  test('a command the server could not do reads as a plain line with the details, until the next week', () => {
    const { sockets, container } = app()
    start()
    connect(sockets)
    run(sockets)
    act(() => {
      sockets[1].receive({ error: 'TRACK failed: household 523 is not in the sample; follow it first' })
      sockets[1].receive({ error: 'STOP failed: simulation loop did not stop within the timeout' })
    })
    flush()
    const notices = [...container.querySelectorAll('.nx-notice')]
    expect(notices.map(notice => notice.getAttribute('role'))).toEqual(['status', 'status'])
    expect(notices[0]).toBeEmptyDOMElement()
    expect(notices[1].textContent).toBe(
      "The simulation couldn't carry out the last request for this town. Details: STOP failed: simulation loop did not stop within the timeout",
    )
    expect(container).not.toHaveTextContent('household 523')
    run(sockets, 12, 13)
    expect(container.querySelectorAll('.nx-notice')[1]).toBeEmptyDOMElement()
  })

  test('a town the server stops with an error: the others pause, and the panel says so plainly', () => {
    const { sockets } = app()
    start()
    connect(sockets)
    run(sockets)
    act(() => { sockets[1].receive({ error: 'float division by zero' }) })
    flush()
    expect(screen.getByRole('alert')).toHaveTextContent(
      'Town B stopped because the simulation hit an error in Year 1, week 12. The other towns are paused.',
    )
    expect(screen.getByText('Details: float division by zero')).toBeInTheDocument()
    expect(sockets[0].commands().at(-1)).toBe('STOP')
    expect(sockets[1].readyState).toBe(3)
    expect(screen.getByRole('button', { name: 'Pause' })).toBeDisabled()
    expect(screen.queryByText('Your rule changes will not be repeated.', { exact: false })).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Start these towns again' }))
    expect(sockets).toHaveLength(4)
  })

  test('paused: a change the town hall applies at once shows as the rules in force, with nothing left to send', () => {
    const { sockets } = app()
    start()
    connect(sockets)
    run(sockets)
    fireEvent.click(screen.getByRole('button', { name: 'Pause' }))
    flush()
    fireEvent.click(screen.getByRole('button', { name: 'Town hall' }))
    const hall = screen.getByRole('complementary', { name: 'Town hall' })
    fireEvent.click(within(hall).getByRole('button', { name: 'Town B' }))
    const wage = () => within(hall).getByRole('group', { name: /^The minimum wage/ })
    const apply = () => within(hall).getByRole('button', { name: 'Change from next week' })
    fireEvent.click(within(wage()).getByRole('button', { name: 'low' }))
    fireEvent.click(apply())
    expect(sockets[1].sent.at(-1)).toEqual({ command: 'CONFIG', config: { minimum_wage_policy: 'low' } })
    flush()
    expect(within(wage()).getByRole('button', { name: 'low' })).toHaveAttribute('aria-pressed', 'true')
    expect(apply()).toBeDisabled()
    act(() => {
      sockets[1].receive({
        type: 'CONFIG_APPLIED', actionId: 'p1', requested: { minimum_wage_policy: 'low' }, applied: { minimum_wage_policy: 'low' }, rejected: {}, effectiveTick: 13,
      })
    })
    flush()
    expect(within(hall).getByText('Year 1, week 13: A lower minimum wage.')).toBeInTheDocument()
    expect(within(wage()).getByRole('button', { name: 'low' })).toHaveAttribute('aria-pressed', 'true')
    expect(apply()).toBeDisabled()
    // Pressing the value in force again sends nothing.
    fireEvent.click(within(wage()).getByRole('button', { name: 'low' }))
    expect(apply()).toBeDisabled()
    expect(sockets[1].commands().filter(command => command === 'CONFIG')).toHaveLength(1)

    // Losing a town after that: the fresh start will not repeat the change.
    act(() => { sockets[0].serverClose() })
    flush()
    expect(screen.getByText('Starting again uses the rules you set up. Your rule changes will not be repeated.')).toBeInTheDocument()
  })

  test('the Town hall toggle moves focus into the drawer and back, and the drawer comes before the columns', () => {
    const { sockets, container } = app()
    start()
    connect(sockets)
    run(sockets)
    const toggle = screen.getByRole('button', { name: 'Town hall' })
    expect(toggle).toHaveAttribute('aria-expanded', 'false')
    fireEvent.click(toggle)
    const hall = screen.getByRole('complementary', { name: 'Town hall' })
    expect(toggle).toHaveAttribute('aria-expanded', 'true')
    expect(toggle).toHaveAttribute('aria-controls', hall.id)
    expect(hall).toContainElement(document.activeElement)
    expect(hall.compareDocumentPosition(container.querySelector('main')) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    fireEvent.click(within(hall).getByRole('button', { name: 'Close the town hall' }))
    expect(screen.queryByRole('complementary', { name: 'Town hall' })).toBeNull()
    expect(document.activeElement).toBe(toggle)
    fireEvent.click(toggle)
    fireEvent.keyDown(document.activeElement, { key: 'Escape' })
    expect(screen.queryByRole('complementary', { name: 'Town hall' })).toBeNull()
    expect(document.activeElement).toBe(toggle)
  })

  test('scrubbed back after the end, the end panel folds to a bar with a way back', () => {
    const { sockets, container } = app()
    start()
    connect(sockets)
    run(sockets)
    act(() => { sockets.forEach(socket => socket.receive({ type: 'HORIZON_REACHED', tick: 12 })) })
    act(() => { sockets.forEach(socket => socket.receive({ type: 'FINISHED', tick: 12, analysisReady: true, runId: 'r', drained: 0 })) })
    flush()
    expect(container.querySelector('.nx-endp-v')).not.toBeNull()
    fireEvent.change(screen.getByRole('slider', { name: 'Week of the run' }), { target: { value: '5' } })
    expect(screen.getByRole('heading', { name: '24 weeks are up.' })).toBeInTheDocument()
    expect(container.querySelector('.nx-endp-v')).toBeNull()
    expect(screen.getByRole('button', { name: 'Add a year' })).toBeEnabled()
    fireEvent.click(screen.getByRole('button', { name: 'Back to the end' }))
    expect(weekShown(container)).toBe('Year 1, week 12')
    expect(container.querySelector('.nx-endp-v')).not.toBeNull()
  })
})
