import useMeasured from '../../charts/useMeasured.js'
import { COPY, formatMoney, formatMoneyShort, townTextColor } from '../catalog.js'
import { countedAt, everMeasured } from '../data/derive.js'
import { countedNote } from '../narration.js'
import Card from './Card.jsx'
import { isNumber, niceScale, r1, textWidth } from './chartKit.js'
import '../next.css'

const KEYS = ['wealthP10', 'wealthP50', 'wealthP90']
const ROW = 54
const TOP = 6
const FALLBACK_WIDTH = 520

// Town i's last count of the three savings figures: { p10, p50, p90 }, or
// null when any is missing.
function rungs(arm, tick) {
  const [p10, p50, p90] = KEYS.map(key => countedAt(arm, key, tick)?.value ?? null)
  return [p10, p50, p90].every(isNumber) ? { p10, p50, p90 } : null
}

function Ladder({ arms, readings }) {
  const [ref, size] = useMeasured()
  const W = Math.max(200, size.width || FALLBACK_WIDTH)
  const H = TOP + arms.length * ROW + 20
  const known = readings.filter(Boolean)
  const scale = niceScale(Math.min(0, ...known.map(r => r.p10)), Math.max(0, ...known.map(r => r.p90)), 4)
  const left = Math.ceil(Math.max(...arms.map(arm => textWidth(arm.label, 13, true)))) + 14
  const right = 26
  const x = value => left + ((value - scale.lo) / (scale.hi - scale.lo || 1)) * (W - left - right)

  return (
    <div ref={ref} className="nx-vchart" aria-hidden="true">
      <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} focusable="false">
        {scale.ticks.map(value => (
          <g key={value}>
            <line className="nx-vgrid" x1={r1(x(value))} x2={r1(x(value))} y1={TOP} y2={H - 18} />
            <text className="nx-vaxl" x={r1(x(value))} y={H - 4} textAnchor="middle">{formatMoneyShort(value)}</text>
          </g>
        ))}
        {arms.map((arm, i) => {
          const reading = readings[i]
          const cy = TOP + i * ROW + ROW / 2
          return (
            <g key={arm.label}>
              <text className="nx-vrowl" x={0} y={cy + 4}>{arm.label}</text>
              {reading ? (
                <>
                  <rect className="nx-wbar" x={r1(x(reading.p10))} y={cy - 7} width={r1(Math.max(1, x(reading.p90) - x(reading.p10)))} height={14} rx={7} style={{ fill: arm.color, stroke: arm.color }} />
                  <circle className="nx-wdot" cx={r1(x(reading.p50))} cy={cy} r={7} style={{ fill: arm.color }} />
                  <text className="nx-vval" x={r1(x(reading.p10))} y={cy + 22} textAnchor="middle">{formatMoney(reading.p10)}</text>
                  <text className="nx-vval" x={r1(x(reading.p90))} y={cy + 22} textAnchor="middle">{formatMoney(reading.p90)}</text>
                  <text className="nx-vval is-mid" x={r1(x(reading.p50))} y={cy - 12} textAnchor="middle" style={{ fill: townTextColor(arm.color) }}>{formatMoney(reading.p50)}</text>
                </>
              ) : (
                <text className="nx-vval" x={left} y={cy + 4}>{COPY.numbers.notMeasured}</text>
              )}
            </g>
          )
        })}
      </svg>
    </div>
  )
}

// "The savings ladder" (mockup 06): per town, a bar from the savings of the
// poorest tenth (wealthP10) to the richest tenth (wealthP90) with a dot for
// the middle household (wealthP50), on one shared axis, as last counted. It
// opens big on typical savings, with the three figures as chips.
export default function WealthLadder({ arms, tick, onSeeBig, className = '' }) {
  const copy = COPY.numbers.ladder
  const measured = KEYS.every(key => everMeasured(arms, key))
  const readings = arms.map(arm => rungs(arm, tick))
  const asOf = arms.map(arm => countedAt(arm, 'wealthP50', tick)?.asOfTick).find(Number.isFinite) ?? null

  let body
  if (!measured) body = <p className="nx-quiet">{COPY.numbers.notMeasured}</p>
  else if (!readings.some(Boolean)) body = <p className="nx-quiet">{COPY.numbers.noWeeks}</p>
  else {
    body = (
      <>
        <p className="def is-top">{copy.lead}</p>
        <Ladder arms={arms} readings={readings} />
        <p className="nx-sr">
          {arms.map((arm, i) => (readings[i]
            ? copy.alt(arm.label, formatMoney(readings[i].p10), formatMoney(readings[i].p50), formatMoney(readings[i].p90))
            : `${arm.label}: ${COPY.numbers.notMeasured}.`)).join(' ')}
        </p>
        <p className="nx-foot">{countedNote(asOf)}</p>
      </>
    )
  }
  return <Card title={copy.title} metricKey="wealthP50" measured={measured} onSeeBig={onSeeBig} className={className}>{body}</Card>
}
