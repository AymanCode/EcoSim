// A shop that gains or loses a floor eases to its new height (spec 4.2), in
// the scene's own loop: React draws every shop at its new height, and before
// the browser paints, the loop puts an easing shop back at the height shown
// and then moves it on each frame for about 0.4 s: the walls stretch, the
// scaffold poles grow with them, the roof and what stands on it (and the sign
// above) move with the walls, and floor windows and scaffold rings above the
// height shown wait until the walls reach them. Only a single forward step
// while playing eases; any other change of week (a scrub, a jump) and
// reduced motion put shops straight at their new height. A shop's nodes are
// found once when its easing starts and again after each week's render
// (React may have redrawn it, say from scaffolding to a finished shop).
import { LAYOUT, iso, r1 } from './geometry.js'
import { SHOP_BOX, drawnHeight, shopWalls } from './shopShape.js'

const EASE_MS = 400
const easeOut = t => 1 - (1 - t) ** 3
const POLES = [0, 0.5, 1]

function nodesOf(group, sign) {
  if (!group) return null
  return {
    left: group.querySelector('.lt-shop-l'),
    right: group.querySelector('.lt-shop-r'),
    top: group.querySelector('.lt-shop-top'),
    steps: [...group.querySelectorAll('[data-z]')],
    poles: [...group.querySelectorAll('.lt-pole')],
    sign: sign ?? null,
  }
}

function paint(rec) {
  const n = rec.nodes
  if (!n) return
  const { left, right } = shopWalls(rec.lot, rec.shown)
  n.left?.setAttribute('points', left)
  n.right?.setAttribute('points', right)
  const lift = r1(rec.target - rec.shown)
  for (const node of [n.top, n.sign]) {
    if (!node) continue
    if (lift === 0) node.removeAttribute('transform')
    else node.setAttribute('transform', `translate(0 ${lift})`)
  }
  for (const step of n.steps) step.style.display = Number(step.dataset.z) > rec.shown + 0.5 ? 'none' : ''
  const x0 = rec.lot.gx + SHOP_BOX.inset
  const y1 = rec.lot.gy + SHOP_BOX.inset + SHOP_BOX.d + 0.05
  n.poles.forEach((pole, i) => pole.setAttribute('y2', iso(x0 + SHOP_BOX.w * (POLES[i] ?? 0), y1, rec.shown)[1]))
}

// Finds the drawn nodes of the shops in `recs` and paints them at the height shown.
function repaint(s, recs) {
  if (!recs.length) return
  const groups = new Map([...s.world.querySelectorAll('[data-kind="shop"]')].map(g => [g.dataset.id, g]))
  const signs = new Map([...s.world.querySelectorAll('[data-sign]')].map(g => [g.dataset.sign, g]))
  for (const rec of recs) {
    rec.nodes = nodesOf(groups.get(String(rec.id)), signs.get(String(rec.id)))
    paint(rec)
  }
}

// After a week's render: shops whose height changed start easing from the
// height shown (`ease`), or stand at the new height. A shop new to its lot
// stands at its height straight away.
export function syncHeights(s, shops, ease) {
  const seen = new Set()
  const settled = []
  for (const shop of shops) {
    const key = `${shop.lot}:${shop.id}`
    seen.add(key)
    const target = drawnHeight(shop)
    const rec = s.heights.get(key)
    if (!rec) {
      s.heights.set(key, { id: shop.id, lot: LAYOUT.lots[shop.lot], target, shown: target, from: target, t0: 0, nodes: null })
      continue
    }
    if (rec.target === target) continue
    rec.target = target
    if (ease) {
      rec.from = rec.shown
      rec.t0 = s.now
      s.easing.add(rec)
    } else {
      if (s.easing.delete(rec)) settled.push(rec)
      rec.shown = rec.from = target
    }
  }
  for (const [key, rec] of s.heights) {
    if (seen.has(key)) continue
    s.heights.delete(key)
    s.easing.delete(rec)
  }
  repaint(s, [...s.easing, ...settled])
}

// Moves every easing shop on to the scene clock's time.
export function stepHeights(s) {
  for (const rec of s.easing) {
    const t = Math.min(1, (s.now - rec.t0) / EASE_MS)
    rec.shown = t >= 1 ? rec.target : rec.from + (rec.target - rec.from) * easeOut(t)
    paint(rec)
    if (t >= 1) s.easing.delete(rec)
  }
}

// Puts every easing shop straight at its height (a jump, or the card hidden).
export function settleHeights(s) {
  for (const rec of s.easing) {
    rec.shown = rec.target
    if (rec.nodes?.left?.isConnected) paint(rec)
  }
  s.easing.clear()
}
