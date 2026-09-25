import { describe, expect, it } from 'vitest'
import { createExperiment, LEAD_PAUSE, LEAD_RESUME } from '../live/experiment.js'
import { DEFAULT_POLICY } from '../catalog.js'
import { fakeSocketFactory } from './fakeSocket.js'

const plan = {
  mode: 'compare', questionId: 'minimum-wage', households: 200, years: 1, seed: 4242,
  towns: [
    { label: 'Town A', color: '#2E6FE0', policy: { ...DEFAULT_POLICY } },
    { label: 'Town B', color: '#E0762C', policy: { ...DEFAULT_POLICY, minimum_wage_policy: 'high' } },
  ],
}
const frame = (tick, extra = {}) => ({ tick, metrics: { trackedSubjects: [], governmentPolicy: DEFAULT_POLICY }, curated: {}, firms: [], events: [], ...extra })

function boot() {
  const { FakeSocket, sockets } = fakeSocketFactory()
  const states = []
  const exp = createExperiment({ plan, url: 'ws://test/ws', experimentId: 'exp-t', owner: 'me', WebSocketImpl: FakeSocket, onChange: s => states.push(s) })
  exp.connect()
  sockets.forEach(s => s.open())
  return { exp, sockets, states }
}
function ready({ sockets }) {
  sockets.forEach((s, i) => { s.receive({ type: 'SESSION', sessionId: `s${i}` }); s.receive({ type: 'SETUP_COMPLETE', config: {} }) })
}
const feed = (socket, ticks) => ticks.forEach(tick => socket.receive(frame(tick)))
const count = (socket, command) => socket.commands().filter(c => c === command).length
const statuses = exp => exp.getState().towns.map(town => town.status)
const allClosed = sockets => sockets.every(s => s.readyState === 3)

describe('createExperiment', () => {
  it('1. sends each town its SETUP after SESSION and STARTs only when every town is set up', () => {
    const t = boot()
    expect(t.sockets).toHaveLength(2)
    t.sockets[0].receive({ type: 'SESSION', sessionId: 'a' })
    expect(t.sockets[0].sent[0]).toEqual({ command: 'SETUP', config: expect.objectContaining({ arm_label: 'Town A', arm_count: 2, experiment_id: 'exp-t', frame_profile: 'lean', initial_policy: {} }) })
    t.sockets[0].receive({ type: 'SETUP_COMPLETE', config: {} })
    expect(t.sockets[0].commands()).not.toContain('START')
    t.sockets[1].receive({ type: 'SESSION', sessionId: 'b' })
    expect(t.sockets[1].sent[0].config.initial_policy).toEqual({ minimum_wage_policy: 'high' })
    t.sockets[1].receive({ type: 'SETUP_COMPLETE', config: {} })
    expect(t.sockets.map(s => s.commands().at(-1))).toEqual(['START', 'START'])
    expect(t.exp.getState().phase).toBe('running')
  })

  it('1b. connecting: one socket per town at the url, the full SETUP config, and the town states', () => {
    const t = boot()
    expect(t.sockets.map(s => s.url)).toEqual(['ws://test/ws', 'ws://test/ws'])
    const state = t.exp.getState()
    expect(state).toMatchObject({ experimentId: 'exp-t', phase: 'connecting', liveTick: 0, error: null })
    expect(state.towns).toEqual([
      { label: 'Town A', status: 'connecting', lastTick: 0, notice: null },
      { label: 'Town B', status: 'connecting', lastTick: 0, notice: null },
    ])
    expect(state.arms.map(arm => arm.label)).toEqual(['Town A', 'Town B'])
    expect(state.arms[0].horizon).toBe(52)
    t.sockets[0].receive({ type: 'SESSION', sessionId: 'a' })
    expect(t.sockets[0].sent[0].config).toEqual({
      num_households: 200, seed: 4242, horizon_ticks: 52, initial_policy: {}, frame_profile: 'lean', enable_llm_government: false,
      experiment_id: 'exp-t', arm_label: 'Town A', arm_count: 2, experiment_owner: 'me',
    })
    t.sockets[0].receive({ type: 'SETUP_COMPLETE', config: { seed: 4242, horizon_ticks: 52 } })
    expect(statuses(t.exp)).toEqual(['ready', 'connecting'])
    expect(t.exp.getState().phase).toBe('connecting')
    // A second connect() opens nothing more.
    t.exp.connect()
    expect(t.sockets).toHaveLength(2)
  })

  it('2. frames reach the arms, liveTick is the lower last tick, and arm.policy follows the frame', () => {
    const t = boot()
    ready(t)
    expect(t.exp.getState().liveTick).toBe(0)
    feed(t.sockets[0], [1, 2, 3])
    expect(t.exp.getState().liveTick).toBe(0)
    const higher = { ...DEFAULT_POLICY, minimum_wage_policy: 'high' }
    t.sockets[1].receive(frame(1, { metrics: { trackedSubjects: [], governmentPolicy: higher } }))
    t.sockets[1].receive(frame(2, { metrics: { trackedSubjects: [], governmentPolicy: higher } }))
    const state = t.exp.getState()
    expect(state.arms[0].ticks).toEqual([1, 2, 3])
    expect(state.arms[1].ticks).toEqual([1, 2])
    expect(state.towns.map(town => town.lastTick)).toEqual([3, 2])
    expect(state.liveTick).toBe(2)
    expect(state.arms[0].policy).toEqual(DEFAULT_POLICY)
    expect(state.arms[1].policy).toEqual(higher)
    // Every publish carries a new array of new arm objects.
    const before = t.states.at(-1)
    t.sockets[1].receive(frame(3))
    const after = t.states.at(-1)
    expect(after).toBe(t.exp.getState())
    expect(after.arms).not.toBe(before.arms)
    expect(after.arms[1]).not.toBe(before.arms[1])
    expect(after.liveTick).toBe(3)
  })

  it('3. holds a town 3 weeks ahead and restarts it once the slowest has caught up', () => {
    expect([LEAD_PAUSE, LEAD_RESUME]).toEqual([3, 0])
    const t = boot()
    ready(t)
    feed(t.sockets[1], [1])
    feed(t.sockets[0], [1, 2, 3])
    // Two weeks ahead is not held.
    expect(count(t.sockets[0], 'STOP')).toBe(0)
    expect(statuses(t.exp)).toEqual(['running', 'running'])
    feed(t.sockets[0], [4])
    expect(t.sockets[0].commands().at(-1)).toBe('STOP')
    expect(statuses(t.exp)).toEqual(['held', 'running'])
    expect(t.exp.getState().phase).toBe('running')
    feed(t.sockets[1], [2, 3])
    expect(statuses(t.exp)).toEqual(['held', 'running'])
    expect(count(t.sockets[0], 'START')).toBe(1)
    feed(t.sockets[1], [4])
    expect(t.sockets[0].commands().at(-1)).toBe('START')
    expect(count(t.sockets[0], 'START')).toBe(2)
    expect(statuses(t.exp)).toEqual(['running', 'running'])
    expect(count(t.sockets[1], 'STOP')).toBe(0)
  })

  it('4. pause and resume reach every town, except a town at the horizon', () => {
    const t = boot()
    ready(t)
    const before = t.states.length
    t.exp.pause()
    expect(t.states.length).toBe(before + 1)
    expect(t.sockets.map(s => s.commands().at(-1))).toEqual(['STOP', 'STOP'])
    expect(statuses(t.exp)).toEqual(['stopped', 'stopped'])
    expect(t.exp.getState().phase).toBe('paused')
    t.exp.resume()
    expect(t.sockets.map(s => s.commands().at(-1))).toEqual(['START', 'START'])
    expect(statuses(t.exp)).toEqual(['running', 'running'])
    expect(t.exp.getState().phase).toBe('running')

    t.sockets[1].receive({ type: 'HORIZON_REACHED', tick: 52 })
    const sentToB = t.sockets[1].sent.length
    t.exp.pause()
    t.exp.resume()
    expect(t.sockets[1].sent.length).toBe(sentToB)
    expect(t.sockets[0].commands().slice(-2)).toEqual(['STOP', 'START'])
    expect(statuses(t.exp)).toEqual(['running', 'horizon'])
  })

  it('4b. while paused, a held town that is caught up waits for resume', () => {
    const t = boot()
    ready(t)
    feed(t.sockets[1], [1])
    feed(t.sockets[0], [1, 2, 3, 4])
    expect(statuses(t.exp)).toEqual(['held', 'running'])
    t.exp.pause()
    // The held town is already stopped: pause sends it nothing more.
    expect(count(t.sockets[0], 'STOP')).toBe(1)
    expect(t.sockets[1].commands().at(-1)).toBe('STOP')
    feed(t.sockets[1], [2, 3, 4])
    expect(t.sockets[0].commands().at(-1)).toBe('STOP')
    expect(statuses(t.exp)).toEqual(['held', 'stopped'])
    t.exp.resume()
    expect(t.sockets[1].commands().at(-1)).toBe('START')
    expect(t.sockets[0].commands().at(-1)).toBe('START')
    expect(statuses(t.exp)).toEqual(['running', 'running'])
  })

  it('5. finishes once every town is at the horizon, and EXTEND reopens the run', () => {
    const t = boot()
    ready(t)
    t.sockets[0].receive({ type: 'HORIZON_REACHED', tick: 52 })
    expect(t.sockets.map(s => count(s, 'FINISH'))).toEqual([0, 0])
    expect(t.exp.getState().phase).toBe('running')
    t.sockets[1].receive({ type: 'HORIZON_REACHED', tick: 52 })
    expect(t.sockets.map(s => count(s, 'FINISH'))).toEqual([1, 1])
    expect(t.exp.getState().phase).toBe('horizon')
    // A repeated HORIZON_REACHED sends no second FINISH.
    t.sockets[0].receive({ type: 'HORIZON_REACHED', tick: 52 })
    expect(t.sockets.map(s => count(s, 'FINISH'))).toEqual([1, 1])
    t.sockets[0].receive({ type: 'FINISHED', tick: 52, analysisReady: true, runId: 'r1', drained: 0 })
    expect(t.exp.getState().phase).toBe('horizon')
    t.sockets[1].receive({ type: 'FINISHED', tick: 52, analysisReady: true, runId: 'r2', drained: 0 })
    expect(statuses(t.exp)).toEqual(['finished', 'finished'])
    expect(t.exp.getState().phase).toBe('finished')

    t.exp.pause()
    expect(t.exp.getState().phase).toBe('finished')
    t.exp.extend(52)
    expect(t.sockets.map(s => s.sent.at(-1))).toEqual([{ command: 'EXTEND', ticks: 52 }, { command: 'EXTEND', ticks: 52 }])
    t.sockets[0].receive({ type: 'EXTENDED', horizonTick: 104, tick: 52, resumed: true })
    expect(statuses(t.exp)).toEqual(['running', 'finished'])
    t.sockets[1].receive({ type: 'EXTENDED', horizonTick: 104, tick: 52, resumed: true })
    expect(statuses(t.exp)).toEqual(['running', 'running'])
    expect(t.exp.getState().phase).toBe('running')
    expect(t.exp.getState().arms.map(arm => arm.horizon)).toEqual([104, 104])

    // The new horizon finishes again, once.
    t.sockets.forEach(s => s.receive({ type: 'HORIZON_REACHED', tick: 104 }))
    expect(t.sockets.map(s => count(s, 'FINISH'))).toEqual([2, 2])
  })

  it('6. a full server fails the experiment and closes every socket', () => {
    const t = boot()
    t.sockets[0].receive({ error: 'Maximum active simulation sessions reached (8)' })
    t.sockets[0].serverClose(1013)
    const state = t.exp.getState()
    expect(state.phase).toBe('failed')
    expect(state.error).toEqual({ kind: 'full', town: 'Town A', message: 'Maximum active simulation sessions reached (8)' })
    expect(allClosed(t.sockets)).toBe(true)
    expect(t.sockets[1].closedWith).toBe(1000)
  })

  it('6b. any other error before SESSION is kind unreachable with the raw text', () => {
    const t = boot()
    t.sockets[1].receive({ error: 'something odd' })
    expect(t.exp.getState().error).toEqual({ kind: 'unreachable', town: 'Town B', message: 'something odd' })
    expect(t.exp.getState().phase).toBe('failed')
    expect(allClosed(t.sockets)).toBe(true)
  })

  it('7. a failed SETUP fails the experiment and closes every socket', () => {
    const t = boot()
    t.sockets.forEach((s, i) => s.receive({ type: 'SESSION', sessionId: `s${i}` }))
    t.sockets[0].receive({ type: 'SETUP_COMPLETE', config: {} })
    t.sockets[1].receive({ error: 'SETUP failed: 6000 households exceeds the per-arm cap of 5000 for 2 arms' })
    const state = t.exp.getState()
    expect(state.phase).toBe('failed')
    expect(state.error.kind).toBe('setup')
    expect(state.error.town).toBe('Town B')
    expect(state.error.message.startsWith('6000 households')).toBe(true)
    expect(allClosed(t.sockets)).toBe(true)
    expect(t.sockets.some(s => s.commands().includes('START'))).toBe(false)
  })

  it('8. an unreachable server fails the experiment and leaves no socket open', () => {
    const t = boot()
    const published = t.states.length
    t.sockets[0].fail()
    const state = t.exp.getState()
    expect(state.phase).toBe('failed')
    expect(state.error).toEqual({ kind: 'unreachable', town: 'Town A', message: '' })
    expect(allClosed(t.sockets)).toBe(true)
    // One publish for the failure; the close events that follow are ignored.
    expect(t.states.length).toBe(published + 1)
    t.sockets[1].receive({ type: 'SESSION', sessionId: 'late' })
    expect(t.sockets[1].sent).toEqual([])
  })

  it('8b. a plain close before SESSION, or during set up, is unreachable too', () => {
    const t = boot()
    t.sockets[1].serverClose()
    expect(t.exp.getState()).toMatchObject({ phase: 'failed', error: { kind: 'unreachable', town: 'Town B', message: '' } })
    expect(allClosed(t.sockets)).toBe(true)

    const u = boot()
    u.sockets.forEach((s, i) => s.receive({ type: 'SESSION', sessionId: `s${i}` }))
    u.sockets[0].receive({ type: 'SETUP_COMPLETE', config: {} })
    u.sockets[0].serverClose()
    expect(u.exp.getState()).toMatchObject({ phase: 'failed', error: { kind: 'unreachable', town: 'Town A' } })
    expect(allClosed(u.sockets)).toBe(true)
    expect(u.sockets.some(s => s.commands().includes('START'))).toBe(false)
  })

  it('8c. a socket that cannot even be constructed fails as unreachable', () => {
    class Broken {
      constructor() { throw new SyntaxError('bad url') }
    }
    const states = []
    const exp = createExperiment({ plan, url: 'nope', experimentId: 'e', owner: 'me', WebSocketImpl: Broken, onChange: s => states.push(s) })
    exp.connect()
    expect(exp.getState()).toMatchObject({ phase: 'failed', error: { kind: 'unreachable', town: 'Town A', message: 'bad url' } })
    expect(states.at(-1)).toBe(exp.getState())
  })

  it('9. a socket lost mid-run pauses the other towns', () => {
    const t = boot()
    ready(t)
    feed(t.sockets[0], [1, 2])
    feed(t.sockets[1], [1, 2])
    t.sockets[1].serverClose()
    const state = t.exp.getState()
    expect(state.phase).toBe('lost')
    expect(state.error).toMatchObject({ kind: 'lost', town: 'Town B' })
    expect(state.error.message).toBe('')
    expect(t.sockets[0].commands().at(-1)).toBe('STOP')
    expect(statuses(t.exp)).toEqual(['stopped', 'lost'])
    expect(t.sockets[0].readyState).toBe(1)
    // Frames still in flight are kept, and nothing restarts the other town.
    feed(t.sockets[0], [3])
    t.exp.resume()
    expect(t.sockets[0].commands().at(-1)).toBe('STOP')
    expect(t.exp.getState().arms[0].ticks).toEqual([1, 2, 3])
    expect(t.exp.getState().phase).toBe('lost')
  })

  it('10. receipts follow CONFIG, CONFIG_QUEUED, CONFIG_APPLIED and CONFIG failed', () => {
    const t = boot()
    ready(t)
    const receipts = () => t.exp.getState().arms[1].receipts
    t.exp.configure(1, { minimum_wage_policy: 'low' })
    expect(t.sockets[1].sent.at(-1)).toEqual({ command: 'CONFIG', config: { minimum_wage_policy: 'low' } })
    expect(receipts()).toEqual([{
      actionId: null, status: 'sending', requested: { minimum_wage_policy: 'low' }, applied: {}, rejected: {}, effectiveTick: null, message: null,
    }])
    t.sockets[1].receive({ type: 'CONFIG_QUEUED', actionId: 'x1', tick: 6 })
    expect(receipts()[0]).toMatchObject({ actionId: 'x1', status: 'queued' })
    t.sockets[1].receive({
      type: 'CONFIG_APPLIED', actionId: 'x1', requested: { minimum_wage_policy: 'low' }, applied: { minimum_wage_policy: 'low' }, rejected: {}, effectiveTick: 7,
    })
    expect(receipts()[0]).toEqual({
      actionId: 'x1', status: 'applied', requested: { minimum_wage_policy: 'low' }, applied: { minimum_wage_policy: 'low' }, rejected: {}, effectiveTick: 7, message: null,
    })

    // Paused: CONFIG_APPLIED comes alone and adopts the new receipt.
    t.exp.pause()
    t.exp.configure(1, { benefit_level: 'high', sector_subsidy_level: 10 })
    t.sockets[1].receive({
      type: 'CONFIG_APPLIED', actionId: 'x2', requested: { benefit_level: 'high', sector_subsidy_level: 10 },
      applied: { benefit_level: 'high' }, rejected: { sector_subsidy_level: 'a sector subsidy needs a target' }, effectiveTick: 8,
    })
    expect(receipts()).toHaveLength(2)
    expect(receipts()[1]).toMatchObject({
      actionId: 'x2', status: 'applied', applied: { benefit_level: 'high' }, rejected: { sector_subsidy_level: 'a sector subsidy needs a target' }, effectiveTick: 8,
    })

    t.exp.configure(1, { minimum_wage_policy: 'high' })
    t.sockets[1].receive({ error: 'CONFIG failed: the run is finished; send EXTEND to continue, or START if it finished before its horizon' })
    expect(receipts()[2]).toMatchObject({
      status: 'failed', message: 'the run is finished; send EXTEND to continue, or START if it finished before its horizon',
    })
    expect(receipts().map(r => r.status)).toEqual(['applied', 'applied', 'failed'])
    expect(t.exp.getState().arms[0].receipts).toEqual([])
    expect(t.exp.getState().phase).toBe('paused')
  })

  it('10b. other server errors become a notice on that town', () => {
    const t = boot()
    ready(t)
    t.sockets[0].receive({ error: 'STOP failed: simulation loop did not stop within the timeout' })
    const state = t.exp.getState()
    expect(state.towns[0].notice).toBe('STOP failed: simulation loop did not stop within the timeout')
    expect(state.towns[1].notice).toBe(null)
    expect(state.phase).toBe('running')
    expect(state.error).toBe(null)
  })

  it('11. close() closes every socket, and nothing that arrives later changes the state', () => {
    const t = boot()
    ready(t)
    t.sockets.forEach(s => feed(s, [1]))
    t.exp.close()
    expect(t.sockets.map(s => s.closedWith)).toEqual([1000, 1000])
    expect(allClosed(t.sockets)).toBe(true)
    const closed = t.exp.getState()
    expect(closed.phase).toBe('closed')
    expect(closed.liveTick).toBe(1)
    const published = t.states.length
    t.sockets[0].receive(frame(2))
    t.sockets[1].receive({ type: 'CONFIG_APPLIED', actionId: 'late', applied: {}, rejected: {}, effectiveTick: 3 })
    t.sockets[1].serverClose()
    t.exp.pause()
    t.exp.configure(0, { benefit_level: 'high' })
    t.exp.close()
    expect(t.states.length).toBe(published)
    expect(t.exp.getState()).toBe(closed)
    expect(t.exp.getState().liveTick).toBe(1)
    expect(t.exp.getState().arms[0].ticks).toEqual([1])
    expect(t.exp.getState().arms[1].receipts).toEqual([])
    expect(t.sockets[0].commands()).not.toContain('CONFIG')
  })

  it('12. track sends TRACK with the household only when there is one', () => {
    const t = boot()
    ready(t)
    t.exp.track(0, 'reshuffle')
    expect(t.sockets[0].sent.at(-1)).toEqual({ command: 'TRACK', action: 'reshuffle' })
    t.exp.track(0, 'pin', 17)
    expect(t.sockets[0].sent.at(-1)).toEqual({ command: 'TRACK', action: 'pin', householdId: 17 })
    expect(t.sockets[1].commands()).not.toContain('TRACK')
    t.sockets[0].receive({ type: 'TRACKED', tracked: [17], pinned: [17], tick: 3, profiles: { 17: { frugality: 1 } } })
    expect(t.exp.getState().arms[0].profiles['17']).toEqual({ frugality: 1 })
  })
})
