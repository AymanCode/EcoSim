// This week's moments (spec 4.2.12), ported from mockup 08 (onWeek, moment,
// puff, walkTo): when the clock steps forward one week while playing, floating
// signs rise over the shops that closed, opened, lost or gained jobs and over
// the bank when loans go bad (it flashes red); a closed shop leaves a puff of
// dust; people laid off walk home carrying a box and new hires walk to work.
// Also the town hall's ring, which pulses twice when the rules change. Signs
// and puffs live in the motion layer, walkers where the scene's places put
// them; all are timed on the scene's own clock (s.now), so pausing stops them
// where they are, and drawn by writing attributes (no CSS animations).
import { COPY, formatMoneyShort } from '../catalog.js'
import { flashOpacity, puffPose, ringPose, risePose, weekMoments, weekWalkers } from './motion.js'
import { WALKER_SHIRTS, el, figureNode, pillNode, swingLegs } from './nodes.js'

const MOMENTS = COPY.diorama.moments
// Most alive at once in one scene, so a busy run at 8 weeks a second does not
// pile them up: each lives 1 to 3 seconds, 8 to 25 weeks.
const MAX = { signs: 8, puffs: 12, movers: 24 }
const MS = { sign: 2800, puff: 1100, flash: 1200, ring: 1000 }

const clamp = (value, lo, hi) => Math.min(hi, Math.max(lo, value))
const r1 = value => Math.round(value * 10) / 10
const pick = list => list[Math.floor(Math.random() * list.length)]

// A floating sign over a place (`key`: a shop's id, or the bank). A newer sign
// over the same place replaces the older one rather than piling on top of it.
function sign(s, key, at, label, tone) {
  const older = s.signs.findIndex(item => item.key === key)
  if (older >= 0) s.signs.splice(older, 1)[0].node.remove()
  const node = el(s.doc, 'g', { class: 'lt-moment' }, s.layers.moments)
  node.appendChild(pillNode(s.doc, at[0], at[1] - 6, label, tone, 7))
  const item = { key, node, t0: s.now }
  drawSign(item, 0)
  s.signs.push(item)
  while (s.signs.length > MAX.signs) s.signs.shift().node.remove()
}

function drawSign(item, t) {
  const { dy, opacity } = risePose(t)
  item.node.setAttribute('transform', `translate(0 ${dy})`)
  item.node.setAttribute('opacity', opacity)
}

function puff(s, at) {
  for (const [dx, dy] of [[-5, 4], [5, 3], [0, 6]]) {
    const node = el(s.doc, 'circle', { r: 4, class: 'lt-puff' }, s.layers.moments)
    const item = { node, x: r1(at[0] + dx), y: r1(at[1] + dy + 10), t0: s.now }
    drawPuff(item, 0)
    s.puffs.push(item)
  }
  while (s.puffs.length > MAX.puffs) s.puffs.shift().node.remove()
}

function drawPuff(item, t) {
  const { scale, opacity } = puffPose(t)
  item.node.setAttribute('transform', `translate(${item.x} ${item.y}) scale(${scale})`)
  item.node.setAttribute('opacity', opacity)
}

// A person laid off walks from the shop to a dark home carrying a box; a new
// hire walks from a lit home to the shop. The second from one shop sets off a
// moment later, beside the first.
function walkTo(s, shop, kind, j) {
  if (s.movers.length >= MAX.movers) return
  const { look, live, work } = s.pools
  const homes = kind === 'lay' ? (look.length ? look : live) : work
  if (!homes.length) return
  const { door, home } = s.places.route(shop, pick(homes), j)
  const { g, legs } = figureNode(s.doc, WALKER_SHIRTS[kind], kind === 'lay')
  g.classList.add('is-moving')
  const mover = { node: g, legs, from: kind === 'lay' ? door : home, to: kind === 'lay' ? home : door, t0: s.now + j * 260, dur: 2600 + Math.random() * 600, slot: null, scale: ' scale(.9)' }
  g.style.opacity = j > 0 ? '0' : '1'
  s.places.put(s, mover, mover.from)
  s.movers.push(mover)
}

// Closures (with a puff of dust), openings, big layoffs and hirings, and bad
// loans (the bank flashes), at most four signs; then the walkers.
export function popWeek(s, model) {
  const { shops } = s.pools
  const { places } = s
  for (const id of model.week.closed) {
    const shop = shops.get(id)
    if (shop) puff(s, places.shopTop(shop))
  }
  // One sign per place a week, the most telling; only drawn shops count.
  const used = new Set()
  const shown = weekMoments(model, Infinity).filter(moment => {
    const key = moment.kind === 'bad' ? 'bank' : moment.firmId
    if (used.has(key) || (key !== 'bank' && !shops.has(key))) return false
    used.add(key)
    return true
  }).slice(0, 4)
  for (const moment of shown) {
    if (moment.kind === 'bad') {
      if (s.flash.node) s.flash.t0 = s.now
      sign(s, 'bank', places.bankTop, MOMENTS.badLoans(formatMoneyShort(moment.amount)), 'closed')
      continue
    }
    const at = places.shopTop(shops.get(moment.firmId))
    const key = moment.firmId
    if (moment.kind === 'closed') sign(s, key, at, MOMENTS.closed, 'closed')
    else if (moment.kind === 'opened') sign(s, key, at, MOMENTS.opened, 'fresh')
    else if (moment.kind === 'lost') sign(s, key, at, MOMENTS.lost(moment.n), 'closed')
    else sign(s, key, at, MOMENTS.gained(moment.n), 'hiring')
  }
  const perShop = new Map()
  for (const walker of weekWalkers(model)) {
    const shop = shops.get(walker.firmId)
    if (!shop) continue
    const j = perShop.get(walker.firmId) ?? 0
    perShop.set(walker.firmId, j + 1)
    walkTo(s, shop, walker.kind, j)
  }
}

// A new ring round the town hall (React draws one for each change of rules)
// pulses twice if it arrives while the scene moves; otherwise it just stands.
export function watchRing(s, root, moving) {
  const node = root.querySelector('.lt-hall-ring')
  if (node === s.ring.node) return
  if (s.ring.node?.isConnected) restRing(s.ring.node)
  s.ring = { node, t0: node && moving ? s.now : null }
}

function restRing(node) {
  node.removeAttribute('transform')
  node.removeAttribute('opacity')
}

// Moves everything a week set going on to the scene clock's time.
export function stepMoments(s) {
  for (let k = s.movers.length - 1; k >= 0; k -= 1) {
    const mover = s.movers[k]
    const t = (s.now - mover.t0) / mover.dur
    if (t >= 1) {
      mover.node.remove()
      s.movers.splice(k, 1)
      continue
    }
    const e = clamp(t, 0, 1)
    s.places.put(s, mover, mover.from.map((v, i) => v + (mover.to[i] - v) * e))
    mover.node.style.opacity = t < 0 ? '0' : t > 0.9 ? r1((1 - t) * 10).toString() : '1'
    swingLegs(mover.legs, s.now / 90)
  }
  for (let k = s.signs.length - 1; k >= 0; k -= 1) {
    const item = s.signs[k]
    const t = (s.now - item.t0) / MS.sign
    if (t >= 1) {
      item.node.remove()
      s.signs.splice(k, 1)
    } else drawSign(item, t)
  }
  for (let k = s.puffs.length - 1; k >= 0; k -= 1) {
    const item = s.puffs[k]
    const t = (s.now - item.t0) / MS.puff
    if (t >= 1) {
      item.node.remove()
      s.puffs.splice(k, 1)
    } else drawPuff(item, t)
  }
  if (s.flash.t0 != null) {
    const t = (s.now - s.flash.t0) / MS.flash
    s.flash.node.setAttribute('opacity', t >= 1 ? '0' : flashOpacity(t))
    if (t >= 1) s.flash.t0 = null
  }
  if (s.ring.t0 != null) {
    const t = (s.now - s.ring.t0) / MS.ring
    if (t >= 1 || !s.ring.node.isConnected) {
      restRing(s.ring.node)
      s.ring.t0 = null
    } else {
      const { scale, opacity } = ringPose(t)
      s.ring.node.setAttribute('transform', `scale(${scale})`)
      s.ring.node.setAttribute('opacity', opacity)
    }
  }
}

// How many one-off things are still under way (signs, puffs, walkers, the
// flash and the ring's pulse).
export const momentsUnderWay = s => s.signs.length + s.puffs.length + s.movers.length + (s.flash.t0 != null ? 1 : 0) + (s.ring.t0 != null ? 1 : 0)

// Takes away everything a week set going: signs, puffs, walkers, the bank's
// flash and the ring's pulse.
export function clearMoments(s) {
  for (const list of [s.signs, s.puffs, s.movers]) {
    for (const thing of list) thing.node.remove()
    list.length = 0
  }
  if (s.flash.t0 != null) s.flash.node.setAttribute('opacity', '0')
  s.flash.t0 = null
  if (s.ring.t0 != null && s.ring.node?.isConnected) restRing(s.ring.node)
  s.ring.t0 = null
}
