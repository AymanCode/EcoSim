// Where the dashboards open their WebSocket. Shared by the classic dashboard
// (src/App.jsx) and the live towns (src/next/live/endpoint.js re-exports it):
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
