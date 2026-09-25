import { useCallback, useEffect, useMemo, useReducer } from 'react'

// Replay clock for recorded towns: a week counter that plays, pauses and jumps.
export const SPEEDS = [0.5, 1, 2, 4]
const WEEKS_PER_SECOND = 8

const clampTick = (tick, maxTick) => Math.min(Math.max(1, maxTick), Math.max(1, Math.round(Number(tick) || 1)))

function reducer(state, action) {
  const last = Math.max(1, action.maxTick ?? 1)
  switch (action.type) {
    case 'advance': {
      if (!state.playing) return state
      const tick = Math.min(last, state.tick + 1)
      return { ...state, tick, playing: tick < last }
    }
    case 'play':
      if (last <= 1) return state
      return { ...state, playing: true, tick: state.tick >= last ? 1 : state.tick }
    case 'pause':
      return state.playing ? { ...state, playing: false } : state
    case 'toggle':
      return reducer(state, { ...action, type: state.playing ? 'pause' : 'play' })
    case 'scrub':
      return { ...state, tick: clampTick(action.tick, last) }
    case 'speed':
      return SPEEDS.includes(action.speed) ? { ...state, speed: action.speed } : state
    default:
      return state
  }
}

const INITIAL = { tick: 1, playing: false, speed: 1 }

export default function useReplay({ maxTick } = {}) {
  const last = Math.max(1, Math.floor(Number(maxTick) || 1))
  const [state, dispatch] = useReducer(reducer, INITIAL)

  useEffect(() => {
    if (!state.playing) return undefined
    const id = setInterval(() => dispatch({ type: 'advance', maxTick: last }), 1000 / (WEEKS_PER_SECOND * state.speed))
    return () => clearInterval(id)
  }, [state.playing, state.speed, last])

  const play = useCallback(() => dispatch({ type: 'play', maxTick: last }), [last])
  const pause = useCallback(() => dispatch({ type: 'pause', maxTick: last }), [last])
  const toggle = useCallback(() => dispatch({ type: 'toggle', maxTick: last }), [last])
  const scrub = useCallback(tick => dispatch({ type: 'scrub', tick, maxTick: last }), [last])
  const setSpeed = useCallback(speed => dispatch({ type: 'speed', speed, maxTick: last }), [last])

  const tick = Math.min(state.tick, last)
  return useMemo(() => ({
    tick, playing: state.playing, play, pause, toggle, scrub, speed: state.speed, setSpeed,
  }), [tick, state.playing, state.speed, play, pause, toggle, scrub, setSpeed])
}
