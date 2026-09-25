import { describe, expect, test } from 'vitest'
import {
  COPY, DEFAULT_POLICY, LEVER_GROUPS, LEVERS, METRICS, QUESTIONS, capitalise, describePolicy, formatMetric, formatMoneyShort, leverValuePhrase,
} from '../catalog.js'
import { policyProblems } from '../policyRules.js'

const REQUIRED_METRICS = [
  'peopleOutOfWorkPer100', 'typicalWeeklyPay', 'priceFood', 'foodSpendPerHousehold', 'gini', 'townHallCash',
  'homelessHouseholds', 'firmsOpen', 'firmsStruggling', 'careDenials', 'bankDefaultsTotal',
]

// backend/policy_schema.py PROMPT_POLICY_LEVERS, with its value sets.
const SCHEMA = {
  wage_tax_rate: 'rate', profit_tax_rate: 'rate', investment_tax_rate: 'rate',
  benefit_level: ['low', 'neutral', 'high', 'crisis'],
  public_works: ['off', 'on'],
  minimum_wage_policy: ['low', 'neutral', 'high'],
  sector_subsidy_target: ['none', 'food', 'housing', 'services', 'healthcare'],
  sector_subsidy_level: [0, 10, 25, 50],
  price_stabilization_target: ['none', 'food', 'services', 'healthcare'],
  price_stabilization_level: ['off', 'monitor', 'soft', 'strict'],
  rent_stabilization_level: ['off', 'monitor', 'soft', 'strict'],
  infrastructure_spending: ['none', 'low', 'medium', 'high'],
  technology_spending: ['none', 'low', 'medium', 'high'],
  social_spending: ['none', 'low', 'medium', 'high'],
  bailout_policy: ['off', 'sector', 'all'],
  bailout_target: ['none', 'food', 'housing', 'services', 'healthcare'],
  bailout_budget: [0, 5000, 10000, 25000, 50000],
}

describe('METRICS', () => {
  test('describes every curated figure the Run screen shows', () => {
    for (const key of REQUIRED_METRICS) {
      const m = METRICS[key]
      expect(m, key).toBeTruthy()
      expect(m.name.length).toBeGreaterThan(2)
      expect(m.meaning.length).toBeGreaterThan(10)
      expect(['per100', 'money', 'price', 'ratio', 'count']).toContain(m.format)
      expect(['lower', 'higher', null]).toContain(m.better)
    }
    expect(METRICS.peopleOutOfWorkPer100.name).toBe('People out of work')
    expect(METRICS.gini.name).toBe('Gap between rich and poor')
  })
})

describe('formatMetric', () => {
  test('formats each unit', () => {
    expect(formatMetric('peopleOutOfWorkPer100', 9.2)).toBe('9 in 100')
    expect(formatMetric('typicalWeeklyPay', 2144.4)).toBe('$2,144')
    expect(formatMetric('townHallCash', -1200.2)).toBe('-$1,200')
    expect(formatMetric('priceFood', 4.7149)).toBe('$4.71')
    expect(formatMetric('gini', 0.4128)).toBe('0.41')
    expect(formatMetric('firmsOpen', 12)).toBe('12')
  })

  test('says "not measured" for missing values', () => {
    expect(formatMetric('gini', null)).toBe('not measured')
    expect(formatMetric('gini', undefined)).toBe('not measured')
    expect(formatMetric('gini', Number.NaN)).toBe('not measured')
  })

  test('short money keeps bars readable', () => {
    expect(formatMoneyShort(28035.2)).toBe('$28k')
    expect(formatMoneyShort(6855.4)).toBe('$6.9k')
    expect(formatMoneyShort(850.4)).toBe('$850')
    expect(formatMoneyShort(-8200)).toBe('-$8.2k')
    expect(formatMoneyShort(1_250_000)).toBe('$1.3m')
  })
})

describe('LEVERS', () => {
  test('names all 17 levers of the policy schema with a phrase for every value', () => {
    expect(Object.keys(LEVERS).sort()).toEqual(Object.keys(SCHEMA).sort())
    for (const [lever, values] of Object.entries(SCHEMA)) {
      expect(LEVERS[lever].name.length, lever).toBeGreaterThan(2)
      if (values === 'rate') continue
      for (const value of values) expect(LEVERS[lever].values[String(value)], `${lever}=${value}`).toBeTruthy()
    }
  })

  test('phrases a value, including tax rates', () => {
    expect(leverValuePhrase('benefit_level', 'high')).toBe('high')
    expect(leverValuePhrase('wage_tax_rate', 0.2)).toBe('20%')
    expect(leverValuePhrase('wage_tax_rate', '0.225')).toBe('22.5%')
  })
})

describe('describePolicy', () => {
  test('describes an empty policy as no changes', () => {
    expect(describePolicy({})).toBe('no changes')
    expect(describePolicy(null)).toBe('no changes')
  })

  test('describes one lever', () => {
    expect(describePolicy({ minimum_wage_policy: 'high' })).toBe('a higher minimum wage')
    expect(describePolicy({ wage_tax_rate: 0.3 })).toBe('a 30% tax on wages')
  })

  test('joins several with "and"', () => {
    expect(describePolicy({ minimum_wage_policy: 'high', benefit_level: 'high' }))
      .toBe('more help for people out of work and a higher minimum wage')
    expect(describePolicy({ wage_tax_rate: 0.3, profit_tax_rate: 0.35, public_works: 'on' }))
      .toBe('a 30% tax on wages, a 35% tax on profits and public works jobs')
  })

  test('reads a grouped lever as one phrase', () => {
    expect(describePolicy({ sector_subsidy_target: 'food', sector_subsidy_level: 25 })).toBe('a 25% subsidy for food firms')
    expect(describePolicy({ price_stabilization_target: 'food', price_stabilization_level: 'strict' })).toBe('strict price controls on food')
    expect(describePolicy({ bailout_policy: 'sector', bailout_target: 'food', bailout_budget: 25000 }))
      .toBe('bailouts for food firms up to $25,000')
  })
})

describe('lever groups, help and question cards', () => {
  test('every lever appears in exactly one group, and every group has a title and a blurb', () => {
    const listed = LEVER_GROUPS.flatMap(group => group.levers)
    expect(listed).toHaveLength(17)
    expect([...listed].sort()).toEqual(Object.keys(LEVERS).sort())
    expect(LEVER_GROUPS.map(group => group.id)).toEqual(['taxes', 'people', 'spending', 'business', 'prices'])
    for (const { id } of LEVER_GROUPS) {
      expect(COPY.levers.groups[id].title.length, id).toBeGreaterThan(2)
      expect(COPY.levers.groups[id].blurb.length, id).toBeGreaterThan(10)
    }
  })

  test('every lever has a one-sentence help line', () => {
    for (const [lever, spec] of Object.entries(LEVERS)) {
      expect(typeof spec.help, lever).toBe('string')
      expect(spec.help.length, lever).toBeGreaterThan(20)
      expect(spec.help, lever).toMatch(/^[A-Z].*\.$/)
      expect(spec.help.match(/\. /g), lever).toBeNull()
    }
  })

  test('two launch questions, each a control town and one changed town whose rules pass the group rules', () => {
    expect(QUESTIONS.map(question => question.id)).toEqual(['minimum-wage', 'benefits'])
    expect(QUESTIONS[0]).toEqual({
      id: 'minimum-wage',
      title: 'What happens if we raise the minimum wage?',
      blurb: 'Higher pay for the lowest earners, higher costs for businesses. Which wins?',
      towns: [{}, { minimum_wage_policy: 'high' }],
    })
    expect(QUESTIONS[1].towns).toEqual([{}, { benefit_level: 'high' }])
    for (const question of QUESTIONS) {
      for (const levers of question.towns) expect(policyProblems({ ...DEFAULT_POLICY, ...levers })).toEqual({})
    }
  })

  test('spending and public works help says the town hall pays only when it has the money', () => {
    // backend/agents.py: roads and technology spend the whole budget or nothing,
    // social spending spends up to the cash there is; economy.py: public works
    // opens only on an affordable start-up budget.
    expect(LEVERS.infrastructure_spending.help).toBe('Sets how much the town hall spends on roads and buildings in each week it has the cash to cover it.')
    expect(LEVERS.technology_spending.help).toBe('Sets how much the town hall spends on new technology in each week it has the cash to cover it.')
    expect(LEVERS.social_spending.help).toBe('Sets how much the town hall spends each week on community programmes, up to the cash it has.')
    expect(LEVERS.public_works.help).toBe('When on, the town hall runs its own business and hires people to work in it, if it can afford to start one.')
    expect(QUESTIONS.map(question => question.blurb).join(' ')).not.toMatch(/\bfirms\b/)
  })

  test('capitalise', () => {
    expect(capitalise('a higher minimum wage')).toBe('A higher minimum wage')
    expect(capitalise('')).toBe('')
  })
})
