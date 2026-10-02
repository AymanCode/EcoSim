// What moves in a town drawing between weeks (spec sections 4 and 7), ported
// from mockup 08 (IsoScene.frame, Scene.flow, launchFlow, ping, Particles,
// newWalker, newCar, place, onWeek, walkTo, moment, puff, paintMood): the
// weather easing to a new mood, clouds drifting, cars and people on the
// roads, coins carrying money, and, when the clock steps forward one week
// while playing, that week's floating signs, dust puffs, the bank's red flash
// and the people hired or laid off walking between shop and home.
//
// One requestAnimationFrame loop per scene. It never sets React state: it
// writes attributes, classes and CSS variables, and adds its own nodes to the
// layers and tile slots the Diorama leaves empty for it (data-layer,
// data-slot). It runs while the run plays; paused, everything in flight stops
// where it is (the scene's own clock stops, and so do the signs' and rings'
// CSS animations) and the loop sleeps once the weather has settled. A change
// of week that is not a single step forward while playing (a scrub, even one
// week on, or a jump) clears what was moving and changes the weather at once.
// With prefers-reduced-motion nothing travels and there are no floating
// signs. A card hidden by Enlarge does nothing at all.
import { useLayoutEffect, useRef } from 'react'
import { COPY, formatMoneyShort } from '../catalog.js'
import { CLOUDS, GRID, LAYOUT, ROAD, iso } from './geometry.js'
import { COIN_WEEKS_PER_SECOND, arcPath, coinsDue, easeInOut, easeToward, isStep, pickWeighted, weekMoments, weekWalkers } from './motion.js'
import { CAR_COLOURS, FLOW_COLOURS, SHIRTS, WALKER_SHIRTS, carNode, el, figureNode, pillNode } from './nodes.js'
import { paintWeather, weatherOf } from './weather.js'

const FLOWS = ['spend', 'pay', 'tax', 'help']
const MOMENTS = COPY.diorama.moments
// Most alive at once in one scene: coins (spec), the rings where coins land
// (spec), floating signs, dust puffs and walkers (so a busy run at 8 weeks a
// second does not pile them up: each lives 1 to 3 seconds, 8 to 25 weeks).
const MAX = { coins: 160, pings: 16, signs: 8, puffs: 12, movers: 24 }
const LIFE = { ping: 720, sign: 2850, puff: 1150 }

const clamp = (value, lo, hi) => Math.min(hi, Math.max(lo, value))
const r1 = value => Math.round(value * 10) / 10
const pick = list => list[Math.floor(Math.random() * list.length)]

// ---------- the island's places ----------

// Where coins leave and land and where floating signs rise, per kind of
// scene (mode). Only the island exists yet; Main Street adds its own.
const ISLAND = {
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
}
const PLACES = { island: ISLAND }

// ---------- building the scene ----------

function sceneOf(svg, mode) {
  const places = PLACES[mode]
  if (!places) throw new Error(`useSceneMotion: no '${mode}' scene`)
  const media = window.matchMedia?.('(prefers-reduced-motion: reduce)') ?? null
  const layer = name => svg.querySelector(`[data-layer="${name}"]`)
  const slots = new Map()
  for (const slot of svg.querySelectorAll('[data-slot]')) slots.set(slot.dataset.slot, slot)
  return {
    doc: svg.ownerDocument,
    places,
    media,
    reduce: Boolean(media?.matches),
    hidden: false,
    slots,
    layers: { coins: layer('coins'), pings: layer('pings'), moments: layer('moments') },
    flash: svg.querySelector('[data-flash="bank"]'),
    weather: weatherOf(svg),
    clouds: [...svg.querySelectorAll('[data-cloud]')].map(g => {
      const start = CLOUDS[Number(g.dataset.cloud)] ?? { x: 0, y: 0 }
      return { g, x: start.x, y: start.y, v: 6 + Math.random() * 6 }
    }),
    mood: null, moodShown: null, moodTarget: null, season: null,
    // The scene's own clock (ms): it runs only while things move, so pausing
    // stops coins, walkers and signs where they are.
    now: 0,
    paused: null,
    debt: { spend: Math.random(), pay: Math.random(), tax: Math.random(), help: Math.random() },
    pools: null,
    cars: [], walkers: [], movers: [],
    coins: [], spare: [], pings: [], signs: [], puffs: [],
    flashStep: 0,
    raf: 0, last: 0, wake: null,
  }
}

// Moves a car or walker to tile position (gx, gy), inside the slot of the tile
// under it, so buildings nearer the viewer hide it.
function place(s, thing, gx, gy) {
  const key = `${clamp(Math.floor(gx), 0, GRID - 1)},${clamp(Math.floor(gy), 0, GRID - 1)}`
  if (thing.slot !== key) {
    s.slots.get(key)?.appendChild(thing.node)
    thing.slot = key
  }
  const [x, y] = iso(gx, gy)
  thing.node.setAttribute('transform', `translate(${x} ${y})${thing.scale}`)
}

const along = thing => (thing.axis === 'x' ? [thing.pos, thing.lane] : [thing.lane, thing.pos])

function newCar(s) {
  const axis = Math.random() < 0.5 ? 'x' : 'y'
  const dir = Math.random() < 0.5 ? -1 : 1
  const car = { node: carNode(s.doc, axis, pick(CAR_COLOURS)), axis, dir, lane: ROAD + (dir > 0 ? 0.68 : 0.32), pos: 0.5 + Math.random() * 15, v: 1.1 + Math.random() * 0.7, slot: null, scale: '' }
  place(s, car, ...along(car))
  return car
}

function newWalker(s) {
  const { g, legs } = figureNode(s.doc, pick(SHIRTS))
  const walker = { node: g, legs, axis: Math.random() < 0.5 ? 'x' : 'y', lane: ROAD + (Math.random() < 0.5 ? 0.07 : 0.93), pos: 0.5 + Math.random() * 15, dir: Math.random() < 0.5 ? -1 : 1, v: 0.35 + Math.random() * 0.25, ph: Math.random() * 6, slot: null, scale: ' scale(.9)' }
  place(s, walker, ...along(walker))
  return walker
}

const swing = (legs, phase) => {
  const k = r1(Math.sin(phase) * 1.2)
  legs.setAttribute('d', `M0 -2.6 l${-k} 2.6 M0 -2.6 l${k} 2.6`)
}

// Cars follow this week's sales, people on the pavements how many have work.
function syncTraffic(s, traffic) {
  while (s.cars.length < traffic.cars) s.cars.push(newCar(s))
  while (s.cars.length > traffic.cars) s.cars.pop().node.remove()
  while (s.walkers.length < traffic.walkers) s.walkers.push(newWalker(s))
  while (s.walkers.length > traffic.walkers) s.walkers.pop().node.remove()
}

// Who coins and walkers can come from or go to this week.
function poolsOf(model) {
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

const paintMood = s => {
  s.moodShown = s.mood
  paintWeather(s.weather, s.mood, s.season)
}

// ---------- coins ----------

// Spending goes from homes to shops (busier shops more often), pay from shops
// to working homes, taxes from working homes or shops to the town hall, and
// help from the town hall to homes looking for work.
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
  if (s.coins.length >= MAX.coins) return
  const [a, b] = coinRoute(s, flow)
  if (!a || !b) return
  const colour = FLOW_COLOURS[flow]
  let coin = s.spare.pop()
  if (!coin) coin = { c: el(s.doc, 'circle', { r: 3, stroke: 'rgba(255,255,255,.8)', 'stroke-width': 0.7 }, s.layers.coins) }
  coin.c.style.display = ''
  coin.c.setAttribute('fill', colour)
  Object.assign(coin, { path: arcPath(a, b, 24 + Math.hypot(b[0] - a[0], b[1] - a[1]) * 0.12), to: b, colour, t0: s.now, dur: 950 + Math.random() * 550 })
  s.coins.push(coin)
}

function ping(s, at, colour) {
  if (s.pings.length >= MAX.pings) return
  const node = el(s.doc, 'circle', { cx: r1(at[0]), cy: r1(at[1]), r: 3.2, class: 'lt-ping', stroke: colour }, s.layers.pings)
  s.pings.push({ node, until: s.now + LIFE.ping })
}

function stepCoins(s) {
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
}

// ---------- this week's moments ----------

// A floating sign over a place (`key`: a shop's id, or the bank). A newer sign
// over the same place replaces the older one rather than piling on top of it.
function sign(s, key, at, label, tone) {
  const older = s.signs.findIndex(item => item.key === key)
  if (older >= 0) s.signs.splice(older, 1)[0].node.remove()
  const g = el(s.doc, 'g', { class: 'lt-moment' }, s.layers.moments)
  g.appendChild(pillNode(s.doc, at[0], at[1] - 6, label, tone, 7))
  s.signs.push({ key, node: g, until: s.now + LIFE.sign })
  while (s.signs.length > MAX.signs) s.signs.shift().node.remove()
}

function puff(s, at) {
  for (const [dx, dy] of [[-5, 4], [5, 3], [0, 6]]) {
    const node = el(s.doc, 'circle', { cx: r1(at[0] + dx), cy: r1(at[1] + dy + 10), r: 4, class: 'lt-puff' }, s.layers.moments)
    s.puffs.push({ node, until: s.now + LIFE.puff })
  }
  while (s.puffs.length > MAX.puffs) s.puffs.shift().node.remove()
}

// A person laid off walks from the shop to a dark home carrying a box; a new
// hire walks from a lit home to the shop. The second from one shop sets off a
// moment later, beside the first.
function walkTo(s, shop, kind, j) {
  if (s.movers.length >= MAX.movers) return
  const { look, live, work } = s.pools
  const homes = kind === 'lay' ? (look.length ? look : live) : work
  if (!homes.length) return
  const lot = LAYOUT.lots[shop.lot]
  const house = LAYOUT.houses[pick(homes)]
  const door = [lot.gx + 0.5 + (j - 0.5) * 0.2, lot.gy + 0.5]
  const home = [house.gx + 0.5, house.gy + 0.9]
  const { g, legs } = figureNode(s.doc, WALKER_SHIRTS[kind], kind === 'lay')
  g.classList.add('is-moving')
  const mover = { node: g, legs, from: kind === 'lay' ? door : home, to: kind === 'lay' ? home : door, t0: s.now + j * 260, dur: 2600 + Math.random() * 600, slot: null, scale: ' scale(.9)' }
  g.style.opacity = j > 0 ? '0' : '1'
  place(s, mover, ...mover.from)
  s.movers.push(mover)
}

function stepMovers(s) {
  for (let k = s.movers.length - 1; k >= 0; k -= 1) {
    const mover = s.movers[k]
    const t = (s.now - mover.t0) / mover.dur
    if (t >= 1) {
      mover.node.remove()
      s.movers.splice(k, 1)
      continue
    }
    const e = clamp(t, 0, 1)
    place(s, mover, mover.from[0] + (mover.to[0] - mover.from[0]) * e, mover.from[1] + (mover.to[1] - mover.from[1]) * e)
    mover.node.style.opacity = t < 0 ? '0' : t > 0.9 ? r1((1 - t) * 10).toString() : '1'
    swing(mover.legs, s.now / 90)
  }
}

// Closures (with a puff of dust), openings, big layoffs and hirings, and bad
// loans (the bank flashes), at most four signs; then the walkers.
function popWeek(s, model) {
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
      s.flashStep = 2
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

const expire = (s, list) => {
  for (let k = list.length - 1; k >= 0; k -= 1) {
    if (list[k].until <= s.now) {
      list[k].node.remove()
      list.splice(k, 1)
    }
  }
}

// Takes away everything a week set moving: coins, rings, signs, puffs,
// walkers and the bank's flash. Cars, people on the roads and clouds stay.
function clearMoving(s) {
  for (const coin of s.coins) {
    coin.c.style.display = 'none'
    s.spare.push(coin)
  }
  s.coins = []
  for (const list of [s.pings, s.signs, s.puffs, s.movers]) {
    for (const thing of list) thing.node.remove()
    list.length = 0
  }
  s.flashStep = 0
  s.flash?.classList.remove('is-on')
}

// While nothing moves, the loop only runs to settle the weather or flash the bank.
const busy = (s, moving) => moving || s.mood !== s.moodTarget || s.flashStep > 0

// Paused, the signs', puffs' and rings' CSS animations stop where they are too.
function holdAnimations(s, paused) {
  if (s.paused === paused) return
  s.paused = paused
  for (const layer of [s.layers.pings, s.layers.moments]) layer?.toggleAttribute('data-paused', paused)
}

// ---------- the hook ----------

export default function useSceneMotion(svgRef, { model, playing = false, speed = 1, towns = 1, scrubs = 0, hidden = false, mode = 'island' }) {
  // The loop reads the latest props from here, written after each render.
  const live = useRef(null)
  useLayoutEffect(() => {
    live.current = { model, playing, speed, towns }
  })
  const scene = useRef(null)
  const lastTick = useRef(null)
  const lastScrubs = useRef(null)

  // Once per scene: find the layers, slots and weather parts, and set up the
  // loop. Taking it down removes everything the loop added (StrictMode and
  // a hidden Activity take effects down and set them up again).
  useLayoutEffect(() => {
    const svg = svgRef.current
    if (!svg) return undefined
    const s = sceneOf(svg, mode)
    scene.current = s

    const frame = now => {
      s.raf = 0
      const dt = clamp((now - s.last) / 1000, 0, 0.1)
      s.last = now
      const { model: m, playing: on, speed: pace, towns: count } = live.current
      const moving = on && !s.reduce
      // The mood eases in, so the weather drifts rather than snaps.
      if (s.mood !== s.moodTarget) {
        s.mood = easeToward(s.mood, s.moodTarget, dt)
        if (s.mood === s.moodTarget || Math.abs(s.mood - s.moodShown) > 0.004) paintMood(s)
      }
      if (s.flashStep === 2) {
        s.flash?.classList.remove('is-on')
        s.flashStep = 1
      } else if (s.flashStep === 1) {
        s.flash?.classList.add('is-on')
        s.flashStep = 0
      }
      if (moving) {
        for (const cloud of s.clouds) {
          cloud.x += cloud.v * dt
          if (cloud.x > 330) cloud.x = -340
          cloud.g.setAttribute('transform', `translate(${r1(cloud.x)} ${cloud.y})`)
        }
        for (const car of s.cars) {
          car.pos += car.dir * car.v * dt
          if (car.pos > GRID - 0.25 || car.pos < 0.25) {
            car.dir *= -1
            car.lane = ROAD + (car.dir > 0 ? 0.68 : 0.32)
          }
          place(s, car, ...along(car))
        }
        for (const walker of s.walkers) {
          walker.pos += walker.dir * walker.v * dt
          if (walker.pos > GRID - 0.3 || walker.pos < 0.3) walker.dir *= -1
          walker.ph += dt * 8
          place(s, walker, ...along(walker))
          swing(walker.legs, walker.ph)
        }
        s.now += dt * 1000
        // No coins in the warm-up weeks, before the town has an economy.
        if (!m.warmUp && s.pools) {
          const due = coinsDue(s.debt, m.flows, dt * COIN_WEEKS_PER_SECOND * pace, pace, count)
          s.debt = due.debt
          for (const flow of FLOWS) for (let n = 0; n < due.launches[flow]; n += 1) launchCoin(s, flow)
        }
        stepMovers(s)
        stepCoins(s)
        expire(s, s.pings)
        expire(s, s.signs)
        expire(s, s.puffs)
      }
      if (!s.hidden && busy(s, moving)) s.raf = requestAnimationFrame(frame)
    }
    s.wake = () => {
      if (s.raf || s.hidden) return
      s.last = performance.now()
      s.raf = requestAnimationFrame(frame)
    }
    // Turning reduced motion on stops what is moving and settles the weather.
    const onPreference = event => {
      s.reduce = event.matches
      holdAnimations(s, !(live.current?.playing && !s.reduce))
      if (!s.reduce) {
        s.wake()
        return
      }
      clearMoving(s)
      if (s.moodTarget != null) {
        s.mood = s.moodTarget
        paintMood(s)
      }
    }
    s.media?.addEventListener?.('change', onPreference)

    return () => {
      cancelAnimationFrame(s.raf)
      s.raf = 0
      s.media?.removeEventListener?.('change', onPreference)
      clearMoving(s)
      for (const coin of s.spare) coin.c.remove()
      for (const thing of [...s.cars, ...s.walkers]) thing.node.remove()
      scene.current = null
      lastTick.current = null
      lastScrubs.current = null
    }
  }, [svgRef, mode])

  // Each new week: traffic follows the model and the mood gets a new target.
  // Playing, the weather eases to it; otherwise it changes at once. A single
  // forward step while playing adds this week's moments and walkers; any
  // other change of week clears what was moving. A week that arrives with a
  // new scrub count came from the timeline (spec 4.2.12: never when scrubbing
  // or jumping), even one week on while playing.
  useLayoutEffect(() => {
    const s = scene.current
    if (!s) return
    if (hidden) {
      s.hidden = true
      cancelAnimationFrame(s.raf)
      s.raf = 0
      clearMoving(s)
      return
    }
    const shownAgain = s.hidden
    s.hidden = false
    const prev = lastTick.current
    lastTick.current = model.tick
    const scrubbed = lastScrubs.current != null && lastScrubs.current !== scrubs
    lastScrubs.current = scrubs
    const stepped = !shownAgain && !scrubbed && isStep(prev, model.tick, playing)
    holdAnimations(s, !(playing && !s.reduce))
    s.pools = poolsOf(model)
    syncTraffic(s, model.traffic)
    const newSeason = s.season !== model.season
    s.season = model.season
    s.moodTarget = model.mood
    if (s.mood == null || !playing || s.reduce || shownAgain) {
      s.mood = model.mood
      paintMood(s)
    } else if (newSeason) {
      paintMood(s)
    }
    if (stepped && !s.reduce) popWeek(s, model)
    else if (prev !== model.tick) clearMoving(s)
    s.wake()
  }, [model, playing, hidden, scrubs])
}
