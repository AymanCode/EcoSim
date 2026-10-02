// One town as a small island seen from above at an angle (mockup 08's
// IsoScene), drawn for the week in `model` (town/model.js townAt). The
// structure is React: sky, clouds, ground, then houses, trees, shops, the town
// hall and the bank back to front (PAINT_ORDER), then the shade, window glows,
// rain, signs and pins. Weather is written straight onto the svg as CSS
// variables on the parts marked data-weather (weather.js). The motion loop (Task 6) finds its layers and the
// per-tile slots through data attributes and fills them without React, so
// those groups have no React children.
import { Fragment, memo, useId, useImperativeHandle, useLayoutEffect, useMemo, useRef } from 'react'
import { COPY } from '../catalog.js'
import { GRID, LAYOUT, PAINT_ORDER, ROAD, VIEWBOX, iso as P, mulberry32, pts } from './geometry.js'
import { WEEKS } from './model.js'
import { raindrops } from './mood.js'
import { Bank, Glow, Hall, House, Pin, Queue, Shop, ShopSign, TagPill, Tree, Treasury, TreasuryAmount } from './parts.jsx'
import { applyWeather } from './weather.js'
import './town.css'

const r1 = value => Math.round(value * 10) / 10
const shopHeight = shop => shop.floors * 8 + 12
const RAIN_BOX = { x: -290, y: -40, w: 580, h: 330 }

// Six clouds; the weather shows as many as the mood calls for.
const CLOUDS = Array.from({ length: 6 }, (_, c) => {
  const s = 0.8 + (c % 3) * 0.25
  return {
    x: r1(-320 + c * 120 + mulberry32(c + 17)() * 60),
    y: -36 + (c % 3) * 16 + (c > 2 ? 40 : 0),
    puffs: [[0, 0, 11], [12, -4, 13], [25, 1, 10], [11, 4, 10]].map(([dx, dy, r]) => ({ cx: r1(dx * s), cy: r1(dy * s), rx: r1(r * s * 1.25), ry: r1(r * s * 0.8) })),
  }
})

const Clouds = memo(function Clouds() {
  return (
    <g data-layer="clouds" className="lt-clouds" data-weather="">
      {CLOUDS.map((cloud, k) => (
        <g key={k} data-cloud={k} transform={`translate(${cloud.x} ${cloud.y})`}>
          {cloud.puffs.map((puff, i) => <ellipse key={i} {...puff} />)}
        </g>
      ))}
    </g>
  )
})

const TILE_FILL = { road: '#E4DACA', civic: '#EEE6D8', lot: '#E7DECF' }

// The island: its earth sides, the tiles (grass takes the weather's colours),
// and the lane markings on the two roads.
const Ground = memo(function Ground() {
  const lane = (a, b) => <line x1={a[0]} y1={a[1]} x2={b[0]} y2={b[1]} stroke="#FBF8F2" strokeWidth={1.1} strokeDasharray="5 5" />
  return (
    <g className="lt-ground" data-weather="">
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
  )
})

const Rain = memo(function Rain({ seed }) {
  const drops = useMemo(() => raindrops(seed, 90, RAIN_BOX), [seed])
  return (
    <g data-layer="rain" className="lt-rain" data-weather="">
      {drops.map((drop, i) => (
        <line key={i} x1={r1(drop.x)} y1={r1(drop.y)} x2={r1(drop.x - 2.5)} y2={r1(drop.y + 8)} style={{ animationDelay: `${drop.delay.toFixed(2)}s` }} />
      ))}
    </g>
  )
})

// A seed from the town's colour, so two towns' rain does not fall in step.
const seedOf = text => [...String(text ?? '')].reduce((hash, ch) => Math.imul(hash ^ ch.charCodeAt(0), 16777619), 2166136261) | 0

export default function Diorama({ model, color, sceneRef }) {
  const id = useId().replace(/[^\w-]/g, '')
  const svgRef = useRef(null)
  useImperativeHandle(sceneRef, () => svgRef.current, [])
  useLayoutEffect(() => applyWeather(svgRef.current, model.mood, model.season), [model.mood, model.season])

  const byLot = new Array(LAYOUT.lots.length).fill(null)
  for (const shop of model.shops) byLot[shop.lot] = shop
  const world = PAINT_ORDER.map(item => {
    if (item.kind === 'house') {
      const house = model.houses[item.index]
      return <House key={`h${item.index}`} index={item.index} state={house.state} long={house.state === 'look' && house.weeks >= WEEKS.longOut} />
    }
    if (item.kind === 'tree') return <Tree key={`t${item.index}`} tree={LAYOUT.trees[item.index]} />
    if (item.kind === 'lot') {
      const shop = byLot[item.index]
      return shop ? <Shop key={`l${item.index}:${shop.id}`} shop={shop} lot={LAYOUT.lots[item.index]} height={shopHeight(shop)} /> : null
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
    if (item.kind === 'bank') return <Bank key="bank" papers={model.bank.papers} />
    return <g key={`s${item.gx},${item.gy}`} data-slot={`${item.gx},${item.gy}`} />
  })
  const more = P(0.6, 0.6, 16)

  return (
    <svg ref={svgRef} className={`lt-scene season-${model.season}`} viewBox={VIEWBOX} aria-hidden="true" focusable="false">
      <defs>
        <linearGradient id={`${id}-sky`} x1={0} y1={0} x2={0} y2={1} data-weather="">
          <stop className="lt-sky-top" offset="0%" />
          <stop className="lt-sky-bottom" offset="100%" />
        </linearGradient>
        <radialGradient id={`${id}-glow`}>
          <stop offset="0%" stopColor="#FFD36B" stopOpacity={0.85} />
          <stop offset="100%" stopColor="#FFD36B" stopOpacity={0} />
        </radialGradient>
        <radialGradient id={`${id}-sun`}>
          <stop offset="0%" stopColor="#FFE3A8" stopOpacity={0.9} />
          <stop offset="100%" stopColor="#FFE3A8" stopOpacity={0} />
        </radialGradient>
      </defs>
      <rect x={-302} y={-50} width={604} height={364} fill={`url(#${id}-sky)`} />
      <g className="lt-sun" data-weather="">
        <circle cx={236} cy={-8} r={46} fill={`url(#${id}-sun)`} />
        <circle cx={236} cy={-8} r={14} fill="#FFD27A" />
      </g>
      <Clouds />
      <ellipse cx={0} cy={300} rx={296} ry={14} fill="rgba(80,55,20,.12)" />
      <Ground />
      <g className="lt-world">{world}</g>
      <rect className="lt-shade" x={-302} y={-50} width={604} height={364} fill="#34405A" data-weather="" />
      <g className="lt-glows" data-weather="">
        {model.houses.map((house, i) => <Glow key={i} index={i} on={house.state === 'work'} fill={`url(#${id}-glow)`} />)}
      </g>
      <Rain seed={seedOf(color)} />
      <g data-layer="pings" />
      <g data-layer="coins" />
      <g className="lt-signs">
        <TreasuryAmount cash={model.hall.cash} />
        {model.shops.map(shop => <ShopSign key={shop.id} shop={shop} lot={LAYOUT.lots[shop.lot]} height={shopHeight(shop)} />)}
        {model.overflow > 0 && <TagPill className="lt-pill lt-more" x={more[0]} y={more[1]} label={COPY.diorama.moreLots(model.overflow)} tone="more" />}
      </g>
      <g data-layer="moments" />
      <g className="lt-pins">
        {model.people.map((person, i) => (
          <Pin key={person.id ?? i} index={i} house={person.house} tone={person.tone} initial={person.name.charAt(0)} />
        ))}
      </g>
    </svg>
  )
}
