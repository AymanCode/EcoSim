import { describe, expect, test } from 'vitest'
import { act, renderHook } from '@testing-library/react'
import { useLiveClock } from '../live/useLiveClock.js'

function clock(liveTick = 1) {
  return renderHook(({ live }) => useLiveClock(live), { initialProps: { live: liveTick } })
}

describe('useLiveClock', () => {
  test('follows the live week as it rises', () => {
    const { result, rerender } = clock(0)
    expect(result.current.tick).toBe(0)
    expect(result.current.following).toBe(true)
    rerender({ live: 3 })
    expect(result.current.tick).toBe(3)
    rerender({ live: 20 })
    expect(result.current.tick).toBe(20)
    expect(result.current.following).toBe(true)
  })

  test('a scrub back holds that week while the towns run on', () => {
    const { result, rerender } = clock(20)
    act(() => result.current.scrub(5))
    expect(result.current.tick).toBe(5)
    expect(result.current.following).toBe(false)
    rerender({ live: 26 })
    expect(result.current.tick).toBe(5)
    expect(result.current.following).toBe(false)
  })

  test('a scrub to the live week follows again', () => {
    const { result, rerender } = clock(20)
    act(() => result.current.scrub(5))
    act(() => result.current.scrub(20))
    expect(result.current.tick).toBe(20)
    expect(result.current.following).toBe(true)
    rerender({ live: 21 })
    expect(result.current.tick).toBe(21)
  })

  test('follow() jumps to the live week', () => {
    const { result, rerender } = clock(20)
    act(() => result.current.scrub(7))
    rerender({ live: 30 })
    act(() => result.current.follow())
    expect(result.current.tick).toBe(30)
    expect(result.current.following).toBe(true)
  })
})
