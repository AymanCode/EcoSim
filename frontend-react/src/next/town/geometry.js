// The diorama's fixed island: 16 × 16 tiles seen from above at an angle, two
// roads crossing at row and column 7, the town hall and the bank beside the
// crossing, 50 shop lots along the roads (nearest the crossing first), the 100
// house tiles nearest the middle and trees on the rest. Nothing here depends
// on a run: the same tile is the same place in every town. Also the Main
// Street layout (a side view) and which house a followed household lives in.

export const TILE_W = 36
export const TILE_H = 18
export const GRID = 16
export const ROAD = 7
export const HOUSES = 100
export const PERSON_HOUSE_CAPACITY = 40
export const LOT_CAPACITY = 50
export const STREET_CAPACITY = 26
export const VIEWBOX = '-302 -50 604 364'

const round1 = value => Math.round(value * 10) / 10
export const r1 = round1

// Screen position of a point on the island; z lifts it straight up.
export function iso(gx, gy, z = 0) {
  return [round1(((gx - gy) * TILE_W) / 2), round1(((gx + gy) * TILE_H) / 2 - z)]
}

export const pts = list => list.map(([x, y]) => `${round1(x)},${round1(y)}`).join(' ')

// Text set on a building's left face (it slopes down to the right).
export const onFace = at => `matrix(1 0.5 0 1 ${round1(at[0])} ${round1(at[1])})`

export function mulberry32(seed) {
  let a = seed | 0
  return () => {
    a = (a + 0x6D2B79F5) | 0
    let t = Math.imul(a ^ (a >>> 15), 1 | a)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

export const HALL = { gx: 8.1, gy: 8.1, w: 1.55, d: 1.55, h: 24 }
export const BANK = { gx: 5.15, gy: 5.15, w: 1.7, d: 1.7, h: 17 }
const CIVIC = new Set(['8,8', '9,8', '8,9', '9,9', '5,5', '6,5', '5,6', '6,6'])
const isRoad = (x, y) => x === ROAD || y === ROAD
const besideRoad = (x, y) => [ROAD - 1, ROAD + 1].includes(x) || [ROAD - 1, ROAD + 1].includes(y)

export const LAYOUT = (() => {
  const lots = []
  const free = []
  const kind = {}
  for (let x = 0; x < GRID; x += 1) {
    for (let y = 0; y < GRID; y += 1) {
      const key = `${x},${y}`
      if (isRoad(x, y)) kind[key] = 'road'
      else if (CIVIC.has(key)) kind[key] = 'civic'
      else if (besideRoad(x, y)) { kind[key] = 'lot'; lots.push({ gx: x, gy: y, d: Math.abs(x - ROAD) + Math.abs(y - ROAD), s: x - y }) }
      else { kind[key] = 'grass'; free.push({ gx: x, gy: y, d: Math.hypot(x - ROAD, y - ROAD) + (mulberry32(x * 31 + y)() - 0.5) * 1.6 }) }
    }
  }
  lots.sort((a, b) => a.d - b.d || a.s - b.s)
  free.sort((a, b) => a.d - b.d)
  const rand = mulberry32(11)
  const trees = free.slice(HOUSES).map(tile => ({ gx: tile.gx, gy: tile.gy, r: rand() })).filter(tree => tree.r < 0.8)
  const tiles = []
  for (let x = 0; x < GRID; x += 1) for (let y = 0; y < GRID; y += 1) tiles.push({ gx: x, gy: y, kind: kind[`${x},${y}`] })
  return {
    tiles,
    lots: lots.map(({ gx, gy }) => ({ gx, gy })),
    houses: free.slice(0, HOUSES).map(({ gx, gy }) => ({ gx, gy })),
    trees,
  }
})()

// Back to front: a tile's things are drawn before anything nearer the viewer.
// Each tile also gets an empty slot just after it, where moving cars and people
// on that tile are drawn so that buildings in front hide them.
export const PAINT_ORDER = (() => {
  const items = []
  const add = (depth, item) => items.push({ depth, item })
  LAYOUT.houses.forEach((tile, index) => add(tile.gx + tile.gy + 1, { kind: 'house', index, gx: tile.gx, gy: tile.gy }))
  LAYOUT.trees.forEach((tile, index) => add(tile.gx + tile.gy + 1, { kind: 'tree', index, gx: tile.gx, gy: tile.gy }))
  LAYOUT.lots.forEach((tile, index) => add(tile.gx + tile.gy + 1, { kind: 'lot', index, gx: tile.gx, gy: tile.gy }))
  add(18, { kind: 'hall', gx: 8, gy: 8 })
  add(12, { kind: 'bank', gx: 5, gy: 5 })
  for (let x = 0; x < GRID; x += 1) for (let y = 0; y < GRID; y += 1) add(x + y + 1.5, { kind: 'slot', gx: x, gy: y })
  return items.sort((a, b) => a.depth - b.depth || a.item.gx - b.item.gx).map(entry => entry.item)
})()

// The scene's six clouds: where each starts in the sky and its four puffs. The
// weather shows as many as the mood calls for; the motion loop drifts them.
export const CLOUDS = Array.from({ length: 6 }, (_, c) => {
  const s = 0.8 + (c % 3) * 0.25
  return {
    x: round1(-320 + c * 120 + mulberry32(c + 17)() * 60),
    y: -36 + (c % 3) * 16 + (c > 2 ? 40 : 0),
    puffs: [[0, 0, 11], [12, -4, 13], [25, 1, 10], [11, 4, 10]].map(([dx, dy, r]) => ({ cx: round1(dx * s), cy: round1(dy * s), rx: round1(r * s * 1.25), ry: round1(r * s * 0.8) })),
  }
})

// A small stable hash of text, for ids that are not numbers.
function textSeed(text) {
  let hash = 2166136261
  for (let i = 0; i < text.length; i += 1) hash = Math.imul(hash ^ text.charCodeAt(i), 16777619)
  return hash | 0
}

export function personHouseStart(id) {
  const number = typeof id === 'number' || (typeof id === 'string' && id.trim() !== '') ? Number(id) : Number.NaN
  const seed = Number.isFinite(number) ? Math.trunc(number) : textSeed(String(id))
  return Math.floor(mulberry32(seed)() * PERSON_HOUSE_CAPACITY)
}

// Numeric IDs sort numerically; other IDs have a deterministic text order.
export function comparePersonIds(a, b) {
  const an = Number(a), bn = Number(b)
  if (Number.isFinite(an) !== Number.isFinite(bn)) return Number.isFinite(an) ? -1 : 1
  if (Number.isFinite(an) && an !== bn) return an - bn
  return String(a) < String(b) ? -1 : String(a) > String(b) ? 1 : 0
}

// Pure placement for an isolated sample, starting at each ID's hash. With all
// 40 middle houses taken, extras share their start house (a bounded fallback).
// The town model uses people.js to retain homes across sample changes.
export function personHouses(ids) {
  const used = new Set()
  const assigned = []
  // Resolve collisions in identity order, then return in the caller's order.
  const ordered = ids.map((id, i) => ({ id, i })).sort((a, b) => comparePersonIds(a.id, b.id) || a.i - b.i)
  for (const { id, i } of ordered) {
    const start = personHouseStart(id)
    let index = start
    for (let step = 0; step < PERSON_HOUSE_CAPACITY && used.has(index); step += 1) index = (start + step + 1) % PERSON_HOUSE_CAPACITY
    if (used.has(index)) index = start
    used.add(index)
    assigned[i] = index
  }
  return assigned
}

// Main Street: shops on 26 lots either side of the town hall and bank (lot 0
// nearest the hall, alternating right and left), 100 houses in four terraced
// rows on the hill behind. Each side spreads its 13 lots evenly from the
// building nearest the hall out to an 8-unit margin at the edge of the picture.
export const STREET = (() => {
  const lotW = 30
  const margin = 8
  const perSide = STREET_CAPACITY / 2
  const rightFrom = 755
  const rightTo = 1200 - margin - lotW
  const leftFrom = 475
  const leftTo = margin
  const lots = []
  for (let k = 0; k < STREET_CAPACITY; k += 1) {
    const n = Math.floor(k / 2)
    const along = n / (perSide - 1)
    lots.push({ x: round1(k % 2 === 0 ? rightFrom + (rightTo - rightFrom) * along : leftFrom + (leftTo - leftFrom) * along), w: lotW })
  }
  const rand = mulberry32(5)
  const houses = []
  for (let i = 0; i < HOUSES; i += 1) {
    const row = Math.floor(i / 25)
    const n = i % 25
    houses.push({
      x: round1(26 + n * 46.4 + (row % 2 ? 23 : 0) + (rand() - 0.5) * 5),
      y: round1(94 + row * 32 + Math.sin(n / 3.2 + row) * 3 + (rand() - 0.5) * 2),
      s: round1(0.86 + row * 0.07),
    })
  }
  return { viewBox: '0 0 1200 340', base: 290, hallX: 600, bankX: 712, treasuryX: 524, lots, houses }
})()
