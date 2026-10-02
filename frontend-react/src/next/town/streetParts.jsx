// Main Street's parts, one small memoised component each, ported from mockup
// 08's StreetScene (drawHouse, drawHall, drawBank, drawShop, and the treasury,
// queue and pins in its constructor and apply). Same coordinates and shapes,
// in the street's own units (STREET.viewBox). Houses share the island's
// lt-house classes, so their states look the same in both drawings; shops
// share lt-shop. Nothing here animates: the motion loop waves the hall's
// flag, flickers a struggling shop's lights (ambient.js), flashes the bank
// (moments.js) and eases a shop to a new height (heights.js: the walls, the
// cornice and what stands on it, and the windows of each floor) by writing
// attributes on the parts marked here.
import { memo } from 'react'
import { COPY, formatMoneyShort } from '../catalog.js'
import { STREET, pts, r1 } from './geometry.js'
import { leased } from './model.js'
import { PILL_TONES, SHIRTS, shopColours } from './nodes.js'
import { BASE, streetHeight, streetWalls } from './streetShape.js'
import { Figure } from './draw.jsx'

const SIGNS = COPY.diorama.signs
const clamp = (value, lo, hi) => Math.min(hi, Math.max(lo, value))
const LEASE_TONE = { fg: '#6F675B', bg: '#F2EEE6' }

// A house on the hill: walls, a chimney, a gabled roof, a window (lit while
// working, with a warm glow round it) and a door.
export const StreetHouse = memo(function StreetHouse({ index, state, long, glow }) {
  const { x, y, s } = STREET.houses[index]
  const tall = 15 + (index % 3) * 1.5
  return (
    <g className={`lt-house is-${state}${long ? ' is-long' : ''}`} data-kind="house" data-index={index} transform={`translate(${x} ${y}) scale(${s})`}>
      <circle className="lt-sglow" cx={-3.75} cy={r1(-tall + 7.75)} r={12} fill={glow} />
      <rect className="lt-wl" x={-11} y={-tall} width={22} height={tall} />
      <rect className="lt-wr" x={5} y={-tall} width={6} height={tall} />
      <rect className="lt-chim" x={5.5} y={-tall - 9} width={3} height={6} />
      <polygon className="lt-rf" points={pts([[-13.5, -tall + 0.5], [0, -tall - 10], [13.5, -tall + 0.5]])} />
      <rect className="lt-win" x={-7} y={r1(-tall + 4.5)} width={6.5} height={6.5} rx={0.6} />
      <rect className="lt-rb" x={1.5} y={-9} width={4.5} height={9} />
    </g>
  )
})

// A sign painted across the shop front at height `y` (CLOSED, FOR LEASE,
// HIRING, NEW); a long word in a smaller size.
function FrontSign({ x, w, y, label, tone }) {
  return (
    <>
      <rect x={r1(x + 1)} y={r1(y)} width={w - 2} height={8} rx={1.5} fill={tone.bg} stroke={tone.fg} strokeWidth={0.7} />
      <text x={r1(x + w / 2)} y={r1(y + 5.7)} textAnchor="middle" fontSize={label.length > 7 ? 4.6 : 5.6} fontWeight={700} fill={tone.fg} letterSpacing={0.3}>{label}</text>
    </>
  )
}

// A shop on its lot, in its sector's colours: a cornice, a window pair per
// floor above, a shop window, a door and a striped awning. Being built:
// see-through walls, scaffold boards and a brace. Struggling: SALE in the
// window. Growing: HIRING across the top floor; new: NEW. Closed: boarded up
// with CLOSED, then FOR LEASE on a lower shell. The richest shop wears a crown.
function StreetShopDrawing({ shop, lot, awning }) {
  const closed = shop.state === 'closed'
  const col = shopColours(shop.sector, closed)
  const h = streetHeight(shop)
  const { x, w } = lot
  const b = BASE
  const { left, right } = streetWalls(lot, h)
  if (shop.fresh && !closed) {
    const levels = []
    for (let z = 8; z < h; z += 9) levels.push(z)
    return (
      <>
        <polygon className="lt-shop-l" points={left} fill={col.l} fillOpacity={0.35} stroke="#8A7F70" strokeDasharray="3 2" strokeWidth={0.8} />
        {levels.map(z => <line key={z} data-z={z} x1={r1(x - 2)} y1={b - z} x2={r1(x + w + 2)} y2={b - z} stroke="#9C8F7C" strokeWidth={0.8} />)}
        <line className="lt-pole" x1={x} y1={b} x2={r1(x + w)} y2={b - h} stroke="#9C8F7C" strokeWidth={0.6} />
      </>
    )
  }
  const floors = Math.max(0, Math.floor((h - 30) / 10))
  const windows = []
  for (let fl = 0; fl < floors; fl += 1) {
    const top = b - 39 - fl * 10
    for (const dx of [5, 15]) windows.push(<rect key={`${fl}-${dx}`} className="lt-win" data-z={39 + fl * 10} x={r1(x + dx)} y={top} width={6} height={5.5} />)
  }
  const sign = shop.state === 'growing' ? { label: SIGNS.hiring, tone: PILL_TONES.hiring } : shop.isNew && !closed ? { label: SIGNS.fresh, tone: PILL_TONES.fresh } : null
  return (
    <>
      <polygon className="lt-shop-l" points={left} fill={col.l} />
      <polygon className="lt-shop-r" points={right} fill={col.r} />
      <g className="lt-wins">
        {windows}
        <rect className="lt-win" x={r1(x + 3)} y={b - 15} width={13} height={11} />
      </g>
      <rect x={r1(x + 19)} y={b - 16} width={6} height={16} fill={col.r} />
      {!closed && (
        <>
          <rect x={r1(x - 2)} y={b - 24} width={w + 4} height={6} fill={awning} />
          <path d={`M${r1(x - 2)} ${b - 18} ${Array.from({ length: 6 }, () => `q ${r1((w + 4) / 12)} 3 ${r1((w + 4) / 6)} 0`).join(' ')}`} fill={col.a} />
        </>
      )}
      {closed && (
        <>
          <line className="lt-board" x1={r1(x + 2)} y1={b - 4} x2={r1(x + w - 2)} y2={b - 22} stroke="#8D7A62" strokeWidth={2.2} />
          <line className="lt-board" x1={r1(x + 2)} y1={b - 22} x2={r1(x + w - 2)} y2={b - 4} stroke="#8D7A62" strokeWidth={2.2} />
          <FrontSign x={x} w={w} y={b - 33} label={leased(shop) ? SIGNS.lease : SIGNS.closed} tone={leased(shop) ? LEASE_TONE : PILL_TONES.closed} />
        </>
      )}
      {shop.state === 'struggling' && (
        <g className="lt-sale-sign">
          <rect x={r1(x + 3.5)} y={b - 13} width={12} height={5} fill="#D9443A" />
          <text x={r1(x + 9.5)} y={b - 9.4} textAnchor="middle" fontSize={3.8} fontWeight={700} fill="#fff">{SIGNS.sale}</text>
        </g>
      )}
      {/* The cornice and what stands on it move with the roof as the height eases. */}
      <g className="lt-shop-top">
        <rect x={r1(x - 1.5)} y={b - h - 3} width={w + 3} height={3.5} fill={col.r} />
        {sign && <FrontSign x={x} w={w} y={b - h + 3} label={sign.label} tone={sign.tone} />}
        {shop.richest && (
          <path className="lt-crown" d={`M${r1(x + w / 2 - 5)} ${b - h - 6} l1 -6 l2.5 3 l1.5 -4 l1.5 4 l2.5 -3 l1 6 z`} fill="#F2C14E" stroke="#B9861A" strokeWidth={0.6} strokeLinejoin="round" />
        )}
      </g>
    </>
  )
}

// What a shop's drawing reads; anything else changing (cash, staff within a
// floor, this week's hires) leaves it as it is.
const sameShop = (a, b) => a.lot === b.lot && a.awning === b.awning && a.shop.id === b.shop.id && streetHeight(a.shop) === streetHeight(b.shop)
  && a.shop.sector === b.shop.sector && a.shop.state === b.shop.state && a.shop.fresh === b.shop.fresh
  && a.shop.isNew === b.shop.isNew && leased(a.shop) === leased(b.shop) && a.shop.richest === b.shop.richest

export const StreetShop = memo(function StreetShop({ shop, lot, awning }) {
  return (
    <g className={`lt-shop is-${shop.state}`} data-kind="shop" data-id={shop.id}>
      <StreetShopDrawing shop={shop} lot={lot} awning={awning} />
    </g>
  )
}, sameShop)

// The banner's text fits across the façade: a long label is squeezed to it.
const BANNER_ROOM = 82
const bannerFit = label => (label.length * 6.4 * 0.62 + label.length * 0.6 > BANNER_ROOM ? { textLength: BANNER_ROOM, lengthAdjust: 'spacingAndGlyphs' } : {})

// The town hall: steps, columns, TOWN HALL on the frieze, a pediment, a flag
// in the town's colour, and a banner naming its changed rule.
export const StreetHall = memo(function StreetHall({ color, banner }) {
  const cx = STREET.hallX
  const b = BASE
  return (
    <g data-kind="hall">
      <rect x={cx - 68} y={b - 6} width={136} height={6} fill="#E2D9C9" />
      <rect x={cx - 62} y={b - 11} width={124} height={5} fill="#EAE2D4" />
      <rect x={cx - 56} y={b - 60} width={112} height={49} fill="#FBF8F1" />
      {[0, 1, 2, 3, 4, 5].map(k => <rect key={k} x={r1(cx - 52 + k * 19.4)} y={b - 58} width={7} height={47} fill="#F0EAE0" stroke="#DCD3C3" strokeWidth={0.7} />)}
      <rect x={cx - 62} y={b - 70} width={124} height={10} fill="#F2ECE1" stroke="#DCD3C3" strokeWidth={0.7} />
      <text x={cx} y={b - 62.6} textAnchor="middle" fontSize={6.6} letterSpacing={1.6} fill="#7D7365" fontWeight={600}>{SIGNS.hall}</text>
      <polygon points={pts([[cx - 66, b - 70], [cx, b - 94], [cx + 66, b - 70]])} fill="#F6F1E8" stroke="#DCD3C3" />
      {banner && (
        <g className="lt-banner">
          <rect x={cx - 44} y={b - 44} width={88} height={11} rx={1.5} fill={color} />
          <text x={cx} y={b - 38.3} textAnchor="middle" dominantBaseline="central" fontSize={6.4} fontWeight={700} fill="#fff" letterSpacing={0.6} {...bannerFit(banner)}>{banner}</text>
        </g>
      )}
      <line x1={cx} y1={b - 94} x2={cx} y2={b - 122} stroke="#6B6257" strokeWidth={1.2} />
      {/* The loop waves the cloth about its left edge, drawn at (0, 0). */}
      <g transform={`translate(${cx} ${b - 117})`}>
        <rect className="lt-flag-wave" x={0} y={-5} width={16} height={10} rx={1} fill={color} />
      </g>
    </g>
  )
})

// The town hall's money beside it: a stack of coins (one per $10,000, 1 to
// 10) with the amount above, or a red slip on a post saying what it owes.
// Nothing when the figure is not measured.
export const StreetTreasury = memo(function StreetTreasury({ cash }) {
  const x = STREET.treasuryX
  const b = BASE
  if (!Number.isFinite(cash)) return <g className="lt-street-treasury" />
  if (cash >= 0) {
    const n = clamp(Math.ceil(cash / 10000), 1, 10)
    return (
      <g className="lt-street-treasury">
        {Array.from({ length: n }, (_, k) => (
          <ellipse key={k} className="lt-coin" cx={x} cy={b - 3 - k * 3} rx={8} ry={3} fill="#E3A92B" stroke="#B9861A" strokeWidth={0.7} />
        ))}
        <text x={x} y={b - n * 3 - 9} textAnchor="middle" fontSize={9} fontWeight={600} fill="#8A6514">{formatMoneyShort(cash)}</text>
      </g>
    )
  }
  return (
    <g className="lt-street-treasury is-owed">
      <line x1={x} y1={b} x2={x} y2={b - 26} stroke="#8D7A62" strokeWidth={1.4} />
      <rect x={x - 17} y={b - 40} width={34} height={15} rx={2} fill="#FBEDEA" stroke="#C8483B" strokeWidth={0.8} />
      <text x={x} y={b - 34.6} textAnchor="middle" fontSize={5.4} fontWeight={600} fill="#C8483B">{SIGNS.owesSlip}</text>
      <text x={x} y={b - 28} textAnchor="middle" fontSize={7.4} fontWeight={700} fill="#C8483B">{formatMoneyShort(-cash)}</text>
    </g>
  )
})

// Families queuing for help in front of the town hall (the model's 0 to 9).
export const StreetQueue = memo(function StreetQueue({ size }) {
  return (
    <g className="lt-street-queue">
      {Array.from({ length: size }, (_, j) => (
        <Figure key={j} x={STREET.hallX - 40 + j * 9} y={BASE + 1} shirt={SHIRTS[j % SHIRTS.length]} scale={1.25} />
      ))}
    </g>
  )
})

// The bank: columns, BANK on the cornice, a gold coin, and a red overlay the
// motion loop flashes when loans go bad.
export const StreetBank = memo(function StreetBank() {
  const cx = STREET.bankX
  const b = BASE
  return (
    <g data-kind="bank">
      <rect x={cx - 36} y={b - 5} width={72} height={5} fill="#DCD8D0" />
      <rect x={cx - 32} y={b - 50} width={64} height={45} fill="#E9E6E0" />
      {[0, 1, 2, 3].map(k => <rect key={k} x={r1(cx - 28 + k * 16.5)} y={b - 47} width={6} height={42} fill="#DFDBD3" />)}
      <rect x={cx - 36} y={b - 58} width={72} height={8} fill="#D9D4CA" />
      <text x={cx} y={b - 51.8} textAnchor="middle" fontSize={6} letterSpacing={1.6} fill="#6F6A61" fontWeight={600}>{SIGNS.bank}</text>
      <circle cx={cx} cy={b - 28} r={6} fill="#E3A92B" stroke="#fff" strokeWidth={1.2} />
      <rect className="lt-flash" data-flash="bank" x={cx - 36} y={b - 58} width={72} height={58} fill="#E0584A" opacity={0} />
    </g>
  )
})

// A pin over the house of someone you follow (the same house as on the
// island), coloured by how they are doing, with their initial. An unseen,
// wider circle takes the pointer, so a finger finds the person on a small
// screen; at r 12 it stays clear of the houses in the row behind.
const PIN_HIT = 12
export const StreetPin = memo(function StreetPin({ index, house, tone, initial }) {
  const spot = STREET.houses[house]
  const y = r1(spot.y - 40 * spot.s)
  return (
    <g className="lt-person lt-street-pin" data-kind="person" data-index={index}>
      <line x1={spot.x} y1={y} x2={spot.x} y2={r1(spot.y - 27 * spot.s)} stroke="#fff" strokeWidth={1.2} />
      <circle className="lt-pin-hit" cx={spot.x} cy={y} r={PIN_HIT} fill="transparent" />
      <circle className={`lt-pin is-${tone}`} cx={spot.x} cy={y} r={7} />
      <text x={spot.x} y={y}>{initial}</text>
    </g>
  )
})
