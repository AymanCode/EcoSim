import { describe, expect, test } from 'vitest'
import { commonTicks, valueAt, snapshotAt, seriesUpTo, compareAt, eventsUpTo } from '../data/derive.js'
import { fixtureArm, TOWN_A, TOWN_B } from './fixture.js'

const KEY = 'peopleOutOfWorkPer100'

function twoTowns() {
  const a = fixtureArm(TOWN_A)
  const b = fixtureArm(TOWN_B)
  b.series[KEY] = b.series[KEY].map(v => v + 3)
  return [a, b]
}

describe('commonTicks', () => {
  test('keeps ticks present in every arm, ascending', () => {
    const [a, b] = twoTowns()
    expect(commonTicks([a, b])).toEqual(a.ticks)
    const shorter = { ...b, ticks: b.ticks.filter(t => t % 2 === 0 || t > 20) }
    const common = commonTicks([a, shorter])
    expect(common[0]).toBe(2)
    expect(common).toContain(21)
    expect(common).not.toContain(3)
    expect(commonTicks([])).toEqual([])
  })
})

describe('valueAt and snapshotAt', () => {
  test('are null before the first recorded tick', () => {
    const arm = fixtureArm()
    expect(valueAt(arm, KEY, 0)).toBeNull()
    expect(snapshotAt(arm, 0)).toBeNull()
  })

  test('use the last recorded tick at or before the asked tick', () => {
    const arm = fixtureArm()
    expect(valueAt(arm, KEY, 11)).toBeCloseTo(41.67, 2)
    expect(valueAt(arm, KEY, 11.5)).toBeCloseTo(41.67, 2)
    expect(valueAt(arm, KEY, 500)).toBeCloseTo(1.67, 2)
    expect(snapshotAt(arm, 13).subjects.map(s => s.id)).toContain(29)
    expect(snapshotAt(arm, 500)).toBe(arm.snapshots[24])
  })

  test('return null for an unknown key', () => {
    expect(valueAt(fixtureArm(), 'noSuchMetric', 5)).toBeNull()
  })
})

describe('seriesUpTo', () => {
  test('lists tick and value pairs through the asked tick', () => {
    const arm = fixtureArm()
    const points = seriesUpTo(arm, 'typicalWeeklyPay', 3)
    expect(points.map(p => p.tick)).toEqual([1, 2, 3])
    expect(points[0].value).toBeCloseTo(35.52, 2)
    expect(seriesUpTo(arm, KEY, 0)).toEqual([])
  })
})

describe('compareAt', () => {
  test('gives each town its value and a delta against the first town', () => {
    const rows = compareAt(twoTowns(), KEY, 11)
    expect(rows).toHaveLength(2)
    expect(rows[0]).toMatchObject({ label: 'Town A', color: TOWN_A.color, deltaVsFirst: null })
    expect(rows[1].label).toBe('Town B')
    expect(rows[1].deltaVsFirst).toBeCloseTo(3, 6)
  })

  test('has a null delta when either value is missing', () => {
    const rows = compareAt(twoTowns(), KEY, 0)
    expect(rows[1].deltaVsFirst).toBeNull()
  })
})

describe('eventsUpTo', () => {
  test('returns events up to the tick, newest first, capped by limit', () => {
    const arm = fixtureArm()
    const events = eventsUpTo(arm, 11, 5)
    expect(events).toHaveLength(5)
    expect(events[0].tick).toBe(11)
    expect(events.every(e => e.tick <= 11)).toBe(true)
    for (let i = 1; i < events.length; i += 1) expect(events[i - 1].tick).toBeGreaterThanOrEqual(events[i].tick)
  })

  test('returns every event up to the tick without a limit', () => {
    const arm = fixtureArm()
    expect(eventsUpTo(arm, 24)).toHaveLength(arm.events.length)
    expect(eventsUpTo(arm, 0)).toEqual([])
  })
})
