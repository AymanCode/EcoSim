import { describe, expect, test } from 'vitest'
import { NUMBER_GROUPS } from '../catalog.js'
import { rowSeries } from '../numbers/compare.js'
import { rowHistory } from '../numbers/rowHistory.js'
import { demoArms } from './fixture.js'

describe('append-aware row histories', () => {
  test('every demo sparkline value matches the original helper, including scrubbed prefixes', () => {
    for (const arm of demoArms()) {
      for (const row of NUMBER_GROUPS.flatMap(group => group.rows)) {
        for (const tick of [104, 5, 11, 26, 60, 103, 104]) {
          expect(rowHistory(arm, row, tick), `${arm.label}: ${row.key} at ${tick}`).toEqual(rowSeries(arm, row, tick))
        }
      }
    }
  })

  test('Jobs added caches each unchanged 26-week window, preserving missing and fractional counts', () => {
    let reads = 0
    const events = Object.fromEntries(Array.from({ length: 65 }, (_, i) => [i + 1, i % 7 === 0 ? null : { hired: i / 10, laidOff: i % 3 === 0 ? null : 0.3 }]))
    const arm = { ticks: [1, 4, 11, 26, 30, 52], eventCounts: new Proxy(events, { get(target, key) { reads += 1; return target[key] } }) }
    const row = { key: 'netJobs26' }
    const original = { ...arm, eventCounts: events }
    const first = rowHistory(arm, row, 52)
    expect(first).toEqual(rowSeries(original, row, 52))
    const before = reads
    expect(rowHistory({ ...arm }, row, 52)).toBe(first)
    expect(reads).toBe(before)
    arm.ticks.push(53)
    expect(rowHistory({ ...arm }, row, 53)).toEqual(rowSeries(original, row, 53))
    expect(reads - before).toBe(26)
    const appended = reads
    for (const tick of [26, 0, 53]) expect(rowHistory(arm, row, tick)).toEqual(rowSeries(original, row, tick))
    expect(reads).toBe(appended)
  })

  test('cumulative and counted histories retain missing observations and duplicate count weeks across append and scrub', () => {
    const arm = { ticks: [], series: { careDenials: [], bankDefaultAmountThisTick: [], wealthP50: [], wealthAsOfTick: [], typicalWeeklyPay: [] } }
    const input = [
      [1, null, null, null], [11, 0, 40, 10], [12, null, 42, 10],
      [15, 0.2, 42, 15], [16, 0.1, null, 15], [20, 3, 35, null], [25, Infinity, 35, 25],
    ]
    const keys = ['careSoFar', 'writtenOffSoFar', 'wealthP50', 'typicalWeeklyPay']
    for (const [tick, count, wealth, asOf] of input) {
      arm.ticks.push(tick)
      arm.series.careDenials.push(count)
      arm.series.bankDefaultAmountThisTick.push(count)
      arm.series.wealthP50.push(wealth)
      arm.series.wealthAsOfTick.push(asOf)
      arm.series.typicalWeeklyPay.push(wealth)
      for (const key of keys) expect(rowHistory(arm, key, tick)).toEqual(rowSeries(arm, key, tick))
    }
    for (const tick of [0, 1, 11, 12, 14, 16, 20, 25]) {
      for (const key of keys) expect(rowHistory(arm, key, tick)).toEqual(rowSeries(arm, key, tick))
    }
  })

  test('source replacement, an added previously missing source and truncation invalidate cached histories', () => {
    const arm = { ticks: [1, 11, 20], series: { careDenials: [null, 1, 2] } }
    for (const key of ['careSoFar', 'wealthP50']) rowHistory(arm, key, 20)
    arm.series.careDenials = [null, 2, 3]
    arm.series.wealthP50 = [10, 20, 30]
    for (const key of ['careSoFar', 'wealthP50']) expect(rowHistory(arm, key, 20)).toEqual(rowSeries(arm, key, 20))
    arm.ticks.length = 1
    expect(rowHistory(arm, 'careSoFar', 20)).toEqual(rowSeries(arm, 'careSoFar', 20))
    arm.eventCounts = { 1: { hired: 2, laidOff: 1 } }
    expect(rowHistory(arm, 'netJobs26', 1)).toEqual([{ tick: 1, value: 1 }])
    arm.eventCounts = { 1: { hired: 5, laidOff: 1 } }
    expect(rowHistory(arm, 'netJobs26', 1)).toEqual([{ tick: 1, value: 4 }])
  })
})
