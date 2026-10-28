// Coins carrying money between homes, shops and the town hall (spec 4.3),
// ported from mockup 08 (Scene.flow, launchFlow, Particles, ping): gold for
// spending (homes to shops, busier shops more often), green for pay (shops to
// working homes), purple for taxes (working homes or shops to the town hall),
// teal for help (the town hall to homes looking for work). Each lands with a
// ring. Coins and rings live in the motion layer and are timed on the scene's
// own clock (s.now), so pausing stops them where they are.
import { COIN_WEEKS_PER_SECOND, arcPath, coinsDue, easeInOut, pickWeighted, pingPose } from './motion.js'
import { FLOW_COLOURS, el } from './nodes.js'

const FLOWS = ['spend', 'pay', 'tax', 'help']
// Most alive at once in one scene (spec).
export const MAX_COINS = 160
const MAX_PINGS = 16
const PING_MS = 700

const clamp = (value, lo, hi) => Math.min(hi, Math.max(lo, value))
const r1 = value => Math.round(value * 10) / 10
const pick = list => list[Math.floor(Math.random() * list.length)]

// Who coins and walkers can come from or go to this week.
export function poolsOf(model) {
  const work = []
  const look = []
  const live = []
  model.houses.forEach((house, i) => {
    if (house.state === 'work') work.push(i)
    if (house.state === 'look') look.push(i)
    if (house.state !== 'home') live.push(i)
  })
  const open = model.shops.filter(shop => shop.state !== 'closed')
  const weights = open.map(shop => Math.max(1, shop.staff))
  const shops = new Map(model.shops.map(shop => [shop.id, shop]))
  return { work, look, live, open, weights, total: weights.reduce((sum, w) => sum + w, 0), shops }
}

function coinRoute(s, flow) {
  const { work, look, live, open, weights, total } = s.pools
  const { places } = s
  const shop = () => (open.length ? places.shop(pickWeighted(open, weights, total)) : null)
  const house = list => (list.length ? places.house(pick(list)) : null)
  if (flow === 'spend') return [house(live), shop()]
  if (flow === 'pay') return [shop(), house(work)]
  if (flow === 'tax') return [Math.random() < 0.5 && work.length ? house(work) : shop(), places.hall]
  return [places.hall, house(look.length ? look : live)]
}

function launchCoin(s, flow) {
  if (s.coins.length >= MAX_COINS) return
  const [a, b] = coinRoute(s, flow)
  if (!a || !b) return
  const colour = FLOW_COLOURS[flow]
  let coin = s.spare.pop()
  if (!coin) coin = { c: el(s.doc, 'circle', { r: 3, stroke: 'rgba(255,255,255,.8)', 'stroke-width': 0.7 }, s.layers.coins) }
  coin.c.style.display = ''
  coin.c.setAttribute('fill', colour)
  // The arch's height: the scene's own (places.arc), or the island's.
  const lift = s.places.arc ? s.places.arc(a, b) : 24 + Math.hypot(b[0] - a[0], b[1] - a[1]) * 0.12
  Object.assign(coin, { path: arcPath(a, b, lift), to: b, colour, t0: s.now, dur: 950 + Math.random() * 550 })
  s.coins.push(coin)
}

// The coins due for dt seconds of play with `towns` towns shown
// (none in the warm-up weeks, before the town has an economy).
export function launchCoins(s, model, dt, towns) {
  if (model.warmUp || !s.pools) return
  const due = coinsDue(s.debt, model.flows, dt * COIN_WEEKS_PER_SECOND, towns)
  s.debt = due.debt
  for (const flow of FLOWS) for (let n = 0; n < due.launches[flow]; n += 1) launchCoin(s, flow)
}

function ping(s, at, colour) {
  if (s.pings.length >= MAX_PINGS) return
  const node = el(s.doc, 'circle', { r: 3.2, class: 'lt-ping', stroke: colour }, s.layers.pings)
  const item = { node, x: r1(at[0]), y: r1(at[1]), t0: s.now }
  drawPing(item, 0)
  s.pings.push(item)
}

function drawPing(item, t) {
  const { scale, opacity } = pingPose(t)
  item.node.setAttribute('transform', `translate(${item.x} ${item.y}) scale(${scale})`)
  item.node.setAttribute('opacity', opacity)
}

export function stepCoins(s) {
  for (let n = s.coins.length - 1; n >= 0; n -= 1) {
    const coin = s.coins[n]
    const t = (s.now - coin.t0) / coin.dur
    if (t >= 1) {
      coin.c.style.display = 'none'
      s.coins.splice(n, 1)
      s.spare.push(coin)
      ping(s, coin.to, coin.colour)
      continue
    }
    const [x, y] = coin.path(easeInOut(clamp(t, 0, 1)))
    coin.c.setAttribute('cx', r1(x))
    coin.c.setAttribute('cy', r1(y))
  }
  for (let k = s.pings.length - 1; k >= 0; k -= 1) {
    const item = s.pings[k]
    const t = (s.now - item.t0) / PING_MS
    if (t >= 1) {
      item.node.remove()
      s.pings.splice(k, 1)
    } else drawPing(item, t)
  }
}

// Takes every coin and ring away (the coins are kept for reuse).
export function clearCoins(s) {
  for (const coin of s.coins) {
    coin.c.style.display = 'none'
    s.spare.push(coin)
  }
  s.coins = []
  for (const item of s.pings) item.node.remove()
  s.pings.length = 0
}
