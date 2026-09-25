import { Profiler, StrictMode } from 'react'
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'
import { act, fireEvent, render, screen } from '@testing-library/react'
import { useExperiment } from '../live/useExperiment.js'
import { DEFAULT_POLICY } from '../catalog.js'
import { fakeSocketFactory } from './fakeSocket.js'

const plan = {
  mode: 'compare', questionId: 'minimum-wage', households: 200, years: 1, seed: 4242,
  towns: [
    { label: 'Town A', color: '#2E6FE0', policy: { ...DEFAULT_POLICY } },
    { label: 'Town B', color: '#E0762C', policy: { ...DEFAULT_POLICY, minimum_wage_policy: 'high' } },
  ],
}
const frame = tick => ({ tick, metrics: { trackedSubjects: [], governmentPolicy: DEFAULT_POLICY }, curated: {}, firms: [], events: [] })

function Probe({ WebSocketImpl }) {
  const { state, start, pause, leave } = useExperiment({ WebSocketImpl, url: 'ws://test/ws' })
  return (
    <div>
      <button type="button" onClick={() => start(plan)}>Start</button>
      <button type="button" onClick={pause}>Pause</button>
      <button type="button" onClick={leave}>Leave</button>
      <p data-testid="week">{state ? `Week ${state.liveTick}` : 'No experiment'}</p>
      <p data-testid="phase">{state?.phase ?? 'none'}</p>
    </div>
  )
}

function setup({ strict = false } = {}) {
  const { FakeSocket, sockets } = fakeSocketFactory()
  const commits = { count: 0 }
  const tree = (
    <Profiler id="probe" onRender={() => { commits.count += 1 }}>
      <Probe WebSocketImpl={FakeSocket} />
    </Profiler>
  )
  const view = render(strict ? <StrictMode>{tree}</StrictMode> : tree)
  return { sockets, commits, ...view }
}

function startAndRun(sockets) {
  fireEvent.click(screen.getByRole('button', { name: 'Start' }))
  act(() => {
    sockets.forEach((socket, i) => {
      socket.open()
      socket.receive({ type: 'SESSION', sessionId: `s${i}` })
      socket.receive({ type: 'SETUP_COMPLETE', config: {} })
    })
  })
  act(() => { vi.advanceTimersByTime(500) })
}

const week = () => screen.getByTestId('week').textContent
const phase = () => screen.getByTestId('phase').textContent

describe('useExperiment', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  test('opens no socket until Start, then one per town', () => {
    const { sockets } = setup()
    expect(sockets).toHaveLength(0)
    expect(week()).toBe('No experiment')
    startAndRun(sockets)
    expect(sockets).toHaveLength(2)
    expect(sockets.map(s => s.url)).toEqual(['ws://test/ws', 'ws://test/ws'])
    expect(sockets.map(s => s.commands())).toEqual([['SETUP', 'START'], ['SETUP', 'START']])
    expect(phase()).toBe('running')
  })

  test('StrictMode still opens exactly one socket per town', () => {
    const { sockets } = setup({ strict: true })
    startAndRun(sockets)
    expect(sockets).toHaveLength(2)
    expect(sockets.every(s => s.readyState === 1)).toBe(true)
  })

  test('20 frames within 50 ms make at most two renders, and the last one shows the newest week', () => {
    const { sockets, commits } = setup()
    startAndRun(sockets)
    commits.count = 0
    for (let tick = 1; tick <= 10; tick += 1) {
      for (const socket of sockets) {
        act(() => { socket.receive(frame(tick)) })
        act(() => { vi.advanceTimersByTime(2) })
      }
    }
    expect(commits.count).toBeLessThanOrEqual(2)
    act(() => { vi.advanceTimersByTime(100) })
    expect(commits.count).toBeLessThanOrEqual(2)
    expect(week()).toBe('Week 10')
  })

  test('commands reach the controller', () => {
    const { sockets } = setup()
    startAndRun(sockets)
    fireEvent.click(screen.getByRole('button', { name: 'Pause' }))
    act(() => { vi.advanceTimersByTime(200) })
    expect(sockets.map(s => s.commands().at(-1))).toEqual(['STOP', 'STOP'])
    expect(phase()).toBe('paused')
  })

  test('leave closes every socket, clears the state, and later messages bring nothing back', () => {
    const { sockets } = setup()
    startAndRun(sockets)
    act(() => { sockets[0].receive(frame(1)) })
    fireEvent.click(screen.getByRole('button', { name: 'Leave' }))
    expect(sockets.every(s => s.readyState === 3 && s.closedWith === 1000)).toBe(true)
    expect(week()).toBe('No experiment')
    act(() => { sockets[1].receive(frame(1)) })
    act(() => { vi.advanceTimersByTime(500) })
    expect(week()).toBe('No experiment')
  })

  test('unmounting closes every socket', () => {
    const { sockets, unmount } = setup()
    startAndRun(sockets)
    unmount()
    expect(sockets.every(s => s.readyState === 3 && s.closedWith === 1000)).toBe(true)
  })
})
