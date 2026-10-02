import { beforeAll, describe, expect, test } from 'vitest'
import { COPY, DEFAULT_POLICY } from '../catalog.js'
import { townAt } from '../town/model.js'
import { demoArms, fixtureArm } from './fixture.js'

let A, B
beforeAll(() => { [A, B] = demoArms() })

describe('townAt', () => {
  test('warm-up weeks are neutral and quiet', () => {
    const model = townAt(A, 5)
    expect(model.warmUp).toBe(true)
    expect(model.mood).toBe(0.62)
    expect(model.hall.queue).toBe(0)
    expect(model.traffic.walkers).toBe(4)
  })

  test('houses follow out of work and homeless', () => {
    const model = townAt(A, 70)
    expect(model.houses).toHaveLength(100)
    expect(model.counts.look).toBe(Math.round(model.facts.out))
    expect(model.counts.work + model.counts.look + model.counts.home).toBe(100)
  })

  test('the demo towns part ways in mood by year 2', () => {
    const a = townAt(A, 100), b = townAt(B, 100)
    expect(a.band).toBe('hard')
    expect(b.mood).toBeGreaterThan(a.mood)
  })

  test('shops: one per lot, states, floors, the richest private shop', () => {
    const model = townAt(A, 70)
    const lots = model.shops.map(shop => shop.lot)
    expect(new Set(lots).size).toBe(lots.length)
    for (const shop of model.shops) {
      expect(['steady', 'growing', 'struggling', 'closed']).toContain(shop.state)
      expect(shop.floors).toBeGreaterThanOrEqual(1)
      expect(shop.floors).toBeLessThanOrEqual(6)
      expect(typeof shop.name).toBe('string')
    }
    const richest = model.shops.filter(shop => shop.richest)
    expect(richest).toHaveLength(1)
    const open = model.shops.filter(shop => shop.state !== 'closed' && !shop.coop)
    expect(richest[0].cash).toBe(Math.max(...open.map(shop => shop.cash)))
    expect(richest[0].coop).toBe(false)
  })

  test('a shop that closed at week 70 is closed for 0 weeks then; firms of week 1 are not new', () => {
    const model = townAt(A, 70)
    const closedNow = model.shops.find(shop => shop.state === 'closed' && shop.closedTick === 70)
    expect(closedNow?.closedFor).toBe(0)
    expect(model.week.closed).toContain(closedNow.id)
    for (const shop of townAt(A, 12).shops.filter(s => s.coop)) expect(shop.isNew || shop.fresh).toBe(false)
  })

  test('the bank and the town hall', () => {
    const model = townAt(A, 70)
    expect(model.bank.bad).toBeGreaterThan(19000)
    expect(model.bank.badNow).toBe(true)
    expect(model.bank.papers).toBeGreaterThan(0)
    expect(model.hall.cash).toBeLessThan(0)
    expect(townAt(A, 70).hall.banner).toBeNull()
    expect(townAt(B, 70).hall.banner).toBe('NEW MIN. WAGE')
  })

  test('people: the first four tracked households, each in a distinct house', () => {
    const model = townAt(A, 60)
    expect(model.people).toHaveLength(4)
    expect(new Set(model.people.map(person => person.house)).size).toBe(4)
    const nikhil = model.people.find(person => person.name === 'Nikhil')
    expect(nikhil.working).toBe(false)
    expect(nikhil.weeksOut).toBeGreaterThan(20)
    expect(['look', 'low']).toContain(nikhil.tone)
  })

  test('an arm without happiness or bank figures still builds a model', () => {
    const model = townAt(fixtureArm(), 11)
    expect(Number.isFinite(model.mood)).toBe(true)
    expect(model.bank.papers).toBe(0)
    expect(model.bank.badNow).toBe(false)
  })

  test('traffic and flows follow the money', () => {
    const model = townAt(A, 40)
    expect(model.traffic.cars).toBe(Math.max(0, Math.min(7, Math.round(model.flows.spend / 5000))))
    expect(model.flows.pay).toBeGreaterThan(0)
  })

  test('every rule lever has a short banner name', () => {
    for (const lever of Object.keys(DEFAULT_POLICY)) expect(COPY.diorama.banner[lever], lever).toEqual(expect.any(String))
  })

  test('the banner names one rule, or NEW RULES when several differ, and the pulse lasts four weeks', () => {
    const arm = demoArms()[0]
    arm.setup = { ...arm.setup, initial_policy: { sector_subsidy_target: 'Food', sector_subsidy_level: 0.2 } }
    expect(townAt(arm, 30).hall.banner).toBe('SUBSIDIES')
    arm.policyChanges = [{ tick: 50, policy: 'wage_tax_rate', value: 0.25 }]
    expect(townAt(arm, 49).hall.banner).toBe('SUBSIDIES')
    expect(townAt(arm, 50).hall.banner).toBe('NEW RULES')
    expect([49, 50, 53, 54].map(tick => townAt(arm, tick).hall.changedTick)).toEqual([null, 50, 50, null])
    arm.setup = { ...arm.setup, initial_policy: {} }
    expect(townAt(arm, 60).hall.banner).toBe('NEW WAGE TAX')
  })

  test('a town with no weeks yet is an empty, calm model', () => {
    const model = townAt({ ticks: [], snapshots: {}, series: {} }, 1)
    expect(model.shops).toEqual([])
    expect(model.people).toEqual([])
    expect(model.houses).toHaveLength(100)
    expect(model.hall.banner).toBeNull()
    expect(model.traffic).toEqual({ cars: 0, walkers: 4 })
  })
})
