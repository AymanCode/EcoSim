// The diorama's homes, trees and pins, one small memoised component each,
// ported from mockup 08 (IsoScene.drawHouse, drawTree and the pins). Same
// coordinates and shapes; colours that follow a state live in town.css under
// lt- class names, so a week change only swaps classes. Each part re-renders
// only when what it draws changes. Nothing here animates: the motion loop
// moves a working home's chimney smoke (ambient.js) by writing its circles'
// attributes, starting from the pose drawn here.
import { memo } from 'react'
import { COPY } from '../catalog.js'
import { LAYOUT, iso as P, mulberry32, pts, r1 } from './geometry.js'
import { SMOKE_REST, smokePose } from './motion.js'
import { Line } from './draw.jsx'

const SIGNS = COPY.diorama.signs

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
    smoke: `translate(${r1(ch[0])} ${r1(ch[1] - 7)})`,
  }
})

// Three puffs over a chimney, drawn where the loop's smoke starts (each a
// third of a cycle apart), so smoke shows even while nothing moves.
const SMOKE = SMOKE_REST.map(phase => smokePose(phase))

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
        <Line a={[s.sale.x, s.sale.y]} b={[s.sale.x, s.sale.y - 9]} stroke="#8D7A62" strokeWidth={0.9} />
        <rect x={r1(s.sale.x - 6)} y={r1(s.sale.y - 13)} width={12} height={5.5} rx={0.8} fill="#C8483B" />
        <text x={s.sale.x} y={r1(s.sale.y - 10.1)} fontSize={2.8} fontWeight={700} fill="#fff" textAnchor="middle">{SIGNS.forSale}</text>
      </g>
      {s.smoky && (
        <g className="lt-smoke" transform={s.smoke}>
          {SMOKE.map((pose, i) => <circle key={i} r={1.8} transform={pose.transform} opacity={pose.opacity} />)}
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
