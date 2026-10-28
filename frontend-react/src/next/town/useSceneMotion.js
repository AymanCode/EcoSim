// What moves in a town drawing between weeks (spec sections 4 and 7), ported
// from mockup 08: the weather easing to a new mood, clouds drifting, rain or
// snow, chimney smoke, waving flags and the rest (ambient.js), cars and
// people on the roads, coins carrying money (coins.js), shops easing to a new
// height (heights.js), and, when the clock steps forward one week while
// playing, that week's floating signs, dust puffs, the bank's red flash and
// the people hired or laid off walking between shop and home (moments.js).
//
// One requestAnimationFrame loop per scene. It never sets React state and
// runs no CSS animations: it writes attributes and CSS variables, and adds
// its own nodes to the layers and slots the Diorama leaves empty for it.
// Where things are in the picture comes from the scene's `places` object
// (islandPlaces.js for the island), so another kind of scene plugs in its own.
//
// The scene keeps its own clock (s.now), which runs only while things move:
// while the run plays, and when a run ends, until what is in flight lands
// (spec 4.2.12; the last week reached by the clock still counts as a step).
// Paused by the viewer, everything stops where it is and the loop sleeps
// once the weather has settled, so a paused town costs no frames. A change of
// week that is not a single step forward while playing (a scrub, even one week
// on, or a jump) clears what was moving and changes the weather and heights
// at once. With prefers-reduced-motion nothing travels or loops and there
// are no floating signs. A card hidden by Enlarge does nothing at all.
//
// While the mood eases, the sky, sun, clouds and rain are repainted every
// frame, but the world layer's colours (grass, shade, glows) only every
// WORLD_PAINT_MS, so the world layer is not redrawn for them every frame.
import { useLayoutEffect, useRef } from 'react'
import { ambientOf, collectAmbient, restAmbient, stepAmbient } from './ambient.js'
import { clearCoins, launchCoins, poolsOf, stepCoins } from './coins.js'
import { settleHeights, stepHeights, syncHeights } from './heights.js'
import { clearMoments, momentsUnderWay, popWeek, stepMoments, watchRing } from './moments.js'
import { easeToward, isStep } from './motion.js'
import { paintWeather, weatherOf } from './weather.js'

const WORLD_PAINT_MS = 250
const clamp = (value, lo, hi) => Math.min(hi, Math.max(lo, value))

function sceneOf(root, places) {
  if (!places) throw new Error('useSceneMotion: a scene needs its places (see islandPlaces.js)')
  const media = window.matchMedia?.('(prefers-reduced-motion: reduce)') ?? null
  const layer = name => root.querySelector(`[data-layer="${name}"]`)
  return {
    doc: root.ownerDocument,
    places,
    where: places.attach(root),
    media,
    reduce: Boolean(media?.matches),
    hidden: false,
    world: layer('world') ?? root,
    layers: { coins: layer('coins'), pings: layer('pings'), moments: layer('moments') },
    weather: weatherOf(root),
    ambient: ambientOf(root, places),
    flash: { node: root.querySelector('[data-flash]'), t0: null },
    ring: { node: null, t0: null },
    mood: null, moodShown: null, moodTarget: null, season: null, worldAt: 0,
    now: 0,
    settling: false,
    debt: { spend: Math.random(), pay: Math.random(), tax: Math.random(), help: Math.random() },
    pools: null,
    cars: [], walkers: [], movers: [],
    coins: [], spare: [], pings: [], signs: [], puffs: [],
    heights: new Map(), easing: new Set(),
    raf: 0, last: 0, wake: null,
  }
}

const paintMood = (s, world) => {
  s.moodShown = s.mood
  paintWeather(s.weather, s.mood, s.season, { world })
}

// Cars and people on the roads follow this week's figures.
function syncTraffic(s, model) {
  const { places } = s
  const { cars, walkers } = places.traffic(model)
  while (s.cars.length < cars) s.cars.push(places.newCar(s))
  while (s.cars.length > cars) s.cars.pop().node.remove()
  while (s.walkers.length < walkers) s.walkers.push(places.newWalker(s))
  while (s.walkers.length > walkers) s.walkers.pop().node.remove()
}

// Whether anything a week set going is still under way.
const underWay = s => s.coins.length + s.pings.length + momentsUnderWay(s) + s.easing.size > 0

// Takes away everything a week set moving: coins, rings, signs, puffs,
// walkers, the bank's flash, and puts easing shops at their height. Cars,
// people on the roads, clouds and the loops stay.
function clearMoving(s) {
  clearCoins(s)
  clearMoments(s)
  settleHeights(s)
}

// `places` describes where things are in this kind of scene (islandPlaces.js);
// pass a module-level object, as the loop is set up again when it changes.
export default function useSceneMotion(rootRef, { model, places, playing = false, towns = 1, scrubs = 0, hidden = false, ended = false }) {
  // The loop reads the latest props from here, written after each render.
  const live = useRef(null)
  useLayoutEffect(() => {
    live.current = { model, playing, towns }
  })
  const scene = useRef(null)
  const last = useRef({ tick: null, scrubs: null, playing: false })

  // Once per scene: find the layers, slots and weather parts, and set up the
  // loop. Taking it down removes everything the loop added (StrictMode and
  // a hidden Activity take effects down and set them up again).
  useLayoutEffect(() => {
    const root = rootRef.current
    if (!root) return undefined
    const s = sceneOf(root, places)
    scene.current = s

    const frame = now => {
      s.raf = 0
      const dt = clamp((now - s.last) / 1000, 0, 0.1)
      s.last = now
      const { model: m, playing: on, towns: count } = live.current
      const moving = (on || s.settling) && !s.reduce
      // The mood eases in, so the weather drifts rather than snaps.
      if (s.mood !== s.moodTarget) {
        s.mood = easeToward(s.mood, s.moodTarget, dt)
        const settled = s.mood === s.moodTarget
        if (settled || Math.abs(s.mood - s.moodShown) > 0.004) {
          const world = settled || now - s.worldAt >= WORLD_PAINT_MS
          if (world) s.worldAt = now
          paintMood(s, world)
        }
      }
      if (moving) {
        s.now += dt * 1000
        stepAmbient(s.ambient, s.now, dt)
        for (const car of s.cars) places.moveCar(s, car, dt)
        for (const walker of s.walkers) places.moveWalker(s, walker, dt)
        if (on) launchCoins(s, m, dt, count)
        stepCoins(s)
        stepMoments(s)
        stepHeights(s)
        // A run that has ended stops once what was in flight has landed.
        if (s.settling && !underWay(s)) s.settling = false
      }
      if (!s.hidden && (moving || s.mood !== s.moodTarget)) s.raf = requestAnimationFrame(frame)
    }
    s.wake = () => {
      if (s.raf || s.hidden) return
      s.last = performance.now()
      s.raf = requestAnimationFrame(frame)
    }
    // Turning reduced motion on stops what is moving, puts the loops back in
    // their drawn pose and settles the weather.
    const onPreference = event => {
      s.reduce = event.matches
      if (!s.reduce) {
        s.wake()
        return
      }
      clearMoving(s)
      restAmbient(s.ambient)
      if (s.moodTarget != null) {
        s.mood = s.moodTarget
        paintMood(s, true)
      }
    }
    s.media?.addEventListener?.('change', onPreference)

    return () => {
      cancelAnimationFrame(s.raf)
      s.raf = 0
      s.media?.removeEventListener?.('change', onPreference)
      clearMoving(s)
      restAmbient(s.ambient)
      for (const coin of s.spare) coin.c.remove()
      for (const thing of [...s.cars, ...s.walkers]) thing.node.remove()
      scene.current = null
      last.current = { tick: null, scrubs: null, playing: false }
    }
  }, [rootRef, places])

  // Each new week: traffic follows the model and the mood gets a new target.
  // Playing, the weather eases to it; otherwise it changes at once. A single
  // forward step while playing adds this week's moments and walkers and eases
  // shops to their new heights; any other change of week clears what was
  // moving. A week that arrives with a new scrub count came from the timeline
  // (spec 4.2.12: never when scrubbing or jumping), even one week on while
  // playing. The week the clock stops on at the end of a run is still a step,
  // and what is in flight then finishes (`ended`); a viewer's pause freezes it.
  useLayoutEffect(() => {
    const s = scene.current
    if (!s) return
    if (hidden) {
      // The card hides on the week of this render: shops stand at its heights.
      s.hidden = true
      cancelAnimationFrame(s.raf)
      s.raf = 0
      syncHeights(s, model.shops, false)
      clearMoving(s)
      return
    }
    const shownAgain = s.hidden
    s.hidden = false
    const prev = last.current
    last.current = { tick: model.tick, scrubs, playing }
    const scrubbed = prev.scrubs != null && prev.scrubs !== scrubs
    const forward = playing || (ended && prev.playing)
    const stepped = !shownAgain && !scrubbed && !s.reduce && isStep(prev.tick, model.tick, forward)
    s.settling = ended && !playing && !s.reduce
    const moving = (playing || s.settling) && !s.reduce
    s.pools = poolsOf(model)
    syncTraffic(s, model)
    const newSeason = s.season !== model.season
    s.season = model.season
    s.moodTarget = model.mood
    if (s.mood == null || !moving || shownAgain) {
      s.mood = model.mood
      paintMood(s, true)
    } else if (newSeason) {
      paintMood(s, true)
    }
    // Heights first: a jump then settles any shop still easing where React
    // has just drawn it, not at the height it was easing to.
    syncHeights(s, model.shops, stepped)
    if (stepped) popWeek(s, model)
    else if (prev.tick !== model.tick) clearMoving(s)
    collectAmbient(s.ambient, s.world, model.houses)
    watchRing(s, s.world, moving)
    s.wake()
  }, [model, playing, hidden, scrubs, ended])
}
