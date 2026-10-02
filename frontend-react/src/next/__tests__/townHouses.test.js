import { describe, expect, test } from 'vitest'
import { houseRank, houseStates, houseWeeks } from '../town/houses.js'
import { demoArms } from './fixture.js'

describe('houses', () => {
  test('the rank is a fixed shuffle of 0..99 per seed', () => {
    const rank = houseRank(1337)
    expect([...rank].sort((x, y) => x - y)).toEqual(Array.from({ length: 100 }, (_, i) => i))
    expect(houseRank(1337)).toEqual(rank)
    expect(houseRank(7)).not.toEqual(rank)
  })

  test('the lowest ranks lose their homes, the next look for work', () => {
    const rank = houseRank(1)
    const { states, counts } = houseStates({ out: 30, homeless: 10, total: 500 }, rank)
    expect(counts).toEqual({ home: 2, look: 30, work: 68 })
    states.forEach((state, i) => {
      if (rank[i] < 2) expect(state).toBe('home')
      else if (rank[i] < 32) expect(state).toBe('look')
      else expect(state).toBe('work')
    })
  })

  test('missing figures mean everyone works', () => {
    expect(houseStates({ out: null, homeless: null, total: null }, houseRank(1)).counts).toEqual({ home: 0, look: 0, work: 100 })
  })

  test('counts how long each house has been in its state', () => {
    const [arm] = demoArms()
    const rank = houseRank(arm.setup.seed)
    const at40 = houseWeeks(arm, 40, rank)
    const at41 = houseWeeks(arm, 41, rank)
    expect(at40).toHaveLength(100)
    const out40 = houseStates({ out: arm.series.peopleOutOfWorkPer100[arm.ticks.indexOf(40)], homeless: 0, total: 500 }, rank).states
    const out41 = houseStates({ out: arm.series.peopleOutOfWorkPer100[arm.ticks.indexOf(41)], homeless: 0, total: 500 }, rank).states
    for (let h = 0; h < 100; h += 1) expect(at41[h]).toBe(out40[h] === out41[h] ? at40[h] + 1 : 1)
  })
})
