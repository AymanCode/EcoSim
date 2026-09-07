import { describe, expect, test } from 'vitest'
import { normalizeLog } from './logs.js'

describe('normalizeLog', () => {
  test('maps SYS log to type System and severity info', () => {
    const log = normalizeLog({ tick: 1, type: 'SYS', txt: 'INITIALIZING KERNEL...' }, 0)
    expect(log.type).toBe('System')
    expect(log.severity.toLowerCase()).toBe('info')
  })

  test('maps message containing distress to severity error', () => {
    const log = normalizeLog({ tick: 3, type: 'FIRM', txt: 'Food Firm #3 entered distress' }, 2)
    expect(log.type).toBe('Firm')
    expect(log.severity.toLowerCase()).toBe('error')
  })
})
