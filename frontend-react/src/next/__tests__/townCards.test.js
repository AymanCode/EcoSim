import { beforeAll, describe, expect, test } from 'vitest'
import { householdName } from '../names.js'
import { placeCard } from '../town/cards.js'
import { WEEKS, townAt } from '../town/model.js'
import { demoArms } from './fixture.js'
import { firm, liveArm, subject } from './townFixture.js'

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
  people: [],
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

  test('the hall with savings and no queue, and the bank when lending is fine', () => {
    const hall = placeCard(sample, { kind: 'hall' })
    expect(hall.rows).toEqual([['Taxes in this week', '$3k'], ['Help paid to families this week', '$0'], ['Saved', '$5.2k']])
    expect(hall.note).toBeNull()
    expect(hall.tag).toEqual({ text: 'Has savings', tone: 'good' })
    expect(placeCard(sample, { kind: 'bank' }).tag).toEqual({ text: 'Lending', tone: 'good' })
  })

  test('the queue is described, never counted', () => {
    for (const queue of [1, 2, 9]) {
      const { note } = placeCard({ ...sample, hall: { ...sample.hall, queue } }, { kind: 'hall' })
      expect(note).toBe('A queue of families is waiting for help.')
    }
  })

  test('no model or no target gives no card', () => {
    expect(placeCard(null, { kind: 'hall' })).toBeNull()
    expect(placeCard(sample, null)).toBeNull()
    expect(placeCard(sample, { kind: 'person', index: 9 })).toBeNull()
  })
})

describe('placeCard for figures the town did not report', () => {
  const unmeasured = {
    ...sample,
    hall: { cash: null, income: null, support: null, queue: 0 },
    bank: { loans: null, bad: null, badNow: false },
  }

  test('the hall says not measured, not $0, and gives no good or bad news', () => {
    const hall = placeCard(unmeasured, { kind: 'hall' })
    expect(hall.rows).toEqual([['Taxes in this week', 'not measured'], ['Help paid to families this week', 'not measured'], ['Saved', 'not measured']])
    expect(hall.tag).toEqual({ text: 'Not measured', tone: 'quiet' })
  })

  test('the bank says not measured for both rows and gives a quiet tag', () => {
    const bank = placeCard(unmeasured, { kind: 'bank' })
    expect(bank.rows).toEqual([['Loans out', 'not measured'], ['Gone bad this week', 'not measured']])
    expect(bank.tag).toEqual({ text: 'Not measured', tone: 'quiet' })
  })

  test('a bank with loans but no bad-loan figure is lending; bad loans still show', () => {
    const lending = placeCard({ ...unmeasured, bank: { loans: 40, bad: null, badNow: false } }, { kind: 'bank' })
    expect(lending.rows[0]).toEqual(['Loans out', '40'])
    expect(lending.tag.text).toBe('Lending')
    expect(placeCard({ ...unmeasured, bank: { loans: null, bad: 8000, badNow: true } }, { kind: 'bank' }).tag.text).toBe('Loans going bad')
  })

  test('a hall in debt still says so', () => {
    const hall = placeCard({ ...unmeasured, hall: { ...unmeasured.hall, cash: -4000 } }, { kind: 'hall' })
    expect(hall.rows[2]).toEqual(['Owes', '$4k'])
    expect(hall.tag).toEqual({ text: 'In debt', tone: 'bad' })
  })
})

describe('placeCard for a person says what the Households panel says', () => {
  const card = (extra, firms = [firm(1)]) => {
    const arm = liveArm([[20, { firms, subjects: [subject(7, extra)] }]])
    return placeCard(townAt(arm, 20), { kind: 'person', index: 0 })
  }

  test('someone who just lost their job and someone out for weeks', () => {
    const just = card({ unemploymentDuration: 0 })
    expect(just.note).toBe('Just started looking for work.')
    expect(just.tag).toEqual({ text: 'Looking for work', tone: 'warn' })
    expect(card({ unemploymentDuration: 41 }).note).toBe('Has been looking for work for 41 weeks.')
    expect(card({ unemploymentDuration: 1 }).note).toBe('Has been looking for work for 1 week.')
  })

  test('someone who cannot work is not looking for work', () => {
    const idle = card({ canWork: false })
    expect(idle.note).toBe('Not working right now.')
    expect(idle.tag).toEqual({ text: 'Not working', tone: 'quiet' })
  })

  test('someone who lost their home, even if they have a job', () => {
    const home = card({ isEmployed: true, housingSecurity: false })
    expect(home.note).toBe('Has no home right now.')
    expect(home.tag).toEqual({ text: 'Lost their home', tone: 'bad' })
  })

  test('someone working names the shop, or no shop at all; never a dangling "Works at"', () => {
    const named = card({ isEmployed: true, employer: 'Shop 1' })
    expect(named.note).toMatch(/^Steady work at .+\.$/)
    expect(named.tag).toEqual({ text: 'Working', tone: 'good' })
    const unnamed = card({ isEmployed: true, employer: null })
    expect(unnamed.note).toBe('In steady work.')
    expect(unnamed.note).not.toMatch(/Works at/i)
  })

  test('rent owed is a row only when there is some; no age and unknown figures read plainly', () => {
    const behind = card({ isEmployed: true, rentArrears: 140, age: null })
    expect(behind.title).toBe(householdName(7))
    expect(behind.rows.at(-1)).toEqual(['Rent owed', '$140'])
    expect(behind.note).toBe('Working, but $140 behind on rent.')
    const vague = card({ cash: null, health: null, happiness: 0.5 })
    expect(vague.rows).toEqual([['Savings', 'not measured'], ['Health', 'not measured'], ['Happiness', 'so-so']])
  })
})
