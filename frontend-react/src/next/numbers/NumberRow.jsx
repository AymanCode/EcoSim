import { memo, useEffect, useId, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { COPY, COUNTED_EVERY_5, WARMUP_TICKS, formatMetric } from '../catalog.js'
import { weekLabel } from '../narration.js'
import { differenceWords, rowDefinition, rowStatus, rowValues } from './compare.js'
import { rowHistory } from './rowHistory.js'
import './numberRow.css'

const SPARK_WIDTH = 84
const SPARK_HEIGHT = 26
const isNumber = value => typeof value === 'number' && Number.isFinite(value)
const keyOf = row => typeof row === 'string' ? row : row.key
const rounded = value => Math.round(value * 10) / 10
const countNote = asOfTick => COPY.numbers.counted(isNumber(asOfTick) && asOfTick >= 1 ? weekLabel(asOfTick) : null)
const reducedMotion = () => globalThis.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false

function rowIsVisible(node) {
  for (let parent = node; parent; parent = parent.parentElement) {
    if (parent.hidden) return false
    // A leaving row is still visibly shrinking, despite being inert already.
    if (parent.classList.contains('nx-row-motion') && parent.dataset.state === 'leaving-row') continue
    if (parent.getAttribute('aria-hidden') === 'true' || parent.hasAttribute('inert')) return false
    if (parent.classList.contains('nx-row-motion') && ['folded', 'leaving-entry', 'entering-entry'].includes(parent.dataset.state)) return false
  }
  return true
}

// The sparkline is a preview only; opening the row replaces it with the full
// visual. Missing observations break the line instead of becoming zeroes.
function Sparkline({ arms, series, tick }) {
  const known = series.flatMap(points => points.filter(point => isNumber(point.value)).map(point => point.value))
  const low = known.length ? Math.min(...known) : 0
  const high = known.length ? Math.max(...known) : 1
  const span = high - low || 1
  const end = Math.max(WARMUP_TICKS + 2, tick)
  const x = at => 2 + ((at - WARMUP_TICKS - 1) / (end - WARMUP_TICKS - 1)) * (SPARK_WIDTH - 4)
  const y = value => high === low ? SPARK_HEIGHT / 2 : SPARK_HEIGHT - 3 - ((value - low) / span) * (SPARK_HEIGHT - 6)
  const pathFor = points => {
    let connected = false
    return points.map(point => {
      if (!isNumber(point.value)) { connected = false; return '' }
      const command = connected ? 'L' : 'M'
      connected = true
      return `${command}${rounded(x(point.tick))} ${rounded(y(point.value))}`
    }).join(' ')
  }
  const paths = series.map(pathFor)

  return (
    <svg width={SPARK_WIDTH} height={SPARK_HEIGHT} viewBox={`0 0 ${SPARK_WIDTH} ${SPARK_HEIGHT}`} aria-hidden="true" focusable="false">
      {arms.map((arm, i) => {
        const points = series[i].filter(point => isNumber(point.value))
        const same = paths.slice(0, i).includes(paths[i])
        return (
          <g key={arm.label}>
            <path d={paths[i]} fill="none" stroke={arm.color} strokeWidth={1.5} strokeLinejoin="round" strokeDasharray={same ? '3 3' : undefined} />
            {points.length === 1 && <circle cx={rounded(x(points[0].tick))} cy={rounded(y(points[0].value))} r={2} fill={arm.color} />}
          </g>
        )
      })}
    </svg>
  )
}

function SparklineTable({ arms, row, series, name }) {
  const key = keyOf(row)
  const byTown = series.map(points => new Map(points.map(point => [point.tick, point.value])))
  const weeks = [...new Set(series.flatMap(points => points.map(point => point.tick)))].sort((a, b) => a - b)
  if (!weeks.length) return null
  return (
    <div className="nx-sr">
      <table>
        <caption>{COPY.numbers.chart.table(name)}</caption>
        <thead><tr><th scope="col">{COPY.numbers.chart.week}</th>{arms.map(arm => <th scope="col" key={arm.label}>{arm.label}</th>)}</tr></thead>
        <tbody>{weeks.map(week => (
          <tr key={week}>
            <th scope="row">{weekLabel(week)}</th>
            {arms.map((arm, i) => <td key={arm.label}>{isNumber(byTown[i].get(week)) ? formatMetric(key, byTown[i].get(week)) : COPY.numbers.notMeasured}</td>)}
          </tr>
        ))}</tbody>
      </table>
    </div>
  )
}

function DifferenceCell({ id, row, readings, tick }) {
  if (readings.length < 2) return null
  const base = readings[0]
  return (
    <span id={id} className="nx-number-differences">
      {tick > WARMUP_TICKS && readings.slice(1).map(reading => {
        const status = rowStatus(row, base.value, reading.value, tick)
        const words = differenceWords(row, base.value, reading.value)
        return (
          <span className="nx-number-difference" key={reading.label}>
            {readings.length > 2 && <span className="nx-number-comparison-town"><i style={{ background: reading.color }} aria-hidden="true" />{reading.label}</span>}
            {(status === 'better' || status === 'worse') && <span className={`nx-number-tag is-${status}`}>{COPY.numbers.tags[status]}</span>}
            {words && <span>{words}</span>}
          </span>
        )
      })}
    </span>
  )
}

/** A controlled, expandable measure. Visuals are supplied as children or by
 * renderVisual; this component does not know which chart a row opens.
 * `id` identifies the whole row; its focusable header is `${id}-button`.
 */
export default function NumberRow({ id, row, arms, tick, open = false, onToggle, children, renderVisual }) {
  const uid = useId().replace(/:/g, '')
  const rowRef = useRef(null)
  const key = keyOf(row)
  const rowId = id ?? `nx-number-${uid}-${key}`
  const inputs = useMemo(() => ({ rowId, row, arms, tick, open, onToggle, children, renderVisual }), [rowId, row, arms, tick, open, onToggle, children, renderVisual])
  const [frame, setFrame] = useState(() => ({ active: false, inputs }))
  // eslint-disable-next-line react-hooks/exhaustive-deps -- ancestor phases can change on any commit without changing this row's props
  useLayoutEffect(() => {
    // Fold phases belong to the sheet's ancestor. Check after its attributes
    // commit, before paint. Stage inputs until then, so even a tick arriving
    // with the final fold phase cannot build a now-hidden history.
    const visible = rowIsVisible(rowRef.current)
    if (visible !== frame.active || (visible && frame.inputs !== inputs)) setFrame({ active: visible, inputs })
  })
  return <div ref={rowRef} id={rowId} className={`nx-number-row${open ? ' is-open' : ''}${arms.length === 1 ? ' is-one-town' : ''}`} data-metric={key} style={{ '--nx-towns': arms.length }}>
    <NumberRowContents {...frame.inputs} active={frame.active} />
  </div>
}

const NumberRowContents = memo(function NumberRowContents({ rowId, row, arms, tick, open, active, onToggle, children, renderVisual }) {
  const regionRef = useRef(null)
  const [retained, setRetained] = useState(open)
  if (open && !retained) setRetained(true)
  const mounted = active && (open || (retained && !reducedMotion()))
  useEffect(() => {
    if (open || !retained) return undefined
    const motion = globalThis.matchMedia?.('(prefers-reduced-motion: reduce)')
    const finish = () => setRetained(false)
    const duration = getComputedStyle(regionRef.current).getPropertyValue('--nx-change').trim()
    const milliseconds = parseFloat(duration) * (duration.endsWith('ms') ? 1 : 1000)
    const timer = setTimeout(finish, motion?.matches ? 0 : Number.isFinite(milliseconds) ? milliseconds : 420)
    const onMotion = event => { if (event.matches) finish() }
    motion?.addEventListener?.('change', onMotion)
    return () => { clearTimeout(timer); motion?.removeEventListener?.('change', onMotion) }
  }, [open, retained])
  const key = keyOf(row)
  const buttonId = `${rowId}-button`
  const regionId = `${rowId}-expanded`
  const meaningId = `${rowId}-meaning`
  const differencesId = `${rowId}-differences`
  const metric = rowDefinition(row)
  const readings = active ? rowValues(arms, row, tick) : []
  const displayReadings = readings.map((reading, index) => {
    const sameAs = tick > WARMUP_TICKS && isNumber(reading.value)
      ? readings.slice(0, index).find(previous => isNumber(previous.value) && previous.formatted === reading.formatted)
      : null
    return { ...reading, sameAs, displayed: sameAs ? COPY.numbers.sameAsTown(sameAs.label) : reading.formatted }
  })
  const series = active && !open ? arms.map(arm => rowHistory(arm, row, tick).filter(point => point.tick > WARMUP_TICKS)) : null
  const counted = COUNTED_EVERY_5.includes(key)
  const countWeeks = [...new Set(readings.map(reading => reading.asOfTick).filter(isNumber))]
  const describedBy = [
    ...readings.map((_, index) => `${rowId}-value-${index}`),
    ...(arms.length > 1 ? [differencesId] : []),
    ...(open ? [meaningId] : []),
  ].join(' ')
  const toggle = () => onToggle?.(!open)
  const onKeyDown = event => {
    if (event.key !== 'Enter' && event.key !== ' ') return
    // Prevent the browser's follow-up click so one key press toggles once.
    event.preventDefault()
    if (!event.repeat) toggle()
  }

  return (
    <>
      <button
        id={buttonId}
        type="button"
        className={`nx-number-button nx-number-grid${arms.length === 1 ? ' is-one-town' : ''}`}
        aria-label={metric.name}
        aria-expanded={open}
        aria-controls={regionId}
        aria-describedby={describedBy || undefined}
        title={metric.meaning}
        onClick={toggle}
        onKeyDown={onKeyDown}
      >
        <span className="nx-number-name">{metric.name}{metric.sub && <small>{metric.sub}</small>}</span>
        {displayReadings.map((reading, index) => (
          <span id={`${rowId}-value-${index}`} className={`nx-number-value${!isNumber(reading.value) ? ' is-not-measured' : ''}${reading.sameAs ? ' is-same-value' : ''}`} key={reading.label} aria-label={COPY.numbers.difference.town(reading.label, reading.displayed)}>
            {reading.displayed}
          </span>
        ))}
        <DifferenceCell id={differencesId} row={row} readings={readings} tick={tick} />
        <span className="nx-number-spark" aria-hidden="true" style={{ visibility: open ? 'hidden' : undefined }}>
          {series && <Sparkline arms={arms} series={series} tick={tick} />}
        </span>
        <span className="nx-number-chevron" aria-hidden="true" />
      </button>
      {series && <SparklineTable arms={arms} row={row} series={series} name={metric.name} />}
      <div
        ref={regionRef}
        id={regionId}
        className="nx-number-expand-motion"
        role="region"
        aria-labelledby={buttonId}
        aria-hidden={!open}
        inert={!open}
        data-state={open ? 'open' : 'closed'}
        onTransitionEnd={event => {
          if (!open && event.target === event.currentTarget && event.propertyName === 'grid-template-rows') setRetained(false)
        }}
      >
        <div className="nx-number-expand-clip">
          <div className="nx-number-expanded">
            {mounted && <>
              {renderVisual ? renderVisual({ row, arms, tick }) : children}
              <p id={meaningId} className="nx-number-meaning">{metric.meaning}</p>
              {counted && (
                <p className="nx-number-counted">{countWeeks.length < 2
                  ? countNote(countWeeks[0] ?? null)
                  : readings.map(reading => COPY.numbers.difference.town(reading.label, countNote(reading.asOfTick))).join(COPY.numbers.fold.join)}</p>
              )}
            </>}
          </div>
        </div>
      </div>
    </>
  )
})
