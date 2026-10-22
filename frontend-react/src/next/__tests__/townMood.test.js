import { describe, expect, test } from 'vitest'
import { moodBand, moodOf, scenePalette, seasonOf } from '../town/mood.js'

describe('mood', () => {
  test('mixes work and happiness', () => {
    expect(moodOf({ out: 5, happiness: 65, warmUp: false })).toBeCloseTo(1)
    expect(moodOf({ out: 45, happiness: 10, warmUp: false })).toBeCloseTo(0)
    expect(moodOf({ out: 25, happiness: 37.5, warmUp: false })).toBeCloseTo(0.55 * 0.5 + 0.45 * 0.5)
  })

  test('is neutral during warm-up and falls back when a figure is missing', () => {
    expect(moodOf({ out: 42, happiness: 69, warmUp: true })).toBe(0.62)
    expect(moodOf({ out: null, happiness: null, warmUp: false })).toBeCloseTo(0.6)
    expect(moodOf({ out: 5, happiness: null, warmUp: false })).toBeCloseTo(0.55 + 0.45 * 0.6)
  })

  test('names the band at its edges', () => {
    expect(moodBand(0.72)).toBe('thriving')
    expect(moodBand(0.7199)).toBe('okay')
    expect(moodBand(0.5)).toBe('okay')
    expect(moodBand(0.4999)).toBe('struggling')
    expect(moodBand(0.3)).toBe('struggling')
    expect(moodBand(0.2999)).toBe('hard')
  })

  test('follows the seasons of a 52-week year', () => {
    expect(seasonOf(1)).toBe('winter')
    expect(seasonOf(9)).toBe('winter')
    expect(seasonOf(10)).toBe('spring')
    expect(seasonOf(22)).toBe('spring')
    expect(seasonOf(23)).toBe('summer')
    expect(seasonOf(36)).toBe('autumn')
    expect(seasonOf(48)).toBe('autumn')
    expect(seasonOf(49)).toBe('winter')
    expect(seasonOf(53)).toBe('winter')
    expect(seasonOf(62)).toBe('spring')
  })

  test('the palette: sun when thriving, rain in hard times, snow in winter, shade capped', () => {
    const good = scenePalette(0.85, 'summer')
    const bad = scenePalette(0.1, 'summer')
    expect(good.sun).toBeGreaterThan(0.9)
    expect(good.rain).toBe(0)
    expect(bad.sun).toBe(0)
    expect(bad.rain).toBeGreaterThan(0.7)
    expect(bad.snow).toBe(false)
    expect(bad.shade).toBeLessThanOrEqual(0.2)
    expect(bad.cloudCount).toBeGreaterThan(good.cloudCount)
    const winter = scenePalette(0.85, 'winter')
    expect(winter.snow).toBe(true)
    expect(winter.rain).toBeGreaterThanOrEqual(0.55)
    expect(good.grassA).toMatch(/^#[0-9a-f]{6}$/i)
  })
})
