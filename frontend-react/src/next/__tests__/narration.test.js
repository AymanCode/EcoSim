import { describe, expect, test } from 'vitest'
import { weekLabel, leadSentence, verdict, eventSentence, householdStateSentence } from '../narration.js'
import { householdName } from '../names.js'
import { fixtureArm, TOWN_A, TOWN_B } from './fixture.js'

const OUT = 'peopleOutOfWorkPer100'
const PAY = 'typicalWeeklyPay'

// Town B built from the same recording with its figures shifted.
function townB({ out = 0, payFactor = 1, policy = {} } = {}) {
  const b = fixtureArm(TOWN_B)
  b.series[OUT] = b.series[OUT].map(v => v + out)
  b.series[PAY] = b.series[PAY].map(v => v * payFactor)
  b.setup = { ...b.setup, initial_policy: policy }
  return b
}

describe('weekLabel', () => {
  test('counts 52-week years from week 1', () => {
    expect(weekLabel(1)).toBe('Year 1, week 1')
    expect(weekLabel(52)).toBe('Year 1, week 52')
    expect(weekLabel(53)).toBe('Year 2, week 1')
    expect(weekLabel(104)).toBe('Year 2, week 52')
  })
})

describe('leadSentence', () => {
  test('one town: the week, people out of work and typical pay', () => {
    expect(leadSentence([fixtureArm()], 11))
      .toBe('Year 1, week 11. 42 in 100 people are out of work and typical weekly pay is $36.')
  })

  test('two towns: compares the second with the first', () => {
    expect(leadSentence([fixtureArm(TOWN_A), townB({ out: -5, payFactor: 1.1 })], 11))
      .toBe('Town B has fewer people out of work than Town A (37 in 100 vs 42 in 100) and pays more ($40 vs $36).')
  })

  test('says "about the same" inside the thresholds', () => {
    expect(leadSentence([fixtureArm(TOWN_A), townB({ out: 0.3, payFactor: 1.005 })], 11))
      .toBe('Town B has about the same number of people out of work as Town A (42 in 100 vs 42 in 100) and pays about the same ($36 vs $36).')
  })

  test('uses "but" when one comparison favours the town and the other does not', () => {
    expect(leadSentence([fixtureArm(TOWN_A), townB({ out: 5, payFactor: 1.1 })], 11))
      .toBe('Town B has more people out of work than Town A (47 in 100 vs 42 in 100) but pays more ($40 vs $36).')
  })

  test('before the first recorded week', () => {
    expect(leadSentence([fixtureArm()], 0)).toMatch(/haven't reported|hasn't reported/)
  })
})

describe('verdict', () => {
  test('two towns: names what differs and asks about the second town\'s policy', () => {
    const text = verdict([fixtureArm(TOWN_A), townB({ out: -5, payFactor: 1.1, policy: { minimum_wage_policy: 'high' } })], 11)
    expect(text.startsWith('So far, Town B has fewer people out of work and higher pay than Town A')).toBe(true)
    expect(text.endsWith('Would you keep a higher minimum wage?')).toBe(true)
  })

  test('two towns with nothing between them still ends with a question', () => {
    const text = verdict([fixtureArm(TOWN_A), townB()], 11)
    expect(text).toContain('about the same')
    expect(text.endsWith('?')).toBe(true)
  })

  test('mentions a cost after "but"', () => {
    const text = verdict([fixtureArm(TOWN_A), townB({ out: 5, payFactor: 1.1, policy: { minimum_wage_policy: 'high' } })], 11)
    expect(text).toContain('higher pay than Town A, but more people out of work')
  })

  test('one town: a summary, not a question', () => {
    const text = verdict([fixtureArm()], 11)
    expect(text.endsWith('?')).toBe(false)
    expect(text).toContain('Town A')
  })
})

describe('eventSentence', () => {
  const names = { householdName: id => `H${id}`, firmName: firm => `F${firm.id}` }
  const ev = (type, extra = {}) => ({ id: `x:${type}`, tick: 3, type, householdId: null, firmId: null, firmName: null, sector: null, value: null, text: null, ...extra })

  test.each([
    [ev('firm_opened', { firmId: 5, firmName: 'FoodCo1' }), 'F5 opened.'],
    [ev('firm_closed', { firmId: 5, firmName: 'FoodCo1' }), 'F5 closed.'],
    [ev('hired', { householdId: 56, firmId: 1, firmName: 'BaselineFood' }), 'H56 started work at F1.'],
    [ev('laid_off', { householdId: 13, firmId: 1, firmName: 'BaselineFood' }), 'H13 lost their job at F1.'],
    [ev('care_denied', { householdId: 25 }), "H25 couldn't afford a doctor."],
    [ev('care_completed', { householdId: 25, firmId: 4 }), 'H25 saw a doctor.'],
    [ev('policy_changed', { text: 'benefit_level=high' }), 'The town hall set help for people out of work to high.'],
    [ev('policy_changed', { text: 'wage_tax_rate=0.2', value: 0.2 }), 'The town hall set the tax on wages to 20%.'],
    [ev('loan_default', { value: 120 }), 'A loan went unpaid.'],
    [ev('shock', { text: 'shock_demand' }), 'Households had an unexpected windfall or bill.'],
    [ev('shock', { text: 'shock_supply' }), 'A supply problem hit some businesses.'],
    [ev('shock', { text: 'shock_health' }), 'An illness went around.'],
    [ev('regime', { text: 'bank_run_started' }), 'Bank run started.'],
    [ev('regime', { text: 'failed_hiring', firmId: 1, firmName: 'BaselineFood' }), "F1 couldn't fill its open jobs."],
    [ev('regime', { text: 'eviction', householdId: 13 }), 'H13 lost their home.'],
    [ev('regime', { text: 'shortage_regime_enter', sector: 'Services' }), 'The town started running short of services.'],
  ])('%#: %j', (event, sentence) => {
    expect(eventSentence(event, names)).toBe(sentence)
  })

  test('uses the friendly names by default', () => {
    const hired = ev('hired', { householdId: 56, firmId: 1, firmName: 'BaselineFood' })
    expect(eventSentence(hired)).toBe(`${householdName(56)} started work at Town Food Co-op.`)
  })

  test('has a fallback for an unknown type', () => {
    expect(eventSentence(ev('mystery'))).toBe('Something changed in the town.')
  })
})

describe('householdStateSentence', () => {
  const base = { housingSecurity: true, isEmployed: true, canWork: true, rentArrears: 0, unemploymentDuration: 0 }

  test('one sentence per situation', () => {
    expect(householdStateSentence(base, { employerName: 'Harbor Grocers' })).toBe('Steady work at Harbor Grocers.')
    expect(householdStateSentence({ ...base, rentArrears: 120.4 })).toBe('Working, but $120 behind on rent.')
    expect(householdStateSentence({ ...base, isEmployed: false, unemploymentDuration: 3 })).toBe('Has been looking for work for 3 weeks.')
    expect(householdStateSentence({ ...base, isEmployed: false, unemploymentDuration: 1 })).toBe('Has been looking for work for 1 week.')
    expect(householdStateSentence({ ...base, isEmployed: false })).toBe('Just started looking for work.')
    expect(householdStateSentence({ ...base, housingSecurity: false })).toBe('Has no home right now.')
    expect(householdStateSentence({ ...base, isEmployed: false, canWork: false })).toBe('Not working right now.')
  })
})
