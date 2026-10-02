// A shop's box on its island lot, shared by the drawing (shops.jsx) and the
// island's height easing (islandPlaces.js, for heights.js): one floor per 9
// staff (model.floorsOf), a lower shell once a closed shop is up for lease,
// its two walls and its scaffold poles.
import { iso as P, pts } from './geometry.js'
import { leased } from './model.js'

export const SHOP_BOX = { inset: 0.1, w: 0.8, d: 0.8 }

// The height a shop's staff calls for, and the height it is drawn at.
export const shopHeight = shop => shop.floors * 8 + 12
export const drawnHeight = shop => (leased(shop) ? Math.min(shopHeight(shop), 14) : shopHeight(shop))

// A shop's two walls on its lot, h high.
export function shopWalls(lot, h) {
  const x0 = lot.gx + SHOP_BOX.inset
  const y0 = lot.gy + SHOP_BOX.inset
  const { w, d } = SHOP_BOX
  return {
    left: pts([P(x0, y0 + d), P(x0 + w, y0 + d), P(x0 + w, y0 + d, h), P(x0, y0 + d, h)]),
    right: pts([P(x0 + w, y0), P(x0 + w, y0 + d), P(x0 + w, y0 + d, h), P(x0 + w, y0, h)]),
  }
}

// Where the scaffold poles stand along the shop's front (left, middle, right),
// and the point of pole `u` at height z.
export const POLES = [0, 0.5, 1]
export function polePoint(lot, u, z) {
  return P(lot.gx + SHOP_BOX.inset + SHOP_BOX.w * u, lot.gy + SHOP_BOX.inset + SHOP_BOX.d + 0.05, z)
}
