import { useId } from 'react'
import { COPY, METRICS, WARMUP_TICKS, formatMetric } from '../catalog.js'
import { compareAt, seriesUpTo } from '../data/derive.js'
import '../next.css'

const VIEW_W = 200
const VIEW_H = 36

const toPath = (points, x, y) => points
  .map((point, i) => `${i ? 'L' : 'M'}${x(point.tick).toFixed(1)} ${y(point.value).toFixed(1)}`)
  .join(' ')

// One sparkline per town through `tick`, all on one scale so heights compare.
// The scale comes from the real weeks; the warm-up weeks are drawn dashed
// inside a "setting up" band (`band`, a percent of the width, or null).
function sparklines(arms, metricKey, tick) {
  const lines = arms.map(arm => seriesUpTo(arm, metricKey, tick).filter(point => point.value !== null))
  const points = lines.flat()
  if (!points.length) return { paths: lines.map(() => null), band: null }
  const live = points.filter(point => point.tick > WARMUP_TICKS)
  const values = (live.length ? live : points).map(point => point.value)
  const ticks = points.map(point => point.tick)
  const lo = Math.min(...values)
  const hi = Math.max(...values)
  const t0 = Math.min(...ticks)
  const t1 = Math.max(...ticks)
  const x = t => (t1 > t0 ? 2 + ((t - t0) / (t1 - t0)) * (VIEW_W - 4) : VIEW_W / 2)
  const y = v => (hi > lo ? 4 + (1 - (v - lo) / (hi - lo)) * (VIEW_H - 8) : VIEW_H / 2)
  const paths = lines.map(line => {
    if (!line.length) return null
    const firstLive = line.findIndex(point => point.tick > WARMUP_TICKS)
    const hasWarm = line[0].tick <= WARMUP_TICKS
    const warm = firstLive < 0 ? line : hasWarm ? line.slice(0, firstLive + 1) : []
    const real = firstLive < 0 ? [] : line.slice(firstLive)
    return { warm: warm.length ? toPath(warm, x, y) : null, live: real.length ? toPath(real, x, y) : null }
  })
  let band = null
  if (t0 <= WARMUP_TICKS) band = t1 <= WARMUP_TICKS ? 100 : Math.round((x(WARMUP_TICKS) / VIEW_W) * 1000) / 10
  return { paths, band }
}

export default function StatCard({ metricKey, arms, tick }) {
  const clipId = `nx-mini-${useId().replace(/:/g, '')}`
  const metric = METRICS[metricKey] ?? { name: metricKey, meaning: '' }
  const rows = compareAt(arms, metricKey, tick)
  const { paths, band } = sparklines(arms, metricKey, tick)

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
      <div className="nx-mini-wrap" aria-hidden="true">
        {band !== null && (
          <div className="nx-mini-warm" style={{ width: `${band}%` }}><span>{COPY.chart.settingUp}</span></div>
        )}
        <svg className="nx-mini" viewBox={`0 0 ${VIEW_W} ${VIEW_H}`} preserveAspectRatio="none" focusable="false">
          <defs>
            <clipPath id={clipId}><rect x={-2} y={0} width={VIEW_W + 4} height={VIEW_H} /></clipPath>
          </defs>
          <g clipPath={`url(#${clipId})`}>
            {paths.map((path, i) => path && (
              <g key={arms[i].label}>
                {path.warm && <path className="is-warm" d={path.warm} style={{ stroke: arms[i].color }} />}
                {path.live && <path d={path.live} style={{ stroke: arms[i].color }} />}
              </g>
            ))}
          </g>
        </svg>
      </div>
      <p className="def">{metric.meaning}</p>
    </div>
  )
}
