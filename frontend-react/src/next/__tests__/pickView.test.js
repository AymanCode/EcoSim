import { describe, expect, test } from 'vitest'
import { pickView } from '../pickView.js'

describe('pickView', () => {
  test('?view=next opens the new Run screen; anything else is the classic dashboard', () => {
    expect(pickView('?view=next')).toBe('next')
    expect(pickView('?demo=1&view=next')).toBe('next')
    expect(pickView('')).toBe('classic')
    expect(pickView('?view=classic')).toBe('classic')
    expect(pickView('?view=Next')).toBe('classic')
    expect(pickView(undefined)).toBe('classic')
  })
})
