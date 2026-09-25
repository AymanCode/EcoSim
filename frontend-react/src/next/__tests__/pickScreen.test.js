import { describe, expect, test } from 'vitest'
import { pickScreen } from '../pickScreen.js'

describe('pickScreen', () => {
  test('a `demo` key opens the recorded demo; anything else opens Set up', () => {
    expect(pickScreen('?view=next&demo')).toBe('demo')
    expect(pickScreen('?demo=1&view=next')).toBe('demo')
    expect(pickScreen('?view=next')).toBe('setup')
    expect(pickScreen('?view=next&demos')).toBe('setup')
    expect(pickScreen('')).toBe('setup')
    expect(pickScreen(undefined)).toBe('setup')
  })
})
