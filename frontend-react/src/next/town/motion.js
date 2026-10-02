// Pure helpers for the scene's animation loop (useSceneMotion.js), ported from
// mockup 08 (Scene.flow, onWeek, frame, arc).
export const COIN_DOLLARS = 1800
const FLOWS = ['spend', 'pay', 'tax', 'help']

// The pace coins count weeks at: the mockup played one week a second, and the
// coin rate (one coin per COIN_DOLLARS, divided by the speed) was set there.
// The replay clock runs 8 weeks a second at 1×, so counting the clock's own
// weeks would launch 8 times as many coins (about 200 a second in each town,
// always at the cap); counting weeks at the mockup's pace keeps the picture as
// calm as the approved mockup. The speed cancels out either way.
export const COIN_WEEKS_PER_SECOND = 1

// How many coins of each kind to launch for `dWeeks` weeks of money moving, and
// the fraction of a coin each flow carries over to the next call.
export function coinsDue(debt, flows, dWeeks, speed, towns) {
  const next = { ...debt }
  const launches = {}
  const calm = COIN_DOLLARS * Math.max(speed, 0.25) * Math.max(1, towns / 2)
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
