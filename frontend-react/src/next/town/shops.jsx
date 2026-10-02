// The diorama's shops and their signs, one small memoised component each,
// ported from mockup 08 (IsoScene.drawShop and drawLotTag). Same coordinates
// and shapes; colours that follow a state live in town.css under lt- class
// names. Nothing here animates. The motion loop eases a shop that gains or
// loses a floor (heights.js: the walls, the scaffold poles, the roof and what
// stands on it, the floors' windows and the sign above), and waves the flags,
// bobs the balloons, swings the crane's hook and flickers a struggling shop's
// lights (ambient.js), by writing attributes on the groups marked here.
import { memo } from 'react'
import { COPY } from '../catalog.js'
import { iso as P, onFace, pts, r1 } from './geometry.js'
import { PILL_TONES, pillBox, shopColours } from './nodes.js'
import { SHOP_BOX, drawnHeight, leased, shopWalls } from './shopShape.js'
import { Line } from './draw.jsx'

const SIGNS = COPY.diorama.signs

// A shop on its lot: walls in its sector's colours, an awning, a lit shop
// window and a pair of windows per floor above. Being built: scaffolding.
// Struggling: SALE on the window, flickering lights, an amber flag. Growing: a
// crane on the roof. New: balloons. Closed: boarded up, then FOR LEASE.
function ShopDrawing({ shop, lot }) {
  const closed = shop.state === 'closed'
  const col = shopColours(shop.sector, closed)
  const h = drawnHeight(shop)
  const x0 = lot.gx + SHOP_BOX.inset
  const y0 = lot.gy + SHOP_BOX.inset
  const { w, d } = SHOP_BOX
  const { left, right } = shopWalls(lot, h)
  const roof = pts([P(x0, y0, h), P(x0 + w, y0, h), P(x0 + w, y0 + d, h), P(x0, y0 + d, h)])
  const snow = pts([P(x0 + 0.06, y0 + 0.06, h + 0.3), P(x0 + w - 0.06, y0 + 0.06, h + 0.3), P(x0 + w - 0.06, y0 + d - 0.06, h + 0.3), P(x0 + 0.06, y0 + d - 0.06, h + 0.3)])
  // While it is being built the walls are see-through, dashed and scaffolded.
  const building = shop.fresh && !closed
  const wall = building ? { stroke: '#8A7F70', strokeDasharray: '2 2', strokeWidth: 0.7, fillOpacity: 0.4 } : {}
  const body = (
    <>
      <polygon className="lt-shop-l" points={left} fill={col.l} {...wall} />
      <polygon className="lt-shop-r" points={right} fill={col.r} {...wall} />
    </>
  )
  // The roof and what stands on it, which move together as the height eases.
  const roofTop = (
    <>
      <polygon points={roof} fill={closed ? '#E3DED5' : '#F3EEE5'} />
      <polygon className="lt-snow" points={snow} />
    </>
  )
  if (building) {
    // Scaffold rings (each hidden while the walls are below it) and poles
    // (which grow with the walls).
    const levels = []
    for (let z = 5; z < h; z += 6) levels.push(z)
    return (
      <>
        {body}
        {levels.map(z => (
          <polyline key={z} data-z={z} points={pts([P(x0 - 0.05, y0 + d + 0.05, z), P(x0 + w + 0.05, y0 + d + 0.05, z), P(x0 + w + 0.05, y0 - 0.05, z)])} fill="none" stroke="#9C8F7C" strokeWidth={0.7} />
        ))}
        {[0, 0.5, 1].map(u => <Line key={u} className="lt-pole" a={P(x0 + w * u, y0 + d + 0.05, 0)} b={P(x0 + w * u, y0 + d + 0.05, h)} stroke="#9C8F7C" strokeWidth={0.7} />)}
        <g className="lt-shop-top">{roofTop}</g>
      </>
    )
  }
  const floors = Math.max(0, Math.floor((h - 12) / 8))
  const windows = []
  for (let fl = 0; fl < floors; fl += 1) {
    const z0 = 12 + fl * 8
    const z1 = z0 + 4
    for (const u of [0.14, 0.56]) {
      windows.push(<polygon key={`l${fl}-${u}`} className="lt-win" data-z={z1} points={pts([P(x0 + w * u, y0 + d, z0), P(x0 + w * (u + 0.28), y0 + d, z0), P(x0 + w * (u + 0.28), y0 + d, z1), P(x0 + w * u, y0 + d, z1)])} />)
      windows.push(<polygon key={`r${fl}-${u}`} className="lt-win" data-z={z1} opacity={0.8} points={pts([P(x0 + w, y0 + d * u, z0), P(x0 + w, y0 + d * (u + 0.28), z0), P(x0 + w, y0 + d * (u + 0.28), z1), P(x0 + w, y0 + d * u, z1)])} />)
    }
  }
  return (
    <>
      {body}
      <polygon points={pts([P(x0 - 0.02, y0 + d + 0.08, 6), P(x0 + w + 0.02, y0 + d + 0.08, 6), P(x0 + w, y0 + d, 9), P(x0, y0 + d, 9)])} fill={col.a} />
      <g className="lt-wins">
        <polygon className="lt-win" points={pts([P(x0 + 0.08, y0 + d, 0.6), P(x0 + w - 0.08, y0 + d, 0.6), P(x0 + w - 0.08, y0 + d, 5.4), P(x0 + 0.08, y0 + d, 5.4)])} />
        {windows}
      </g>
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
      {shop.state === 'struggling' && <SaleSign x0={x0} y0={y0} w={w} d={d} />}
      <g className="lt-shop-top">
        {roofTop}
        {shop.state === 'struggling' && <Flag top={P(x0 + w / 2, y0 + d / 2, h)} />}
        {shop.state === 'growing' && <Crane base={P(x0 + w * 0.75, y0 + d * 0.3, h)} />}
        {shop.isNew && !closed && <Balloons top={P(x0 + w * 0.2, y0 + d * 0.8, h)} />}
      </g>
    </>
  )
}

// Struggling: SALE painted on the shop window, and an amber flag on the roof.
function SaleSign({ x0, y0, w, d }) {
  return (
    <g className="lt-sale-sign" transform={onFace(P(x0 + w / 2, y0 + d, 3))}>
      <rect x={-7.5} y={-2.6} width={15} height={5.2} rx={0.6} fill="#D9443A" />
      <text x={0} y={0.2} fontSize={4.2} fontWeight={700} fill="#fff" textAnchor="middle" dominantBaseline="central">{SIGNS.sale}</text>
    </g>
  )
}

// The cloth waves from the pole: the loop skews it about its left edge,
// drawn at (0, 0).
function Flag({ top }) {
  return (
    <>
      <Line a={top} b={[top[0], top[1] - 13]} stroke="#6B6257" strokeWidth={0.9} />
      <g transform={`translate(${r1(top[0])} ${r1(top[1] - 10.5)})`}>
        <path className="lt-flag-wave" d="M0 -2.5 l8 2.5 l-8 2.5 z" fill="#E09A1E" />
      </g>
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
const sameShop = (a, b) => a.lot === b.lot && a.shop.id === b.shop.id && drawnHeight(a.shop) === drawnHeight(b.shop)
  && a.shop.sector === b.shop.sector && a.shop.state === b.shop.state && a.shop.fresh === b.shop.fresh
  && a.shop.isNew === b.shop.isNew && leased(a.shop) === leased(b.shop)

export const Shop = memo(function Shop({ shop, lot }) {
  return (
    <g className={`lt-shop is-${shop.state}`} data-kind="shop" data-id={shop.id}>
      <ShopDrawing shop={shop} lot={lot} />
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
// richest open shop. It rides with the roof while the shop's height eases.
function signFor(shop) {
  if (shop.state === 'growing') return { label: SIGNS.hiring, tone: 'hiring' }
  if (shop.state === 'closed' && !leased(shop)) return { label: SIGNS.closed, tone: 'closed' }
  if (shop.isNew) return { label: SIGNS.fresh, tone: 'fresh' }
  return null
}

const sameSign = (a, b) => a.lot === b.lot && drawnHeight(a.shop) === drawnHeight(b.shop) && a.shop.id === b.shop.id && a.shop.state === b.shop.state
  && a.shop.isNew === b.shop.isNew && leased(a.shop) === leased(b.shop) && a.shop.richest === b.shop.richest

export const ShopSign = memo(function ShopSign({ shop, lot }) {
  const sign = signFor(shop)
  if (!sign && !shop.richest) return null
  const lift = shop.state === 'growing' ? 30 : shop.isNew ? 24 : 12
  const [x, y] = P(lot.gx + 0.5, lot.gy + 0.5, drawnHeight(shop) + lift)
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
