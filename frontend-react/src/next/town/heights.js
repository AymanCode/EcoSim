// A shop that gains or loses a floor eases to its new height (spec 4.2), in
// the scene's own loop: React draws every shop at its new height, and before
// the browser paints, the loop puts an easing shop back at the height shown
// and then moves it on each frame for about 0.4 s: the walls stretch, the
// scaffold poles grow with them, the roof and what stands on it (and the sign
// above) move with the walls, and floor windows and scaffold rings above the
// height shown wait until the walls reach them. Only a single forward step
// while playing eases; any other change of week (a scrub, a jump, Enlarge) and
// reduced motion put shops straight at their new height. A shop's nodes are
// found when its easing starts and again after each week's render (React may
// have redrawn it, say from scaffolding to a finished shop).
//
// The nodes are found by their marks (a shop's [data-kind="shop"][data-id]
// group with .lt-shop-l, .lt-shop-r, .lt-shop-top, [data-z] and .lt-pole
// parts, and its [data-sign] group); the geometry comes from the scene's
// places (places.heights), so each kind of scene draws its own shops. A scene
// whose places have no `heights` keeps its shops as React draws them.
//
//   places.heights.target(shop)        the height React draws the shop at
//   places.heights.walls(shop, h)      { left, right } wall points at height h
//   places.heights.lift(target, h)     how far up the roof and sign move, on
//                                      screen, between height h and target
//   places.heights.pole(shop, i, h)    scaffold pole i's top (y2) at height h

const EASE_MS = 400
const easeOut = t => 1 - (1 - t) ** 3
const r1 = value => Math.round(value * 10) / 10

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

function paint(geo, rec) {
  const n = rec.nodes
  if (!n) return
  const { left, right } = geo.walls(rec.shop, rec.shown)
  n.left?.setAttribute('points', left)
  n.right?.setAttribute('points', right)
  const lift = r1(geo.lift(rec.target, rec.shown))
  for (const node of [n.top, n.sign]) {
    if (!node) continue
    if (lift === 0) node.removeAttribute('transform')
    else node.setAttribute('transform', `translate(0 ${lift})`)
  }
  for (const step of n.steps) step.style.display = Number(step.dataset.z) > rec.shown + 0.5 ? 'none' : ''
  n.poles.forEach((pole, i) => pole.setAttribute('y2', geo.pole(rec.shop, i, rec.shown)))
}

// Finds the drawn nodes of the shops in `recs` and paints them at the height shown.
function repaint(s, recs) {
  if (!recs.length) return
  const groups = new Map([...s.world.querySelectorAll('[data-kind="shop"]')].map(g => [g.dataset.id, g]))
  const signs = new Map([...s.world.querySelectorAll('[data-sign]')].map(g => [g.dataset.sign, g]))
  for (const rec of recs) {
    rec.nodes = nodesOf(groups.get(String(rec.shop.id)), signs.get(String(rec.shop.id)))
    paint(s.places.heights, rec)
  }
}

// After a week's render: shops whose height changed start easing from the
// height shown (`ease`), or stand at the new height React just drew; an
// easing shop whose height did not change is found again where React drew it.
// A shop new to its lot stands at its height straight away. Called before
// settleHeights on a jump, so a shop caught mid-ease ends at its new height.
export function syncHeights(s, shops, ease) {
  const geo = s.places.heights
  if (!geo) return
  const seen = new Set()
  const settled = []
  for (const shop of shops) {
    const key = `${shop.lot}:${shop.id}`
    seen.add(key)
    const target = geo.target(shop)
    const rec = s.heights.get(key)
    if (!rec) {
      s.heights.set(key, { shop, target, shown: target, from: target, t0: 0, nodes: null })
      continue
    }
    rec.shop = shop
    if (rec.target === target) continue
    rec.target = target
    if (ease) {
      rec.from = rec.shown
      rec.t0 = s.now
      s.easing.add(rec)
    } else {
      // React drew the new height; anything the loop left on the shop goes.
      s.easing.delete(rec)
      if (rec.nodes) settled.push(rec)
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
  const geo = s.places.heights
  for (const rec of s.easing) {
    const t = Math.min(1, (s.now - rec.t0) / EASE_MS)
    rec.shown = t >= 1 ? rec.target : rec.from + (rec.target - rec.from) * easeOut(t)
    paint(geo, rec)
    if (t >= 1) s.easing.delete(rec)
  }
}

// Puts every easing shop straight at its height (a jump, or the card hidden).
export function settleHeights(s) {
  for (const rec of s.easing) {
    rec.shown = rec.target
    if (rec.nodes?.left?.isConnected) paint(s.places.heights, rec)
  }
  s.easing.clear()
}
