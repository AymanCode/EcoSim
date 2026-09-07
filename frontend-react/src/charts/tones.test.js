import { describe, expect, test } from 'vitest'
import { TONES, toneVar, thresholdTone } from './tones.js'

describe('tones', () => {
  test('toneVar maps warn to var(--warn)', () => {
    expect(toneVar('warn')).toBe('var(--warn)')
  })

  test('toneVar maps flat to var(--ink3)', () => {
    expect(toneVar('flat')).toBe('var(--ink3)')
  })

  test('thresholdTone returns crit for values < 0.3', () => {
    expect(thresholdTone(0.2)).toBe('crit')
  })

  test('thresholdTone returns warn for values < 0.5 but >= 0.3', () => {
    expect(thresholdTone(0.4)).toBe('warn')
  })

  test('thresholdTone returns acc for values >= 0.5', () => {
    expect(thresholdTone(0.6)).toBe('acc')
  })
})
