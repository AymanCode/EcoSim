// Where the live towns connect, and the ids that tie their sessions together.

// Mirrors the classic dashboard (resolveWebSocketEndpoint in src/App.jsx):
// VITE_WS_URL when set, else /ws on the page's own host (the Vite dev proxy or
// nginx forwards it), else the backend's default port.
export function resolveSocketUrl(env = import.meta.env, location = typeof window === 'undefined' ? undefined : window.location) {
  const configured = String(env?.VITE_WS_URL ?? '').trim()
  if (configured) return configured
  if (location?.host) {
    const protocol = location.protocol === 'https:' ? 'wss' : 'ws'
    return `${protocol}://${location.host}/ws`
  }
  return 'ws://localhost:8002/ws'
}

// The server groups an experiment's sessions by this id (at most 64 characters).
export function newExperimentId(now = Date.now(), random = Math.random) {
  return `exp-${now.toString(36)}-${Math.floor(random() * 36 ** 6).toString(36).padStart(6, '0')}`
}

const OWNER_KEY = 'ecosim-owner'
let tabOwner = null

function randomOwner() {
  const uuid = globalThis.crypto?.randomUUID?.()
  return `owner-${uuid ?? `${Math.random().toString(36).slice(2)}${Math.random().toString(36).slice(2)}`}`.slice(0, 64)
}

// The experiment owner, stable for this tab: kept in sessionStorage when the
// browser allows it, else for as long as this module lives.
export function ownerId() {
  try {
    const stored = globalThis.sessionStorage.getItem(OWNER_KEY)
    if (stored) return stored
  } catch {
    // Storage is blocked or missing: fall back to the module's id.
  }
  tabOwner ??= randomOwner()
  try {
    globalThis.sessionStorage.setItem(OWNER_KEY, tabOwner)
  } catch {
    // As above.
  }
  return tabOwner
}
