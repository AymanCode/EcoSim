// Which app the page opens: the new Run screen at ?view=next, else the
// classic dashboard. The Run screen (src/next/) is the current UI; the classic
// dashboard (src/App.jsx) is frozen legacy UI, even though it is still the URL
// default.
export function pickView(search) {
  return new URLSearchParams(search ?? '').get('view') === 'next' ? 'next' : 'classic'
}
