import { toneVar, thresholdTone } from './tones.js'

// Ported from `profileBars` in docs/superpowers/specs/2026-09-06-prototype.html:
// one `.pb` row per dimension with a coloured fill and a median tick (`.md`),
// plus a footer note explaining the tick.
export default function ProfileBars({ dims, median }) {
  return (
    <div>
      {dims.map((d, i) => {
        const pct = Math.round(d.value * 100)
        const medPct = Math.round((median?.[i] ?? 0) * 100)
        const tone = toneVar(thresholdTone(d.value))
        return (
          <div className="pb" key={i}>
            <span>{d.label}</span>
            <div className="tr">
              <div className="fl" style={{ width: `${pct}%`, background: tone }} />
              <i className="md" style={{ left: `${medPct}%` }} />
            </div>
            <span className="nv">{pct}</span>
          </div>
        )
      })}
      <div className="muted" style={{ fontSize: '10.5px', marginTop: 4 }}>tick mark = population median</div>
    </div>
  )
}
