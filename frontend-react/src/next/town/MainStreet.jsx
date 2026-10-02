// Main Street, up close (spec 4.3.17): one town seen from the side, in the
// picture-book style of mockup 07 option B, as mockup 08's StreetScene draws
// it. The shops on the 26 lots nearest the crossing stand along the pavement,
// the town hall and the bank in the middle, the 100 houses in rows on the
// hill behind, under the same weather as the town's card.
//
// Like the Diorama it is three stacked svgs sharing one viewBox and one box:
//
//   back    the sky, the sun and the hills (their colours follow the weather);
//   world   the houses, the street, the shops, the town hall with its money
//           and queue, the bank, the walk group where the motion loop puts
//           the people on the pavement, the shade, and the pins: everything
//           the viewer can point at;
//   motion  rain or snow, coins, rings, floating signs and dust puffs.
//
// The world has no CSS animations or transitions; a week change swaps its
// classes at once and the motion loop (useSceneMotion, with Main Street's
// places) moves what moves by writing attributes. The parts that never
// change are made once, and the walk group has no React children, so a week
// change neither rebuilds them nor touches what the loop added.
import { memo, useId, useImperativeHandle, useMemo, useRef } from 'react'
import { STREET } from './geometry.js'
import { WEEKS } from './model.js'
import { raindrops } from './mood.js'
import { SHOP_COLOURS } from './nodes.js'
import { STREET_PLACES } from './streetPlaces.js'
import { streetModel } from './streetShape.js'
import { StreetBank, StreetHall, StreetHouse, StreetPin, StreetQueue, StreetShop, StreetTreasury } from './streetParts.jsx'
import useSceneMotion from './useSceneMotion.js'
import './town.css'

const W = 1200
const H = 340
const RAIN_BOX = { x: 0, y: -10, w: 1210, h: 330 }
const DROP_GROUPS = 7
const SECTORS = Object.keys(SHOP_COLOURS)
const r1 = value => Math.round(value * 10) / 10

// The sky, the sun and two hills with the meadow below them.
const Back = memo(function Back({ id }) {
  return (
    <svg className="lt-layer lt-back" data-layer="back" viewBox={STREET.viewBox} aria-hidden="true" focusable="false">
      <defs>
        <linearGradient id={`${id}-sky`} x1={0} y1={0} x2={0} y2={1} data-weather="sky">
          <stop className="lt-sky-top" offset="0%" />
          <stop className="lt-sky-bottom" offset="100%" />
        </linearGradient>
      </defs>
      <rect width={W} height={H} fill={`url(#${id}-sky)`} />
      <circle className="lt-sun" data-weather="sun" cx={1060} cy={40} r={22} fill="#FBD7A2" />
      <g className="lt-hills" data-weather="hills">
        <path className="lt-hill-a" d="M0 74 C 180 40, 360 70, 560 52 S 900 36, 1200 66 L1200 340 L0 340 Z" />
        <path className="lt-hill-b" d="M0 104 C 220 82, 500 98, 760 86 S 1060 94, 1200 100 L1200 340 L0 340 Z" />
        <rect className="lt-meadow" x={0} y={206} width={W} height={90} />
      </g>
    </svg>
  )
})

// The pavement, the road with its lane line, and the far kerb.
const GROUND = (
  <g className="lt-street-ground">
    <rect x={0} y={288} width={W} height={14} fill="#E9E1D3" />
    <rect x={0} y={302} width={W} height={30} fill="#D8CFBF" />
    <line x1={0} y1={317} x2={W} y2={317} stroke="#F4EFE6" strokeWidth={1.6} strokeDasharray="14 12" />
    <rect x={0} y={332} width={W} height={8} fill="#E9E1D3" />
  </g>
)
// Where the loop draws the people on the pavement (STREET_PLACES.put).
const WALK = <g data-layer="walk" />

// Rain (or snow in winter), in DROP_GROUPS groups the loop moves down.
const Rain = memo(function Rain({ seed }) {
  const groups = useMemo(() => {
    const out = Array.from({ length: DROP_GROUPS }, () => [])
    raindrops(seed, 140, RAIN_BOX).forEach(drop => {
      out[Math.min(DROP_GROUPS - 1, Math.floor((-drop.delay / 0.7) * DROP_GROUPS))].push(drop)
    })
    return out
  }, [seed])
  return (
    <g data-layer="rain" className="lt-rain" data-weather="rain">
      {groups.map((drops, k) => (
        <g key={k} data-drops={k}>
          {drops.map((drop, i) => <line key={i} x1={r1(drop.x)} y1={r1(drop.y)} x2={r1(drop.x - 2.5)} y2={r1(drop.y + 9)} />)}
        </g>
      ))}
    </g>
  )
})

const Motion = memo(function Motion({ seed }) {
  return (
    <svg className="lt-layer lt-motion" data-layer="motion" viewBox={STREET.viewBox} aria-hidden="true" focusable="false">
      <Rain seed={seed} />
      <g data-layer="pings" />
      <g data-layer="coins" />
      <g data-layer="moments" />
    </svg>
  )
})

// A seed from the town's colour, so the street's rain differs from the town's.
const seedOf = text => [...`street ${text ?? ''}`].reduce((hash, ch) => Math.imul(hash ^ ch.charCodeAt(0), 16777619), 2166136261) | 0

function MainStreet({ model, color, sceneRef, playing = false, speed = 1, towns = 1, scrubs = 0, ended = false }) {
  const id = useId().replace(/[^\w-]/g, '')
  const rootRef = useRef(null)
  useImperativeHandle(sceneRef, () => rootRef.current, [])
  // The loop sees only the street's shops (coins land on their doors).
  const scene = useMemo(() => streetModel(model), [model])
  useSceneMotion(rootRef, { model: scene, places: STREET_PLACES, playing, speed, towns, scrubs, ended })

  const glow = `url(#${id}-sglow)`
  const byLot = new Array(STREET.lots.length).fill(null)
  for (const shop of scene.shops) byLot[shop.lot] = shop

  return (
    <div ref={rootRef} className="lt-stage" aria-hidden="true">
      <Back id={id} />
      <svg className="lt-scene lt-street-scene" data-layer="world" viewBox={STREET.viewBox} aria-hidden="true" focusable="false">
        <defs>
          <radialGradient id={`${id}-sglow`}>
            <stop offset="0%" stopColor="#FFD36B" stopOpacity={0.8} />
            <stop offset="100%" stopColor="#FFD36B" stopOpacity={0} />
          </radialGradient>
          {SECTORS.map(sector => (
            <pattern key={sector} id={`${id}-aw-${sector}`} width={6} height={6} patternUnits="userSpaceOnUse">
              <rect width={6} height={6} fill={SHOP_COLOURS[sector].a} />
              <rect width={3} height={6} fill="#FFFFFF" opacity={0.55} />
            </pattern>
          ))}
        </defs>
        <g className="lt-street-homes">
          {model.houses.map((house, i) => (
            <StreetHouse key={i} index={i} state={house.state} long={house.state === 'look' && house.weeks >= WEEKS.longOut} glow={glow} />
          ))}
        </g>
        {GROUND}
        <g className="lt-street-shops">
          {STREET.lots.map((lot, n) => {
            const shop = byLot[n]
            if (!shop) return null
            const sector = SHOP_COLOURS[shop.sector] ? shop.sector : 'Other'
            return <StreetShop key={`${n}:${shop.id}`} shop={shop} lot={lot} awning={`url(#${id}-aw-${sector})`} />
          })}
        </g>
        <StreetHall color={color} banner={model.hall.banner} />
        <StreetTreasury cash={model.hall.cash} />
        <StreetQueue size={model.hall.queue} />
        <StreetBank />
        {WALK}
        <rect className="lt-shade" x={0} y={0} width={W} height={H} fill="#151E32" data-weather="shade" />
        <g className="lt-pins">
          {model.people.map((person, i) => (
            <StreetPin key={person.id ?? i} index={i} house={person.house} tone={person.tone} initial={person.name.charAt(0)} />
          ))}
        </g>
      </svg>
      <Motion seed={seedOf(color)} />
    </div>
  )
}

export default memo(MainStreet)
