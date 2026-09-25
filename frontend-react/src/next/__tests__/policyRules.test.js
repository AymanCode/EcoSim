import { describe, expect, test } from 'vitest'
import { COPY, DEFAULT_POLICY } from '../catalog.js'
import { policyProblems } from '../policyRules.js'

// A port of backend/policy_vectors.py policy_group_errors: same checks, same order.
describe('policyProblems', () => {
  test('the usual rules break nothing', () => {
    expect(policyProblems(DEFAULT_POLICY)).toEqual({})
    expect(policyProblems({})).toEqual({})
    expect(policyProblems(null)).toEqual({})
  })

  test('a subsidy level above 0 needs a target', () => {
    expect(policyProblems({ ...DEFAULT_POLICY, sector_subsidy_level: 10 }))
      .toEqual({ sector_subsidy: COPY.levers.rules.sector_subsidy })
    expect(policyProblems({ ...DEFAULT_POLICY, sector_subsidy_level: 10, sector_subsidy_target: 'food' })).toEqual({})
    // A target with no level is allowed, as in the backend.
    expect(policyProblems({ ...DEFAULT_POLICY, sector_subsidy_target: 'food' })).toEqual({})
  })

  test('bailouts that are off lend nothing: no sector, no budget', () => {
    const rule = { bailout: COPY.levers.rules.bailout_off }
    expect(policyProblems({ ...DEFAULT_POLICY, bailout_target: 'food' })).toEqual(rule)
    expect(policyProblems({ ...DEFAULT_POLICY, bailout_budget: 5000 })).toEqual(rule)
    expect(policyProblems({ ...DEFAULT_POLICY, bailout_target: 'food', bailout_budget: 5000 })).toEqual(rule)
    expect(policyProblems({ bailout_target: 'food' })).toEqual(rule)
  })

  test('bailouts for one sector need the sector first, then a budget', () => {
    expect(policyProblems({ ...DEFAULT_POLICY, bailout_policy: 'sector' }))
      .toEqual({ bailout: COPY.levers.rules.bailout_target })
    expect(policyProblems({ ...DEFAULT_POLICY, bailout_policy: 'sector', bailout_budget: 5000 }))
      .toEqual({ bailout: COPY.levers.rules.bailout_target })
    expect(policyProblems({ ...DEFAULT_POLICY, bailout_policy: 'sector', bailout_target: 'food' }))
      .toEqual({ bailout: COPY.levers.rules.bailout_budget })
    expect(policyProblems({ ...DEFAULT_POLICY, bailout_policy: 'sector', bailout_target: 'food', bailout_budget: 5000 })).toEqual({})
  })

  test('bailouts for any business take no sector, then need a budget', () => {
    expect(policyProblems({ ...DEFAULT_POLICY, bailout_policy: 'all', bailout_target: 'food', bailout_budget: 5000 }))
      .toEqual({ bailout: COPY.levers.rules.bailout_all })
    // The sector rule comes before the budget rule, as in the backend.
    expect(policyProblems({ ...DEFAULT_POLICY, bailout_policy: 'all', bailout_target: 'food' }))
      .toEqual({ bailout: COPY.levers.rules.bailout_all })
    expect(policyProblems({ ...DEFAULT_POLICY, bailout_policy: 'all' }))
      .toEqual({ bailout: COPY.levers.rules.bailout_budget })
    expect(policyProblems({ ...DEFAULT_POLICY, bailout_policy: 'all', bailout_budget: 5000 })).toEqual({})
    expect(policyProblems({ bailout_policy: 'all', bailout_budget: 5000 })).toEqual({})
  })

  test('reports both groups, subsidy first', () => {
    const problems = policyProblems({ ...DEFAULT_POLICY, sector_subsidy_level: 25, bailout_policy: 'all' })
    expect(Object.keys(problems)).toEqual(['sector_subsidy', 'bailout'])
  })

  test('reads numbers sent as text the way the backend coerces them', () => {
    expect(policyProblems({ ...DEFAULT_POLICY, sector_subsidy_level: '0' })).toEqual({})
    expect(policyProblems({ ...DEFAULT_POLICY, sector_subsidy_level: '25' })).toHaveProperty('sector_subsidy')
    expect(policyProblems({ ...DEFAULT_POLICY, bailout_policy: 'sector', bailout_target: 'food', bailout_budget: '0' }))
      .toEqual({ bailout: COPY.levers.rules.bailout_budget })
    expect(policyProblems({ ...DEFAULT_POLICY, bailout_budget: '0' })).toEqual({})
    expect(policyProblems({ ...DEFAULT_POLICY, bailout_budget: '5000' })).toEqual({ bailout: COPY.levers.rules.bailout_off })
  })

  test('every rule reads as newcomer copy', () => {
    expect(Object.keys(COPY.levers.rules).sort())
      .toEqual(['bailout_all', 'bailout_budget', 'bailout_off', 'bailout_target', 'sector_subsidy'])
    for (const text of Object.values(COPY.levers.rules)) {
      expect(text.length).toBeGreaterThan(20)
      expect(text).not.toMatch(/sector_subsidy|bailout_|'none'/)
    }
  })
})
