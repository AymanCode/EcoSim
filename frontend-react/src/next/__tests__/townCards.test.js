import { beforeAll, describe, expect, test } from 'vitest'
import { placeCard } from '../town/cards.js'
import { WEEKS, townAt } from '../town/model.js'
import { demoArms } from './fixture.js'

let model
beforeAll(() => { model = townAt(demoArms()[0], 70) })

describe('placeCard', () => {
  test('a dark house says how long it has been dark', () => {
    const index = model.houses.findIndex(house => house.state === 'look')
    const card = placeCard(model, { kind: 'house', index }, 500)
    expect(card.title).toBe('Looking for work')
    expect(card.note).toMatch(/lost their job/)
    expect(card.tag.tone).toBe('warn')
  })

  test('the richest shop says so', () => {
    const shop = model.shops.find(s => s.richest)
    const card = placeCard(model, { kind: 'shop', id: shop.id })
    expect(card.title).toBe(shop.name)
    expect(card.note).toMatch(/richest/)
    expect(card.rows.map(([label]) => label)).toEqual(['Staff', 'Cash in the bank'])
  })

  test('a closed shop names its closing week', () => {
    const shop = model.shops.find(s => s.state === 'closed')
    const card = placeCard(model, { kind: 'shop', id: shop.id })
    expect(card.rows[0][0]).toBe('Closed')
    expect(card.rows[0][1]).toMatch(/Year \d, week \d+/)
  })

  test('the town hall, the bank and a person', () => {
    expect(placeCard(model, { kind: 'hall' }).tag.text).toBe('In debt')
    expect(placeCard(model, { kind: 'bank' }).tag.text).toBe('Loans going bad')
    const person = placeCard(model, { kind: 'person', index: 0 })
    expect(person.sub).toBe('someone you follow')
    expect(person.rows.map(([label]) => label)).toEqual(expect.arrayContaining(['Savings', 'Health', 'Happiness']))
  })

  test('an unknown target gives no card', () => {
    expect(placeCard(model, { kind: 'shop', id: -1 })).toBeNull()
    expect(placeCard(model, { kind: 'nothing' })).toBeNull()
  })
})

// A hand-made model: the card words at their edges, with no demo data in the way.
const sample = {
  houses: [
    { state: 'work', weeks: 1 }, { state: 'look', weeks: 1 }, { state: 'look', weeks: WEEKS.longOut - 1 },
    { state: 'look', weeks: WEEKS.longOut }, { state: 'home', weeks: 3 },
  ],
  shops: [
    { id: 1, name: 'Oak Bakery', sector: 'Food', staff: 12, cash: 8400, state: 'growing', coop: true, fresh: false, isNew: false, richest: false, hired: 2, laidOff: 1, closedTick: null, closedFor: null },
    { id: 2, name: 'New Café', sector: 'Services', staff: 3, cash: 900, state: 'steady', coop: false, fresh: true, isNew: false, richest: false, hired: 0, laidOff: 0, closedTick: null, closedFor: null },
    { id: 3, name: 'Just Open', sector: 'Services', staff: 4, cash: 900, state: 'struggling', coop: false, fresh: false, isNew: true, richest: false, hired: 0, laidOff: 0, closedTick: null, closedFor: null },
    { id: 4, name: 'Shut Early', sector: 'Food', staff: 5, cash: null, state: 'closed', coop: false, fresh: false, isNew: false, richest: false, hired: 0, laidOff: 0, closedTick: 60, closedFor: WEEKS.lease - 1 },
    { id: 5, name: 'Shut Long', sector: 'Food', staff: 5, cash: null, state: 'closed', coop: false, fresh: false, isNew: false, richest: false, hired: 0, laidOff: 0, closedTick: 60, closedFor: WEEKS.lease },
  ],
  hall: { cash: 5200, income: 3000, support: 0, queue: 0 },
  bank: { loans: 120, bad: 0, badNow: false },
  people: [
    { name: 'Ana', age: null, working: false, cash: 20, health: null, happiness: 0.5, weeksOut: 1, rentOwed: 140, employer: null },
    { name: 'Raj', age: 40, working: true, cash: 900, health: 0.7, happiness: 0.2, weeksOut: 0, rentOwed: 0, employer: 'Oak Bakery' },
  ],
}

describe('placeCard at its edges', () => {
  test('houses: a working home, weeds only from the long-out week, a lost home', () => {
    expect(placeCard(sample, { kind: 'house', index: 0 }, 500).note).toBe('Lights on: the people here have jobs. Working for 1 week in a row.')
    expect(placeCard(sample, { kind: 'house', index: 1 }, 500).note).toBe('Lights off: someone here lost their job 1 week ago.')
    expect(placeCard(sample, { kind: 'house', index: 2 }, 500).note).not.toMatch(/weeds/)
    expect(placeCard(sample, { kind: 'house', index: 3 }, 500).note).toMatch(/weeds/)
    const lost = placeCard(sample, { kind: 'house', index: 4 }, 500)
    expect(lost.tag).toEqual({ text: 'lost their home', tone: 'bad' })
    expect(lost.sub).toBe('stands for 5 households')
    expect(placeCard(sample, { kind: 'house', index: 5 }, 500)).toBeNull()
  })

  test('shops: sector and co-op, this week, the three opening states', () => {
    const coop = placeCard(sample, { kind: 'shop', id: 1 })
    expect(coop.sub).toBe('Food · town co-op')
    expect(coop.note).toBe('This week: hired 2, let 1 go.')
    expect(coop.tag).toEqual({ text: 'Growing, hiring', tone: 'good' })
    expect(placeCard(sample, { kind: 'shop', id: 2 }).tag).toEqual({ text: 'Being built', tone: 'info' })
    expect(placeCard(sample, { kind: 'shop', id: 3 }).tag).toEqual({ text: 'Just opened', tone: 'info' })
    expect(placeCard(sample, { kind: 'shop', id: 2 }).note).toBeNull()
  })

  test('a closed shop is up for lease from the same week the drawing says so', () => {
    expect(placeCard(sample, { kind: 'shop', id: 4 }).note).toBe('Boarded up. It ran out of cash.')
    expect(placeCard(sample, { kind: 'shop', id: 5 }).note).toBe('Empty and up for lease.')
  })

  test('hall in the black with no queue, bank lending, a person with rent owed and no age', () => {
    const hall = placeCard(sample, { kind: 'hall' })
    expect(hall.rows[2]).toEqual(['Saved', '$5.2k'])
    expect(hall.note).toBeNull()
    expect(hall.tag).toEqual({ text: 'In the black', tone: 'good' })
    expect(placeCard(sample, { kind: 'bank' }).tag).toEqual({ text: 'Lending', tone: 'good' })
    const ana = placeCard(sample, { kind: 'person', index: 0 })
    expect(ana.title).toBe('Ana')
    expect(ana.rows).toEqual([['Savings', '$20'], ['Health', '–'], ['Happiness', 'so-so'], ['Rent owed', '$140']])
    expect(ana.note).toBe('Out of work for 1 week')
    const raj = placeCard(sample, { kind: 'person', index: 1 })
    expect(raj.title).toBe('Raj, 40')
    expect(raj.note).toBe('Works at Oak Bakery')
    expect(raj.rows.map(([label]) => label)).not.toContain('Rent owed')
  })

  test('no model or no target gives no card', () => {
    expect(placeCard(null, { kind: 'hall' })).toBeNull()
    expect(placeCard(sample, null)).toBeNull()
    expect(placeCard(sample, { kind: 'person', index: 9 })).toBeNull()
  })
})
