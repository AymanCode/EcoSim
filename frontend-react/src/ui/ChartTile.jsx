import Delta from './Delta.jsx'
import TimeSeries from '../charts/TimeSeries.jsx'
import useCountUp from './useCountUp.js'
import { deltaVs, series } from '../telemetry.js'

// Ported from the `ctile()` helper in
// docs/superpowers/specs/2026-09-06-prototype.html: the same `.l`/`.v`
// header as StatTile's `tile()`, but the footer is a full-size TimeSeries
// chart (`.tile.ctile` + `.cap`) instead of a caption/sparkline row.
export default function ChartTile({
  label,
  value,
  format = (v) => v,
  history,
  tick,
  tone,
  upBad = false,
  caption,
  unit = 'pct',
  name,
}) {
  const display = useCountUp(value)
  const { diff, pct } = deltaVs(value, history, 0)
  const chartTone = tone === 'warn' || tone === 'crit' ? tone : 'acc'

  return (
    <div className={['tile', 'ctile', tone].filter(Boolean).join(' ')}>
      <div className="l">
        <span>{label}</span>
        <Delta diff={diff} pct={pct} unit={unit} upBad={upBad} vsTick={tick} />
      </div>
      <div className="v num">{format(display)}</div>
      <div className="cap">{caption}</div>
      <TimeSeries
        series={[{ data: series(history), tone: chartTone, name: name || label }]}
        format={format}
        axes={false}
        n={120}
      />
    </div>
  )
}
