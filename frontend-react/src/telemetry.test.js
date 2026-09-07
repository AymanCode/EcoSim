import { describe, expect, test } from 'vitest'
import { renderHook } from '@testing-library/react'
import frame from './test/fixtures/frame.json'
import { series, latest, backN, deltaVs, stress, employment, appendCurrent, useTickHistory } from './telemetry.js'

describe('telemetry', () => {
  const m = frame.metrics
  test('series and latest read histories defensively', () => {
    expect(series(m.gdpHistory).length).toBe(3); expect(series(undefined)).toEqual([]); expect(latest(m.gdpHistory)).toBe(m.gdpHistory[2].value); expect(latest(undefined, 7)).toBe(7)
  })
  test('backN and deltaVs', () => {
    expect(backN(m.gdpHistory, 1)).toBe(m.gdpHistory[1].value)
    const d = deltaVs(10, [{ tick: 1, value: 8 }, { tick: 2, value: 9 }], 1)
    expect(d.diff).toBe(2); expect(d.pct).toBe(25)
  })
  test('derived metrics are bounded', () => {
    expect(stress({ unemployment: 200, happiness: 0, firmDistressPressure: 100 })).toBe(100)
    expect(employment({ unemployment: 28.8 })).toBeCloseTo(71.2)
  })
  test('appendCurrent adds a live point only when newer', () => {
    const h = [{ tick: 25, value: 1 }]
    expect(appendCurrent(h, 30, 2)).toEqual([{ tick: 25, value: 1 }, { tick: 30, value: 2 }])
    expect(appendCurrent(h, 25, 2)).toEqual(h)
  })
  test('useTickHistory records history up to max entries', () => {
    const { result, rerender } = renderHook(({ t, v }) => useTickHistory(t, v, 3), { initialProps: { t: 1, v: { a: 1 } } })
    rerender({ t: 2, v: { a: 2 } })
    rerender({ t: 3, v: { a: 3 } })
    rerender({ t: 4, v: { a: 4 } })
    expect(result.current.a.length).toBe(3)
    expect(result.current.a[result.current.a.length - 1]).toEqual({ tick: 4, value: 4 })
  })
})
