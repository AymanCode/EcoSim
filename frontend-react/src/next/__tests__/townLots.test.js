import { describe, expect, test } from 'vitest'
import { createArm, ingest } from '../data/session.js'
import { mulberry32 } from '../town/geometry.js'
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

// An arm built the way the app builds it: one frame per week through `ingest`,
// so a repeated or out-of-order week behaves exactly as it does live.
const frame = (tick, open, closed = []) => ({
  tick, metrics: {}, curated: {}, firms: open.map(id => ({ id })), firmsClosed: closed.map(id => ({ id })),
})
function liveArm(weeks) {
  const arm = createArm({ label: 'Town', color: '#000' })
  for (const [tick, open, closed] of weeks) ingest(arm, frame(tick, open, closed))
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

  test('in every week of the demo, no two firms on the island share a lot', () => {
    const [a, b] = demoArms()
    for (const arm of [a, b]) {
      const lots = lotAssignment(arm)
      for (const tick of arm.ticks) {
        const snapshot = arm.snapshots[tick]
        const used = [...snapshot.firms, ...snapshot.firmsClosed].map(firm => lots.get(firm.id))
        expect(new Set(used).size).toBe(used.length)
      }
    }
  })
})

describe('lotAssignment when earlier weeks change', () => {
  test('a repeated last week, overwritten in place, is replayed', () => {
    const arm = liveArm([[1, [1, 2]], [2, [1, 2]]])
    expect(lotAssignment(arm, 5).get(2)).toBe(1)
    ingest(arm, frame(2, [7]))
    const lots = lotAssignment(arm, 5)
    // Week 2 now holds only firm 7; firms 1 and 2 were freed that week.
    expect(lots.get(7)).toBe(0)
    expect(lots.get(1)).toBe(0)
    expect(lots.get(2)).toBe(1)
  })

  test('a repeated week in the middle, overwritten in place, is replayed', () => {
    const arm = liveArm([[1, [1, 2]], [2, [1, 2]], [3, [1, 2]]])
    expect(lotAssignment(arm, 5).has(6)).toBe(false)
    ingest(arm, frame(2, [1, 2, 6]))
    expect(lotAssignment(arm, 5).get(6)).toBe(2)
  })

  test('a week that arrives late and lands in the middle is replayed in order', () => {
    const arm = liveArm([[1, [1]], [3, [1, 2]]])
    const before = lotAssignment(arm, 5)
    expect([before.get(1), before.get(2)]).toEqual([0, 1])
    // Firm 2 is now seen in week 2, while firm 1 is gone, so it takes lot 0 first.
    ingest(arm, frame(2, [2]))
    const lots = lotAssignment(arm, 5)
    expect(lots.get(2)).toBe(0)
    expect(lots.get(1)).toBe(1)
  })

  test('a different capacity is answered afresh, and back again', () => {
    const arm = liveArm([[1, [1, 2, 3, 4]]])
    expect(lotAssignment(arm, 5).get(4)).toBe(3)
    expect(lotAssignment(arm, 3).get(4)).toBeNull()
    expect(lotAssignment(arm, 5).get(4)).toBe(3)
  })
})

describe('lotAssignment against a fresh replay', () => {
  test('matches a replay with nothing cached after any mix of new, late and repeated weeks', () => {
    const rand = mulberry32(2024)
    const some = () => [1, 2, 3, 4, 5, 6, 7].filter(() => rand() < 0.4)
    const arm = createArm({ label: 'Town', color: '#000' })
    for (let step = 0; step < 60; step += 1) {
      ingest(arm, frame(1 + Math.floor(rand() * 9), some(), some()))
      expect(lotAssignment(arm, 4)).toEqual(lotAssignment({ ...arm, ticks: [...arm.ticks] }, 4))
    }
  })
})

describe('lotAssignment when a firm is seen again after a gap', () => {
  test('a firm that left and came back does not share a lot with a newcomer', () => {
    const arm = armOf([[[1, 2], []], [[], []], [[1, 2, 3], []]])
    const lots = lotAssignment(arm, 5)
    expect(lots.get(1)).toBe(0)
    expect(lots.get(2)).toBe(1)
    expect(lots.get(3)).toBe(2)
  })

  test('a firm whose old lot was given away takes the first free one', () => {
    const arm = armOf([[[1], []], [[], []], [[2], []], [[1, 2], []]])
    const lots = lotAssignment(arm, 5)
    expect(lots.get(2)).toBe(0)
    expect(lots.get(1)).toBe(1)
  })

  test('a returning firm with no free lot left is counted, not drawn on top of another', () => {
    const arm = armOf([[[1], []], [[], []], [[2], []], [[1, 2], []]])
    const lots = lotAssignment(arm, 1)
    expect(lots.get(2)).toBe(0)
    expect(lots.get(1)).toBeNull()
  })

  test('a firm that never had a lot stays uncounted when a lot frees up later', () => {
    // Firm 2 was never drawn, so giving it firm 1's freed lot would also put it on top of firm 1 in week 1.
    const arm = armOf([[[1, 2], []], [[2], []]])
    const lots = lotAssignment(arm, 1)
    expect(lots.get(1)).toBe(0)
    expect(lots.get(2)).toBeNull()
  })
})
