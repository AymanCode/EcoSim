// Main Street's places for the motion loop (useSceneMotion; see
// islandPlaces.js for what each member means), from mockup 08's StreetScene
// (houseAt, shopAt, hallAt, route and the walkers in apply and frame).
//
// Positions are the street's own units (STREET.viewBox, 1200 × 340). Coins
// arc between the homes on the hill, the shop doors and the town hall. People
// stroll the pavement, and anyone the week moves (strolling, hired or laid
// off) is drawn in the street's walk group, after the shops and civic
// buildings and under the shade, as nothing on the street stands in front of
// the pavement. Someone laid off walks out of the shop door and off along the
// pavement towards home, carrying a box; a new hire walks back the other way
// to the door. Main Street has no cars: its traffic always has none, so the
// loop never asks it for one. Its shops ease to a new height like the
// island's; it has no clouds.
import { STREET } from './geometry.js'
import { SHIRTS, figureNode, swingLegs } from './nodes.js'
import { BASE, streetHeight, streetWalls } from './streetShape.js'

const clamp = (value, lo, hi) => Math.min(hi, Math.max(lo, value))
const r1 = value => Math.round(value * 10) / 10
const pick = list => list[Math.floor(Math.random() * list.length)]

// Where people walk: the pavement in front of the shops (y), and how far a
// person hired or laid off walks along it in their 2.6 to 3.2 s.
const PAVEMENT = { y: BASE + 8, depth: 3, door: BASE + 7, home: BASE + 10 }
const STROLL = 120
const FIGURE_SCALE = ' scale(1.3)'

const door = shop => {
  const lot = STREET.lots[shop.lot]
  return lot.x + lot.w / 2
}

function put(s, thing, [x, y]) {
  if (thing.node.parentNode !== s.where.walk) s.where.walk.appendChild(thing.node)
  thing.node.setAttribute('transform', `translate(${r1(x)} ${r1(y)})${thing.scale}`)
}

export const STREET_PLACES = {
  attach: root => ({ walk: root.querySelector('[data-layer="walk"]') }),

  house: index => {
    const spot = STREET.houses[index]
    return [spot.x, r1(spot.y - 18 * spot.s)]
  },
  shop: shop => [door(shop), BASE - 20],
  shopTop: shop => [door(shop), BASE - streetHeight(shop) - 14],
  hall: [STREET.hallX, BASE - 74],
  bankTop: [STREET.bankX, BASE - 66],
  // Coins rise higher the farther they go along the street.
  arc: (a, b) => 36 + Math.abs(b[0] - a[0]) * 0.08,

  traffic: model => model.traffic,
  newWalker(s) {
    const { g, legs } = figureNode(s.doc, pick(SHIRTS))
    const walker = {
      node: g, legs, x: Math.random() * 1200, y: PAVEMENT.y + Math.random() * PAVEMENT.depth,
      v: (Math.random() < 0.5 ? -1 : 1) * (14 + Math.random() * 12), ph: Math.random() * 6, scale: FIGURE_SCALE,
    }
    put(s, walker, [walker.x, walker.y])
    return walker
  },
  // Off one end of the street and back in at the other.
  moveWalker(s, walker, dt) {
    walker.x += walker.v * dt
    if (walker.x < -10) walker.x = 1210
    if (walker.x > 1210) walker.x = -10
    walker.ph += dt * 9
    put(s, walker, [walker.x, walker.y])
    swingLegs(walker.legs, walker.ph)
  },

  // The second person from one shop sets off beside the first.
  route(shop, home, j) {
    const x = door(shop) + (j - 0.5) * 8
    const toward = clamp(STREET.houses[home].x - x, -STROLL, STROLL)
    return { door: [x, PAVEMENT.door], home: [x + toward, PAVEMENT.home] }
  },
  mover: node => ({ node, scale: FIGURE_SCALE }),
  put,

  // A height is how far the roof stands above the pavement, so the roof and
  // what stands on it move down on screen by what the walls still have to drop.
  heights: {
    target: streetHeight,
    walls: (shop, h) => streetWalls(STREET.lots[shop.lot], h),
    lift: (target, h) => target - h,
    pole: (shop, i, h) => r1(BASE - h),
  },
}
