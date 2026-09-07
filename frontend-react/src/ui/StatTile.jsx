import Delta from './Delta.jsx'
import Sparkline from '../charts/Sparkline.jsx'
import useCountUp from './useCountUp.js'
import { deltaVs, series } from '../telemetry.js'

// Ported from the `tile()` helper in
// docs/superpowers/specs/2026-09-06-prototype.html: `.tile` > `.l` (label +
// delta) / `.v` (count-up value) / `.foot` (caption + sparkline). The delta
// compares the live `value` against the most recently recorded sample in
// `history` (backN(history, 0), i.e. the last entry) since `value` itself is
// the not-yet-appended current tick.
export default function StatTile({
  label,
  value,
  format = (v) => v,
  history,
  tick,
  tone,
  upBad = false,
  caption,
  unit = 'pct',
}) {
  const display = useCountUp(value)
  const { diff, pct } = deltaVs(value, history, 0)
  const sparkData = [...series(history).map((d) => d.value).slice(-24), value]
  const sparkTone = tone === 'warn' || tone === 'crit' ? tone : 'acc'

  return (
    <div className={['tile', tone].filter(Boolean).join(' ')}>
      <div className="l">
        <span>{label}</span>
        <Delta diff={diff} pct={pct} unit={unit} upBad={upBad} vsTick={tick} />
      </div>
      <div className="v num">{format(display)}</div>
      <div className="foot">
        <span className="cap">{caption}</span>
        <Sparkline data={sparkData} tone={sparkTone} />
      </div>
    </div>
  )
}
