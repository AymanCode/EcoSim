import Delta from './Delta.jsx'
import Pill from './Pill.jsx'
import useCountUp from './useCountUp.js'
import { deltaVs } from '../telemetry.js'

// Ported from the `.hero` block in
// docs/superpowers/specs/2026-09-06-prototype.html (e.g. the "Net fiscal
// balance" hero at line 566): `.lbl` label, a large count-up `.v`, then a
// `.meta` row with the delta and an optional status pill, followed by
// `children` — usually a chart filling the rest of the card. Unlike
// `.tile`, the tone class lands on `.v` itself (`.hero .v.good`/`.crit`),
// not on the wrapper.
export default function HeroMetric({
  label,
  value,
  format = (v) => v,
  history,
  tone,
  tick,
  upBad = false,
  unit = 'pct',
  pill,
  children,
}) {
  const display = useCountUp(value)
  const { diff, pct } = deltaVs(value, history, 0)

  return (
    <div className="hero">
      <div className="lbl">{label}</div>
      <div className={['v', 'num', tone].filter(Boolean).join(' ')}>{format(display)}</div>
      <div className="meta">
        <Delta diff={diff} pct={pct} unit={unit} upBad={upBad} vsTick={tick} />
        {pill && <Pill tone={pill.tone}>{pill.label}</Pill>}
      </div>
      {children}
    </div>
  )
}
