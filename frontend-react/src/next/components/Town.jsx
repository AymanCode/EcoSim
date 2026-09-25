import { useMemo } from 'react'
import { COPY, HOUSEHOLD_STATES, formatMetric } from '../catalog.js'
import { snapshotAt, valueAt } from '../data/derive.js'
import '../next.css'

// Drawing space, from the mockup's townSVG.
const W = 560
const H = 300
const HOUSES = 100
const COLS = 20
const CELL_W = (W - 40) / COLS
const CELL_H = 26
const HOUSE_TOP = 176
const STREET_Y = 142
const STREET_LEFT = 26
const STREET_RIGHT = W - 26
const MAX_BUILDINGS = 16
const MORE_ROOM = 58
const HALL_PULSE_WEEKS = 4
const CIVIC = [
  { x: 200, label: COPY.town.hall, hall: true },
  { x: 300, label: COPY.town.bank, hall: false },
]

const round = value => Math.round(value * 100) / 100
const clamp = (value, lo, hi) => Math.min(hi, Math.max(lo, value))

function mulberry32(seed) {
  let a = seed | 0
  return () => {
    a = (a + 0x6D2B79F5) | 0
    let t = Math.imul(a ^ (a >>> 15), 1 | a)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

// Each house gets a fixed spot and a fixed rank from the town's seed. The
// lowest ranks lose their home, the next look for work, so when a figure moves
// only the houses at the edge change colour. Matched towns share a seed, so
// the same house means the same place in every town.
function houseLayout(seed) {
  const rand = mulberry32(Number(seed) || 0)
  const order = Array.from({ length: HOUSES }, (_, i) => i)
  for (let i = HOUSES - 1; i > 0; i -= 1) {
    const j = Math.floor(rand() * (i + 1))
    ;[order[i], order[j]] = [order[j], order[i]]
  }
  const rank = new Array(HOUSES)
  order.forEach((house, position) => { rank[house] = position })
  const spots = Array.from({ length: HOUSES }, (_, i) => ({
    x: round(20 + (i % COLS) * CELL_W + CELL_W / 2 + (rand() - 0.5) * 3),
    y: round(HOUSE_TOP + Math.floor(i / COLS) * CELL_H + (rand() - 0.5) * 3),
  }))
  return { rank, spots }
}

// Open firms by id so they keep their lot, then closed lots, 16 at most.
function streetLayout(snapshot) {
  const open = [...(snapshot?.firms ?? [])].sort((a, b) => a.id - b.id)
  const closed = [...(snapshot?.firmsClosed ?? [])].sort((a, b) => (a.closedTick - b.closedTick) || (a.id - b.id))
  const busiest = Math.max(1, ...open.map(firm => firm.staff || 0))
  const all = [
    ...open.map(firm => ({ key: `open-${firm.id}`, kind: firm.state === 'struggling' ? 'struggling' : 'open', staff: firm.staff })),
    ...closed.map(firm => ({ key: `closed-${firm.id}`, kind: 'closed', staff: firm.lastStaff })),
  ]
  const shown = all.slice(0, MAX_BUILDINGS)
  const hidden = all.length - shown.length
  const room = STREET_RIGHT - STREET_LEFT - (hidden > 0 ? MORE_ROOM : 0)
  const pitch = Math.min(42, room / Math.max(1, shown.length))
  const width = Math.min(30, pitch - 8)
  const buildings = shown.map((building, i) => {
    const h = round(24 + Math.min(1, (building.staff || 0) / busiest) * 26)
    return { ...building, x: round(STREET_LEFT + i * pitch), y: round(STREET_Y - h), w: round(width), h }
  })
  return { buildings, hidden, moreX: round(STREET_LEFT + shown.length * pitch + 2) }
}

function Windows({ x, y, w, h }) {
  const cols = w >= 26 ? 3 : w >= 17 ? 2 : 1
  const rows = Math.floor((h - 12) / 12)
  const span = cols * 4 + (cols - 1) * 5
  const left = x + (w - span) / 2
  const cells = []
  for (let r = 0; r < rows; r += 1) {
    for (let c = 0; c < cols; c += 1) {
      cells.push(<rect key={`${r}-${c}`} className="nx-window" x={round(left + c * 9)} y={round(y + 11 + r * 12)} width={4} height={5} />)
    }
  }
  return cells
}

function Building({ kind, x, y, w, h }) {
  if (kind === 'closed') {
    const cx = x + w / 2
    const cy = y + h / 2
    return (
      <g className="nx-bldg is-closed">
        <rect className="nx-lot" x={x} y={y} width={w} height={h} />
        <path className="nx-cross" d={`M${round(cx - 6)} ${round(cy - 6)} l12 12 M${round(cx + 6)} ${round(cy - 6)} l-12 12`} />
      </g>
    )
  }
  const struggling = kind === 'struggling'
  return (
    <g className={`nx-bldg${struggling ? ' is-struggling' : ''}`}>
      <rect className="nx-bldg-body" x={x} y={y} width={w} height={h} />
      <rect className="nx-bldg-roof" x={x} y={y} width={w} height={6} />
      <Windows x={x} y={y} w={w} h={h} />
      {struggling && (
        <g>
          <circle className="nx-flag" cx={round(x + w)} cy={y} r={7} />
          <text className="nx-flag-mark" x={round(x + w)} y={round(y + 3.5)} textAnchor="middle">!</text>
        </g>
      )}
    </g>
  )
}

// One house. Looking-for-work houses get an empty window and lost homes a
// dashed outline, so the three states read without colour too.
function House({ x, y, state, className }) {
  return (
    <g className={`${className} is-${state}`}>
      <rect x={round(x - 7)} y={y} width={14} height={11} rx={1.5} />
      <path d={`M${round(x - 9)} ${y} L${x} ${round(y - 7)} L${round(x + 9)} ${y} Z`} />
      {state === 'look' && <rect className="nx-seek" x={round(x - 2.5)} y={round(y + 3)} width={5} height={5} />}
      <rect className="nx-lost" x={round(x - 7)} y={y} width={14} height={11} />
    </g>
  )
}

// The newest rule change in the last four weeks, or null. Changes are kept in
// tick order.
function recentChange(arm, tick) {
  const changes = arm?.policyChanges ?? []
  for (let i = changes.length - 1; i >= 0; i -= 1) {
    if (changes[i].tick > tick) continue
    return changes[i].tick > tick - HALL_PULSE_WEEKS ? changes[i] : null
  }
  return null
}

// The town hall pulses a ring in the town's colour while its rules are new;
// a newer change starts the pulse again.
function Civic({ x, label, hall, color, changed }) {
  return (
    <g className={hall ? `nx-townhall${changed ? ' is-changed' : ''}` : undefined}>
      {changed && <title>{COPY.town.hallChanged}</title>}
      <rect className="nx-civic" x={x} y={34} width={74} height={32} />
      <path className="nx-civic" d={`M${x - 4} 34 L${x + 37} 15 L${x + 78} 34 Z`} />
      {[0, 1, 2, 3].map(i => <rect key={i} className="nx-pillar" x={x + 9 + i * 17} y={40} width={5} height={26} />)}
      {hall && <rect x={x + 35} y={5} width={3} height={12} style={{ fill: color }} />}
      <text className="nx-label" x={x + 37} y={80} textAnchor="middle">{label}</text>
      {changed && (
        <circle key={changed.id ?? changed.tick} className="nx-hall-ring" cx={x + 37} cy={47} r={45} style={{ stroke: color }} />
      )}
    </g>
  )
}

export default function Town({ arm, tick }) {
  const seed = arm?.setup?.seed
  const layout = useMemo(() => houseLayout(seed), [seed])
  const snapshot = snapshotAt(arm, tick)
  const street = useMemo(() => streetLayout(snapshot), [snapshot])
  const changed = recentChange(arm, tick)

  const total = valueAt(arm, 'householdsTotal', tick)
  const homelessCount = valueAt(arm, 'homelessHouseholds', tick) ?? 0
  const outOfWork = valueAt(arm, 'peopleOutOfWorkPer100', tick)
  const pay = valueAt(arm, 'typicalWeeklyPay', tick)
  const home = total > 0 ? clamp(Math.round((100 * homelessCount) / total), 0, HOUSES) : 0
  const look = clamp(Math.round(outOfWork ?? 0), 0, HOUSES - home)
  const work = HOUSES - home - look
  const firmsOpen = valueAt(arm, 'firmsOpen', tick) ?? snapshot?.firms?.length ?? 0
  const struggling = valueAt(arm, 'firmsStruggling', tick) ?? 0
  const closed = snapshot?.firmsClosed?.length ?? 0

  const stateOf = rank => (rank < home ? 'home' : rank < home + look ? 'look' : 'work')

  return (
    <div className="nx-card nx-townc">
      <svg className="nx-town" viewBox={`0 0 ${W} ${H}`} aria-hidden="true" focusable="false">
        <rect className="nx-ground" x={0} y={0} width={W} height={H} rx={10} />
        {CIVIC.map(civic => <Civic key={civic.label} {...civic} color={arm?.color} changed={civic.hall ? changed : null} />)}
        {street.buildings.map(({ key, ...building }) => <Building key={key} {...building} />)}
        {street.hidden > 0 && (
          <text className="nx-bldg-more" x={street.moreX} y={STREET_Y - 8}>{COPY.town.moreBuildings(street.hidden)}</text>
        )}
        <line className="nx-street" x1={16} x2={W - 16} y1={STREET_Y + 1} y2={STREET_Y + 1} />
        <text className="nx-label" x={26} y={158}>{COPY.town.mainStreet}</text>
        {layout.spots.map((spot, i) => (
          <House key={i} className="nx-house" x={spot.x} y={spot.y} state={stateOf(layout.rank[i])} />
        ))}
      </svg>
      <ul className="nx-sr">
        <li>{COPY.town.altHouses(work, look, home)}</li>
        <li>{COPY.town.altFirms(firmsOpen, struggling, closed)}</li>
        {changed && <li>{COPY.town.hallChanged}</li>}
      </ul>
      <div className="nx-legend" aria-hidden="true">
        {['work', 'look', 'home'].map(state => (
          <span key={state}>
            <svg className="nx-key" viewBox="0 0 20 16" focusable="false"><House className="nx-keyhouse" x={10} y={4.5} state={state} /></svg>
            {HOUSEHOLD_STATES[state].legend}
          </span>
        ))}
        <span className="nx-scale">{COPY.town.houseScale(total)}</span>
      </div>
      <div className="nx-facts">
        <div className="nx-fact"><div className="v">{formatMetric('peopleOutOfWorkPer100', outOfWork)}</div><div className="k">{COPY.town.outOfWork}</div></div>
        <div className="nx-fact"><div className="v">{formatMetric('typicalWeeklyPay', pay)}</div><div className="k">{COPY.town.typicalPay}</div></div>
        <div className="nx-fact"><div className="v">{COPY.town.firms(firmsOpen)}</div><div className="k">{COPY.town.firmStates(struggling, closed)}</div></div>
      </div>
    </div>
  )
}
