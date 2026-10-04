import { describe, expect, test } from 'vitest'
import { ingest } from '../data/session.js'
import { mulberry32, PERSON_HOUSE_CAPACITY, personHouses } from '../town/geometry.js'
import { townAt } from '../town/model.js'
import { householdHousesAt } from '../town/people.js'
import { frame, freshCopy, liveArm, subject } from './townFixture.js'

const subjects = ids => ids.map(id => subject(id))
const armOf = samples => liveArm(samples.map((ids, i) => [i + 1, { subjects: subjects(ids) }]))
const byId = (arm, tick) => new Map(arm.snapshots[tick].subjects.map(({ id }, i) => [id, householdHousesAt(arm, tick)[i]]))

describe('householdHousesAt', () => {
  test('starts with the pure sample placement, then keeps retained homes', () => {
    const arm = armOf([[1, 16, 2, 3], [16, 2, 3, 4]])
    expect(householdHousesAt(arm, 1)).toEqual(personHouses([1, 16, 2, 3]))
    expect(byId(arm, 2).get(16)).toBe(26)
    expect(byId(arm, 2).get(4)).toBe(personHouses([4])[0])
  })

  test('a departure frees its house in the same week, without moving an incumbent', () => {
    const arm = armOf([[1, 16], [16, 47]])
    // IDs 1, 16 and 47 all hash to house 25.
    expect(byId(arm, 2).get(16)).toBe(26)
    expect(byId(arm, 2).get(47)).toBe(25)
  })

  test('a returning household prefers its old house, even when its hash house is free', () => {
    const arm = armOf([[1, 16], [], [16]])
    expect(byId(arm, 3).get(16)).toBe(26)
    expect(personHouses([16])[0]).toBe(25)
  })

  test('a returner cannot displace the new holder of its old house', () => {
    const arm = armOf([[1], [16], [1, 16], [16]])
    expect(byId(arm, 2).get(16)).toBe(25)
    expect(byId(arm, 3).get(16)).toBe(25)
    expect(byId(arm, 3).get(1)).toBe(26)
    expect(byId(arm, 4).get(16)).toBe(25)
  })

  test('the whole tracked sample retains homes when households move into or out of the first four', () => {
    const arm = armOf([[2, 3, 4, 5, 1, 16], [16, 1, 2, 3, 4, 5]])
    expect(byId(arm, 1).get(16)).toBe(26)
    const people = townAt(arm, 2).people
    expect(people.map(person => person.id)).toEqual([16, 1, 2, 3])
    for (const person of people) expect(person.house).toBe(byId(arm, 1).get(person.id))
  })

  test('reorders within every week leave identity assignments unchanged', () => {
    const samples = [[1, 16, 2, 3], [16, 2, 3, 4], [1, 4, 16, 3], [16, 3, 4, 5]]
    const arm = armOf(samples), reversed = armOf(samples.map(ids => [...ids].reverse()))
    for (const tick of arm.ticks) expect(byId(arm, tick)).toEqual(byId(reversed, tick))
  })

  test('shallow copies and appended weeks reuse earlier answers without changing them', () => {
    const arm = armOf([[1, 16]])
    const first = householdHousesAt(arm, 1)
    expect(householdHousesAt({ ...arm }, 1)).toBe(first)
    ingest(arm, frame(2, { subjects: subjects([16, 2, 3, 4]) }))
    expect(householdHousesAt(arm, 1)).toBe(first)
    expect(householdHousesAt(arm, 1)).toEqual([25, 26])
    expect(householdHousesAt(arm, 1.5)).toBe(first)
    expect(householdHousesAt(arm, 0)).toEqual([])
    expect(householdHousesAt(null, 1)).toEqual([])
  })

  test('late weeks, repeated weeks and removal of an earlier week rebuild the replay', () => {
    const arm = liveArm([[1, { subjects: subjects([1]) }], [3, { subjects: subjects([1, 16]) }]])
    expect(byId(arm, 3).get(16)).toBe(26)
    ingest(arm, frame(2, { subjects: subjects([16]) }))
    expect(byId(arm, 3).get(16)).toBe(25)
    expect(byId(arm, 3).get(1)).toBe(26)
    ingest(arm, frame(2, { subjects: subjects([1]) }))
    expect(byId(arm, 3).get(16)).toBe(26)
    ingest(arm, frame(3, { subjects: subjects([16]) }))
    expect(byId(arm, 3).get(16)).toBe(25)
    arm.ticks.splice(1, 1)
    for (const tick of arm.ticks) expect(householdHousesAt(arm, tick)).toEqual(householdHousesAt(freshCopy(arm), tick))
    arm.ticks.pop()
    expect(householdHousesAt(arm, 3)).toEqual([25])
  })

  test('rechecks the arm even when a different snapshots object shares the same ticks', () => {
    const arm = armOf([[1, 16]])
    expect(householdHousesAt(arm, 1)).toEqual([25, 26])
    const other = { ...arm, snapshots: { 1: { subjects: subjects([16]) } } }
    expect(householdHousesAt(other, 1)).toEqual([25])
    expect(householdHousesAt(arm, 1)).toEqual([25, 26])
    arm.snapshots[1].subjects.splice(0, 1)
    expect(householdHousesAt(arm, 1)).toEqual([25])
  })

  test('bad and duplicate IDs finish with distinct, bounded assignments', () => {
    const ids = [undefined, undefined, null, NaN, Infinity, 'abc', 'abd', '12', 1.5, -3, 5, 5]
    const arm = armOf([ids, [...ids].reverse()])
    for (const tick of arm.ticks) {
      const houses = householdHousesAt(arm, tick)
      expect(houses).toHaveLength(ids.length)
      expect(new Set(houses).size).toBe(ids.length)
      expect(houses.every(house => Number.isInteger(house) && house >= 0 && house < PERSON_HOUSE_CAPACITY)).toBe(true)
      expect(houses).toEqual(householdHousesAt(freshCopy(arm), tick))
    }
  })

  test('45 IDs reserve at most 40 houses; overflow can fill a vacancy without moving retained homes', () => {
    const ids = Array.from({ length: 45 }, (_, id) => id)
    const arm = armOf([ids, ids.slice(1)])
    const first = householdHousesAt(arm, 1), second = householdHousesAt(arm, 2)
    expect(new Set(first.filter(house => house != null)).size).toBe(40)
    expect(first.filter(house => house == null)).toHaveLength(5)
    expect(second.filter(house => house == null)).toHaveLength(4)
    for (let id = 1; id < 40; id += 1) expect(second[id - 1]).toBe(first[id])
    expect(byId(arm, 2).get(40)).toBe(first[0])
    ingest(arm, frame(3, { subjects: subjects([40, 41, 42, 43, ...ids.slice(1, 40)]) }))
    expect(townAt(arm, 3).people.map(person => person.id)).toEqual([40])
  })

  test('matches a fresh replay after mixes of new, late and repeated weeks', () => {
    const rand = mulberry32(404)
    const arm = liveArm([])
    for (let step = 0; step < 50; step += 1) {
      const ids = [1, 16, 19, 2, 3, 4, 5].filter(() => rand() < 0.6)
      ingest(arm, frame(1 + Math.floor(rand() * 10), { subjects: subjects(ids) }))
      for (const tick of arm.ticks) expect(householdHousesAt(arm, tick)).toEqual(householdHousesAt(freshCopy(arm), tick))
    }
  })
})
