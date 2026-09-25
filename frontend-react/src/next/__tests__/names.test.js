import { describe, expect, test } from 'vitest'
import { FIRST_NAMES, householdName, firmDisplayName, firmNamesFor } from '../names.js'

describe('householdName', () => {
  test('is deterministic and differs between neighbours', () => {
    expect(householdName(7)).toBe(householdName(7))
    expect(householdName(7)).not.toBe(householdName(8))
    expect(typeof householdName(7)).toBe('string')
    expect(householdName(7).length).toBeGreaterThan(1)
  })

  test('draws from a fixed list of at least 60 distinct first names', () => {
    expect(FIRST_NAMES.length).toBeGreaterThanOrEqual(60)
    expect(new Set(FIRST_NAMES).size).toBe(FIRST_NAMES.length)
    const firstSixty = new Set(Array.from({ length: 60 }, (_, id) => householdName(id)))
    expect(firstSixty.size).toBe(60)
  })

  test('accepts string ids the way profiles key them', () => {
    expect(householdName('56')).toBe(householdName(56))
  })
})

describe('firmDisplayName', () => {
  test('names a baseline firm after its sector', () => {
    expect(firmDisplayName({ id: 1, name: 'BaselineFood', sector: 'Food', isBaseline: true })).toBe('Town Food Co-op')
    expect(firmDisplayName({ id: 4, name: 'BaselineHealthcare', sector: 'Healthcare', isBaseline: true })).toBe('Town Healthcare Co-op')
  })

  test('gives other firms a stable per-sector name by id', () => {
    const a = firmDisplayName({ id: 5, name: 'FoodCo1', sector: 'Food', isBaseline: false })
    expect(a).toBe(firmDisplayName({ id: 5, name: 'FoodCo1', sector: 'Food', isBaseline: false }))
    expect(a).not.toBe(firmDisplayName({ id: 6, name: 'FoodCo2', sector: 'Food', isBaseline: false }))
    expect(firmNamesFor('Food')).toContain(a)
    for (const sector of ['Food', 'Housing', 'Services', 'Healthcare', 'PublicWorks']) {
      const names = firmNamesFor(sector)
      expect(names.length).toBeGreaterThanOrEqual(12)
      expect(new Set(names).size).toBe(names.length)
    }
  })

  test('infers sector and baseline from the good name when they are missing', () => {
    expect(firmDisplayName({ id: 5, name: 'FoodCo1' })).toBe(firmDisplayName({ id: 5, name: 'FoodCo1', sector: 'Food', isBaseline: false }))
    expect(firmDisplayName({ id: 3, name: 'BaselineServices' })).toBe('Town Services Co-op')
  })
})
