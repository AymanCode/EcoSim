import { useEffect, useRef, useState } from 'react'

const reducedMotion = () => globalThis.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false
const resting = folded => folded ? 'folded' : 'row'

// Fold entries leave before their rows grow, and rows finish collapsing before
// their entries return. First render is already at rest. No per-tick animation.
export default function useFoldLayout(rows, foldedKeys, openKeys = []) {
  const starts = useRef(new Map())
  // Opening a row is a transition input even if promotion already removed it
  // from foldedKeys. A jump must not wait inside the outgoing entry's fade.
  const target = rows.map(row => `${row.key}:${foldedKeys.includes(row.key)}:${openKeys.includes(row.key)}`).join('|')
  const [layout, setLayout] = useState(() => ({ target, entries: Object.fromEntries(rows.map(row => [row.key, { folded: foldedKeys.includes(row.key), phase: resting(foldedKeys.includes(row.key)) }])) }))
  if (layout.target !== target) {
    const snap = reducedMotion()
    setLayout({ target, entries: Object.fromEntries(rows.map(row => {
      const folded = foldedKeys.includes(row.key)
      const previous = layout.entries[row.key]
      let phase = previous?.phase
      if (!previous || snap) phase = resting(folded)
      else if (!folded && openKeys.includes(row.key) && phase === 'leaving-entry') phase = 'entering-row'
      else if (previous.folded !== folded) {
        // An outgoing entry has not exposed its row yet. Reverse only that
        // entry's fade; a growing/collapsing row reverses its CSS transition.
        phase = folded
          ? previous.phase === 'leaving-entry' ? 'entering-entry' : 'leaving-row'
          : openKeys.includes(row.key) || previous.phase === 'leaving-row' ? 'entering-row' : 'leaving-entry'
      }
      return [row.key, { folded, phase, promoted: !folded && openKeys.includes(row.key) ? true : previous?.promoted && !folded }]
    })) })
  }
  useEffect(() => {
    const timers = Object.entries(layout.entries).flatMap(([key, entry]) => {
      const next = { 'leaving-entry': ['entering-row', 160], 'entering-row': ['row', 420], 'leaving-row': ['entering-entry', 420], 'entering-entry': ['folded', 160] }[entry.phase]
      if (!next) { starts.current.delete(key); return [] }
      if (starts.current.get(key)?.phase !== entry.phase) starts.current.set(key, { phase: entry.phase, at: Date.now() })
      return [setTimeout(() => setLayout(current => {
        if (current.entries[key]?.phase !== entry.phase) return current
        return { ...current, entries: { ...current.entries, [key]: { ...current.entries[key], phase: reducedMotion() ? resting(entry.folded) : next[0], promoted: next[0] === 'entering-row' || current.entries[key].promoted } } }
      }), Math.max(0, next[1] - (Date.now() - starts.current.get(key).at)))]
    })
    return () => timers.forEach(clearTimeout)
  }, [layout.entries])
  return layout.entries
}
