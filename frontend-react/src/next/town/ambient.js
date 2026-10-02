// What keeps moving in a town while the run plays (spec 4.1 and 4.2), ported
// from mockup 08's CSS loops: clouds drift, rain or snow falls, working
// chimneys smoke, struggling shops' flags wave and their lights flicker, new
// shops' balloons bob and growing shops' crane hooks swing.
//
// The motion loop writes these as plain attributes on the scene's own clock
// (s.now), never as CSS animations: the browser gives every SVG shape with a
// running animation a compositor layer of its own, and every shape painted
// after it that overlaps it one more (measured: 566 layers for two towns),
// which cost more per frame than drawing the shapes. Paused, they stop where
// they are; with reduced motion they stand in the pose React drew.
//
// Chimney smoke, flags, balloons, hooks and lights stay in the world layer,
// in their place in painter's order, so buildings in front still hide them.
import { CLOUDS } from './geometry.js'
import { LOOP_MS, bobPose, fallOffset, flagPose, flickerOpacity, smokePhase, smokePose } from './motion.js'

const r1 = value => Math.round(value * 10) / 10
const phase = (now, ms, offset = 0) => (now / ms + offset) % 1
// Flags, balloons and hooks move in three phases, so they do not all keep step.
const THIRDS = [0, 1 / 3, 2 / 3]

// The parts found once per scene: the clouds (each drifting from where React
// drew it), the rain's groups of drops, and each smoky home's three puffs
// (React keeps them, working or not).
export function ambientOf(root) {
  const chimneys = new Map()
  for (const group of root.querySelectorAll('.lt-smoke')) {
    const house = group.closest('[data-kind="house"]')
    if (house) chimneys.set(Number(house.dataset.index), [...group.children])
  }
  return {
    clouds: [...root.querySelectorAll('[data-cloud]')].map(g => {
      const start = CLOUDS[Number(g.dataset.cloud)] ?? { x: 0, y: 0 }
      return { g, x: start.x, y: start.y, v: 6 + Math.random() * 6 }
    }),
    rain: root.querySelector('[data-layer="rain"]'),
    drops: [...root.querySelectorAll('[data-drops]')],
    chimneys,
    smoke: [[], [], []],
    flags: [],
    balloons: [],
    hooks: [],
    lights: [],
    flicker: null,
  }
}

// After each week: the chimneys that smoke (working homes), and the flags,
// balloons, hooks and struggling shops' lights the week drew.
export function collectAmbient(a, world, houses) {
  a.smoke = [[], [], []]
  houses.forEach((house, index) => {
    if (house.state !== 'work') return
    a.chimneys.get(index)?.forEach((circle, i) => a.smoke[i % 3].push(circle))
  })
  a.flags = []
  a.balloons = []
  a.hooks = []
  const lights = []
  for (const node of world.querySelectorAll('.lt-flag-wave, .lt-balloons, .lt-crane-hook, .lt-shop.is-struggling .lt-wins')) {
    const list = node.classList
    if (list.contains('lt-flag-wave')) a.flags.push(node)
    else if (list.contains('lt-balloons')) a.balloons.push(node)
    else if (list.contains('lt-crane-hook')) a.hooks.push(node)
    else lights.push(node)
  }
  // A shop that is no longer struggling keeps its lights on.
  for (const group of a.lights) if (!lights.includes(group) && group.isConnected) group.removeAttribute('opacity')
  a.lights = lights
  a.flicker = null
}

// When the scene is taken down: struggling shops' lights back on (the
// drawing may change before a new loop finds them again).
export function restAmbient(a) {
  for (const group of a.lights) if (group.isConnected) group.removeAttribute('opacity')
  a.lights = []
}

// Moves everything on to the scene clock's time (dt seconds since the last frame).
export function stepAmbient(a, now, dt) {
  for (const cloud of a.clouds) {
    cloud.x += cloud.v * dt
    if (cloud.x > 330) cloud.x = -340
    cloud.g.setAttribute('transform', `translate(${r1(cloud.x)} ${cloud.y})`)
  }
  if (a.rain && !a.rain.classList.contains('is-dry')) {
    const snow = a.rain.classList.contains('is-snow')
    a.drops.forEach((group, k) => {
      const [x, y] = fallOffset(phase(now, snow ? LOOP_MS.snow : LOOP_MS.rain, k / a.drops.length), snow)
      group.setAttribute('transform', `translate(${x} ${y})`)
    })
  }
  a.smoke.forEach((circles, i) => {
    if (!circles.length) return
    const { transform, opacity } = smokePose(smokePhase(now, i))
    for (const circle of circles) {
      circle.setAttribute('transform', transform)
      circle.setAttribute('opacity', opacity)
    }
  })
  if (a.flags.length) {
    const poses = THIRDS.map(k => flagPose(phase(now, LOOP_MS.flag, k)))
    a.flags.forEach((flag, i) => flag.setAttribute('transform', poses[i % 3]))
  }
  if (a.balloons.length) {
    const poses = THIRDS.map(k => bobPose(phase(now, LOOP_MS.balloons, k), -2.5))
    a.balloons.forEach((group, i) => group.setAttribute('transform', poses[i % 3]))
  }
  if (a.hooks.length) {
    const poses = THIRDS.map(k => bobPose(phase(now, LOOP_MS.hook, k), 3))
    a.hooks.forEach((group, i) => group.setAttribute('transform', poses[i % 3]))
  }
  const flicker = flickerOpacity(phase(now, LOOP_MS.flicker))
  if (flicker !== a.flicker) {
    a.flicker = flicker
    for (const group of a.lights) group.setAttribute('opacity', flicker)
  }
}
