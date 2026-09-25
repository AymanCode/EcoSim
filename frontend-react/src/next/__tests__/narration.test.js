import { describe, expect, test } from 'vitest'
import {
  weekLabel, leadSentence, verdict, eventSentence, eventGroupSentence, householdStateSentence, experimentQuestion, policyMarkerLabel,
  townWideSentence,
} from '../narration.js'
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
    [ev('regime', { text: 'eviction', householdId: 13 }), 'H13 had to move after falling behind on rent.'],
    [ev('regime', { text: 'shortage_regime_enter', sector: 'Services' }), 'The town started running short of services.'],
  ])('%#: %j', (event, sentence) => {
    expect(eventSentence(event, names)).toBe(sentence)
  })

  test('says a household lost its home only when told it has no home now', () => {
    const eviction = ev('regime', { text: 'eviction', householdId: 13 })
    expect(eventSentence(eviction, { ...names, lostHome: true })).toBe('H13 lost their home.')
    expect(eventSentence(eviction, { ...names, lostHome: false })).toBe('H13 had to move after falling behind on rent.')
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

describe('eventGroupSentence', () => {
  const regime = (code, extra = {}) => ({ id: `${code}:${extra.firmId ?? extra.sector ?? 0}`, tick: 8, type: 'regime', text: code, ...extra })

  test('one event reads like eventSentence', () => {
    const event = regime('failed_hiring', { firmId: 1, firmName: 'FoodCo1' })
    expect(eventGroupSentence([event])).toBe(eventSentence(event))
  })

  test('repeats become one counted sentence', () => {
    const events = [1, 2, 3].map(firmId => regime('failed_hiring', { firmId, firmName: `FoodCo${firmId}` }))
    expect(eventGroupSentence(events)).toBe("3 businesses couldn't fill their open jobs.")
    const hires = [4, 5].map(householdId => ({ id: `h${householdId}`, tick: 1, type: 'hired', householdId, firmId: 1, firmName: 'BaselineFood', text: null }))
    expect(eventGroupSentence(hires)).toBe('2 of the families we follow found work.')
    const layoffs = hires.map(event => ({ ...event, type: 'laid_off' }))
    expect(eventGroupSentence(layoffs)).toBe('2 of the families we follow lost their jobs.')
    const evictions = [7, 8, 9].map(householdId => regime('eviction', { householdId }))
    expect(eventGroupSentence(evictions)).toBe('3 of the families we follow had to move after falling behind on rent.')
    const opened = [1, 2, 3, 4].map(firmId => ({ id: `o${firmId}`, tick: 11, type: 'firm_opened', firmId, firmName: `FoodCo${firmId}`, text: null }))
    expect(eventGroupSentence(opened)).toBe('4 new businesses opened.')
  })

  test('counts each business once', () => {
    const events = [regime('failed_hiring', { firmId: 1, firmName: 'FoodCo1' }), regime('failed_hiring', { firmId: 1, firmName: 'FoodCo1' })]
    expect(eventGroupSentence(events)).toBe(eventSentence(events[0]))
  })

  test('shortages name every good', () => {
    const events = [regime('shortage_regime_enter', { sector: 'Food' }), regime('shortage_regime_enter', { sector: 'Housing' })]
    expect(eventGroupSentence(events)).toBe('The town started running short of food and housing.')
  })

  test('an unknown code gets a count', () => {
    expect(eventGroupSentence([regime('odd_thing'), regime('odd_thing')])).toBe('Odd thing, 2 times.')
  })
})

describe('experimentQuestion', () => {
  test('asks about the second town\'s policy', () => {
    expect(experimentQuestion([fixtureArm(TOWN_A), townB({ policy: { minimum_wage_policy: 'high' } })]))
      .toBe('What happens with a higher minimum wage?')
  })

  test('two towns on the same rules, and one town', () => {
    expect(experimentQuestion([fixtureArm(TOWN_A), townB()])).toBe('What happens when two towns keep the same rules?')
    expect(experimentQuestion([fixtureArm(TOWN_A)])).toBe('What happens in Town A?')
  })
})

describe('policyMarkerLabel', () => {
  test('names the town and the new rule in two short lines', () => {
    expect(policyMarkerLabel(fixtureArm(TOWN_B), { tick: 7, policy: 'benefit_level', value: 'high' }))
      .toEqual(['Town B switched to', 'more help for people out of work'])
  })
})

describe('townWideSentence', () => {
  test('one line when at least 20 people were hired or laid off across town', () => {
    expect(townWideSentence({ hired: 102, laidOff: 17 })).toBe('Across town, 102 people found work this week.')
    expect(townWideSentence({ hired: 3, laidOff: 233 })).toBe('Across town, 233 people lost their jobs this week.')
    expect(townWideSentence({ hired: 36, laidOff: 34 })).toBe('Across town, 36 people found work and 34 lost their jobs this week.')
    expect(townWideSentence({ hired: 19, laidOff: 19 })).toBeNull()
    expect(townWideSentence(null)).toBeNull()
  })
})

describe('warm-up weeks', () => {
  test('the lead says the towns are still being set up and start the same', () => {
    expect(leadSentence([fixtureArm(TOWN_A), townB({ out: 5 })], 5))
      .toBe('Year 1, week 5. Both towns are still being set up and start the same; the real economy starts in week 11.')
    expect(leadSentence([fixtureArm(TOWN_A)], 10))
      .toBe('Year 1, week 10. Town A is still being set up; the real economy starts in week 11.')
  })

  test('the verdict waits for the real economy', () => {
    expect(verdict([fixtureArm(TOWN_A), townB({ out: 5, policy: { minimum_wage_policy: 'high' } })], 5))
      .toBe('Both towns are still being set up and start the same. From week 11 you can see what a higher minimum wage does.')
    expect(verdict([fixtureArm(TOWN_A), townB()], 10))
      .toBe('Both towns are still being set up and start the same. From week 11 you can see how they compare.')
    expect(verdict([fixtureArm(TOWN_A)], 3)).toBe('Town A is still being set up. Its economy starts in week 11.')
  })
})

describe('leadSentence compares what it shows', () => {
  function flat(meta, out, pay) {
    const arm = fixtureArm(meta)
    arm.series[OUT] = arm.series[OUT].map(() => out)
    arm.series[PAY] = arm.series[PAY].map(() => pay)
    return arm
  }

  test('values that round to the same figure read "about the same"', () => {
    expect(leadSentence([flat(TOWN_A, 41.6, 36.2), flat(TOWN_B, 42.4, 36.4)], 20))
      .toBe('Town B has about the same number of people out of work as Town A (42 in 100 vs 42 in 100) and pays about the same ($36 vs $36).')
  })

  test('values that round apart are compared as shown', () => {
    expect(leadSentence([flat(TOWN_A, 42.4, 36.4), flat(TOWN_B, 42.6, 36.6)], 20))
      .toBe('Town B has more people out of work than Town A (43 in 100 vs 42 in 100) but pays more ($37 vs $36).')
  })
})

describe('verdict over the last three months', () => {
  test('averages the last 13 weeks after warm-up', () => {
    const a = fixtureArm(TOWN_A)
    const b = townB({ policy: { minimum_wage_policy: 'high' } })
    // Better than Town A every week of the window but the last.
    b.series[OUT] = a.series[OUT].map((v, i) => (a.ticks[i] === 24 ? v + 5 : v - 5))
    const text = verdict([a, b], 24)
    expect(text.startsWith('Over the last three months, Town B has fewer people out of work than Town A')).toBe(true)
    expect(verdict([a, b], 15).startsWith('So far, Town B has fewer people out of work')).toBe(true)
  })

  test('names food prices plainly', () => {
    const b = townB()
    b.series.priceFood = b.series.priceFood.map(v => v * 1.2)
    const text = verdict([fixtureArm(TOWN_A), b], 24)
    expect(text).toContain('higher food prices')
    expect(text).not.toContain('dearer')
  })

  test('homes lost count once the gap is 1 in 100 households', () => {
    const withHomes = (arm, extra) => {
      arm.series.householdsTotal = arm.series.householdsTotal.map(() => 500)
      arm.series.homelessHouseholds = arm.series.homelessHouseholds.map(() => 10 + extra)
      return arm
    }
    expect(verdict([withHomes(fixtureArm(TOWN_A), 0), withHomes(townB(), 2)], 24)).not.toContain('without a home')
    expect(verdict([withHomes(fixtureArm(TOWN_A), 0), withHomes(townB(), 6)], 24)).toContain('more households without a home')
  })

  test('one town never prints "not measured people"', () => {
    const arm = fixtureArm()
    arm.series[OUT] = arm.series[OUT].map(() => null)
    const text = verdict([arm], 20)
    expect(text).not.toContain('not measured people')
    expect(text).toContain('the number of people out of work is not measured yet')
    expect(leadSentence([arm], 20)).toBe('Year 1, week 20. The number of people out of work is not measured yet and typical weekly pay is $41.')
  })
})
