import { describe, expect, test } from 'vitest'
import { GRID, HOUSES, LAYOUT, LOT_CAPACITY, PAINT_ORDER, ROAD, STREET, STREET_CAPACITY, iso, personHouses } from '../town/geometry.js'

const key = ({ gx, gy }) => `${gx},${gy}`

describe('island layout', () => {
  test('projects tiles isometrically', () => {
    expect(iso(0, 0)).toEqual([0, 0])
    expect(iso(1, 0)).toEqual([18, 9])
    expect(iso(0, 1)).toEqual([-18, 9])
    expect(iso(0, 0, 10)).toEqual([0, -10])
  })

  test('has 50 lots beside the roads, nearest the crossing first', () => {
    expect(LAYOUT.lots).toHaveLength(LOT_CAPACITY)
    for (const lot of LAYOUT.lots) {
      const besideRoad = [ROAD - 1, ROAD + 1].includes(lot.gx) || [ROAD - 1, ROAD + 1].includes(lot.gy)
      expect(besideRoad).toBe(true)
    }
    const distance = lot => Math.abs(lot.gx - ROAD) + Math.abs(lot.gy - ROAD)
    for (let i = 1; i < LAYOUT.lots.length; i += 1) expect(distance(LAYOUT.lots[i])).toBeGreaterThanOrEqual(distance(LAYOUT.lots[i - 1]))
  })

  test('uses every tile once: roads, civic, lots, houses, trees and plain grass', () => {
    expect(LAYOUT.tiles).toHaveLength(GRID * GRID)
    expect(new Set(LAYOUT.tiles.map(key)).size).toBe(GRID * GRID)
    expect(LAYOUT.houses).toHaveLength(HOUSES)
    const taken = [...LAYOUT.lots, ...LAYOUT.houses, ...LAYOUT.trees].map(key)
    expect(new Set(taken).size).toBe(taken.length)
    const kinds = Object.fromEntries(LAYOUT.tiles.map(tile => [key(tile), tile.kind]))
    for (const house of LAYOUT.houses) expect(kinds[key(house)]).toBe('grass')
    for (const lot of LAYOUT.lots) expect(kinds[key(lot)]).toBe('lot')
  })

  test('draws back to front, with a slot after every tile', () => {
    const depth = item => (item.kind === 'hall' ? 18 : item.kind === 'bank' ? 12 : item.gx + item.gy + (item.kind === 'slot' ? 1.5 : 1))
    for (let i = 1; i < PAINT_ORDER.length; i += 1) expect(depth(PAINT_ORDER[i])).toBeGreaterThanOrEqual(depth(PAINT_ORDER[i - 1]))
    expect(PAINT_ORDER.filter(item => item.kind === 'slot')).toHaveLength(GRID * GRID)
    expect(PAINT_ORDER.filter(item => item.kind === 'house')).toHaveLength(HOUSES)
  })

  test('gives followed households distinct houses near the middle, the same ones every time', () => {
    const picked = personHouses([38, 366, 289, 226])
    expect(new Set(picked).size).toBe(4)
    for (const index of picked) expect(index).toBeLessThan(40)
    expect(personHouses([38, 366, 289, 226])).toEqual(picked)
    expect(personHouses([5, 5 + 40])).toHaveLength(2)
    expect(new Set(personHouses([5, 5 + 40])).size).toBe(2)
  })

  test('Main Street has 26 lots and 100 houses on the hill', () => {
    expect(STREET.lots).toHaveLength(STREET_CAPACITY)
    expect(STREET.houses).toHaveLength(HOUSES)
    const xs = STREET.lots.map(lot => lot.x)
    expect(new Set(xs).size).toBe(xs.length)
    for (const lot of STREET.lots) expect(lot.x + lot.w < STREET.hallX - 70 || lot.x > STREET.bankX + 40).toBe(true)
  })
})
