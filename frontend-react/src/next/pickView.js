// Which app the page opens: the new Run screen at ?view=next, else the
// classic dashboard.
export function pickView(search) {
  return new URLSearchParams(search ?? '').get('view') === 'next' ? 'next' : 'classic'
}
