// Pure helpers for the scene's animation loop (useSceneMotion.js), ported from
// mockup 08 (Scene.flow, onWeek, frame, arc).
export const COIN_DOLLARS = 1800
const FLOWS = ['spend', 'pay', 'tax', 'help']

// The pace coins count weeks at: the mockup played one week a second, with
// one coin per COIN_DOLLARS. The replay clock runs 8 weeks a second, so counting
// its own weeks would launch 8 times as many coins (about 200 a second in each town,
// always at the cap); counting weeks at the mockup's pace keeps the picture as
// calm as the approved mockup.
export const COIN_WEEKS_PER_SECOND = 1

// How many coins of each kind to launch for `dWeeks` weeks of money moving, and
// the fraction of a coin each flow carries over to the next call.
export function coinsDue(debt, flows, dWeeks, towns) {
  const next = { ...debt }
  const launches = {}
  const calm = COIN_DOLLARS * Math.max(1, towns / 2)
  for (const flow of FLOWS) {
    next[flow] = (next[flow] ?? 0) + ((flows?.[flow] ?? 0) / calm) * dWeeks
    let n = 0
    while (next[flow] >= 1 && n < 8) { next[flow] -= 1; n += 1 }
    if (n === 8) next[flow] = Math.min(next[flow], 1)
    launches[flow] = n
  }
  return { debt: next, launches }
}

// A week change is a step only when the clock moved forward by one while playing.
export const isStep = (prevTick, tick, playing) => Boolean(playing) && prevTick != null && tick === prevTick + 1

// This week's floating signs, most telling first.
export function weekMoments(model, limit = 4) {
  const week = model?.week
  if (!week) return []
  const list = [
    ...week.closed.map(firmId => ({ kind: 'closed', firmId })),
    ...week.opened.map(firmId => ({ kind: 'opened', firmId })),
    ...[...week.layoffs].filter(([, n]) => n >= 2).sort((a, b) => b[1] - a[1]).map(([firmId, n]) => ({ kind: 'lost', firmId, n })),
    ...[...week.hires].filter(([, n]) => n >= 2).sort((a, b) => b[1] - a[1]).map(([firmId, n]) => ({ kind: 'gained', firmId, n })),
    ...(week.bad >= 500 ? [{ kind: 'bad', amount: week.bad }] : []),
  ]
  return list.slice(0, limit)
}

// This week's walkers: people laid off carry a box home, new hires walk to work.
export function weekWalkers(model, limit = 6) {
  const week = model?.week
  if (!week) return []
  const out = []
  const add = (pairs, kind) => {
    for (const [firmId, n] of [...pairs].sort((a, b) => b[1] - a[1])) {
      for (let k = 0; k < Math.min(n, 2) && out.length < limit; k += 1) out.push({ firmId, kind })
    }
  }
  add(week.layoffs, 'lay')
  add(week.hires, 'hire')
  return out
}

// Part of the way from `current` to `target` for `dt` seconds: at the default
// rate the time constant is 1 / 1.6 = 0.625 s (63% of the way after 0.625 s,
// 95% after about 1.9 s). It lands on the target once within 0.004, which
// takes ln(gap / 0.004) / rate seconds: about 2.7 s for a gap of 0.3.
export function easeToward(current, target, dt, rate = 1.6) {
  const next = current + (target - current) * Math.min(1, dt * rate)
  return Math.abs(target - next) < 0.004 ? target : next
}

// A coin's path: a straight line from a to b lifted into an arch h high.
export const arcPath = (a, b, h) => t => [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t - h * 4 * t * (1 - t)]

// Slow in, slow out, for a coin's flight (t from 0 to 1).
export const easeInOut = t => (t < 0.5 ? 2 * t * t : 1 - ((-2 * t + 2) ** 2) / 2)

// One item from a list, more likely the heavier it is (`weights` sums to `total`).
export function pickWeighted(list, weights, total, random = Math.random) {
  let r = random() * total
  for (let i = 0; i < list.length; i += 1) {
    r -= weights[i]
    if (r <= 0) return list[i]
  }
  return list[list.length - 1]
}

// ---------- poses for what loops or plays once ----------
// The scene's moving details as pure functions of time, so the motion loop
// can write them as plain attributes (no CSS animations: on an SVG part the
// browser gives every animated shape a compositor layer of its own, and the
// shapes drawn after it more layers, measured at 566 layers for two towns).
// Each takes a phase or progress from 0 to 1 and matches the mockup's CSS
// keyframes closely enough to look the same.

// CSS ease-out (cubic-bezier(0, 0, .58, 1)), closely enough.
export const easeOut = t => 1 - (1 - t) ** 2
// Smoothly there and back again over one cycle.
const swell = p => (1 - Math.cos(2 * Math.PI * p)) / 2
const f2 = value => Number(value.toFixed(2))

// How long each loop takes (ms).
export const LOOP_MS = { smoke: 2800, flag: 1800, balloons: 2200, hook: 3000, flicker: 2600, rain: 700, snow: 3200 }

// A chimney's three puffs are a third of a cycle apart; at the scene clock's
// zero they stand where the drawing puts them (SMOKE_REST).
export const smokePhase = (now, i) => (now / LOOP_MS.smoke + 0.25 + i / 3) % 1
export const SMOKE_REST = [0, 1, 2].map(i => smokePhase(0, i))

// A chimney puff drawn at (0, 0): it rises up and to the right, grows and fades.
export function smokePose(p) {
  const e = easeOut(p)
  const opacity = p < 0.15 ? 0.85 * easeOut(p / 0.15) : 0.85 * (1 - easeOut((p - 0.15) / 0.85))
  return { transform: `translate(${f2(5 * e)} ${f2(-14 * e)}) scale(${f2(0.5 + 1.2 * e)})`, opacity: f2(opacity) }
}

// A flag waving from its pole (its left edge at (0, 0)).
export const flagPose = p => `skewY(${f2(-6 * swell(p))}) scale(${f2(1 - 0.08 * swell(p))} 1)`

// Balloons bob up, a crane's hook swings down, and back.
export const bobPose = (p, lift) => `translate(0 ${f2(lift * swell(p))})`

// A struggling shop's lights: on, then dim for a moment, twice a cycle.
export function flickerOpacity(p) {
  if (p >= 0.38 && p < 0.44) return 0.25
  if (p >= 0.71 && p < 0.76) return 0.4
  return 1
}

// Where a falling drop (or snowflake) is in its fall.
export function fallOffset(p, snow) {
  return snow ? [f2(6 * p), f2(-24 + 54 * p)] : [f2(-7 * p), f2(-20 + 46 * p)]
}

// A floating sign rises into view, holds, then rises on and fades (2.8 s).
export function risePose(t) {
  if (t < 0.12) {
    const e = easeOut(t / 0.12)
    return { dy: f2(6 * (1 - e)), opacity: f2(e) }
  }
  const e = easeOut((t - 0.12) / 0.88)
  return { dy: f2(-16 * e), opacity: t < 0.75 ? 1 : f2(1 - easeOut((t - 0.75) / 0.25)) }
}

// A ring where a coin lands (0.7 s), and a puff of dust where a shop closed (1.1 s).
export const pingPose = t => ({ scale: f2(0.4 + 1.8 * easeOut(t)), opacity: f2(0.9 * (1 - easeOut(t))) })
export const puffPose = t => ({ scale: f2(0.4 + 2 * easeOut(t)), opacity: f2(0.8 * (1 - easeOut(t))) })

// The town hall's ring pulses twice (two 0.5 s beats) when the rules change.
export function ringPose(t) {
  const beat = swell((t * 2) % 1)
  return { scale: f2(1 + 0.06 * beat), opacity: f2(1 - 0.7 * beat) }
}

// The bank's red flash when loans go bad (1.2 s).
export const flashOpacity = t => f2(t < 0.15 ? 0.55 * easeOut(t / 0.15) : 0.55 * (1 - easeOut((t - 0.15) / 0.85)))
