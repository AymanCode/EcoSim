import { useId } from 'react'
import useMeasured from '../../charts/useMeasured.js'
import { COPY, WARMUP_TICKS, formatMoney } from '../catalog.js'
import { everMeasured, valueAt } from '../data/derive.js'
import { weekLabel } from '../narration.js'
import Card, { Bolded, Hatch, SwatchKey, TownName } from './Card.jsx'
import { isNumber, r1, windowStart } from './chartKit.js'
import '../next.css'

const WEEKS = 26
const H = 78
const BASE = H - 2
const FALLBACK_WIDTH = 260
const IN = 'townHallIncome'
const OUT = 'familySupportPaid'

// The window's weeks for one town: [{ tick, in, out }], a missing week null.
function weeksOf(arm, first, last) {
  const rows = []
  for (let week = first; week <= last; week += 1) {
    const recorded = arm.ticks?.includes(week)
    rows.push({ tick: week, in: recorded ? valueAt(arm, IN, week) : null, out: recorded ? valueAt(arm, OUT, week) : null })
  }
  return rows
}

// One town's weeks: two bars a week side by side, the taxes collected (solid)
// and the help paid to families (light), on a scale shared by every town.
function PairedBars({ rows, max, tick, color }) {
  const [ref, size] = useMeasured()
  const hatchId = `nx-io-hatch-${useId().replace(/:/g, '')}`
  const W = Math.max(120, size.width || FALLBACK_WIDTH)
  const slot = W / WEEKS
  const barWidth = Math.max(1.5, (slot - 3) / 2)
  const first = rows[0]?.tick ?? 1
  const x = week => (week - first) * slot + (slot - 2 * barWidth - 1) / 2
  const height = value => (isNumber(value) && value > 0 ? Math.max(1, (value / max) * (BASE - 4)) : 0)
  const warmEnd = Math.min(WARMUP_TICKS, tick)

  return (
    <div ref={ref} className="nx-vchart" aria-hidden="true">
      <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} focusable="false">
        <defs><Hatch id={hatchId} /></defs>
        {first <= WARMUP_TICKS && (
          <rect className="nx-vwarm" x={0} y={0} width={r1((warmEnd - first + 1) * slot)} height={BASE} fill={`url(#${hatchId})`} />
        )}
        {rows.map(row => {
          const inHeight = height(row.in)
          const outHeight = height(row.out)
          return (
            <g key={row.tick}>
              {isNumber(row.in) && <rect className="nx-io-in" x={r1(x(row.tick))} y={r1(BASE - inHeight)} width={r1(barWidth)} height={r1(inHeight)} style={{ fill: color }} />}
              {isNumber(row.out) && <rect className="nx-io-out" x={r1(x(row.tick) + barWidth + 1)} y={r1(BASE - outHeight)} width={r1(barWidth)} height={r1(outHeight)} style={{ fill: color }} />}
            </g>
          )
        })}
        <line className="nx-vmid" x1={0} x2={W} y1={BASE} y2={BASE} />
      </svg>
    </div>
  )
}

function WeeksTable({ arms, perTown }) {
  const copy = COPY.numbers
  const shown = value => (isNumber(value) ? formatMoney(value) : copy.notRecorded)
  return (
    // In a block box: a table grows to fit its cells whatever its width, so
    // on its own it would widen the page at phone width.
    <div className="nx-sr">
      <table>
        <caption>{copy.inOut.table}</caption>
        <thead>
          <tr>
            <th scope="col">{copy.week}</th>
            {arms.flatMap(arm => [
              <th scope="col" key={`${arm.label}-i`}>{copy.column(arm.label, copy.inOut.inColumn)}</th>,
              <th scope="col" key={`${arm.label}-o`}>{copy.column(arm.label, copy.inOut.outColumn)}</th>,
            ])}
          </tr>
        </thead>
        <tbody>
          {(perTown[0] ?? []).map((row, index) => (
            <tr key={row.tick}>
              <th scope="row">{weekLabel(row.tick)}</th>
              {perTown.flatMap((rows, i) => [
                <td key={`${arms[i].label}-i`}>{shown(rows[index].in)}</td>,
                <td key={`${arms[i].label}-o`}>{shown(rows[index].out)}</td>,
              ])}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// "Money in and out, week by week": per town, the last 26 weeks of the taxes
// the town hall collected (townHallIncome) beside the help it paid to
// families (familySupportPaid, the welcome payments of the first weeks
// included). Neither is everything the town hall takes in or pays out, so
// the note says the two do not add up to the change in its cash, and their
// gap is never named. It opens big on the taxes, with both flows as chips.
export default function MoneyInOut({ arms, tick, onSeeBig, className = '' }) {
  const copy = COPY.numbers.inOut
  const measured = everMeasured(arms, IN) && everMeasured(arms, OUT)
  const last = Math.floor(tick)
  const first = windowStart(last, WEEKS)
  const perTown = last >= 1 ? arms.map(arm => weeksOf(arm, first, last)) : []
  const weeks = perTown[0]?.length ?? 0
  const max = Math.max(1, ...perTown.flatMap(rows => rows.flatMap(row => [row.in, row.out].filter(isNumber))))

  let body
  if (!measured) body = <p className="nx-quiet">{COPY.numbers.notMeasured}</p>
  else if (!weeks) body = <p className="nx-quiet">{COPY.numbers.noWeeks}</p>
  else {
    body = (
      <>
        <p className="def is-top">{copy.lead(weeks)}</p>
        <SwatchKey items={[{ label: copy.in, className: 'is-in' }, { label: copy.out, className: 'is-out' }]} />
        {arms.map((arm, i) => {
          const rows = perTown[i]
          const now = rows[rows.length - 1]
          return (
            <div className="nx-vpanel" key={arm.label}>
              <div className="nx-vhead">
                <TownName arm={arm} />
                <span>
                  {isNumber(now.in) || isNumber(now.out)
                    ? <Bolded parts={copy.thisWeek(isNumber(now.in) ? formatMoney(now.in) : COPY.numbers.notRecorded, isNumber(now.out) ? formatMoney(now.out) : COPY.numbers.notRecorded)} />
                    : COPY.numbers.hires.thisWeekMissing}
                </span>
              </div>
              <PairedBars rows={rows} max={max} tick={tick} color={arm.color} />
              <div className="nx-vaxis" aria-hidden="true"><span>{weekLabel(first)}</span><span>{COPY.numbers.thisWeek}</span></div>
            </div>
          )
        })}
        <p className="nx-foot">{copy.note}</p>
        <WeeksTable arms={arms} perTown={perTown} />
      </>
    )
  }
  return <Card title={copy.title} metricKey={IN} measured={measured} onSeeBig={onSeeBig} className={className}>{body}</Card>
}
