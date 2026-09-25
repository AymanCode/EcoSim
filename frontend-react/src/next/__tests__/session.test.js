import { describe, expect, test } from 'vitest'
import { parseSession, buildArm, isFrame } from '../data/session.js'
import { FIXTURE_TEXT, fixtureArm, TOWN_A } from './fixture.js'

describe('parseSession', () => {
  test('returns the header and the message payloads in wire order', () => {
    const { header, messages } = parseSession(FIXTURE_TEXT)
    expect(header.kind).toBe('header')
    expect(header.setup.seed).toBe(7)
    expect(messages[0].type).toBe('SESSION')
    expect(messages.filter(isFrame)).toHaveLength(24)
    // `sent` lines and the footer are not messages.
    expect(messages.some(m => m.command)).toBe(false)
    expect(messages.some(m => m.kind === 'footer')).toBe(false)
  })

  test('tolerates blank lines and CRLF endings', () => {
    const text = FIXTURE_TEXT.split('\n').join('\r\n') + '\r\n\r\n'
    expect(parseSession(text).messages.filter(isFrame)).toHaveLength(24)
  })

  test('names the line of malformed JSON', () => {
    expect(() => parseSession('{"kind":"header","setup":{}}\n{nope')).toThrow(/line 2/)
  })
})

describe('buildArm', () => {
  test('carries label, colour, setup and horizon', () => {
    const arm = fixtureArm()
    expect(arm.label).toBe(TOWN_A.label)
    expect(arm.color).toBe(TOWN_A.color)
    expect(arm.setup.seed).toBe(7)
    expect(arm.setup.initial_policy).toEqual({})
    expect(arm.horizon).toBe(24)
  })

  test('has one entry per tick in ascending order', () => {
    const arm = fixtureArm()
    expect(arm.ticks).toHaveLength(24)
    expect(arm.ticks[0]).toBe(1)
    expect(arm.ticks[23]).toBe(24)
    expect(arm.series.peopleOutOfWorkPer100).toHaveLength(24)
    expect(arm.series.typicalWeeklyPay[0]).toBeCloseTo(35.52, 2)
    // Null stays null rather than turning into zero.
    expect(arm.series.bankDefaultsTotal.every(v => v === null)).toBe(true)
  })

  test('merges tracked profiles from SETUP_COMPLETE and every TRACKED reply', () => {
    const arm = fixtureArm()
    for (const id of ['56', '25', '36', '31', '48', '15', '41', '13', '29', '21', '59', '44', '49', '58']) {
      expect(arm.profiles[id]).toBeTruthy()
    }
    expect(typeof arm.profiles['56'].spendingTendency).toBe('number')
  })

  test('keeps a snapshot of firms, subjects, closed firms and event counts per tick', () => {
    const arm = fixtureArm()
    expect(arm.snapshots[1].firms).toHaveLength(4)
    expect(arm.snapshots[24].firms).toHaveLength(9)
    expect(arm.snapshots[24].subjects).toHaveLength(8)
    expect(arm.snapshots[24].firmsClosed).toEqual([])
    expect(arm.snapshots[1].eventCounts.hired).toBe(58)
  })

  test('concatenates events in order and records the policy change', () => {
    const arm = fixtureArm()
    expect(arm.events.length).toBe(79)
    expect(arm.events[0].tick).toBe(1)
    expect(arm.events[arm.events.length - 1].tick).toBe(24)
    expect(arm.policyChanges).toEqual([{ tick: 7, policy: 'benefit_level', value: 'high' }])
  })

  test('indexes every firm it has seen by id and by name', () => {
    const arm = fixtureArm()
    expect(arm.firmDirectory.byId[5]).toMatchObject({ id: 5, name: 'FoodCo1', sector: 'Food', isBaseline: false })
    expect(arm.firmDirectory.byName.BaselineFood).toMatchObject({ id: 1, isBaseline: true })
  })

  test('falls back to the header horizon, then to the last tick', () => {
    const session = parseSession(FIXTURE_TEXT)
    const noComplete = { ...session, messages: session.messages.filter(m => m.type !== 'SETUP_COMPLETE') }
    expect(buildArm(noComplete, TOWN_A).horizon).toBe(24)
    const bare = { header: { setup: {} }, messages: noComplete.messages }
    expect(buildArm(bare, TOWN_A).horizon).toBe(24)
  })
})
