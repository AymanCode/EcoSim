import { useId } from 'react'
import useMeasured from '../../charts/useMeasured.js'
import { COPY, METRICS, WARMUP_TICKS, formatEndLabel, formatMetric, formatMoney, formatMoneyShort, townTextColor } from '../catalog.js'
import { countedSeriesUpTo, everMeasured, valueAt } from '../data/derive.js'
import { weekLabel } from '../narration.js'
import Card, { Hatch, Values } from './Card.jsx'
import { isNumber, niceScale, r1, spreadLabels, textWidth } from './chartKit.js'
import '../next.css'

const KEY = 'townHallCash'
const WEEKS = 52
const WEEKS_PER_YEAR = 52
const H = 220
const PAD_TOP = 14
const PAD_BOTTOM = 24
const LINE_H = 15
const FALLBACK_WIDTH = 640

// The first week of the stretch below zero that runs up to `tick` (setting
// up included: a debt from week 5 is owed since week 5); null when the town
// has money this week.
function owingSince(arm, tick) {
  if (!(valueAt(arm, KEY, tick) < 0)) return null
  const points = countedSeriesUpTo(arm, KEY, tick)
  let since = null
  for (let i = points.length - 1; i >= 0 && points[i].value < 0; i -= 1) since = points[i].tick
  return since
}

// "$1.35 million" for a start of a million or more, else to the thousand
// ("$446,000"), and a start under a thousand as it is.
function about(value) {
  if (Math.abs(value) >= 1e6) return COPY.numbers.cash.million((value / 1e6).toFixed(2))
  return formatMoney(Math.abs(value) >= 1000 ? Math.round(value / 1000) * 1000 : value)
}

function Lines({ arms, lines, first, tick, scale, rings }) {
  const [ref, size] = useMeasured()
  const uid = useId().replace(/:/g, '')
  const hatchId = `nx-cash-hatch-${uid}`
  const clipId = `nx-cash-clip-${uid}`
  const W = Math.max(240, size.width || FALLBACK_WIDTH)
  const last = first + WEEKS - 1
  const yLabels = scale.ticks.map(value => formatMoneyShort(value))
  const left = Math.max(40, Math.ceil(Math.max(...yLabels.map(label => textWidth(label, 11.5)))) + 12)
  const ends = arms.map((arm, i) => {
    const point = lines[i][lines[i].length - 1]
    return point ? { arm, point, value: formatEndLabel(KEY, point.value) } : null
  }).filter(Boolean)
  const right = Math.ceil(Math.max(40, ...ends.flatMap(end => [textWidth(end.arm.label, 13, true), textWidth(end.value, 13, true)]))) + 14
  const x = week => left + ((week - (first - 1)) / WEEKS) * (W - left - right)
  const y = value => PAD_TOP + (1 - (value - scale.lo) / (scale.hi - scale.lo || 1)) * (H - PAD_TOP - PAD_BOTTOM)
  const top = PAD_TOP - 4
  const bottom = H - PAD_BOTTOM
  const clampY = value => Math.max(top, Math.min(bottom, y(value)))
  const bounds = []
  for (let week = Math.ceil(first / WEEKS_PER_YEAR) * WEEKS_PER_YEAR; week < last; week += WEEKS_PER_YEAR) bounds.push(week)
  const placed = spreadLabels(ends.map(end => ({ ...end, y: clampY(end.point.value) })), LINE_H * 2 + 2, top + LINE_H, bottom - 4)
  const bandLabel = y(scale.lo) - y(0) >= 14
  const startLabel = weekLabel(first)

  return (
    <div ref={ref} className="nx-vchart" aria-hidden="true">
      <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} focusable="false">
        <defs>
          <Hatch id={hatchId} />
          <clipPath id={clipId}><rect x={left - 3} y={top} width={W - left - right + 6} height={bottom - top} /></clipPath>
        </defs>
        {first <= WARMUP_TICKS && (
          <rect className="nx-vwarm" x={r1(x(first - 1))} y={top} width={r1(x(WARMUP_TICKS) - x(first - 1))} height={bottom - top} fill={`url(#${hatchId})`} />
        )}
        {tick < last && <rect className="nx-vfuture" x={r1(x(tick))} y={top} width={r1(x(last) - x(tick))} height={bottom - top} />}
        {scale.lo < 0 && (
          <rect className="nx-owes" x={left} y={r1(y(0))} width={r1(W - left - right)} height={r1(y(scale.lo) - y(0))} />
        )}
        {scale.ticks.map((value, i) => (
          <g key={value}>
            <line className={`nx-vgrid${value === 0 ? ' is-zero' : ''}`} x1={left} x2={W - right} y1={r1(y(value))} y2={r1(y(value))} />
            <text className="nx-cy" x={left - 8} y={r1(y(value) + 4)} textAnchor="end">{yLabels[i]}</text>
          </g>
        ))}
        {bounds.map(week => (
          <g key={week}>
            {/* Between the last week of a year and the first of the next. */}
            <line className="nx-vbound" x1={r1(x(week + 0.5))} x2={r1(x(week + 0.5))} y1={top} y2={bottom} />
            {x(week + 0.5) + 4 > left + textWidth(startLabel, 11.5) + 10 && (
              <text className="nx-cx" x={r1(x(week + 0.5) + 4)} y={H - 6}>{COPY.chart.year(week / WEEKS_PER_YEAR + 1)}</text>
            )}
          </g>
        ))}
        <text className="nx-cx" x={left} y={H - 6}>{startLabel}</text>
        <g clipPath={`url(#${clipId})`}>
          {arms.map((arm, i) => {
            const warm = lines[i].filter(point => point.tick <= WARMUP_TICKS)
            const live = lines[i].filter(point => point.tick > WARMUP_TICKS)
            if (warm.length && live.length) warm.push(live[0])
            const d = points => points.map((point, k) => `${k ? 'L' : 'M'}${r1(x(point.tick))} ${r1(y(point.value))}`).join(' ')
            return (
              <g key={arm.label}>
                {warm.length > 0 && <path className="nx-cwarm" d={d(warm)} style={{ stroke: arm.color }} />}
                {live.length > 0 && <path className="nx-cline" d={d(live)} style={{ stroke: arm.color }} />}
              </g>
            )
          })}
        </g>
        {scale.lo < 0 && bandLabel && <text className="nx-owes-label" x={left + 6} y={r1(y(scale.lo) - 5)}>{COPY.numbers.cash.band}</text>}
        <line className="nx-vnow" x1={r1(x(tick))} x2={r1(x(tick))} y1={top - 2} y2={bottom} />
        {rings.map(ring => (
          <circle key={ring.arm.label} className="nx-cring" cx={r1(x(ring.tick))} cy={r1(y(ring.value))} r={4.5} style={{ stroke: ring.arm.color }} />
        ))}
        {ends.map(end => (
          <circle key={end.arm.label} className="nx-cdot" cx={r1(x(end.point.tick))} cy={r1(clampY(end.point.value))} r={4} style={{ fill: end.arm.color }} />
        ))}
        {placed.map(end => (
          <text key={end.arm.label} className="nx-cend" x={r1(x(end.point.tick) + 10)} y={r1(end.y - 3)} style={{ fill: townTextColor(end.arm.color) }}>
            <tspan x={r1(x(end.point.tick) + 10)}>{end.arm.label}</tspan>
            <tspan x={r1(x(end.point.tick) + 10)} dy={LINE_H}>{end.value}</tspan>
          </text>
        ))}
      </svg>
    </div>
  )
}

// Town hall cash (mockup 06): the last 52 weeks of every town's balance.
// Below zero is a red "owes" band, drawn only when a town's cash is below
// zero somewhere in these weeks, and the first week of a debt that runs to
// this week is ringed. The scale is set by the weeks after setting up: a
// starting balance that would flatten it is told in a note, not drawn as a
// point. It opens big on the whole run.
export default function CashChart({ arms, tick, onSeeBig, className = '' }) {
  const metric = METRICS[KEY]
  const copy = COPY.numbers.cash
  const measured = everMeasured(arms, KEY)
  const now = Math.floor(tick)
  const first = Math.max(1, now - WEEKS + 1)
  const lines = arms.map(arm => countedSeriesUpTo(arm, KEY, now).filter(point => point.tick >= first))
  const drawn = lines.flat()
  const live = drawn.filter(point => point.tick > WARMUP_TICKS)
  const scale = niceScale(
    Math.min(0, ...drawn.map(point => point.value)),
    Math.max(0, ...(live.length ? live : drawn).map(point => point.value)),
    5,
  )
  const since = arms.map(arm => owingSince(arm, now))
  const rings = arms.map((arm, i) => {
    const week = since[i]
    const point = week !== null && week >= first ? lines[i].find(entry => entry.tick === week) : null
    return point ? { arm, tick: point.tick, value: point.value } : null
  }).filter(Boolean)
  const starts = arms.map(arm => countedSeriesUpTo(arm, KEY, now)[0]?.value).filter(isNumber)
  const startNote = starts.length === arms.length && starts.some(value => value > scale.hi)
    ? copy.startNote(copy.started(arms.map(arm => arm.label), starts.map(about)), first > 1)
    : null
  const owed = arms.map((arm, i) => (since[i] === null ? null : copy.owed(arm.label, weekLabel(since[i]), rings.some(ring => ring.arm === arm))))
    .filter(Boolean)
  const trend = arms.map((arm, i) => {
    const line = lines[i]
    if (!line.length) return null
    const start = line[0]
    const end = line[line.length - 1]
    const shown = value => formatMetric(KEY, value)
    return start === end
      ? COPY.numbers.trendOne(arm.label, shown(end.value), weekLabel(end.tick))
      : COPY.numbers.trend(arm.label, shown(start.value), weekLabel(start.tick), shown(end.value), weekLabel(end.tick))
  }).filter(Boolean).join(' ')

  let body
  if (!measured) body = <p className="nx-quiet">{COPY.numbers.notMeasured}</p>
  else if (!drawn.length) body = <p className="nx-quiet">{COPY.numbers.noWeeks}</p>
  else {
    body = (
      <>
        <Values arms={arms} texts={arms.map(arm => formatMetric(KEY, valueAt(arm, KEY, now)))} />
        <Lines arms={arms} lines={lines} first={first} tick={now} scale={scale} rings={rings} />
        <p className="nx-sr">{trend}</p>
        <p className="def">{[metric.meaning, ...owed].join(' ')}</p>
        {startNote && <p className="nx-foot">{startNote}</p>}
      </>
    )
  }
  return <Card title={metric.name} metricKey={KEY} measured={measured} onSeeBig={onSeeBig} className={className}>{body}</Card>
}
