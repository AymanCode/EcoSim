import { toneVar } from './tones.js'

// Ported from the `wealthbars` markup in
// docs/superpowers/specs/2026-09-06-prototype.html: a `.stack` of proportional
// segments (2px gaps come from `.stack` in tokens.css) plus a `.legend` row
// with a swatch, label and percentage per segment.
export default function CompositionBar({ segments }) {
  const total = segments.reduce((sum, s) => sum + s.value, 0) || 1

  return (
    <div>
      <div className="stack">
        {segments.map((s, i) => (
          <div key={i} style={{ width: `${(s.value / total) * 100}%`, background: toneVar(s.tone) }} />
        ))}
      </div>
      <div className="legend" style={{ marginTop: 8, justifyContent: 'space-between' }}>
        {segments.map((s, i) => (
          <span key={i}>
            <i style={{ background: toneVar(s.tone) }} />
            {s.label} <b className="mono" style={{ color: toneVar('ink') }}>{s.value.toFixed(1)}%</b>
          </span>
        ))}
      </div>
    </div>
  )
}
