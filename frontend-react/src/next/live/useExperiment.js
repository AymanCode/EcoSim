import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { createExperiment } from './experiment.js'
import { newExperimentId, ownerId, resolveSocketUrl } from './endpoint.js'

// The live experiment for React. Sockets open only in start(), a user action,
// never in render or an effect, so StrictMode cannot open a second set.
// The controller's state reaches React at most once per THROTTLE_MS: the first
// change at once, then the newest one at the end of each window.
const THROTTLE_MS = 100

export function useExperiment({ WebSocketImpl = globalThis.WebSocket, url } = {}) {
  const [state, setState] = useState(null)
  const controllerRef = useRef(null)
  const throttleRef = useRef({ timer: null, pending: null })

  const stopThrottle = useCallback(() => {
    const throttle = throttleRef.current
    clearTimeout(throttle.timer)
    throttle.timer = null
    throttle.pending = null
  }, [])

  const deliver = useCallback(next => {
    const throttle = throttleRef.current
    if (throttle.timer) {
      throttle.pending = next
      return
    }
    setState(next)
    throttle.timer = setTimeout(function flush() {
      throttle.timer = null
      const newest = throttle.pending
      if (!newest) return
      throttle.pending = null
      setState(newest)
      throttle.timer = setTimeout(flush, THROTTLE_MS)
    }, THROTTLE_MS)
  }, [])

  // Detach before closing, so the controller's last publish is not delivered.
  const detach = useCallback(() => {
    const controller = controllerRef.current
    controllerRef.current = null
    stopThrottle()
    controller?.close()
  }, [stopThrottle])

  const start = useCallback(plan => {
    detach()
    const controller = createExperiment({
      plan,
      url: url ?? resolveSocketUrl(),
      experimentId: newExperimentId(),
      owner: ownerId(),
      WebSocketImpl,
      onChange: next => {
        if (controllerRef.current === controller) deliver(next)
      },
    })
    controllerRef.current = controller
    controller.connect()
  }, [WebSocketImpl, url, deliver, detach])

  const leave = useCallback(() => {
    detach()
    setState(null)
  }, [detach])

  const pause = useCallback(() => controllerRef.current?.pause(), [])
  const resume = useCallback(() => controllerRef.current?.resume(), [])
  const extend = useCallback(weeks => controllerRef.current?.extend(weeks), [])
  const configure = useCallback((index, levers) => controllerRef.current?.configure(index, levers), [])
  const track = useCallback((index, action, householdId) => controllerRef.current?.track(index, action, householdId), [])

  useEffect(() => detach, [detach])

  return useMemo(() => ({
    state, start, pause, resume, extend, configure, track, leave,
  }), [state, start, pause, resume, extend, configure, track, leave])
}

export default useExperiment
