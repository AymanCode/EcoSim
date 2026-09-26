import { useId } from 'react'
import useMeasured from '../../charts/useMeasured.js'
import { COPY, COUNTED_EVERY_5, METRICS, WARMUP_TICKS, formatMetric } from '../catalog.js'
import { countedAt, countedSeriesUpTo, everMeasured, valueAt } from '../data/derive.js'
import { countedNote, weekLabel } from '../narration.js'
import Card, { Values } from './Card.jsx'
import '../next.css'

// Port of mockup 06's tile: a number's name, each town's value with its colour
// dot, and a sparkline over the whole run. The setting-up weeks are a hatched
// band with the lines dashed in it, the weeks still to come are shaded, and a
// cursor marks the week shown. A COUNTED_EVERY_5 number is drawn only at the
// weeks it was counted and says when it was last counted. The chart is drawn
// at its measured width so its dots stay round.
const PAD = { l: 2, r: 2, t: 5, b: 5 }
const FALLBACK_WIDTH = 240
const MIN_WIDTH = 140
const r1 = value => Math.round(value * 10) / 10
const r2 = value => Math.round(value * 100) / 100

const pathOf = (points, x, y) => points.map((point, i) => `${i ? 'L' : 'M'}${r1(x(point.tick))} ${r1(y(point.value))}`).join(' ')

const sameLine = (a, b) => a.length === b.length && a.every((point, i) => point.tick === b[i].tick && point.value === b[i].value)

// A town's whole recording of a number as chart points, cached on the
// number's series array and the count of recorded weeks: the arrays only grow
// (data/session.js), so a new week recomputes and a replayed week does not.
const RECORDED = new WeakMap()

function recordedPoints(arm, metricKey) {
  const values = arm?.series?.[metricKey]
  if (!values) return []
  const length = arm.ticks?.length ?? 0
  const cached = RECORDED.get(values)
  if (cached && cached.ticks === arm.ticks && cached.length === length) return cached.points
  const points = countedSeriesUpTo(arm, metricKey, Infinity)
  RECORDED.set(values, { ticks: arm.ticks, length, points })
  return points
}

// The y range from the real weeks of the whole recording, so the lines keep
// their places while the clock moves; warm-up values may fall outside it.
function yRange(arms, metricKey) {
  const all = arms.flatMap(arm => recordedPoints(arm, metricKey))
  const live = all.filter(point => point.tick > WARMUP_TICKS)
  const values = (live.length ? live : all).map(point => point.value)
  let lo = Math.min(...values)
  let hi = Math.max(...values)
  const pad = (hi - lo) * 0.12 || Math.abs(hi) * 0.1 || 1
  lo -= pad
  hi += pad
  return { lo, hi }
}

function Sparkline({ arms, metricKey, tick, horizon, height, lines }) {
  const [ref, size] = useMeasured()
  const uid = useId().replace(/:/g, '')
  const clipId = `nx-tclip-${uid}`
  const hatchId = `nx-thatch-${uid}`
  const W = Math.max(MIN_WIDTH, size.width || FALLBACK_WIDTH)
  const H = height
  const x = t => PAD.l + (t / horizon) * (W - PAD.l - PAD.r)
  const { lo, hi } = yRange(arms, metricKey)
  const y = v => PAD.t + (1 - (v - lo) / (hi - lo)) * (H - PAD.t - PAD.b)
  const clampY = v => Math.max(PAD.t - 2, Math.min(H - PAD.b + 2, y(v)))
  const top = PAD.t - 3
  const plotH = H - PAD.t - PAD.b + 6

  return (
    <div ref={ref} className="nx-tchart" aria-hidden="true">
      <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} focusable="false">
        <defs>
          <clipPath id={clipId}>
            <rect x={PAD.l - 3} y={top} width={W - PAD.l - PAD.r + 6} height={plotH} />
          </clipPath>
          <pattern id={hatchId} width={6} height={6} patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <rect className="nx-hatch-bg" width={6} height={6} />
            <line className="nx-hatch" x1={0} y1={0} x2={0} y2={6} />
          </pattern>
        </defs>
        <rect className="nx-twarm-band" x={r2(x(0))} y={top} width={r2(x(Math.min(WARMUP_TICKS, horizon)) - x(0))} height={plotH} fill={`url(#${hatchId})`} />
        {tick < horizon && (
          <rect className="nx-tfuture" x={r2(x(tick))} y={top} width={r2(x(horizon) - x(tick))} height={plotH} />
        )}
        <g clipPath={`url(#${clipId})`}>
          {lines.map((line, i) => {
            const warm = line.filter(point => point.tick <= WARMUP_TICKS)
            const live = line.filter(point => point.tick > WARMUP_TICKS)
            if (warm.length && live.length) warm.push(live[0])
            // A line that repeats an earlier town's is dashed so both show.
            const same = lines.slice(0, i).some(other => sameLine(other, line))
            const color = arms[i].color
            return (
              <g key={arms[i].label}>
                {warm.length > 0 && <path className="nx-twarm" d={pathOf(warm, x, y)} style={{ stroke: color }} />}
                {live.length > 0 && <path className={`nx-tline${same ? ' is-same' : ''}`} d={pathOf(live, x, y)} style={{ stroke: color }} />}
              </g>
            )
          })}
        </g>
        <line className="nx-tnow" x1={r2(x(tick))} x2={r2(x(tick))} y1={top - 2} y2={top + plotH} />
        {lines.map((line, i) => {
          const last = line[line.length - 1]
          return last ? (
            <circle key={arms[i].label} className="nx-tdot" cx={r1(x(last.tick))} cy={r1(clampY(last.value))} r={3.2} style={{ fill: arms[i].color }} />
          ) : null
        })}
      </svg>
    </div>
  )
}

// One sentence per town for screen readers: its first real week (or its
// first week, before then) and the week shown. `lines` are the drawn points.
function trendText(arms, metricKey, lines) {
  return arms.map((arm, index) => {
    const line = lines[index]
    if (!line.length) return null
    const first = line.find(point => point.tick > WARMUP_TICKS) ?? line[0]
    const last = line[line.length - 1]
    const shown = value => formatMetric(metricKey, value)
    return first === last
      ? COPY.numbers.trendOne(arm.label, shown(last.value), weekLabel(last.tick))
      : COPY.numbers.trend(arm.label, shown(first.value), weekLabel(first.tick), shown(last.value), weekLabel(last.tick))
  }).filter(Boolean).join(' ')
}

// Clicking the tile, or Enter or Space on it, calls onSeeBig(metricKey). A
// number the recording never carried says so, and opens nothing.
// `chartNote`, when given, is a sentence drawn in place of the sparkline (a
// price that has not moved); `children` go under the meaning.
export default function Tile({ metricKey, arms, tick, onSeeBig, className = '', height = 56, chartNote = null, children }) {
  const metric = METRICS[metricKey] ?? { name: metricKey, meaning: '', format: 'count' }
  const measured = everMeasured(arms, metricKey)
  const horizon = Math.max(1, tick, ...arms.map(arm => arm.horizon || 0))
  const counted = COUNTED_EVERY_5.includes(metricKey)
  const asOf = counted ? arms.map(arm => countedAt(arm, metricKey, tick)?.asOfTick).find(Number.isFinite) ?? null : null
  const lines = measured && !chartNote ? arms.map(arm => countedSeriesUpTo(arm, metricKey, tick)) : []

  return (
    <Card title={metric.name} metricKey={metricKey} measured={measured} onSeeBig={onSeeBig} className={className}>
      {measured ? (
        <>
          <Values arms={arms} texts={arms.map(arm => formatMetric(metricKey, valueAt(arm, metricKey, tick)))} />
          {chartNote ? <p className="nx-quiet">{chartNote}</p> : (
            <>
              <Sparkline arms={arms} metricKey={metricKey} tick={tick} horizon={horizon} height={height} lines={lines} />
              <p className="nx-sr">{trendText(arms, metricKey, lines)}</p>
            </>
          )}
        </>
      ) : (
        <p className="nx-quiet">{COPY.numbers.notMeasured}</p>
      )}
      <p className="def">{metric.meaning}</p>
      {children}
      {measured && counted && <p className="nx-foot">{countedNote(asOf)}</p>}
    </Card>
  )
}
