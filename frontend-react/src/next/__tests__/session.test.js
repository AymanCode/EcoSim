import { describe, expect, test } from 'vitest'
import { parseSession, buildArm, createArm, ingest, isFrame } from '../data/session.js'
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

  test('keeps a snapshot of firms, subjects and closed firms per tick, and the town-wide event counts', () => {
    const arm = fixtureArm()
    expect(arm.snapshots[1].firms).toHaveLength(4)
    expect(arm.snapshots[24].firms).toHaveLength(9)
    expect(arm.snapshots[24].subjects).toHaveLength(8)
    expect(arm.snapshots[24].firmsClosed).toEqual([])
    expect(arm.eventCounts[1].hired).toBe(58)
    expect(arm.eventCounts[11]).toMatchObject({ hired: expect.any(Number), laidOff: expect.any(Number) })
  })

  test('snapshots keep only the fields the screen reads', () => {
    const arm = fixtureArm()
    expect(Object.keys(arm.snapshots[24]).sort()).toEqual(['firms', 'firmsClosed', 'subjects'])
    expect(Object.keys(arm.snapshots[24].firms[0]).sort())
      .toEqual(['cash', 'id', 'isBaseline', 'name', 'sector', 'staff', 'state'])
    expect(Object.keys(arm.snapshots[24].subjects[0]).sort()).toEqual([
      'age', 'canWork', 'cash', 'employer', 'employerCategory', 'housingSecurity', 'id', 'isEmployed',
      'rentArrears', 'unemploymentDuration', 'wage',
    ])
  })

  test('concatenates events in order and records the policy change', () => {
    const arm = fixtureArm()
    expect(arm.events.length).toBe(79)
    expect(arm.events[0].tick).toBe(1)
    expect(arm.events[arm.events.length - 1].tick).toBe(24)
    expect(arm.policyChanges).toEqual([{ id: expect.stringMatching(/^7:policy_changed:/), tick: 7, policy: 'benefit_level', value: 'high' }])
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

const frameMessages = session => session.messages.filter(isFrame)

describe('setup and horizon from the wire', () => {
  test('SETUP_COMPLETE overrides the header, the header is the fallback', () => {
    const session = parseSession(FIXTURE_TEXT)
    const header = { ...session.header, setup: { ...session.header.setup, seed: 99, num_households: 1, horizon_ticks: 5, initial_policy: { public_works: 'on' }, arm_label: 'kept' } }
    const arm = buildArm({ ...session, header }, TOWN_A)
    expect(arm.setup).toMatchObject({ seed: 7, num_households: 60, horizon_ticks: 24, initial_policy: {}, arm_label: 'kept' })
    const noComplete = { header, messages: session.messages.filter(m => m.type !== 'SETUP_COMPLETE') }
    expect(buildArm(noComplete, TOWN_A).setup).toMatchObject({ seed: 99, num_households: 1, initial_policy: { public_works: 'on' } })
  })

  test('the horizon follows each frame and EXTENDED', () => {
    const session = parseSession(FIXTURE_TEXT)
    const arm = createArm({ ...TOWN_A, setup: session.header.setup })
    session.messages.forEach(message => ingest(arm, message))
    expect(arm.horizon).toBe(24)
    ingest(arm, { type: 'EXTENDED', horizonTick: 76, tick: 24, resumed: true })
    expect(arm.horizon).toBe(76)
    const last = frameMessages(session).at(-1)
    ingest(arm, { ...last, tick: 25, horizonTick: 80 })
    expect(arm.horizon).toBe(80)
  })

  test('with no horizon anywhere it is the last tick', () => {
    const session = parseSession(FIXTURE_TEXT)
    const messages = session.messages
      .filter(m => m.type !== 'SETUP_COMPLETE')
      .map(m => (isFrame(m) ? { ...m, horizonTick: null } : m))
    expect(buildArm({ header: { setup: {} }, messages }, TOWN_A).horizon).toBe(24)
  })
})

describe('incremental ingest', () => {
  test('message by message equals buildArm, at every step', () => {
    const session = parseSession(FIXTURE_TEXT)
    const arm = createArm({ ...TOWN_A, setup: session.header.setup })
    session.messages.forEach((message, i) => {
      expect(ingest(arm, message)).toBe(arm)
      if (i % 7 === 0) expect(arm).toEqual(buildArm({ header: session.header, messages: session.messages.slice(0, i + 1) }, TOWN_A))
    })
    expect(arm).toEqual(buildArm(session, TOWN_A))
  })

  test('each tick carries exactly its frame\'s figures and events, in wire order', () => {
    const session = parseSession(FIXTURE_TEXT)
    const arm = buildArm(session, TOWN_A)
    const frames = frameMessages(session)
    frames.forEach((frame, i) => {
      expect(arm.ticks[i]).toBe(frame.tick)
      expect(arm.series.peopleOutOfWorkPer100[i]).toBe(frame.curated.peopleOutOfWorkPer100)
      expect(arm.snapshots[frame.tick].subjects.map(s => s.id)).toEqual(frame.metrics.trackedSubjects.map(s => s.id))
    })
    expect(arm.events.map(e => e.id)).toEqual(frames.flatMap(f => f.events.map(e => e.id)))
  })

  test('frames out of order land in tick order', () => {
    const session = parseSession(FIXTURE_TEXT)
    const frames = frameMessages(session)
    const others = session.messages.filter(m => !isFrame(m))
    const shuffled = [...frames.slice(12), ...frames.slice(0, 12)]
    const arm = createArm({ ...TOWN_A, setup: session.header.setup })
    ;[...others, ...shuffled].forEach(message => ingest(arm, message))
    expect(arm).toEqual(buildArm(session, TOWN_A))
  })

  test('a repeated tick replaces the earlier frame, its events and its policy changes', () => {
    const session = parseSession(FIXTURE_TEXT)
    const arm = buildArm(session, TOWN_A)
    const week7 = frameMessages(session).find(f => f.tick === 7)
    ingest(arm, { ...week7, curated: { ...week7.curated, peopleOutOfWorkPer100: 99 }, events: [] })
    expect(arm.ticks).toHaveLength(24)
    expect(arm.series.peopleOutOfWorkPer100[6]).toBe(99)
    expect(arm.events.some(e => e.tick === 7)).toBe(false)
    expect(arm.policyChanges).toEqual([])
    const ticks = arm.events.map(e => e.tick)
    expect(ticks).toEqual([...ticks].sort((a, b) => a - b))
  })

  test('a figure that first appears late is null before it', () => {
    const arm = createArm(TOWN_A)
    ingest(arm, { tick: 1, metrics: {}, curated: { a: 1 } })
    ingest(arm, { tick: 2, metrics: {}, curated: { a: 2, b: 5 } })
    expect(arm.series).toEqual({ a: [1, 2], b: [null, 5] })
  })
})
