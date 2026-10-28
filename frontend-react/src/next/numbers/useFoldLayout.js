import { useEffect, useRef, useState } from 'react'

const reducedMotion = () => globalThis.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false
const resting = folded => folded ? 'folded' : 'row'

// Fold entries fade while their rows grow. Rows finish collapsing before their
// entries return. First render is already at rest. No per-tick animation.
export default function useFoldLayout(rows, foldedKeys, openKeys = []) {
  const starts = useRef(new Map())
  // Opening a row is a transition input even if promotion already removed it
  // from foldedKeys, so a jump can also reverse a collapse.
  const target = rows.map(row => `${row.key}:${foldedKeys.includes(row.key)}:${openKeys.includes(row.key)}`).join('|')
  const [layout, setLayout] = useState(() => ({ target, entries: Object.fromEntries(rows.map(row => [row.key, { folded: foldedKeys.includes(row.key), phase: resting(foldedKeys.includes(row.key)) }])) }))
  if (layout.target !== target) {
    const snap = reducedMotion()
    setLayout({ target, entries: Object.fromEntries(rows.map(row => {
      const folded = foldedKeys.includes(row.key)
      const previous = layout.entries[row.key]
      let phase = previous?.phase
      let leavingEntry = previous?.leavingEntry ?? false
      if (!previous || snap) { phase = resting(folded); leavingEntry = false }
      else if (previous.folded !== folded) {
        // Promotion exposes current row values immediately. Retain only the
        // outgoing fold entry for its shorter fade; reversals retarget the row.
        phase = folded ? 'leaving-row' : 'entering-row'
        leavingEntry = !folded && ['folded', 'entering-entry'].includes(previous.phase)
      }
      return [row.key, { folded, phase, leavingEntry, promoted: !folded && (openKeys.includes(row.key) || previous?.folded) ? true : previous?.promoted && !folded }]
    })) })
  }
  useEffect(() => {
    const timers = Object.entries(layout.entries).flatMap(([key, entry]) => {
      const next = { 'entering-row': ['row', 420], 'leaving-row': ['entering-entry', 420], 'entering-entry': ['folded', 160] }[entry.phase]
      if (!next) { starts.current.delete(key); return [] }
      if (starts.current.get(key)?.phase !== entry.phase) starts.current.set(key, { phase: entry.phase, at: Date.now() })
      const elapsed = Date.now() - starts.current.get(key).at
      const timers = [setTimeout(() => setLayout(current => {
        if (current.entries[key]?.phase !== entry.phase) return current
        return { ...current, entries: { ...current.entries, [key]: { ...current.entries[key], phase: reducedMotion() ? resting(entry.folded) : next[0], leavingEntry: false } } }
      }), Math.max(0, next[1] - elapsed))]
      if (entry.leavingEntry) timers.push(setTimeout(() => setLayout(current => {
        if (current.entries[key]?.phase !== entry.phase || !current.entries[key].leavingEntry) return current
        return { ...current, entries: { ...current.entries, [key]: { ...current.entries[key], leavingEntry: false } } }
      }), Math.max(0, 160 - elapsed)))
      return timers
    })
    return () => timers.forEach(clearTimeout)
  }, [layout.entries])
  return layout.entries
}
