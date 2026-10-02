// Main Street's shapes, shared by its drawing (streetParts.jsx, MainStreet.jsx)
// and by its places for the motion loop (streetPlaces.js): which of the
// town's shops stand on the street, how tall each is drawn, its walls, and
// the week's model as the street's loop sees it. Ported from mockup 08's
// StreetScene (drawShop and apply). Pure.
import { STREET, STREET_CAPACITY } from './geometry.js'
import { leased } from './shopShape.js'

const clamp = (value, lo, hi) => Math.min(hi, Math.max(lo, value))
const r1 = value => Math.round(value * 10) / 10

// The pavement's edge, where every shop and civic building stands.
export const BASE = STREET.base

// A shop is on Main Street when it holds one of the 26 lots nearest the
// crossing (the island's lot numbers, nearest first).
export const onStreet = shop => shop.lot != null && shop.lot < STREET_CAPACITY

// A shop's height on the street: a 30-unit ground floor and 10 for each floor
// above (one floor per 9 staff, model.floorsOf); up for lease, a lower shell
// of one floor, as on the island (spec 4.2.9).
export const LEASE_SHELL = 40
const fullHeight = shop => 30 + 10 * shop.floors
export const streetHeight = shop => (leased(shop) ? Math.min(fullHeight(shop), LEASE_SHELL) : fullHeight(shop))

const at = (x, y) => `${r1(x)},${r1(y)}`

// A shop's two walls on its lot, h high: the front, and the darker strip down
// its right side.
export function streetWalls(lot, h) {
  const top = BASE - h
  const right = lot.x + lot.w
  return {
    left: [at(lot.x, top), at(right, top), at(right, BASE), at(lot.x, BASE)].join(' '),
    right: [at(right - 5, top), at(right, top), at(right, BASE), at(right - 5, BASE)].join(' '),
  }
}

// How many people stroll the pavement: one for every 15 staff in the town,
// 2 to 24, and 3 in the warm-up weeks (mockup 08).
export const strollers = model => (model.warmUp ? 3 : clamp(Math.round((model.facts?.staff ?? 0) / 15), 2, 24))

// The week as Main Street's motion loop sees it: only the shops on the street
// (coins land on their doors, signs rise over their roofs, their heights
// ease), no cars, and the people strolling the pavement.
export function streetModel(model) {
  return { ...model, shops: model.shops.filter(onStreet), traffic: { cars: 0, walkers: strollers(model) } }
}
