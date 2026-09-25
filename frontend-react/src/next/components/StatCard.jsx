import { METRICS, formatMetric } from '../catalog.js'
import { compareAt, seriesUpTo } from '../data/derive.js'
import '../next.css'

const VIEW_W = 200
const VIEW_H = 36

// One sparkline per town through `tick`, all on one scale so heights compare.
function sparklines(arms, metricKey, tick) {
  const lines = arms.map(arm => seriesUpTo(arm, metricKey, tick).filter(point => point.value !== null))
  const points = lines.flat()
  if (!points.length) return lines.map(() => null)
  const values = points.map(point => point.value)
  const ticks = points.map(point => point.tick)
  const lo = Math.min(...values)
  const hi = Math.max(...values)
  const t0 = Math.min(...ticks)
  const t1 = Math.max(...ticks)
  const x = t => (t1 > t0 ? 2 + ((t - t0) / (t1 - t0)) * (VIEW_W - 4) : VIEW_W / 2)
  const y = v => (hi > lo ? 4 + (1 - (v - lo) / (hi - lo)) * (VIEW_H - 8) : VIEW_H / 2)
  return lines.map(line => (line.length
    ? line.map((point, i) => `${i ? 'L' : 'M'}${x(point.tick).toFixed(1)} ${y(point.value).toFixed(1)}`).join(' ')
    : null))
}

export default function StatCard({ metricKey, arms, tick }) {
  const metric = METRICS[metricKey] ?? { name: metricKey, meaning: '' }
  const rows = compareAt(arms, metricKey, tick)
  const paths = sparklines(arms, metricKey, tick)

  return (
    <div className="nx-stat">
      <h4>{metric.name}</h4>
      <div className="pair">
        {rows.map(row => (
          <div className="nx-pv" key={row.label}>
            <b><i style={{ background: row.color }} aria-hidden="true" />{formatMetric(metricKey, row.value)}</b>
            <small>{row.label}</small>
          </div>
        ))}
      </div>
      <svg className="nx-mini" viewBox={`0 0 ${VIEW_W} ${VIEW_H}`} preserveAspectRatio="none" aria-hidden="true" focusable="false">
        {paths.map((d, i) => d && <path key={arms[i].label} d={d} style={{ stroke: arms[i].color }} />)}
      </svg>
      <p className="def">{metric.meaning}</p>
    </div>
  )
}
