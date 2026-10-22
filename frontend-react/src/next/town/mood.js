// How a town is doing, as one number from 0 (hard times) to 1 (thriving), and
// the scene colours that follow from it (spec section 5).
import { mulberry32 } from './geometry.js'

export const MOOD_KEYS = ['thriving', 'okay', 'struggling', 'hard']
const clamp = (value, lo, hi) => Math.min(hi, Math.max(lo, value))
const known = value => typeof value === 'number' && Number.isFinite(value)

export function moodOf({ out, happiness, warmUp }) {
  if (warmUp) return 0.62
  const jobs = known(out) ? clamp(1 - (out - 5) / 40, 0, 1) : 0.6
  const happy = known(happiness) ? clamp((happiness - 10) / 55, 0, 1) : 0.6
  return 0.55 * jobs + 0.45 * happy
}

export function moodBand(value) {
  if (value >= 0.72) return 'thriving'
  if (value >= 0.5) return 'okay'
  if (value >= 0.3) return 'struggling'
  return 'hard'
}

export function seasonOf(tick) {
  const week = ((Math.max(1, Math.round(tick)) - 1) % 52) + 1
  if (week <= 9 || week >= 49) return 'winter'
  if (week <= 22) return 'spring'
  if (week <= 35) return 'summer'
  return 'autumn'
}

function hex(colour) {
  const n = parseInt(colour.slice(1), 16)
  return [n >> 16, (n >> 8) & 255, n & 255]
}
export function mix(a, b, t) {
  const A = hex(a)
  const B = hex(b)
  return `#${A.map((v, i) => Math.round(v + (B[i] - v) * t).toString(16).padStart(2, '0')).join('')}`
}
// Blend across [value, colour] stops sorted by value.
function ramp(stops, v) {
  if (v <= stops[0][0]) return stops[0][1]
  for (let i = 1; i < stops.length; i += 1) {
    if (v <= stops[i][0]) return mix(stops[i - 1][1], stops[i][1], (v - stops[i - 1][0]) / (stops[i][0] - stops[i - 1][0]))
  }
  return stops[stops.length - 1][1]
}

export function scenePalette(mood, season) {
  const v = clamp(mood, 0, 1)
  const dry = clamp((0.62 - v) / 0.45, 0, 1)
  const winter = season === 'winter'
  return {
    skyTop: ramp([[0.1, '#9fa9b6'], [0.38, '#d3d6d8'], [0.6, '#f1e6d6'], [0.85, '#fcd9ae']], v),
    skyBottom: ramp([[0.1, '#d7dce2'], [0.38, '#eeede8'], [0.6, '#fbf7f0'], [0.85, '#fcf3e3']], v),
    sun: clamp((v - 0.48) / 0.25, 0, 1),
    cloudFill: ramp([[0.15, '#8c96a4'], [0.45, '#d9dce0'], [0.75, '#ffffff']], v),
    cloudCount: 1 + Math.round(clamp((0.8 - v) / 0.6, 0, 1) * 5),
    cloudOpacity: 0.55 + clamp(0.6 - v, 0, 0.4),
    rain: Math.max(clamp((0.33 - v) / 0.14, 0, 1) * 0.8, winter ? 0.55 : 0),
    snow: winter,
    shade: clamp((0.62 - v) * 0.42, 0, 0.2),
    grassA: mix('#c5d3a6', '#d3c9a0', dry),
    grassB: mix('#bdcc9d', '#c9be91', dry),
    hillA: mix('#daddc4', '#ded6bc', dry),
    hillB: mix('#cbd4b2', '#d4c9a6', dry),
    meadow: mix('#c3cda8', '#cec29c', dry),
    glow: 0.55 + clamp((0.62 - v) * 1.2, 0, 0.45),
  }
}

// Fixed raindrop positions for a scene, so the rain looks the same each load.
export function raindrops(seed, count, box) {
  const rand = mulberry32(seed)
  return Array.from({ length: count }, () => ({ x: box.x + rand() * box.w, y: box.y + rand() * box.h, delay: -rand() * 0.7 }))
}
