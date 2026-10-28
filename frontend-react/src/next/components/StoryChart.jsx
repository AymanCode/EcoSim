import { useId, useState } from 'react'
import useMeasured from '../../charts/useMeasured.js'
import { COPY, COUNTED_EVERY_5, METRICS, NUMBER_DERIVED_ROWS, STORY_METRICS, WARMUP_TICKS, formatEndLabel, formatMetric, formatMetricShort, townTextColor } from '../catalog.js'
import { countedAt, countedSeriesUpTo, seriesUpTo, valueAt } from '../data/derive.js'
import { policyChangesByWeek, policyMarkerLabel, startNote, weekLabel } from '../narration.js'
import '../next.css'

// Port of the mockup's storyChart: one number for every town from week 0 to
// the horizon, the weeks not yet played shaded, direct end labels, a marker
// per policy change. The warm-up weeks sit in a hatched "setting up" band with
// the lines dashed there, and the y-axis ignores them. Label widths are
// estimated (no DOM measuring), so every label keeps a little slack.
// The numbers sheet reuses it for any METRICS key: `metricKeys` lists its
// chips (STORY_METRICS by default, as on the Run screen), and with
// `countedWeeks` a COUNTED_EVERY_5 number is drawn only at the weeks it was
// counted, its dot on the last count, and its table lists counts.
// `inline` omits the card, heading and chips, adds a local chart key, and
// gives every recorded week in the table. `hideEndLabels` and `interactive`
// independently opt into label-free lines and a pointer/keyboard crosshair.
// All three default off so the Run screen keeps its existing output.
const HEIGHT = 320
const PAD_TOP = 44
const PAD_RIGHT = 156
const COMPACT_BELOW = 560
const PHONE_BELOW = 400
const PAD_BOTTOM = 30
const FALLBACK_WIDTH = 720
const WEEKS_PER_YEAR = 52
const TABLE_EVERY = 13
const END_GAP = 18
const LINE_H = 16
const round = value => Math.round(value * 10) / 10

// Rough text widths for the two label styles, in px.
const textWidth = (text, size = 12.5, bold = false) => String(text).length * size * (bold ? 0.56 : 0.52)

const STEP_FLOOR = { per100: 1, count: 1, money: 1, price: 0.01, ratio: 0.01, outOf100: 1, percent: 1 }

function isMultiple(step, floor) {
  if (!floor) return true
  const ratio = step / floor
  return Math.abs(ratio - Math.round(ratio)) < 1e-9
}

// Gridlines on round numbers: the smallest nice step that needs six lines or fewer.
function yScaleFor(values, format) {
  let lo = values.length ? Math.min(...values) : 0
  let hi = values.length ? Math.max(...values) : 1
  if (format === 'per100' || format === 'count') lo = Math.min(0, lo)
  if (hi - lo < 1e-9) {
    const pad = Math.abs(hi) * 0.1 || 1
    lo -= format === 'per100' && lo === 0 ? 0 : pad
    hi += pad
  }
  const floor = STEP_FLOOR[format] ?? 0
  const magnitude = 10 ** Math.floor(Math.log10((hi - lo) / 6))
  const steps = [1, 2, 2.5, 5, 10, 20, 25, 50, 100]
    .map(m => m * magnitude)
    .filter(step => step >= floor && isMultiple(step, floor))
  for (const step of steps) {
    const start = Math.floor(lo / step + 1e-9) * step
    const end = Math.ceil(hi / step - 1e-9) * step
    const count = Math.round((end - start) / step) + 1
    if (count <= 6) {
      const ticks = Array.from({ length: count }, (_, i) => Number((start + i * step).toFixed(6)))
      return { lo: start, hi: end, ticks }
    }
  }
  return { lo, hi, ticks: [lo, hi] }
}

function xMarks(horizon) {
  if (horizon >= WEEKS_PER_YEAR) {
    const years = Math.ceil(horizon / WEEKS_PER_YEAR)
    return {
      labels: Array.from({ length: years }, (_, i) => {
        const start = i * WEEKS_PER_YEAR
        const span = Math.min(WEEKS_PER_YEAR, horizon - start)
        return { at: start + span / 2, text: COPY.chart.year(i + 1) }
      }).filter(label => horizon - (label.at - WEEKS_PER_YEAR / 2) >= WEEKS_PER_YEAR / 4),
      bounds: Array.from({ length: years - 1 }, (_, i) => (i + 1) * WEEKS_PER_YEAR).filter(at => at < horizon),
    }
  }
  const step = horizon > 26 ? 13 : 4
  const labels = []
  for (let week = step; week <= horizon; week += step) labels.push({ at: week, text: COPY.chart.week(week) })
  return { labels, bounds: [] }
}

// Splits a town's points at the end of warm-up. The dashed part runs on to the
// first real week so the two parts join.
function splitWarmUp(points) {
  const firstLive = points.findIndex(point => point.tick > WARMUP_TICKS)
  const hasWarm = points.length > 0 && points[0].tick <= WARMUP_TICKS
  if (firstLive < 0) return { warm: points, live: [] }
  return { warm: hasWarm ? points.slice(0, firstLive + 1) : [], live: points.slice(firstLive) }
}

function pathFor(points, x, y) {
  let d = ''
  let open = false
  for (const point of points) {
    if (point.value === null) {
      open = false
      continue
    }
    d += `${open ? 'L' : 'M'}${round(x(point.tick))} ${round(y(point.value))} `
    open = true
  }
  return d.trim()
}

// Push labels apart to at least `gap` px, keeping them between top and bottom.
function spread(items, gap, top, bottom) {
  const sorted = [...items].sort((a, b) => a.y - b.y)
  for (let i = 1; i < sorted.length; i += 1) {
    if (sorted[i].y - sorted[i - 1].y < gap) sorted[i].y = sorted[i - 1].y + gap
  }
  const overflow = sorted.length ? sorted[sorted.length - 1].y - bottom : 0
  if (overflow > 0) {
    sorted[sorted.length - 1].y = bottom
    for (let i = sorted.length - 2; i >= 0; i -= 1) {
      if (sorted[i + 1].y - sorted[i].y < gap) sorted[i].y = sorted[i + 1].y - gap
    }
  }
  const underflow = sorted.length ? top - sorted[0].y : 0
  if (underflow > 0) sorted.forEach(item => { item.y += underflow })
  return sorted
}

const overlaps = (a, b) => a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h

function place(candidates, taken) {
  const free = candidates.find(box => !taken.some(other => overlaps(box, other)))
  return free ?? null
}

function MetricChips({ metricKey, metricKeys, onMetricChange }) {
  if (metricKeys.length < 2) return null
  return (
    <div className="nx-chips" role="group" aria-label={COPY.chart.chips}>
      {metricKeys.map(key => (
        <button
          key={key}
          type="button"
          className="nx-mchip"
          aria-pressed={key === metricKey}
          onClick={() => onMetricChange?.(key)}
        >
          {METRICS[key].name}
        </button>
      ))}
    </div>
  )
}

// The weeks of the counts up to `tick`, at least TABLE_EVERY weeks apart, and
// the last one, with each town's count made that week (null when a town has no
// count that week). A row never shows an earlier count under a later week,
// even when the frame of a count's week is missing.
function countRows(arms, metricKey, tick) {
  const byTown = arms.map(arm => new Map(countedSeriesUpTo(arm, metricKey, tick).map(point => [point.tick, point.value])))
  const counts = [...new Set(byTown.flatMap(points => [...points.keys()]))].sort((a, b) => a - b)
  const weeks = []
  for (const week of counts) if (!weeks.length || week - weeks[weeks.length - 1] >= TABLE_EVERY) weeks.push(week)
  if (counts.length && weeks[weeks.length - 1] !== counts[counts.length - 1]) weeks.push(counts[counts.length - 1])
  return weeks.map(week => ({ week, values: byTown.map(points => points.get(week) ?? null) }))
}

function weeklyRows(arms, metricKey, tick) {
  const weeks = []
  for (let week = TABLE_EVERY; week <= tick; week += TABLE_EVERY) weeks.push(week)
  if (tick >= 1 && weeks[weeks.length - 1] !== tick) weeks.push(tick)
  return weeks.map(week => ({ week, values: arms.map(arm => valueAt(arm, metricKey, week)) }))
}

function ValueTable({ arms, metricKey, tick, name, counted, inline }) {
  let rows
  if (inline) {
    const byTown = arms.map(arm => new Map((counted ? countedSeriesUpTo : seriesUpTo)(arm, metricKey, tick).map(point => [point.tick, point.value])))
    const weeks = [...new Set(byTown.flatMap(points => [...points.keys()]))].sort((a, b) => a - b)
    rows = weeks.map(week => ({ week, values: byTown.map(points => points.get(week) ?? null) }))
  } else rows = counted ? countRows(arms, metricKey, tick) : weeklyRows(arms, metricKey, tick)
  const table = (
    <table className={inline ? undefined : 'nx-sr'}>
      <caption>{inline ? COPY.numbers.chart.table(name) : counted ? COPY.chart.countedCaption(name) : COPY.chart.tableCaption(name)}</caption>
      <thead>
        <tr>
          <th scope="col">{inline ? COPY.numbers.chart.week : COPY.chart.weekColumn}</th>
          {arms.map(arm => <th key={arm.label} scope="col">{arm.label}</th>)}
        </tr>
      </thead>
      <tbody>
        {rows.map(({ week, values }) => (
          <tr key={week}>
            <th scope="row">{weekLabel(week)}</th>
            {arms.map((arm, i) => <td key={arm.label}>{inline && values[i] === null ? COPY.numbers.notRecorded : formatMetric(metricKey, values[i])}</td>)}
          </tr>
        ))}
      </tbody>
    </table>
  )
  return inline ? <div className="nx-sr">{table}</div> : table
}

export default function StoryChart({
  arms, metricKey, tick, horizon, onMetricChange, playing = false, metricKeys = STORY_METRICS, countedWeeks = false,
  hideEndLabels = false, inline = false, interactive = false, className = '',
}) {
  const [ref, size] = useMeasured()
  const [hoverWeek, setHoverWeek] = useState(null)
  const uid = useId().replace(/:/g, '')
  const clipId = `nx-plot-${uid}`
  const linesClipId = `nx-lines-${uid}`
  const hatchId = `nx-hatch-${uid}`
  const tooltipId = `nx-tooltip-${uid}`
  const metric = METRICS[metricKey] ?? { name: metricKey, meaning: '', format: 'count' }
  const end = Math.max(1, Number(horizon) || 0, tick)
  const counted = countedWeeks && COUNTED_EVERY_5.includes(metricKey)

  const W = size.width || FALLBACK_WIDTH
  const H = HEIGHT
  // Phones keep a text identity at each endpoint; wider narrow charts also
  // show the value on a second line. Inline numbers charts keep their layout.
  const phone = !inline && W < PHONE_BELOW
  const compact = !phone && W < COMPACT_BELOW
  const endTownLabel = arm => phone ? arm.label.replace(/^Town ([A-Z])$/, '$1') : arm.label
  const values = arms.flatMap(arm => (arm.series?.[metricKey] ?? []).filter(value => value !== null))
  // The y-axis is set by the real weeks; warm-up values may fall outside it.
  const liveValues = arms.flatMap(arm => (arm.series?.[metricKey] ?? [])
    .filter((value, i) => value !== null && arm.ticks[i] > WARMUP_TICKS))
  const scale = yScaleFor(liveValues.length ? liveValues : values, metric.format)
  const yLabels = scale.ticks.map(value => formatMetricShort(metricKey, value))
  const padL = Math.max(44, Math.ceil(Math.max(...yLabels.map(label => textWidth(label, 12))) + 14))
  const endLines = item => {
    if (phone) return [endTownLabel(item.arm)]
    const value = formatEndLabel(metricKey, item.value)
    return compact ? [item.arm.label, value] : [COPY.chart.endLabel(item.arm.label, value)]
  }
  // Counted markers follow the plotted observation, including a recovery
  // after a missing reading; ordinary counts retain the week they were made.
  const readings = arms
    .map(arm => {
      if (!counted) return { arm, value: valueAt(arm, metricKey, tick), at: tick }
      const count = countedAt(arm, metricKey, tick)
      const point = countedSeriesUpTo(arm, metricKey, tick).at(-1)
      return { arm, value: count?.value ?? null, at: point?.tick ?? tick }
    })
    .filter(item => item.value !== null)
  // Sized for the widest label the whole recording could need, so the plot
  // keeps its width while the replay plays.
  const endWidth = phone
    ? Math.max(0, ...arms.map(arm => textWidth(endTownLabel(arm), 13, true)))
    : compact
    ? Math.max(0, ...arms.map(arm => textWidth(arm.label, 13, true)), ...values.map(value => textWidth(formatEndLabel(metricKey, value), 13, true)))
    : 0
  const plotRight = W - (hideEndLabels ? 16 : phone || compact ? Math.ceil(endWidth) + 20 : PAD_RIGHT)
  const x = t => padL + (t / end) * (plotRight - padL)
  const y = v => PAD_TOP + (1 - (v - scale.lo) / (scale.hi - scale.lo || 1)) * (H - PAD_TOP - PAD_BOTTOM)
  const plotTop = PAD_TOP - 10
  const plotBottom = H - PAD_BOTTOM
  const clampY = value => Math.min(plotBottom, Math.max(plotTop, value))
  const cursorX = x(tick)
  const marks = xMarks(end)
  const warmEnd = Math.min(WARMUP_TICKS, end)

  // End labels first: they carry the numbers.
  const endHeight = compact ? 2 * LINE_H : END_GAP
  const ends = spread(
    readings.map(item => ({ ...item, dotX: x(item.at), dotY: clampY(y(item.value)), y: clampY(y(item.value)) })),
    endHeight,
    PAD_TOP - 4 + (compact ? LINE_H / 2 : 0),
    H - PAD_BOTTOM - 6 - (compact ? LINE_H / 2 : 0),
  ).map(item => {
    const lines = endLines(item)
    const w = Math.max(...lines.map(line => textWidth(line, 13, true))) + 4
    return { ...item, lines, box: { x: cursorX + 10, y: item.y - endHeight / 2, w, h: endHeight } }
  })
  const taken = hideEndLabels ? [] : ends.map(item => item.box)

  const note = inline && tick <= WARMUP_TICKS ? null : startNote(arms.length)
  const noteX = phone ? 0 : padL
  if (note) taken.push({ x: noteX, y: 6, w: textWidth(note, 12.5, true), h: 18 })

  // "setting up" sits at the top of the warm-up band, or its foot if a label is there.
  let warmLabel = null
  if (warmEnd > 0) {
    const w = textWidth(COPY.chart.settingUp, 12)
    const candidates = [
      { x: x(0) + 6, y: PAD_TOP - 6, w, h: 18 },
      { x: x(0) + 6, y: H - PAD_BOTTOM - 22, w, h: 18 },
    ]
    warmLabel = place(candidates, taken) ?? candidates[0]
    taken.push(warmLabel)
  }

  // "the weeks ahead" sits at the foot of the shading, or its top if a label is there.
  let ahead = null
  const aheadWidth = textWidth(COPY.chart.weeksAhead, 12)
  if (tick < end && x(end) - cursorX > aheadWidth + 20) {
    // Just past the cursor if free, else just past whichever label is in the way.
    const starts = [cursorX + 8, ...taken.map(box => box.x + box.w + 10).filter(at => at > cursorX + 8)].sort((a, b) => a - b)
    const spot = place(starts.flatMap(at => [
      { x: at, y: H - PAD_BOTTOM - 22, w: aheadWidth, h: 18 },
      { x: at, y: PAD_TOP - 6, w: aheadWidth, h: 18 },
    ]).filter(box => box.x + box.w <= x(end)), taken)
    if (spot) {
      taken.push(spot)
      ahead = { x: spot.x - cursorX, y: spot.y + 13 }
    }
  }

  // Policy markers, one per town per week of change, each label in the first
  // free slot beside its line.
  const markers = []
  arms.forEach(arm => {
    for (const [week, changes] of policyChangesByWeek(arm, change => change.tick <= tick && change.tick <= end)) {
      const at = x(week)
      const lines = policyMarkerLabel(arm, changes)
      const w = Math.max(...lines.map((line, i) => textWidth(line, 12.5, i === 0))) + 4
      const h = lines.length * LINE_H + 2
      const candidates = []
      for (let top = PAD_TOP + 2; top + h <= H - PAD_BOTTOM - 4; top += h + 6) {
        candidates.push({ x: at + 7, y: top, w, h, anchor: 'start' })
        candidates.push({ x: at - 7 - w, y: top, w, h, anchor: 'end' })
      }
      const fits = candidates.filter(box => box.x >= padL - 4 && box.x + box.w <= W)
      const spot = phone ? null : place(fits, taken)
      if (spot) taken.push(spot)
      markers.push({ key: `${arm.label}:${week}`, arm, at, lines, spot })
    }
  })

  // Hover never reaches the not-yet-played weeks. For counted metrics the
  // crosshair uses the last actual count, just as the endpoint does.
  const selectedWeek = interactive && hoverWeek !== null ? Math.max(0, Math.min(tick, hoverWeek)) : null
  const hoverValues = selectedWeek === null ? [] : arms.map(arm => {
    const count = counted ? countedAt(arm, metricKey, selectedWeek) : null
    const point = counted ? countedSeriesUpTo(arm, metricKey, selectedWeek).at(-1) : null
    return { arm, value: counted ? count?.value ?? null : valueAt(arm, metricKey, selectedWeek), at: point?.tick ?? selectedWeek }
  })
  const pointerMove = event => {
    const bounds = event.currentTarget.getBoundingClientRect()
    const px = ((event.clientX - bounds.left) / (bounds.width || W)) * W
    if (px < padL || px > plotRight) return setHoverWeek(null)
    setHoverWeek(Math.max(0, Math.min(tick, Math.round(((px - padL) / (plotRight - padL || 1)) * end))))
  }
  const inspectWeek = event => {
    let week
    if (event.key === 'ArrowLeft') week = (selectedWeek ?? tick) - 1
    else if (event.key === 'ArrowRight') week = (selectedWeek ?? tick) + 1
    else if (event.key === 'Home') week = arms.reduce((first, arm) => Math.min(first, arm.ticks[0] ?? tick), tick)
    else if (event.key === 'End') week = tick
    else if (event.key === 'Escape') {
      setHoverWeek(null)
      return // Escape still reaches the sheet's close handler.
    } else return
    event.preventDefault()
    setHoverWeek(Math.max(0, Math.min(tick, week)))
  }
  const interaction = interactive ? {
    tabIndex: 0,
    role: 'group',
    'aria-label': COPY.numbers.chart.tooltip(metric.name),
    'aria-describedby': selectedWeek === null ? undefined : tooltipId,
    onPointerMove: pointerMove,
    onPointerLeave: () => setHoverWeek(null),
    onFocus: () => setHoverWeek(tick),
    onBlur: () => setHoverWeek(null),
    onKeyDown: inspectWeek,
  } : {}

  return (
    <div className={`${inline ? 'nx-storyc nx-story-inline' : 'nx-card nx-storyc'}${className ? ` ${className}` : ''}`}>
      {!inline && <>
        <h3>{metric.name}</h3>
        <p className="cs">{metric.meaning}</p>
        <MetricChips metricKey={metricKey} metricKeys={metricKeys} onMetricChange={onMetricChange} />
      </>}
      {phone && markers.length > 0 && <div className="nx-phone-rules cs" style={{ marginTop: 8 }}>
        {markers.map(({ key, lines }) => <div key={key}>
          <b>{lines[0]}</b>{' '}{lines.slice(1).join(' ')}
        </div>)}
      </div>}
      <div key="plot" ref={ref} className={`nx-chart${playing ? ' is-playing' : ''}`} style={{ height: H }} {...interaction}>
        <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} aria-hidden="true" focusable="false">
          <defs>
            <clipPath id={clipId}>
              <rect x={padL} y={0} width={Math.max(0, x(end) - padL)} height={H} />
            </clipPath>
            <clipPath id={linesClipId}>
              <rect x={padL - 6} y={plotTop} width={Math.max(0, x(end) - padL + 12)} height={plotBottom - plotTop} />
            </clipPath>
            <pattern id={hatchId} width={6} height={6} patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
              <rect className="nx-hatch-bg" width={6} height={6} />
              <line className="nx-hatch" x1={0} y1={0} x2={0} y2={6} />
            </pattern>
          </defs>
          <g className="nx-yaxis">
            {scale.ticks.map((value, i) => (
              <g key={value}>
                <line x1={padL} x2={plotRight} y1={round(y(value))} y2={round(y(value))} />
                <text x={padL - 8} y={round(y(value) + 4)} textAnchor="end">{yLabels[i]}</text>
              </g>
            ))}
          </g>
          <g className="nx-xaxis">
            {marks.bounds.map(at => <line key={at} className="nx-bound" x1={round(x(at))} x2={round(x(at))} y1={PAD_TOP - 10} y2={H - PAD_BOTTOM} />)}
            <line x1={padL} x2={plotRight} y1={H - PAD_BOTTOM} y2={H - PAD_BOTTOM} />
            {marks.labels.map(label => (
              <text key={label.text} x={round(x(label.at))} y={H - 8} textAnchor="middle">{label.text}</text>
            ))}
          </g>
          {warmEnd > 0 && (
            <rect className="nx-warm" x={round(x(0))} y={plotTop} width={round(x(warmEnd) - x(0))} height={plotBottom - plotTop} fill={`url(#${hatchId})`} />
          )}
          <g clipPath={`url(#${clipId})`}>
            <g className="nx-cursor" style={{ transform: `translateX(${round(cursorX)}px)` }}>
              <rect className="nx-future" x={0} y={PAD_TOP - 10} width={Math.max(0, x(end) - padL)} height={H - PAD_TOP - PAD_BOTTOM + 10} />
              <line className="nx-now" x1={0} x2={0} y1={PAD_TOP - 10} y2={H - PAD_BOTTOM} />
              {ahead && <text className="nx-ahead" x={round(ahead.x)} y={round(ahead.y)}>{COPY.chart.weeksAhead}</text>}
            </g>
          </g>
          <g className="nx-rules">
            {markers.map(({ key, arm, at }) => (
              <line key={key} x1={round(at)} x2={round(at)} y1={PAD_TOP - 4} y2={H - PAD_BOTTOM} style={{ stroke: arm.color }} />
            ))}
          </g>
          <g clipPath={`url(#${linesClipId})`}>
            {arms.map(arm => {
              const points = counted ? countedSeriesUpTo(arm, metricKey, tick) : seriesUpTo(arm, metricKey, tick)
              const { warm, live } = splitWarmUp(points)
              const warmD = pathFor(warm, x, y)
              const liveD = pathFor(live, x, y)
              return (
                <g key={arm.label}>
                  {warmD && <path className="nx-warmline" d={warmD} style={{ stroke: arm.color }} />}
                  {liveD && <path className="nx-line" d={liveD} style={{ stroke: arm.color }} />}
                </g>
              )
            })}
          </g>
          {note && <text className="nx-ann is-bold" x={noteX} y={20}>{note}</text>}
          {warmLabel && <text className="nx-warm-label" x={round(warmLabel.x)} y={round(warmLabel.y + 13)}>{COPY.chart.settingUp}</text>}
          {markers.map(({ key, arm, at, lines, spot }) => (
            <g key={key} className="nx-marker">
              <path d={`M${round(at - 5)} ${H - PAD_BOTTOM} L${round(at + 5)} ${H - PAD_BOTTOM} L${round(at)} ${H - PAD_BOTTOM + 7} Z`} style={{ fill: arm.color }} />
              {spot && lines.map((line, i) => (
                <text
                  key={line}
                  className={`nx-ann${i === 0 ? ' is-bold' : ''}`}
                  x={round(spot.anchor === 'start' ? spot.x : spot.x + spot.w)}
                  y={round(spot.y + 12 + i * LINE_H)}
                  textAnchor={spot.anchor}
                >
                  {line}
                </text>
              ))}
            </g>
          ))}
          {ends.map(item => (
            <g key={item.arm.label}>
              {!hideEndLabels && Math.abs(item.y - item.dotY) > 4 && (
                <path className="nx-leader" d={`M${round(item.dotX + 5)} ${round(item.dotY)} L${round(cursorX + 9)} ${round(item.y)}`} style={{ stroke: item.arm.color }} />
              )}
              <circle className="nx-dot" cx={round(item.dotX)} cy={round(item.dotY)} r={5} style={{ fill: item.arm.color }} />
              {!hideEndLabels && <text className="nx-endl" x={round(cursorX + 12)} y={round(item.y + 4.5 - ((item.lines.length - 1) * LINE_H) / 2)} style={{ fill: townTextColor(item.arm.color) }}>
                {item.lines.length === 1 ? item.lines[0] : item.lines.map((line, i) => (
                  <tspan key={line} x={round(cursorX + 12)} dy={i ? LINE_H : 0}>{line}</tspan>
                ))}
              </text>}
            </g>
          ))}
          {selectedWeek !== null && <g className="nx-crosshair" clipPath={`url(#${linesClipId})`}>
            <line x1={round(x(selectedWeek))} x2={round(x(selectedWeek))} y1={plotTop} y2={plotBottom} style={{ stroke: 'var(--nx-ink3)', strokeWidth: 1, strokeDasharray: '3 3' }} />
            {hoverValues.filter(item => item.value !== null).map(item => (
              <circle key={item.arm.label} className="nx-dot" cx={round(x(item.at))} cy={round(clampY(y(item.value)))} r={4} style={{ fill: item.arm.color }} />
            ))}
          </g>}
        </svg>
        {selectedWeek !== null && <div id={tooltipId} role="tooltip" className="nx-chart-tooltip" style={{
          position: 'absolute', top: 0, left: Math.max(0, Math.min(W - 220, x(selectedWeek) + 10)),
          maxWidth: '100%', padding: '8px 10px', border: '1px solid var(--nx-line2)', borderRadius: 8,
          background: 'var(--nx-panel)', color: 'var(--nx-ink)', fontSize: 12, pointerEvents: 'none', zIndex: 1,
        }}>
          <b>{weekLabel(selectedWeek)}</b>
          {hoverValues.map(item => <div key={item.arm.label} style={{ color: townTextColor(item.arm.color) }}>
            {COPY.numbers.column(item.arm.label, item.value === null
              ? (inline && seriesUpTo(item.arm, NUMBER_DERIVED_ROWS[metricKey]?.source ?? metricKey, selectedWeek).some(point => Number.isFinite(point.value)) ? COPY.numbers.missingReading : COPY.numbers.notMeasured)
              : formatMetric(metricKey, item.value))}
          </div>)}
        </div>}
      </div>
      {inline && <ul className="nx-skey" aria-label={COPY.numbers.chart.label}>
        {warmEnd > 0 && <li><i className="nx-ckey-warm" aria-hidden="true" />{COPY.numbers.chart.warm}</li>}
        {tick < end && <li><i aria-hidden="true" style={{ background: 'var(--nx-future)' }} />{COPY.numbers.chart.future}</li>}
      </ul>}
      <ValueTable arms={arms} metricKey={metricKey} tick={tick} name={metric.name} counted={counted} inline={inline} />
    </div>
  )
}
