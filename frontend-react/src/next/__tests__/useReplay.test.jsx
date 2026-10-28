import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'
import { act, renderHook } from '@testing-library/react'
import useReplay from '../useReplay.js'

describe('useReplay', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  test('starts paused at week 1', () => {
    const { result } = renderHook(() => useReplay({ maxTick: 104 }))
    expect(result.current.tick).toBe(1)
    expect(result.current.playing).toBe(false)
    act(() => { vi.advanceTimersByTime(2000) })
    expect(result.current.tick).toBe(1)
  })

  test('plays 8 weeks a second and pauses without advancing', () => {
    const { result } = renderHook(() => useReplay({ maxTick: 104 }))
    act(() => result.current.play())
    expect(result.current.playing).toBe(true)
    act(() => { vi.advanceTimersByTime(124) })
    expect(result.current.tick).toBe(1)
    act(() => { vi.advanceTimersByTime(1) })
    expect(result.current.tick).toBe(2)
    act(() => { vi.advanceTimersByTime(875) })
    expect(result.current.tick).toBe(9)
    act(() => { vi.advanceTimersByTime(1000) })
    expect(result.current.tick).toBe(17)
    act(() => result.current.pause())
    act(() => { vi.advanceTimersByTime(1000) })
    expect(result.current.tick).toBe(17)
    act(() => result.current.play())
    act(() => { vi.advanceTimersByTime(125) })
    expect(result.current.tick).toBe(18)
  })

  test('stops at the last week', () => {
    const { result } = renderHook(() => useReplay({ maxTick: 10 }))
    act(() => result.current.toggle())
    act(() => { vi.advanceTimersByTime(5000) })
    expect(result.current.tick).toBe(10)
    expect(result.current.playing).toBe(false)
  })

  test('playing again from the last week starts over', () => {
    const { result } = renderHook(() => useReplay({ maxTick: 10 }))
    act(() => result.current.scrub(10))
    act(() => result.current.toggle())
    expect(result.current.playing).toBe(true)
    expect(result.current.tick).toBe(1)
  })

  test('scrub clamps to 1..maxTick and rounds', () => {
    const { result } = renderHook(() => useReplay({ maxTick: 24 }))
    act(() => result.current.scrub(0))
    expect(result.current.tick).toBe(1)
    act(() => result.current.scrub(500))
    expect(result.current.tick).toBe(24)
    act(() => result.current.scrub(4.6))
    expect(result.current.tick).toBe(5)
    act(() => result.current.scrub('12'))
    expect(result.current.tick).toBe(12)
  })
})
