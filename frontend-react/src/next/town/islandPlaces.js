// The island's places for the motion loop (useSceneMotion): everything the
// loop needs to know about where things are in this kind of picture. The loop
// asks a scene's places object and nothing else about its layout, so another
// kind of scene (Main Street, Task 8) plugs in its own object with the same
// members:
//
//   attach(root)            what the scene finds once in its drawing, kept
//                           as s.where (here: the per-tile slots)
//   house(index), shop(shop), shopTop(shop), hall, bankTop
//                           screen points where coins leave and land and
//                           where floating signs rise
//   traffic(model)          how many cars and people are out this week
//   newCar(s), newWalker(s) a car or person (a node and its state), drawn
//   moveCar(s, car, dt), moveWalker(s, walker, dt)
//                           moves one on for dt seconds, and draws it
//   route(shop, home, j)    a person walking between a shop's door and home
//                           number `home`, in the places' own coordinates
//   put(s, thing, at)       draws a moving thing (thing.node) at `at`
//
// On the island, positions are tile coordinates [gx, gy]; cars and people
// walk the two roads; anything moving is drawn inside the slot of the tile
// under it, an empty group just after the tile's buildings in painter's
// order, so buildings nearer the viewer hide it.
import { GRID, LAYOUT, ROAD, iso } from './geometry.js'
import { CAR_COLOURS, SHIRTS, carNode, figureNode, swingLegs } from './nodes.js'

const clamp = (value, lo, hi) => Math.min(hi, Math.max(lo, value))
const pick = list => list[Math.floor(Math.random() * list.length)]

// A car or person on a road: along the x road (pos is gx) or the y road.
const along = thing => (thing.axis === 'x' ? [thing.pos, thing.lane] : [thing.lane, thing.pos])

function put(s, thing, [gx, gy]) {
  const key = `${clamp(Math.floor(gx), 0, GRID - 1)},${clamp(Math.floor(gy), 0, GRID - 1)}`
  if (thing.slot !== key) {
    s.where.slots.get(key)?.appendChild(thing.node)
    thing.slot = key
  }
  const [x, y] = iso(gx, gy)
  thing.node.setAttribute('transform', `translate(${x} ${y})${thing.scale}`)
}

export const ISLAND = {
  attach(root) {
    const slots = new Map()
    for (const slot of root.querySelectorAll('[data-slot]')) slots.set(slot.dataset.slot, slot)
    return { slots }
  },

  house: index => {
    const tile = LAYOUT.houses[index]
    return iso(tile.gx + 0.5, tile.gy + 0.5, 12)
  },
  shop: shop => {
    const lot = LAYOUT.lots[shop.lot]
    return iso(lot.gx + 0.5, lot.gy + 0.5, shop.floors * 8 + 15)
  },
  shopTop: shop => {
    const lot = LAYOUT.lots[shop.lot]
    return iso(lot.gx + 0.5, lot.gy + 0.5, shop.floors * 8 + 12 + 14)
  },
  hall: iso(8.88, 8.88, 34),
  bankTop: iso(6, 6, 34),

  // Cars follow this week's sales, people on the pavements how many have work.
  traffic: model => model.traffic,
  newCar(s) {
    const axis = Math.random() < 0.5 ? 'x' : 'y'
    const dir = Math.random() < 0.5 ? -1 : 1
    const car = { node: carNode(s.doc, axis, pick(CAR_COLOURS)), axis, dir, lane: ROAD + (dir > 0 ? 0.68 : 0.32), pos: 0.5 + Math.random() * 15, v: 1.1 + Math.random() * 0.7, slot: null, scale: '' }
    put(s, car, along(car))
    return car
  },
  newWalker(s) {
    const { g, legs } = figureNode(s.doc, pick(SHIRTS))
    const walker = { node: g, legs, axis: Math.random() < 0.5 ? 'x' : 'y', lane: ROAD + (Math.random() < 0.5 ? 0.07 : 0.93), pos: 0.5 + Math.random() * 15, dir: Math.random() < 0.5 ? -1 : 1, v: 0.35 + Math.random() * 0.25, ph: Math.random() * 6, slot: null, scale: ' scale(.9)' }
    put(s, walker, along(walker))
    return walker
  },
  moveCar(s, car, dt) {
    car.pos += car.dir * car.v * dt
    if (car.pos > GRID - 0.25 || car.pos < 0.25) {
      car.dir *= -1
      car.lane = ROAD + (car.dir > 0 ? 0.68 : 0.32)
    }
    put(s, car, along(car))
  },
  moveWalker(s, walker, dt) {
    walker.pos += walker.dir * walker.v * dt
    if (walker.pos > GRID - 0.3 || walker.pos < 0.3) walker.dir *= -1
    walker.ph += dt * 8
    put(s, walker, along(walker))
    swingLegs(walker.legs, walker.ph)
  },

  // The second person from one shop sets off beside the first.
  route(shop, home, j) {
    const lot = LAYOUT.lots[shop.lot]
    const house = LAYOUT.houses[home]
    return { door: [lot.gx + 0.5 + (j - 0.5) * 0.2, lot.gy + 0.5], home: [house.gx + 0.5, house.gy + 0.9] }
  },
  put,
}
