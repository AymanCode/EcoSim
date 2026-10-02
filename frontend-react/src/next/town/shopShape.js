// A shop's box on its lot, shared by the drawing (shops.jsx) and the motion
// loop's height easing (heights.js): one floor per 9 staff (model.floorsOf),
// a lower shell once a closed shop is up for lease, and its two walls.
import { iso as P, pts } from './geometry.js'
import { WEEKS } from './model.js'

export const SHOP_BOX = { inset: 0.1, w: 0.8, d: 0.8 }

export const leased = shop => shop.state === 'closed' && shop.closedFor >= WEEKS.lease

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
