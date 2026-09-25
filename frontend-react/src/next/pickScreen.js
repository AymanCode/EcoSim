// Which screen the new app opens on: the recorded demo when the query has a
// `demo` key (?view=next&demo), else Set up.
export function pickScreen(search) {
  return new URLSearchParams(search ?? '').has('demo') ? 'demo' : 'setup'
}
