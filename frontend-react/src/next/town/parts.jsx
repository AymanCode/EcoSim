// The diorama's parts, one small memoised component each, ported from mockup
// 08 (IsoScene.drawHouse, drawTree, drawShop, drawLotTag, drawHall, drawBank,
// the treasury, queue and loan papers in apply, and the pins). Same
// coordinates and shapes; colours that follow a state live in town.css under
// lt- class names, so a week change only swaps classes. Each part re-renders
// only when what it draws changes.
import { memo } from 'react'
import { COPY, formatMoneyShort } from '../catalog.js'
import { BANK, HALL, LAYOUT, iso as P, mulberry32, pts } from './geometry.js'
import { WEEKS } from './model.js'
import { FIGURE, PILL_TONES, SHIRTS, pillBox, shopColours } from './nodes.js'

const r1 = value => Math.round(value * 10) / 10
const clamp = (value, lo, hi) => Math.min(hi, Math.max(lo, value))
const SIGNS = COPY.diorama.signs

// A line between two points.
function Line({ a, b, ...rest }) {
  return <line x1={r1(a[0])} y1={r1(a[1])} x2={r1(b[0])} y2={r1(b[1])} {...rest} />
}

// Text set on a building's left face (it slopes down to the right).
const onFace = at => `matrix(1 0.5 0 1 ${r1(at[0])} ${r1(at[1])})`

// ---------- houses ----------

// Each house's shape, from its tile and index: the same everywhere, every week.
const HOUSE_SHAPES = LAYOUT.houses.map((tile, index) => {
  const rnd = mulberry32(index * 7 + 3)
  const smoky = rnd() < 0.4
  const x0 = tile.gx + 0.2
  const y0 = tile.gy + 0.2
  const w = 0.6
  const d = 0.6
  const hh = 8 + Math.round(rnd() * 3)
  const r = 6
  const rA = P(x0 - 0.04, y0 + d / 2, hh + r)
  const rB = P(x0 + w + 0.04, y0 + d / 2, hh + r)
  const ch = P(x0 + w * 0.78, y0 + d * 0.22, hh + r * 0.5)
  const sA = P(x0 - 0.02, y0 + d / 2 + 0.06, hh + r - 1)
  const sB = P(x0 + w + 0.02, y0 + d / 2 + 0.06, hh + r - 1)
  const wx = x0 + w * 0.32
  const ww = w * 0.3
  const fp = P(x0 + 0.05, y0 + d + 0.16)
  const wp = P(x0 + w + 0.1, y0 + d + 0.02)
  const sp = P(x0 + 0.1, y0 + d + 0.18)
  return {
    smoky,
    wl: pts([P(x0, y0 + d), P(x0 + w, y0 + d), P(x0 + w, y0 + d, hh), P(x0, y0 + d, hh)]),
    wr: pts([P(x0 + w, y0), P(x0 + w, y0 + d), P(x0 + w, y0 + d, hh), P(x0 + w, y0, hh)]),
    rb: pts([P(x0 - 0.04, y0 - 0.04, hh), P(x0 + w + 0.04, y0 - 0.04, hh), rB, rA]),
    chimney: { x: r1(ch[0] - 1.4), y: r1(ch[1] - 6) },
    gable: pts([P(x0 + w, y0, hh), P(x0 + w, y0 + d, hh), P(x0 + w, y0 + d / 2, hh + r)]),
    rf: pts([P(x0 - 0.04, y0 + d + 0.04, hh), P(x0 + w + 0.04, y0 + d + 0.04, hh), rB, rA]),
    snow: pts([P(x0 - 0.02, y0 + d * 0.78, hh + 2), P(x0 + w + 0.02, y0 + d * 0.78, hh + 2), sB, sA]),
    win: pts([P(wx, y0 + d, 2.2), P(wx + ww, y0 + d, 2.2), P(wx + ww, y0 + d, 5.8), P(wx, y0 + d, 5.8)]),
    flowers: [['#E86A8A', 0, 0], ['#F2C14E', 2.4, 0.8], ['#FFFFFF', 4.6, 0.2], ['#B06CC8', 6.6, 1]]
      .map(([fill, dx, dy]) => ({ fill, cx: r1(fp[0] + dx), cy: r1(fp[1] + dy - 0.6) })),
    weeds: {
      cx: r1(wp[0]), cy: r1(wp[1] + 0.5),
      d: [-2.5, 0, 2.5].map(dx => `M${r1(wp[0] + dx)} ${r1(wp[1])} l-1.2 -3.2 M${r1(wp[0] + dx)} ${r1(wp[1])} l0.2 -3.8 M${r1(wp[0] + dx)} ${r1(wp[1])} l1.3 -3`),
    },
    sale: { x: r1(sp[0]), y: r1(sp[1]) },
    smoke: { cx: r1(ch[0]), cy: r1(ch[1] - 7) },
  }
})

// One house: lit and smoking with flowers while working, dark (and after
// WEEKS.longOut weeks faded, with weeds) while looking for work, an empty
// dashed outline with a FOR SALE sign once the home is lost.
export const House = memo(function House({ index, state, long }) {
  const s = HOUSE_SHAPES[index]
  const cls = `lt-house is-${state}${long ? ' is-long' : ''}${s.smoky ? ' is-smoky' : ''}`
  return (
    <g className={cls} data-kind="house" data-index={index}>
      <polygon className="lt-wl" points={s.wl} />
      <polygon className="lt-wr" points={s.wr} />
      <polygon className="lt-rb" points={s.rb} />
      <rect className="lt-chim" x={s.chimney.x} y={s.chimney.y} width={2.8} height={6} />
      <polygon className="lt-gable" points={s.gable} />
      <polygon className="lt-rf" points={s.rf} />
      <polygon className="lt-snow" points={s.snow} />
      <polygon className="lt-win" points={s.win} />
      <g className="lt-flowers">
        {s.flowers.map((f, i) => <circle key={i} cx={f.cx} cy={f.cy} r={0.95} fill={f.fill} />)}
      </g>
      <g className="lt-weeds">
        <ellipse cx={s.weeds.cx} cy={s.weeds.cy} rx={4.5} ry={1.8} fill="#A79B6A" />
        {s.weeds.d.map((d, i) => <path key={i} d={d} stroke="#7D7A3E" strokeWidth={0.7} fill="none" />)}
      </g>
      <g className="lt-sale">
        <line x1={s.sale.x} y1={s.sale.y} x2={s.sale.x} y2={r1(s.sale.y - 9)} stroke="#8D7A62" strokeWidth={0.9} />
        <rect x={r1(s.sale.x - 6)} y={r1(s.sale.y - 13)} width={12} height={5.5} rx={0.8} fill="#C8483B" />
        <text x={s.sale.x} y={r1(s.sale.y - 10.1)} fontSize={2.8} fontWeight={700} fill="#fff" textAnchor="middle">{SIGNS.forSale}</text>
      </g>
      {s.smoky && (
        <g className="lt-smoke">
          {[0, 1, 2].map(i => <circle key={i} cx={s.smoke.cx} cy={s.smoke.cy} r={1.8} />)}
        </g>
      )}
    </g>
  )
})

// The warm glow of a lit window, drawn in its own layer over the shade so
// working homes stand out more the darker the town gets.
export const Glow = memo(function Glow({ index, on, fill }) {
  const tile = LAYOUT.houses[index]
  const [cx, cy] = P(tile.gx + 0.45, tile.gy + 0.8, 4)
  return <circle className={`lt-glow${on ? ' is-on' : ''}`} cx={cx} cy={cy} r={9} fill={fill} />
})

// ---------- trees ----------

// A round tree (some blossom in spring) or a pine with a snowy tip.
export const Tree = memo(function Tree({ tree }) {
  const c = P(tree.gx + 0.5 + (tree.r - 0.4) * 0.3, tree.gy + 0.5 - (tree.r - 0.4) * 0.3)
  const [x, y] = c
  return (
    <g className={`lt-tree${tree.r < 0.18 ? ' is-blossom' : ''}`}>
      <ellipse cx={r1(x + 2)} cy={r1(y + 1)} rx={6} ry={2.6} fill="rgba(60,70,30,.16)" />
      {tree.r < 0.45 ? (
        <>
          <rect x={r1(x - 0.9)} y={r1(y - 6)} width={1.8} height={6} fill="#8A6A48" />
          <path className="lt-branches" d={`M${r1(x)} ${r1(y - 5)} l-4 -7 M${r1(x)} ${r1(y - 6)} l3.5 -8 M${r1(x)} ${r1(y - 9)} l0 -6 M${r1(x - 2)} ${r1(y - 8.5)} l-2 -2.5`} />
          <circle className="lt-leaf1" cx={r1(x)} cy={r1(y - 10)} r={6} />
          <circle className="lt-leaf2" cx={r1(x - 1.8)} cy={r1(y - 11.8)} r={3.4} />
        </>
      ) : (
        <>
          <rect x={r1(x - 0.8)} y={r1(y - 4)} width={1.6} height={4} fill="#7A5C3E" />
          <polygon points={pts([[x, y - 19], [x + 5, y - 4], [x - 5, y - 4]])} fill="#5F8A5A" />
          <polygon points={pts([[x, y - 19], [x + 5, y - 4], [x, y - 5]])} fill="#4F774B" />
          <polygon className="lt-snowtip" points={pts([[x, y - 19], [x + 2.2, y - 12.5], [x - 2.2, y - 12.5]])} />
        </>
      )}
    </g>
  )
})

// ---------- shops ----------

const leased = shop => shop.state === 'closed' && shop.closedFor >= WEEKS.lease
// A closed shop sinks to a lower shell once it is up for lease.
const drawnHeight = (shop, height) => (leased(shop) ? Math.min(height, 14) : height)

// A shop on its lot: walls in its sector's colours, an awning, a lit shop
// window and a pair of windows per floor above. Being built: scaffolding.
// Struggling: SALE on the window, flickering lights, an amber flag. Growing: a
// crane on the roof. New: balloons. Closed: boarded up, then FOR LEASE.
function ShopDrawing({ shop, lot, height }) {
  const closed = shop.state === 'closed'
  const col = shopColours(shop.sector, closed)
  const h = drawnHeight(shop, height)
  const x0 = lot.gx + 0.1
  const y0 = lot.gy + 0.1
  const w = 0.8
  const d = 0.8
  const left = pts([P(x0, y0 + d), P(x0 + w, y0 + d), P(x0 + w, y0 + d, h), P(x0, y0 + d, h)])
  const right = pts([P(x0 + w, y0), P(x0 + w, y0 + d), P(x0 + w, y0 + d, h), P(x0 + w, y0, h)])
  const roof = pts([P(x0, y0, h), P(x0 + w, y0, h), P(x0 + w, y0 + d, h), P(x0, y0 + d, h)])
  const snow = pts([P(x0 + 0.06, y0 + 0.06, h + 0.3), P(x0 + w - 0.06, y0 + 0.06, h + 0.3), P(x0 + w - 0.06, y0 + d - 0.06, h + 0.3), P(x0 + 0.06, y0 + d - 0.06, h + 0.3)])
  // While it is being built the walls are see-through, dashed and scaffolded.
  const building = shop.fresh && !closed
  const wall = building ? { stroke: '#8A7F70', strokeDasharray: '2 2', strokeWidth: 0.7, fillOpacity: 0.4 } : {}
  const body = (
    <>
      <polygon className="lt-shop-l" points={left} fill={col.l} {...wall} />
      <polygon className="lt-shop-r" points={right} fill={col.r} {...wall} />
      <polygon points={roof} fill={closed ? '#E3DED5' : '#F3EEE5'} />
      <polygon className="lt-snow" points={snow} />
    </>
  )
  if (building) {
    const levels = []
    for (let z = 5; z < h; z += 6) levels.push(z)
    return (
      <>
        {body}
        {levels.map(z => (
          <polyline key={z} points={pts([P(x0 - 0.05, y0 + d + 0.05, z), P(x0 + w + 0.05, y0 + d + 0.05, z), P(x0 + w + 0.05, y0 - 0.05, z)])} fill="none" stroke="#9C8F7C" strokeWidth={0.7} />
        ))}
        {[0, 0.5, 1].map(u => <Line key={u} a={P(x0 + w * u, y0 + d + 0.05, 0)} b={P(x0 + w * u, y0 + d + 0.05, h)} stroke="#9C8F7C" strokeWidth={0.7} />)}
      </>
    )
  }
  const floors = Math.max(0, Math.floor((h - 12) / 8))
  const windows = []
  for (let fl = 0; fl < floors; fl += 1) {
    const z0 = 12 + fl * 8
    const z1 = z0 + 4
    for (const u of [0.14, 0.56]) {
      windows.push(<polygon key={`l${fl}-${u}`} className="lt-win" points={pts([P(x0 + w * u, y0 + d, z0), P(x0 + w * (u + 0.28), y0 + d, z0), P(x0 + w * (u + 0.28), y0 + d, z1), P(x0 + w * u, y0 + d, z1)])} />)
      windows.push(<polygon key={`r${fl}-${u}`} className="lt-win" opacity={0.8} points={pts([P(x0 + w, y0 + d * u, z0), P(x0 + w, y0 + d * (u + 0.28), z0), P(x0 + w, y0 + d * (u + 0.28), z1), P(x0 + w, y0 + d * u, z1)])} />)
    }
  }
  return (
    <>
      {body}
      <polygon points={pts([P(x0 - 0.02, y0 + d + 0.08, 6), P(x0 + w + 0.02, y0 + d + 0.08, 6), P(x0 + w, y0 + d, 9), P(x0, y0 + d, 9)])} fill={col.a} />
      <polygon className="lt-win" points={pts([P(x0 + 0.08, y0 + d, 0.6), P(x0 + w - 0.08, y0 + d, 0.6), P(x0 + w - 0.08, y0 + d, 5.4), P(x0 + 0.08, y0 + d, 5.4)])} />
      {windows}
      {closed && (
        <>
          <Line className="lt-board" a={P(x0 + 0.1, y0 + d, 1)} b={P(x0 + w - 0.1, y0 + d, Math.min(h - 2, 13))} stroke="#8D7A62" strokeWidth={1.6} />
          <Line className="lt-board" a={P(x0 + w - 0.1, y0 + d, 1)} b={P(x0 + 0.1, y0 + d, Math.min(h - 2, 13))} stroke="#8D7A62" strokeWidth={1.6} />
          {leased(shop) && (
            <g className="lt-lease" transform={onFace(P(x0 + w / 2, y0 + d, 9.5))}>
              <rect x={-9} y={-2.7} width={18} height={5.4} rx={0.6} fill="#FBF8F1" stroke="#8F877A" strokeWidth={0.4} />
              <text x={0} y={0.2} fontSize={3.3} fontWeight={700} fill="#6F675B" textAnchor="middle" dominantBaseline="central">{SIGNS.lease}</text>
            </g>
          )}
        </>
      )}
      {shop.state === 'struggling' && <Struggling x0={x0} y0={y0} w={w} d={d} h={h} />}
      {shop.state === 'growing' && <Crane base={P(x0 + w * 0.75, y0 + d * 0.3, h)} />}
      {shop.isNew && !closed && <Balloons top={P(x0 + w * 0.2, y0 + d * 0.8, h)} />}
    </>
  )
}

function Struggling({ x0, y0, w, d, h }) {
  const top = P(x0 + w / 2, y0 + d / 2, h)
  return (
    <>
      <g className="lt-sale-sign" transform={onFace(P(x0 + w / 2, y0 + d, 3))}>
        <rect x={-7.5} y={-2.6} width={15} height={5.2} rx={0.6} fill="#D9443A" />
        <text x={0} y={0.2} fontSize={4.2} fontWeight={700} fill="#fff" textAnchor="middle" dominantBaseline="central">{SIGNS.sale}</text>
      </g>
      <Line a={top} b={[top[0], top[1] - 13]} stroke="#6B6257" strokeWidth={0.9} />
      <path className="lt-flag-wave" d={`M${r1(top[0])} ${r1(top[1] - 13)} l8 2.5 l-8 2.5 z`} fill="#E09A1E" />
    </>
  )
}

// A little tower crane on the roof of a growing shop.
function Crane({ base }) {
  const top = [base[0], base[1] - 22]
  const rungs = []
  for (let y = base[1] - 4; y > top[1]; y -= 4) rungs.push(y)
  return (
    <g>
      <Line a={base} b={top} stroke="#E3A92B" strokeWidth={1.6} />
      {rungs.map(y => <Line key={y} a={[base[0] - 0.8, y]} b={[base[0] + 0.8, y - 4]} stroke="#C9901F" strokeWidth={0.5} />)}
      <Line a={[top[0] - 16, top[1]]} b={[top[0] + 6, top[1]]} stroke="#E3A92B" strokeWidth={1.4} />
      <rect x={r1(top[0] + 3)} y={r1(top[1] - 0.5)} width={3.5} height={3} fill="#6B6257" />
      <g className="lt-crane-hook">
        <Line a={[top[0] - 12, top[1]]} b={[top[0] - 12, top[1] + 9]} stroke="#6B6257" strokeWidth={0.5} />
        <rect x={r1(top[0] - 14)} y={r1(top[1] + 9)} width={4} height={3} fill="#B98C5A" />
      </g>
    </g>
  )
}

function Balloons({ top }) {
  return (
    <g className="lt-balloons">
      {[['#E8556B', -3, -14], ['#F2C14E', 1, -17], ['#5BA4E6', 4, -13]].map(([fill, dx, dy]) => (
        <g key={fill}>
          <Line a={top} b={[top[0] + dx, top[1] + dy + 2.5]} stroke="#8F877A" strokeWidth={0.4} />
          <ellipse cx={r1(top[0] + dx)} cy={r1(top[1] + dy)} rx={2.3} ry={2.8} fill={fill} />
        </g>
      ))}
    </g>
  )
}

// What a shop's drawing reads; anything else changing (cash, staff within a
// floor, this week's hires) leaves it as it is.
const sameShop = (a, b) => a.lot === b.lot && a.height === b.height && a.shop.id === b.shop.id
  && a.shop.sector === b.shop.sector && a.shop.state === b.shop.state && a.shop.fresh === b.shop.fresh
  && a.shop.isNew === b.shop.isNew && leased(a.shop) === leased(b.shop)

export const Shop = memo(function Shop({ shop, lot, height }) {
  return (
    <g className={`lt-shop is-${shop.state}`} data-kind="shop" data-id={shop.id}>
      <ShopDrawing shop={shop} lot={lot} height={height} />
    </g>
  )
}, sameShop)

// A sign pill centred at (x, y).
export function TagPill({ x, y, label, tone, size = 5.6, className = 'lt-pill' }) {
  const { fg, bg } = PILL_TONES[tone]
  return (
    <g className={className} transform={`translate(${r1(x)} ${r1(y)})`}>
      <rect {...pillBox(label, size)} fill={bg} stroke={fg} strokeWidth={0.6} />
      <text x={0} y={0.4} fontSize={size} fill={fg}>{label}</text>
    </g>
  )
}

// The floating sign above a shop's roof (HIRING, CLOSED for WEEKS.lease weeks,
// NEW), drawn in the top layer so nothing covers it, and the crown over the
// richest open shop.
function signFor(shop) {
  if (shop.state === 'growing') return { label: SIGNS.hiring, tone: 'hiring' }
  if (shop.state === 'closed' && !leased(shop)) return { label: SIGNS.closed, tone: 'closed' }
  if (shop.isNew) return { label: SIGNS.fresh, tone: 'fresh' }
  return null
}

const sameSign = (a, b) => a.lot === b.lot && a.height === b.height && a.shop.id === b.shop.id && a.shop.state === b.shop.state
  && a.shop.isNew === b.shop.isNew && leased(a.shop) === leased(b.shop) && a.shop.richest === b.shop.richest

export const ShopSign = memo(function ShopSign({ shop, lot, height }) {
  const sign = signFor(shop)
  if (!sign && !shop.richest) return null
  const lift = shop.state === 'growing' ? 30 : shop.isNew ? 24 : 12
  const [x, y] = P(lot.gx + 0.5, lot.gy + 0.5, drawnHeight(shop, height) + lift)
  const crownY = y - (sign ? 10 : 0)
  return (
    <g data-sign={shop.id}>
      {sign && <TagPill x={x} y={y} label={sign.label} tone={sign.tone} />}
      {shop.richest && (
        <path className="lt-crown" d={`M${r1(x - 5)} ${r1(crownY + 2)} l1 -6 l2.5 3 l1.5 -4 l1.5 4 l2.5 -3 l1 6 z`} fill="#F2C14E" stroke="#B9861A" strokeWidth={0.6} strokeLinejoin="round" />
      )}
    </g>
  )
}, sameSign)

// ---------- the town hall ----------

// The banner's text fits the façade: a long label is squeezed to its width.
const BANNER_ROOM = 22
const bannerFit = label => (label.length * 4.6 * 0.64 > BANNER_ROOM ? { textLength: BANNER_ROOM, lengthAdjust: 'spacingAndGlyphs' } : {})

// The town hall: columns, a flag in the town's colour, a banner naming its
// changed rule, and a ring on the ground pulsing for WEEKS.pulse weeks after
// the rules change (a newer change starts it again).
export const Hall = memo(function Hall({ color, banner, changed }) {
  const { gx: x0, gy: y0, w, d, h } = HALL
  const rA = P(x0 - 0.06, y0 + d / 2, h + 9)
  const rB = P(x0 + w + 0.06, y0 + d / 2, h + 9)
  const top = P(x0 + w / 2, y0 + d / 2, h + 9)
  const [rx, ry] = P(x0 + w / 2, y0 + d / 2)
  const bannerA = P(x0 + 0.1, y0 + d, h - 4)
  const bannerB = P(x0 + w - 0.1, y0 + d, h - 4)
  return (
    <g data-kind="hall">
      {changed != null && (
        <ellipse key={changed} className="lt-hall-ring" cx={rx} cy={ry} rx={40} ry={20} stroke={color} />
      )}
      <polygon points={pts([P(x0 - 0.08, y0 + d + 0.12), P(x0 + w + 0.08, y0 + d + 0.12), P(x0 + w + 0.08, y0 + d + 0.12, 3), P(x0 - 0.08, y0 + d + 0.12, 3)])} fill="#E2D9C9" />
      <polygon points={pts([P(x0, y0 + d), P(x0 + w, y0 + d), P(x0 + w, y0 + d, h), P(x0, y0 + d, h)])} fill="#FBF8F1" />
      <polygon points={pts([P(x0 + w, y0), P(x0 + w, y0 + d), P(x0 + w, y0 + d, h), P(x0 + w, y0, h)])} fill="#E3DCCF" />
      {[0, 1, 2, 3, 4, 5].map(k => {
        const u = x0 + 0.12 + k * 0.25
        return <Line key={k} a={P(u, y0 + d, 3)} b={P(u, y0 + d, h - 3)} stroke="#DCD3C3" strokeWidth={2.2} />
      })}
      {banner && (
        <g className="lt-banner">
          <polygon points={pts([bannerA, bannerB, [bannerB[0], bannerB[1] + 7], [bannerA[0], bannerA[1] + 7]])} fill={color} />
          <text x={0} y={0} fontSize={4.6} fontWeight={700} fill="#fff" textAnchor="middle" dominantBaseline="central" letterSpacing={0.3}
            transform={onFace(P(x0 + w / 2, y0 + d, h - 7.6))} {...bannerFit(banner)}>{banner}</text>
        </g>
      )}
      <polygon points={pts([P(x0 - 0.06, y0 - 0.06, h), P(x0 + w + 0.06, y0 - 0.06, h), rB, rA])} fill="#D8CEBD" />
      <polygon points={pts([P(x0 + w, y0, h), P(x0 + w, y0 + d, h), P(x0 + w, y0 + d / 2, h + 9)])} fill="#EFE8DC" />
      <polygon points={pts([P(x0 - 0.06, y0 + d + 0.06, h), P(x0 + w + 0.06, y0 + d + 0.06, h), rB, rA])} fill="#F2ECE1" />
      <polygon className="lt-snow" points={pts([P(x0 - 0.05, y0 + d * 0.72, h + 3), P(x0 + w + 0.05, y0 + d * 0.72, h + 3), P(x0 + w + 0.03, y0 + d / 2 + 0.05, h + 8), P(x0 - 0.03, y0 + d / 2 + 0.05, h + 8)])} />
      <Line a={top} b={[top[0], top[1] - 20]} stroke="#6B6257" strokeWidth={1.1} />
      <rect className="lt-flag-wave" x={r1(top[0])} y={r1(top[1] - 20)} width={11} height={7} rx={1} fill={color} />
    </g>
  )
})

// The town hall's money in front of it: a stack of coins (one per $12,000, 1
// to 10), or a red IOU slip when it owes. Nothing when the figure is not
// measured. The amount is a separate part (TreasuryAmount) drawn in the top
// layer, so buildings in front never hide it.
const TREASURY = P(9.84, 9.84)
const coinsFor = cash => clamp(Math.ceil(cash / 12000), 1, 10)

export const Treasury = memo(function Treasury({ cash }) {
  const [x, y] = TREASURY
  if (!Number.isFinite(cash)) return <g className="lt-treasury" />
  if (cash >= 0) {
    return (
      <g className="lt-treasury">
        {Array.from({ length: coinsFor(cash) }, (_, k) => (
          <ellipse key={k} className="lt-coin" cx={x} cy={r1(y - k * 2.3)} rx={4.6} ry={2.2} fill="#E3A92B" stroke="#B9861A" strokeWidth={0.6} />
        ))}
      </g>
    )
  }
  return (
    <g className="lt-treasury is-owed">
      <path d={`M${r1(x - 6)} ${r1(y - 9)} h12 v8 l-2 -1.4 l-2 1.4 l-2 -1.4 l-2 1.4 l-2 -1.4 l-2 1.4 z`} fill="#FBEDEA" stroke="#C8483B" strokeWidth={0.8} />
    </g>
  )
})

// The amount beside the coin stack ("$78k"), or "owes $23k" beside the IOU
// slip; beside rather than above (as in the mockup), so it never runs into
// the banner on the town hall's façade.
export const TreasuryAmount = memo(function TreasuryAmount({ cash }) {
  if (!Number.isFinite(cash)) return null
  const [x, y] = TREASURY
  const owes = cash < 0
  return (
    <text className={`lt-amount${owes ? ' is-owed' : ''}`} x={r1(x + (owes ? 7.5 : 6.5))} y={r1(owes ? y - 2.5 : y - (coinsFor(cash) - 1) * 2.3 + 2.8)}>
      {owes ? `${SIGNS.owes} ${formatMoneyShort(-cash)}` : formatMoneyShort(cash)}
    </text>
  )
})

// A person standing at (x, y), as the motion loop's figureNode draws one.
export function Figure({ x, y, shirt, carry = false, scale = 1 }) {
  const { body, head, box } = FIGURE
  return (
    <g className="lt-walker" transform={`translate(${r1(x)} ${r1(y)})${scale === 1 ? '' : ` scale(${scale})`}`}>
      <path d={FIGURE.legs} strokeWidth={0.9} fill="none" />
      <line x1={body.x1} y1={body.y1} x2={body.x2} y2={body.y2} stroke={shirt} strokeWidth={body.width} />
      <circle cx={head.cx} cy={head.cy} r={head.r} fill={head.fill} stroke="none" />
      {carry && <rect x={box.x} y={box.y} width={box.width} height={box.height} fill={box.fill} stroke={box.stroke} strokeWidth={box.strokeWidth} />}
    </g>
  )
}

// Families queuing for help outside the town hall (the model's 0 to 9).
export const Queue = memo(function Queue({ size }) {
  return (
    <g className="lt-queue">
      {Array.from({ length: size }, (_, j) => {
        const [x, y] = P(8.22 + j * 0.16, 9.9 + (j % 2) * 0.04)
        return <Figure key={j} x={x} y={y} shirt={SHIRTS[j % SHIRTS.length]} scale={0.85} />
      })}
    </g>
  )
})

// ---------- the bank ----------

// The bank, a stack of loan papers on its roof (the model's 0 to 7), and a red
// overlay the motion loop flashes when loans go bad.
export const Bank = memo(function Bank({ papers }) {
  const { gx: x0, gy: y0, w, d, h } = BANK
  const coin = P(x0 + w + 0.001, y0 + d / 2, h / 2)
  return (
    <g data-kind="bank">
      <polygon points={pts([P(x0, y0 + d), P(x0 + w, y0 + d), P(x0 + w, y0 + d, h), P(x0, y0 + d, h)])} fill="#E6E2DA" />
      <polygon points={pts([P(x0 + w, y0), P(x0 + w, y0 + d), P(x0 + w, y0 + d, h), P(x0 + w, y0, h)])} fill="#C8C3B9" />
      <polygon points={pts([P(x0, y0, h), P(x0 + w, y0, h), P(x0 + w, y0 + d, h), P(x0, y0 + d, h)])} fill="#F1EEE8" />
      <polygon points={pts([P(x0, y0, h + 2), P(x0 + w, y0, h + 2), P(x0 + w, y0 + d, h + 2), P(x0, y0 + d, h + 2)])} fill="#D9D4CA" />
      <polygon className="lt-snow" points={pts([P(x0 + 0.1, y0 + 0.1, h + 2.2), P(x0 + w - 0.1, y0 + 0.1, h + 2.2), P(x0 + w - 0.1, y0 + d - 0.1, h + 2.2), P(x0 + 0.1, y0 + d - 0.1, h + 2.2)])} />
      {[0, 1, 2, 3, 4].map(k => {
        const u = x0 + 0.18 + k * 0.33
        return <Line key={k} a={P(u, y0 + d, 2)} b={P(u, y0 + d, h - 3)} stroke="#D2CDC3" strokeWidth={2} />
      })}
      <circle cx={r1(coin[0])} cy={r1(coin[1])} r={4} fill="#E3A92B" stroke="#fff" strokeWidth={1} />
      <polygon className="lt-flash" data-flash="bank" opacity={0} fill="#E0584A"
        points={pts([P(x0 + w, y0), P(x0 + w, y0 + d), P(x0 + w, y0 + d, h), P(x0 + w, y0, h), P(x0, y0, h), P(x0, y0 + d, h), P(x0, y0 + d)])} />
      <g className="lt-papers">
        {Array.from({ length: papers }, (_, k) => {
          const z = 19.5 + k * 1.3
          return <polygon key={k} points={pts([P(5.7, 5.7, z), P(6.3, 5.7, z), P(6.3, 6.3, z), P(5.7, 6.3, z)])} fill={k % 2 ? '#FFFFFF' : '#F3EEE3'} stroke="#C9C2B4" />
        })}
      </g>
    </g>
  )
})

// ---------- people you follow ----------

// A pin over the house of someone you follow, coloured by how they are doing
// (lt-pin is-work, is-look, is-low or is-idle) with their initial.
export const Pin = memo(function Pin({ index, house, tone, initial }) {
  const tile = LAYOUT.houses[house]
  const c = P(tile.gx + 0.5, tile.gy + 0.5, 32)
  const base = P(tile.gx + 0.5, tile.gy + 0.5, 18)
  return (
    <g className="lt-person" data-kind="person" data-index={index}>
      <Line a={c} b={base} stroke="#fff" strokeWidth={1.2} />
      <circle className={`lt-pin is-${tone}`} cx={r1(c[0])} cy={r1(c[1])} r={6.8} />
      <text x={r1(c[0])} y={r1(c[1])}>{initial}</text>
    </g>
  )
})
