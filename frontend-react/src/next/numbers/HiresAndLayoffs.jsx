import { useId } from 'react'
import useMeasured from '../../charts/useMeasured.js'
import { COPY, WARMUP_TICKS } from '../catalog.js'
import { weeklyCounts } from '../data/derive.js'
import { weekLabel } from '../narration.js'
import Card, { Bolded, Hatch, SwatchKey, TownName } from './Card.jsx'
import { everCounted, r1, total } from './chartKit.js'
import '../next.css'

const WEEKS = 26
const H = 92
const MID = 46
const FALLBACK_WIDTH = 260
const KEYS = ['hired', 'laidOff']

// One town's weeks as mirrored bars: people hired above the line, laid off
// below, on a scale shared by every town (`max`). Each week has a slot of
// the same width, so a window shorter than 26 weeks fills from the left; the
// setting-up weeks in it are hatched and this week's bars are solid.
function MirroredBars({ rows, max, tick }) {
  const [ref, size] = useMeasured()
  const hatchId = `nx-hl-hatch-${useId().replace(/:/g, '')}`
  const W = Math.max(120, size.width || FALLBACK_WIDTH)
  const slot = W / WEEKS
  const barWidth = Math.max(2, slot - 3)
  const first = rows[0]?.tick ?? 1
  const x = week => (week - first) * slot
  const height = count => (count > 0 ? Math.max(1, (count / max) * (MID - 3)) : 0)
  const warmEnd = Math.min(WARMUP_TICKS, tick)

  return (
    <div ref={ref} className="nx-vchart" aria-hidden="true">
      <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} focusable="false">
        <defs><Hatch id={hatchId} /></defs>
        {first <= WARMUP_TICKS && (
          <rect className="nx-vwarm" x={0} y={0} width={r1(x(warmEnd + 1))} height={H} fill={`url(#${hatchId})`} />
        )}
        {rows.map(row => {
          const x0 = r1(x(row.tick) + (slot - barWidth) / 2)
          const now = row.tick === tick ? ' is-now' : ''
          const up = height(row.hired)
          const down = height(row.laidOff)
          return (
            <g key={row.tick}>
              {up > 0 && <rect className={`nx-hl-up${now}`} x={x0} y={r1(MID - 1 - up)} width={r1(barWidth)} height={r1(up)} rx={1.5} />}
              {down > 0 && <rect className={`nx-hl-down${now}`} x={x0} y={MID + 1} width={r1(barWidth)} height={r1(down)} rx={1.5} />}
            </g>
          )
        })}
        <line className="nx-vmid" x1={0} x2={W} y1={MID} y2={MID} />
      </svg>
    </div>
  )
}

// The text alternative: every week's hires and lay-offs, per town.
function WeeksTable({ arms, perTown }) {
  const copy = COPY.numbers
  const shown = value => (value === null ? copy.notRecorded : String(value))
  return (
    // In a block box: a table grows to fit its cells whatever its width, so
    // on its own it would widen the page at phone width.
    <div className="nx-sr">
      <table>
        <caption>{copy.hires.table}</caption>
        <thead>
          <tr>
            <th scope="col">{copy.week}</th>
            {arms.flatMap(arm => [
              <th scope="col" key={`${arm.label}-h`}>{copy.column(arm.label, copy.hires.hired)}</th>,
              <th scope="col" key={`${arm.label}-l`}>{copy.column(arm.label, copy.hires.laidOff)}</th>,
            ])}
          </tr>
        </thead>
        <tbody>
          {(perTown[0] ?? []).map((row, index) => (
            <tr key={row.tick}>
              <th scope="row">{weekLabel(row.tick)}</th>
              {perTown.flatMap((rows, i) => [
                <td key={`${arms[i].label}-h`}>{shown(rows[index].hired)}</td>,
                <td key={`${arms[i].label}-l`}>{shown(rows[index].laidOff)}</td>,
              ])}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// "Hired and laid off, week by week" (mockup 06): the last 26 weeks per town
// from the town-wide event counts, this week's hires and lay-offs above each
// chart and the window's totals under it. A week with no counts draws
// nothing and is "not recorded" in the table, never zero.
export default function HiresAndLayoffs({ arms, tick, className = '' }) {
  const copy = COPY.numbers.hires
  const measured = KEYS.some(key => everCounted(arms, key))
  const perTown = arms.map(arm => weeklyCounts(arm, KEYS, tick, WEEKS))
  const weeks = perTown[0]?.length ?? 0
  const max = Math.max(1, ...perTown.flatMap(rows => rows.flatMap(row => KEYS.map(key => row[key] ?? 0))))

  let body
  if (!measured) body = <p className="nx-quiet">{COPY.numbers.notMeasured}</p>
  else if (!weeks) body = <p className="nx-quiet">{COPY.numbers.noWeeks}</p>
  else {
    body = (
      <>
        <p className="def is-top">{copy.lead(weeks)}</p>
        <SwatchKey items={[{ label: copy.hired, className: 'is-hired' }, { label: copy.laidOff, className: 'is-laid-off' }]} />
        <div className="nx-vpair">
          {arms.map((arm, i) => {
            const rows = perTown[i]
            const now = rows[rows.length - 1]
            const known = now.hired !== null || now.laidOff !== null
            return (
              <div className="nx-vpanel" key={arm.label}>
                <div className="nx-vhead">
                  <TownName arm={arm} />
                  <span>{known ? <Bolded parts={copy.thisWeek(now.hired ?? 0, now.laidOff ?? 0)} /> : copy.thisWeekMissing}</span>
                </div>
                <MirroredBars rows={rows} max={max} tick={tick} />
                <div className="nx-vaxis" aria-hidden="true"><span>{weekLabel(rows[0].tick)}</span><span>{COPY.numbers.thisWeek}</span></div>
                <p className="nx-foot">{copy.inThese(total(rows, 'hired'), total(rows, 'laidOff'))}</p>
              </div>
            )
          })}
        </div>
        <WeeksTable arms={arms} perTown={perTown} />
      </>
    )
  }
  return <Card title={copy.title} className={className}>{body}</Card>
}
