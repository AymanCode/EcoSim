// A live experiment: one WebSocket per town, speaking the frame-2 protocol
// (docs/WEBSOCKET_PROTOCOL.md). No React here. Every server message goes into
// its town's arm (data/session.js `ingest`), and a plain State is published
// through `onChange` after every handled message and every command.
//
// State = { experimentId, phase, arms, liveTick, towns, error }
//   phase: 'connecting' | 'running' | 'paused' | 'horizon' | 'finished' | 'lost' | 'failed' | 'closed'
//   arms: a new array of shallow arm copies on every publish
//   liveTick: the lowest latest tick over the towns (0 before any frame)
//   towns: [{ label, status, lastTick, notice }], status one of 'connecting', 'ready',
//          'running', 'held' (stopped to let the others catch up), 'stopped' (paused),
//          'horizon', 'finished', 'lost'
//   error: null | { kind: 'full'|'unreachable'|'setup'|'lost', town, message }
import { addPendingConfig, createArm, failPendingConfig, ingest, isFrame } from '../data/session.js'
import { setupConfigs } from './plan.js'

// A town this many weeks ahead of the slowest running town gets STOP,
// and START again once the slowest has caught up to this lead.
export const LEAD_PAUSE = 3
export const LEAD_RESUME = 0

const OPEN = 1
const FULL = 'Maximum active simulation sessions'
const SETUP_FAILED = 'SETUP failed: '
const CONFIG_FAILED = 'CONFIG failed: '
const CLOSE_NORMAL = 1000

const isNumber = value => typeof value === 'number' && Number.isFinite(value)

export function createExperiment({ plan, url, experimentId, owner, WebSocketImpl, onChange }) {
  const configs = setupConfigs(plan, { experimentId, owner })
  // Until SETUP_COMPLETE confirms it, a town's setup is the config we send.
  const arms = plan.towns.map((town, i) => createArm({ label: town.label, color: town.color, setup: configs[i] }))
  const towns = plan.towns.map(town => ({ label: town.label, status: 'connecting', lastTick: 0, notice: null }))
  const sockets = []
  const hasSession = towns.map(() => false)
  const finishSent = towns.map(() => false)
  let connected = false
  let started = false // START has gone to every town
  let userPaused = false
  let failed = false
  let closed = false
  let error = null

  const anyLost = () => towns.some(town => town.status === 'lost')
  const usable = () => connected && !failed && !closed
  // Messages and events from a socket this experiment no longer listens to are dropped.
  const current = (index, socket) => !failed && !closed && sockets[index] === socket

  function phase() {
    if (failed) return 'failed'
    if (closed) return 'closed'
    if (anyLost()) return 'lost'
    if (towns.every(town => town.status === 'finished')) return 'finished'
    if (towns.every(town => town.status === 'horizon' || town.status === 'finished')) return 'horizon'
    if (!started) return 'connecting'
    if (userPaused) return 'paused'
    return 'running'
  }

  function snapshot() {
    return {
      experimentId,
      phase: phase(),
      arms: arms.map(arm => ({ ...arm })),
      liveTick: towns.length ? Math.min(...towns.map(town => town.lastTick)) : 0,
      towns: towns.map(town => ({ ...town })),
      error: error ? { ...error } : null,
    }
  }

  let state = snapshot()

  function publish() {
    state = snapshot()
    onChange?.(state)
  }

  function send(index, message) {
    const socket = sockets[index]
    if (!socket || socket.readyState !== OPEN) return false
    try {
      socket.send(JSON.stringify(message))
      return true
    } catch {
      return false
    }
  }

  // Closing a socket releases the server's household reservation for it. The
  // handlers come off first, so the close events that follow reach no one.
  function closeAll() {
    for (const socket of sockets) {
      if (!socket) continue
      socket.onopen = null
      socket.onmessage = null
      socket.onclose = null
      socket.onerror = null
      try {
        socket.close(CLOSE_NORMAL)
      } catch {
        // Already closed.
      }
    }
  }

  function fail(index, kind, message) {
    if (failed || closed) return
    failed = true
    error = { kind, town: towns[index]?.label ?? null, message }
    closeAll()
  }

  function startAll() {
    started = true
    towns.forEach((town, i) => {
      send(i, { command: 'START' })
      town.status = 'running'
    })
  }

  // Keep the towns within LEAD_PAUSE weeks of each other.
  function align() {
    const moving = towns.filter(town => town.status === 'running' || town.status === 'held')
    if (!moving.length) return
    const slowest = Math.min(...moving.map(town => town.lastTick))
    const mayRun = !userPaused && !anyLost()
    towns.forEach((town, i) => {
      if (town.status === 'running' && town.lastTick - slowest >= LEAD_PAUSE) {
        send(i, { command: 'STOP' })
        town.status = 'held'
      } else if (town.status === 'held' && town.lastTick - slowest <= LEAD_RESUME && mayRun) {
        send(i, { command: 'START' })
        town.status = 'running'
      }
    })
  }

  function finishIfAllAtHorizon() {
    if (!towns.every(town => town.status === 'horizon' || town.status === 'finished')) return
    towns.forEach((town, i) => {
      if (town.status !== 'horizon' || finishSent[i]) return
      send(i, { command: 'FINISH' })
      finishSent[i] = true
    })
  }

  function handleError(index, text) {
    if (!hasSession[index]) {
      fail(index, text.includes(FULL) ? 'full' : 'unreachable', text)
    } else if (text.startsWith(SETUP_FAILED)) {
      fail(index, 'setup', text.slice(SETUP_FAILED.length))
    } else if (text.startsWith(CONFIG_FAILED)) {
      failPendingConfig(arms[index], text.slice(CONFIG_FAILED.length))
    } else {
      towns[index].notice = text
    }
  }

  function handleMessage(index, message) {
    const town = towns[index]
    switch (message.type) {
      case 'SESSION':
        hasSession[index] = true
        send(index, { command: 'SETUP', config: configs[index] })
        break
      case 'SETUP_COMPLETE':
        if (town.status === 'connecting') town.status = 'ready'
        if (!started && towns.every(t => t.status === 'ready')) startAll()
        break
      case 'HORIZON_REACHED':
        if (isNumber(message.tick)) town.lastTick = Math.max(town.lastTick, message.tick)
        if (town.status !== 'finished') town.status = 'horizon'
        finishIfAllAtHorizon()
        break
      case 'FINISHED':
        town.status = 'finished'
        break
      case 'EXTENDED':
        // The server resumes the loop itself: no START needed.
        town.status = 'running'
        finishSent[index] = false
        userPaused = false
        break
      default:
        if (isFrame(message)) {
          town.lastTick = Math.max(town.lastTick, message.tick)
          align()
        }
    }
  }

  function onMessage(index, socket, event) {
    if (!current(index, socket)) return
    let message
    try {
      message = JSON.parse(event?.data)
    } catch {
      return
    }
    if (!message || typeof message !== 'object') return
    ingest(arms[index], message)
    if (message.error != null && !message.type) handleError(index, String(message.error))
    else handleMessage(index, message)
    publish()
  }

  function onClose(index, socket) {
    if (!current(index, socket)) return
    if (!started) {
      // Before START nothing has run: give every reservation back.
      fail(index, 'unreachable', '')
    } else if (towns[index].status !== 'lost') {
      towns[index].status = 'lost'
      error ??= { kind: 'lost', town: towns[index].label, message: '' }
      towns.forEach((town, i) => {
        if (i === index || town.status !== 'running') return
        send(i, { command: 'STOP' })
        town.status = 'stopped'
      })
    }
    publish()
  }

  function onError(index, socket) {
    if (!current(index, socket)) return
    // After START the close event that follows marks the town lost.
    if (started) return
    fail(index, 'unreachable', '')
    publish()
  }

  return {
    connect() {
      if (connected || failed || closed) return
      connected = true
      for (let i = 0; i < towns.length; i += 1) {
        let socket
        try {
          socket = new WebSocketImpl(url)
        } catch (reason) {
          fail(i, 'unreachable', String(reason?.message ?? ''))
          break
        }
        sockets[i] = socket
        socket.onmessage = event => onMessage(i, socket, event)
        socket.onclose = () => onClose(i, socket)
        socket.onerror = () => onError(i, socket)
      }
      publish()
    },

    pause() {
      if (!usable()) return
      if (started && !anyLost()) {
        userPaused = true
        towns.forEach((town, i) => {
          if (town.status !== 'running') return
          send(i, { command: 'STOP' })
          town.status = 'stopped'
        })
      }
      publish()
    },

    resume() {
      if (!usable()) return
      if (started && !anyLost()) {
        userPaused = false
        towns.forEach((town, i) => {
          if (town.status !== 'stopped') return
          send(i, { command: 'START' })
          town.status = 'running'
        })
        align()
      }
      publish()
    },

    extend(weeks) {
      if (!usable()) return
      towns.forEach((_, i) => send(i, { command: 'EXTEND', ticks: weeks }))
      publish()
    },

    configure(index, levers) {
      if (!usable()) return
      if (sockets[index]?.readyState === OPEN) {
        addPendingConfig(arms[index], levers)
        send(index, { command: 'CONFIG', config: { ...levers } })
      }
      publish()
    },

    track(index, action, householdId) {
      if (!usable()) return
      const message = { command: 'TRACK', action }
      if (householdId != null) message.householdId = householdId
      send(index, message)
      publish()
    },

    close() {
      if (closed) return
      closed = true
      closeAll()
      publish()
    },

    getState() {
      return state
    },
  }
}
