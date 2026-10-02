import { describe, expect, test } from 'vitest'
import { lotAssignment } from '../town/lots.js'
import { demoArms } from './fixture.js'

// A tiny arm: firms present per week (open ids, closed ids).
function armOf(weeks) {
  const arm = { ticks: [], snapshots: {} }
  weeks.forEach(([open, closed], i) => {
    const tick = i + 1
    arm.ticks.push(tick)
    arm.snapshots[tick] = { firms: open.map(id => ({ id })), firmsClosed: closed.map(id => ({ id })) }
  })
  return arm
}

describe('lotAssignment', () => {
  test('a firm keeps its lot, nearest-first, while it is open or recently closed', () => {
    const arm = armOf([[[1, 2], []], [[1, 2, 3], []], [[2, 3], [1]]])
    const lots = lotAssignment(arm, 5)
    expect(lots.get(1)).toBe(0)
    expect(lots.get(2)).toBe(1)
    expect(lots.get(3)).toBe(2)
  })

  test('frees a lot when its firm leaves the closed list, for a later firm', () => {
    const arm = armOf([[[1, 2], []], [[2], [1]], [[2], []], [[2, 4], []]])
    const lots = lotAssignment(arm, 5)
    expect(lots.get(1)).toBe(0)
    expect(lots.get(4)).toBe(0)
  })

  test('never gives one lot to two firms at the same time, and counts the overflow', () => {
    const arm = armOf([[[1, 2, 3], []], [[1, 2, 3, 4], []]])
    const lots = lotAssignment(arm, 3)
    expect(lots.get(4)).toBeNull()
    expect(new Set([1, 2, 3].map(id => lots.get(id))).size).toBe(3)
  })

  test('extends as weeks arrive without changing earlier answers', () => {
    const arm = armOf([[[1], []], [[1, 2], []]])
    expect(lotAssignment(arm, 4).get(2)).toBe(1)
    arm.ticks.push(3)
    arm.snapshots[3] = { firms: [{ id: 1 }, { id: 2 }, { id: 9 }], firmsClosed: [] }
    const lots = lotAssignment(arm, 4)
    expect(lots.get(2)).toBe(1)
    expect(lots.get(9)).toBe(2)
  })

  test('fits the whole demo without overflow', () => {
    const [a, b] = demoArms()
    for (const arm of [a, b]) {
      const lots = lotAssignment(arm)
      for (const lot of lots.values()) expect(lot).not.toBeNull()
    }
  })
})
