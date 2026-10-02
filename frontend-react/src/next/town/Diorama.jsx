// One town as a small island seen from above at an angle (mockup 08's
// IsoScene), drawn for the week in `model` (town/model.js townAt) as three
// stacked svgs that share one viewBox and one box (data-layer):
//
//   back    the sky, the sun and the clouds;
//   world   the ground, then houses, trees, shops, the town hall and the bank
//           back to front (PAINT_ORDER), then the shade, window glows, signs
//           and pins: everything the viewer can point at (Task 7);
//   motion  rain or snow, and the coins, rings, floating signs and dust puffs
//           the motion loop adds.
//
// The back and motion layers are their own compositor layers and take no
// pointer events, so what moves there every frame never makes the browser
// redraw the world, and the pointer always finds the world. The world has no
// CSS animations or transitions; a week change swaps its classes at once.
// What moves between weeks (useSceneMotion) is not React: the weather's CSS
// variables on the parts marked data-weather, cloud drift, rain, smoke and the
// other loops, the cars and people the loop adds to the per-tile slots, and
// the motion layer's groups. Those groups have no React children, and the
// parts that never change (back, motion, trees, slots, ground) are made once,
// so a week change neither rebuilds them nor touches what the loop added.
import { Fragment, memo, useId, useImperativeHandle, useMemo, useRef } from 'react'
import { COPY } from '../catalog.js'
import { CLOUDS, GRID, LAYOUT, PAINT_ORDER, ROAD, VIEWBOX, iso as P, pts, r1 } from './geometry.js'
import { WEEKS } from './model.js'
import { raindrops } from './mood.js'
import { Bank, Hall, Queue, Treasury, TreasuryAmount } from './civic.jsx'
import { Glow, House, Pin, Tree } from './homes.jsx'
import { ISLAND } from './islandPlaces.js'
import { Shop, ShopSign, TagPill } from './shops.jsx'
import useSceneMotion from './useSceneMotion.js'
import './town.css'

const RAIN_BOX = { x: -290, y: -40, w: 580, h: 330 }
// The rain falls in groups of drops a step apart in their fall, so the loop
// moves a few groups rather than every drop.
const DROP_GROUPS = 7

// The sky: a gradient that follows the weather, the sun, and six clouds (the
// weather shows as many as the mood calls for).
const Back = memo(function Back({ id }) {
  return (
    <svg className="lt-layer lt-back" data-layer="back" viewBox={VIEWBOX} aria-hidden="true" focusable="false">
      <defs>
        <linearGradient id={`${id}-sky`} x1={0} y1={0} x2={0} y2={1} data-weather="sky">
          <stop className="lt-sky-top" offset="0%" />
          <stop className="lt-sky-bottom" offset="100%" />
        </linearGradient>
        <radialGradient id={`${id}-sun`}>
          <stop offset="0%" stopColor="#FFE3A8" stopOpacity={0.9} />
          <stop offset="100%" stopColor="#FFE3A8" stopOpacity={0} />
        </radialGradient>
      </defs>
      <rect x={-302} y={-50} width={604} height={364} fill={`url(#${id}-sky)`} />
      <g className="lt-sun" data-weather="sun">
        <circle cx={236} cy={-8} r={46} fill={`url(#${id}-sun)`} />
        <circle cx={236} cy={-8} r={14} fill="#FFD27A" />
      </g>
      <g data-layer="clouds" className="lt-clouds" data-weather="clouds">
        {CLOUDS.map((cloud, k) => (
          <g key={k} data-cloud={k} transform={`translate(${cloud.x} ${cloud.y})`}>
            {cloud.puffs.map((puff, i) => <ellipse key={i} {...puff} />)}
          </g>
        ))}
      </g>
    </svg>
  )
})

const TILE_FILL = { road: '#E4DACA', civic: '#EEE6D8', lot: '#E7DECF' }

// The island: its shadow, its earth sides, the tiles (grass takes the
// weather's colours), and the lane markings on the two roads.
const Ground = memo(function Ground() {
  const lane = (a, b) => <line x1={a[0]} y1={a[1]} x2={b[0]} y2={b[1]} stroke="#FBF8F2" strokeWidth={1.1} strokeDasharray="5 5" />
  return (
    <>
      <ellipse cx={0} cy={300} rx={296} ry={14} fill="rgba(80,55,20,.12)" />
      <g className="lt-ground" data-weather="grass">
        <polygon points={pts([P(0, GRID), P(GRID, GRID), P(GRID, GRID, -16), P(0, GRID, -16)])} fill="#B89A73" />
        <polygon points={pts([P(GRID, 0), P(GRID, GRID), P(GRID, GRID, -16), P(GRID, 0, -16)])} fill="#9C7F5B" />
        <polygon points={pts([P(0, GRID, -12), P(GRID, GRID, -12), P(GRID, GRID, -16), P(0, GRID, -16)])} fill="#8E7351" />
        <polygon points={pts([P(GRID, 0, -12), P(GRID, GRID, -12), P(GRID, GRID, -16), P(GRID, 0, -16)])} fill="#7D6447" />
        {LAYOUT.tiles.map(({ gx, gy, kind }) => (
          <polygon
            key={`${gx},${gy}`}
            className={kind === 'grass' ? `lt-grass ${(gx + gy) % 2 ? 'is-a' : 'is-b'}` : undefined}
            points={pts([P(gx, gy), P(gx + 1, gy), P(gx + 1, gy + 1), P(gx, gy + 1)])}
            fill={TILE_FILL[kind]}
            stroke="rgba(255,255,255,.28)"
          />
        ))}
        {lane(P(0, ROAD + 0.5), P(GRID, ROAD + 0.5))}
        {lane(P(ROAD + 0.5, 0), P(ROAD + 0.5, GRID))}
      </g>
    </>
  )
})

// Rain (or snow in winter), in DROP_GROUPS groups the loop moves down.
const Rain = memo(function Rain({ seed }) {
  const groups = useMemo(() => {
    const out = Array.from({ length: DROP_GROUPS }, () => [])
    raindrops(seed, 90, RAIN_BOX).forEach(drop => {
      out[Math.min(DROP_GROUPS - 1, Math.floor((-drop.delay / 0.7) * DROP_GROUPS))].push(drop)
    })
    return out
  }, [seed])
  return (
    <g data-layer="rain" className="lt-rain" data-weather="rain">
      {groups.map((drops, k) => (
        <g key={k} data-drops={k}>
          {drops.map((drop, i) => <line key={i} x1={r1(drop.x)} y1={r1(drop.y)} x2={r1(drop.x - 2.5)} y2={r1(drop.y + 8)} />)}
        </g>
      ))}
    </g>
  )
})

// What moves on top: rain, then the rings where coins land, the coins, and
// this week's floating signs and dust puffs (filled by the motion loop).
const Motion = memo(function Motion({ seed }) {
  return (
    <svg className="lt-layer lt-motion" data-layer="motion" viewBox={VIEWBOX} aria-hidden="true" focusable="false">
      <Rain seed={seed} />
      <g data-layer="pings" />
      <g data-layer="coins" />
      <g data-layer="moments" />
    </svg>
  )
})

// A seed from the town's colour, so two towns' rain does not fall in step.
const seedOf = text => [...String(text ?? '')].reduce((hash, ch) => Math.imul(hash ^ ch.charCodeAt(0), 16777619), 2166136261) | 0

// The parts of the world that never change, made once: trees and the empty
// per-tile slots, by their place in PAINT_ORDER; React skips an element it
// has already rendered, so a week change costs nothing here.
const STILL = PAINT_ORDER.map(item => {
  if (item.kind === 'tree') return <Tree key={`t${item.index}`} tree={LAYOUT.trees[item.index]} />
  if (item.kind === 'slot') return <g key={`s${item.gx},${item.gy}`} data-slot={`${item.gx},${item.gy}`} />
  return null
})
const GROUND = <Ground />

function Diorama({ model, color, sceneRef, playing = false, speed = 1, towns = 1, scrubs = 0, hidden = false, ended = false }) {
  const id = useId().replace(/[^\w-]/g, '')
  const rootRef = useRef(null)
  useImperativeHandle(sceneRef, () => rootRef.current, [])
  useSceneMotion(rootRef, { model, places: ISLAND, playing, speed, towns, scrubs, hidden, ended })

  const byLot = new Array(LAYOUT.lots.length).fill(null)
  for (const shop of model.shops) byLot[shop.lot] = shop
  const world = PAINT_ORDER.map((item, i) => {
    if (STILL[i]) return STILL[i]
    if (item.kind === 'house') {
      const house = model.houses[item.index]
      return <House key={`h${item.index}`} index={item.index} state={house.state} long={house.state === 'look' && house.weeks >= WEEKS.longOut} />
    }
    if (item.kind === 'lot') {
      const shop = byLot[item.index]
      return shop ? <Shop key={`l${item.index}:${shop.id}`} shop={shop} lot={LAYOUT.lots[item.index]} /> : null
    }
    if (item.kind === 'hall') {
      return (
        <Fragment key="hall">
          <Hall color={color} banner={model.hall.banner} changed={model.hall.changedTick} />
          <Treasury cash={model.hall.cash} />
          <Queue size={model.hall.queue} />
        </Fragment>
      )
    }
    return <Bank key="bank" papers={model.bank.papers} />
  })
  const more = P(0.6, 0.6, 16)

  return (
    <div ref={rootRef} className="lt-stage" aria-hidden="true">
      <Back id={id} />
      <svg className={`lt-scene season-${model.season}`} data-layer="world" viewBox={VIEWBOX} aria-hidden="true" focusable="false">
        <defs>
          <radialGradient id={`${id}-glow`}>
            <stop offset="0%" stopColor="#FFD36B" stopOpacity={0.85} />
            <stop offset="100%" stopColor="#FFD36B" stopOpacity={0} />
          </radialGradient>
        </defs>
        {GROUND}
        <g className="lt-world">{world}</g>
        <rect className="lt-shade" x={-302} y={-50} width={604} height={364} fill="#151E32" data-weather="shade" />
        <g className="lt-glows" data-weather="glow">
          {model.houses.map((house, i) => <Glow key={i} index={i} on={house.state === 'work'} fill={`url(#${id}-glow)`} />)}
        </g>
        <g className="lt-signs">
          <TreasuryAmount cash={model.hall.cash} />
          {model.shops.map(shop => <ShopSign key={shop.id} shop={shop} lot={LAYOUT.lots[shop.lot]} />)}
          {model.overflow > 0 && <TagPill className="lt-pill lt-more" x={more[0]} y={more[1]} label={COPY.diorama.moreLots(model.overflow)} tone="more" />}
        </g>
        <g className="lt-pins">
          {model.people.map((person, i) => (
            <Pin key={person.id ?? i} index={i} house={person.house} tone={person.tone} initial={person.name.charAt(0)} />
          ))}
        </g>
      </svg>
      <Motion seed={seedOf(color)} />
    </div>
  )
}

export default memo(Diorama)
