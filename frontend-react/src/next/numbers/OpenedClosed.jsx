import { useId } from 'react'
import useMeasured from '../../charts/useMeasured.js'
import { COPY, WARMUP_TICKS } from '../catalog.js'
import { weeklyCounts } from '../data/derive.js'
import { weekLabel } from '../narration.js'
import Card, { Bolded, Hatch, TownName } from './Card.jsx'
import { everCounted, r1, total } from './chartKit.js'
import '../next.css'

const WEEKS = 26
const H = 74
const MID = 37
const FALLBACK_WIDTH = 260
const OPENED = 'firmsOpened'
const CLOSED = 'firmsClosed'

// Weeks close together (3 or fewer apart) read as one burst; a burst of more
// than one business gets its count.
function bursts(rows, key) {
  const found = []
  for (const row of rows) {
    const count = row[key]
    if (!(count > 0)) continue
    const last = found[found.length - 1]
    if (last && row.tick - last.to <= 3) {
      last.to = row.tick
      last.count += count
    } else found.push({ from: row.tick, to: row.tick, count })
  }
  return found.filter(burst => burst.count > 1)
}

// One town's weeks as a strip: a mark above the line for each week a business
// opened, below for each week one closed, longer when more did; this week at
// the right, the setting-up weeks hatched.
function Strip({ rows, tick }) {
  const [ref, size] = useMeasured()
  const hatchId = `nx-oc-hatch-${useId().replace(/:/g, '')}`
  const W = Math.max(120, size.width || FALLBACK_WIDTH)
  const slot = (W - 4) / WEEKS
  const first = rows[0]?.tick ?? 1
  const x = week => 2 + (week - first + 0.5) * slot
  const reach = count => Math.min(20, 8 + 3 * count)
  const warmEnd = Math.min(WARMUP_TICKS, tick)

  return (
    <div ref={ref} className="nx-vchart" aria-hidden="true">
      <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} focusable="false">
        <defs><Hatch id={hatchId} /></defs>
        {first <= WARMUP_TICKS && (
          <rect className="nx-vwarm" x={2} y={2} width={r1((warmEnd - first + 1) * slot)} height={H - 4} fill={`url(#${hatchId})`} />
        )}
        <line className="nx-vnow" x1={r1(x(tick))} x2={r1(x(tick))} y1={2} y2={H - 2} />
        <line className="nx-vmid is-light" x1={2} x2={W - 2} y1={MID} y2={MID} />
        {rows.map(row => (
          <g key={row.tick}>
            {row[OPENED] > 0 && <line className="nx-oc-open" x1={r1(x(row.tick))} x2={r1(x(row.tick))} y1={MID - 2} y2={MID - reach(row[OPENED])} />}
            {row[CLOSED] > 0 && <line className="nx-oc-close" x1={r1(x(row.tick))} x2={r1(x(row.tick))} y1={MID + 2} y2={MID + reach(row[CLOSED])} />}
          </g>
        ))}
        {bursts(rows, OPENED).map(burst => (
          <text key={`o${burst.from}`} className="nx-oc-count is-open" x={r1(x((burst.from + burst.to) / 2))} y={MID - 26} textAnchor="middle">+{burst.count}</text>
        ))}
        {bursts(rows, CLOSED).map(burst => (
          <text key={`c${burst.from}`} className="nx-oc-count is-close" x={r1(x((burst.from + burst.to) / 2))} y={MID + 34} textAnchor="middle">−{burst.count}</text>
        ))}
      </svg>
    </div>
  )
}

// "Opened and closed" (mockup 06): per town, a strip of the last 26 weeks
// with a mark for each week a business opened or closed, the totals so far
// above it and the window's under it. From the town-wide event counts; a week
// with no counts draws nothing.
export default function OpenedClosed({ arms, tick, className = '' }) {
  const copy = COPY.numbers.openClose
  const measured = [OPENED, CLOSED].some(key => everCounted(arms, key))
  const perTown = arms.map(arm => weeklyCounts(arm, [OPENED, CLOSED], tick, WEEKS))
  const soFar = arms.map(arm => weeklyCounts(arm, [OPENED, CLOSED], tick, Math.max(1, Math.floor(tick))))
  const weeks = perTown[0]?.length ?? 0
  const listed = (rows, key) => rows.filter(row => row[key] > 0).map(row => copy.weekCount(weekLabel(row.tick), row[key]))

  let body
  if (!measured) body = <p className="nx-quiet">{COPY.numbers.notMeasured}</p>
  else if (!weeks) body = <p className="nx-quiet">{COPY.numbers.noWeeks}</p>
  else {
    body = (
      <>
        <p className="def is-top">{copy.lead(weeks)}</p>
        {arms.map((arm, i) => {
          const rows = perTown[i]
          return (
            <div className="nx-vpanel" key={arm.label}>
              <div className="nx-vhead">
                <TownName arm={arm} />
                <span><Bolded parts={copy.soFar(total(soFar[i], OPENED), total(soFar[i], CLOSED))} /></span>
              </div>
              <Strip rows={rows} tick={tick} />
              <div className="nx-vaxis" aria-hidden="true"><span>{weekLabel(rows[0].tick)}</span><span>{COPY.numbers.thisWeek}</span></div>
              <p className="nx-foot">{copy.inThese(total(rows, OPENED), total(rows, CLOSED))}</p>
            </div>
          )
        })}
        <p className="nx-sr">{arms.map((arm, i) => copy.alt(arm.label, listed(perTown[i], OPENED), listed(perTown[i], CLOSED))).join(' ')}</p>
      </>
    )
  }
  return <Card title={copy.title} className={className}>{body}</Card>
}
