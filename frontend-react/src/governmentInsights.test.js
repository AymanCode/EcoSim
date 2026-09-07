import { describe, expect, test } from 'vitest'

import {
  LEVER_DEFAULTS,
  LEVER_GROUPS,
  changeNarrative,
  classifyActor,
  countActiveInterventions,
  describeEvidenceAudit,
  fiscalModeLabel,
  formatLeverValue,
  goalHeadline,
  impactSince,
  isLeverActive,
  latestChangeByLever,
  leverLabel,
  parsePreviousValue,
  splitPolicyChanges,
} from './governmentInsights.js'

const AI_REASON = 'LLM government set benefit_level from neutral to high. Food firms are short on stock.'
const AUTO_REASON = 'Automatic government adjustment changed wage_tax_rate from 0.150000 to 0.183000'
const USER_REASON = 'User updated public_works to on'

describe('lever catalogue', () => {
  test('every grouped lever (including pairs) has a default', () => {
    const keys = LEVER_GROUPS.flatMap(group => group.levers.flatMap(lever => [lever.key, lever.pair?.key].filter(Boolean)))
    expect(keys).toHaveLength(17)
    keys.forEach(key => expect(LEVER_DEFAULTS).toHaveProperty(key))
  })

  test('labels resolve for grouped, paired, and unknown keys', () => {
    expect(leverLabel('wage_tax_rate')).toBe('Wage tax')
    expect(leverLabel('sector_subsidy_level')).toBe('Sector subsidy level')
    expect(leverLabel('universal_basic_income')).toBe('Universal basic income')
  })

  test('formats lever values for display', () => {
    expect(formatLeverValue('wage_tax_rate', 0.18)).toBe('18.0%')
    expect(formatLeverValue('sector_subsidy_level', 25)).toBe('25%')
    expect(formatLeverValue('bailout_budget', 50000)).toBe('$50K')
    expect(formatLeverValue('bailout_budget', 0)).toBe('$0')
    expect(formatLeverValue('public_works', 'on')).toBe('On')
    expect(formatLeverValue('public_works', false)).toBe('Off')
    expect(formatLeverValue('benefit_level', 'neutral')).toBe('Neutral')
    expect(formatLeverValue('bailout_target', 'none')).toBe('None')
  })
})

describe('classifyActor', () => {
  test('recognises the three server reason prefixes', () => {
    expect(classifyActor(AI_REASON)).toBe('ai')
    expect(classifyActor(USER_REASON)).toBe('you')
    expect(classifyActor(AUTO_REASON)).toBe('auto')
  })

  test('falls back to unknown', () => {
    expect(classifyActor('something else')).toBe('unknown')
    expect(classifyActor(undefined)).toBe('unknown')
  })
})

describe('parsePreviousValue and changeNarrative', () => {
  test('extracts the before value from LLM and automatic reasons', () => {
    expect(parsePreviousValue(AI_REASON)).toBe('neutral')
    expect(parsePreviousValue(AUTO_REASON)).toBe('0.150000')
  })

  test('returns null when the reason carries no before value', () => {
    expect(parsePreviousValue(USER_REASON)).toBeNull()
    expect(parsePreviousValue('')).toBeNull()
  })

  test('strips the mechanical sentence from an LLM reason', () => {
    expect(changeNarrative(AI_REASON)).toBe('Food firms are short on stock.')
    expect(changeNarrative('LLM government set benefit_level from neutral to high.')).toBe('')
    expect(changeNarrative(USER_REASON)).toBe('')
  })
})

describe('isLeverActive', () => {
  test('numbers compare with tolerance', () => {
    expect(isLeverActive('wage_tax_rate', 0.15)).toBe(false)
    expect(isLeverActive('wage_tax_rate', 0.1500000001)).toBe(false)
    expect(isLeverActive('wage_tax_rate', 0.18)).toBe(true)
    expect(isLeverActive('bailout_budget', '0')).toBe(false)
  })

  test('strings compare case-insensitively', () => {
    expect(isLeverActive('benefit_level', 'Neutral')).toBe(false)
    expect(isLeverActive('benefit_level', 'high')).toBe(true)
  })

  test('public works accepts on/off and booleans', () => {
    expect(isLeverActive('public_works', 'off')).toBe(false)
    expect(isLeverActive('public_works', false)).toBe(false)
    expect(isLeverActive('public_works', 'on')).toBe(true)
    expect(isLeverActive('public_works', true)).toBe(true)
  })

  test('unknown levers and missing values are never active', () => {
    expect(isLeverActive('made_up', 3)).toBe(false)
    expect(isLeverActive('wage_tax_rate', undefined)).toBe(false)
  })
})

describe('countActiveInterventions', () => {
  test('defaults count zero, modified snapshot counts each changed lever', () => {
    expect(countActiveInterventions({ ...LEVER_DEFAULTS })).toBe(0)
    expect(countActiveInterventions({})).toBe(0)
    expect(countActiveInterventions({ ...LEVER_DEFAULTS, wage_tax_rate: 0.18, public_works: 'on', sector_subsidy_target: 'food', sector_subsidy_level: 25 })).toBe(4)
  })
})

describe('policy change helpers', () => {
  const changes = [
    { tick: 1400, policy: 'wage_tax_rate', value: 0.2, reason: 'User updated wage_tax_rate to 0.2' },
    { tick: 1249, policy: 'benefit_level', value: 'high', reason: AI_REASON },
    { tick: 1100, policy: 'public_works', value: 'on', reason: USER_REASON },
    { tick: 900, policy: 'wage_tax_rate', value: 0.18, reason: 'User updated wage_tax_rate to 0.18' },
    { tick: 850, policy: 'wage_tax_rate', value: 0.16, reason: 'User updated wage_tax_rate to 0.16' },
  ]

  test('latestChangeByLever keeps the newest entry per lever and drops future ticks', () => {
    const latest = latestChangeByLever(changes, 1275)
    expect(latest.get('wage_tax_rate')).toMatchObject({ tick: 900, actor: 'you', value: 0.18, previous: null })
    expect(latest.get('benefit_level')).toMatchObject({ tick: 1249, actor: 'ai', previous: 'neutral' })
    expect(latest.get('public_works')).toMatchObject({ tick: 1100, actor: 'you' })
    expect(latest.size).toBe(3)
  })

  test('splitPolicyChanges separates current-run entries from a previous run', () => {
    const { current, previous } = splitPolicyChanges(changes, 1275)
    expect(current.map(c => c.tick)).toEqual([1249, 1100, 900, 850])
    expect(previous.map(c => c.tick)).toEqual([1400])
    expect(splitPolicyChanges(undefined, 10)).toEqual({ current: [], previous: [] })
  })
})

describe('impactSince', () => {
  const histories = {
    gdp: [{ tick: 1, value: 3.9 }, { tick: 1225, value: 4.21 }, { tick: 1250, value: 4.26 }, { tick: 1275, value: 4.3 }],
    unemployment: [{ tick: 1, value: 20 }, { tick: 1225, value: 11.8 }, { tick: 1250, value: 11.5 }, { tick: 1275, value: 11.2 }],
    happiness: [{ tick: 1, value: 50 }, { tick: 1225, value: 54.1 }, { tick: 1250, value: 54.6 }, { tick: 1275, value: 55 }],
    fiscal: [{ tick: 1, value: 0 }, { tick: 1225, value: -0.038 }, { tick: 1250, value: -0.03 }, { tick: 1275, value: -0.0214 }],
  }

  test('measures from the last sample at or before the change', () => {
    const impact = impactSince(1249, histories)
    expect(impact.status).toBe('ready')
    expect(impact.ticks).toBe(50)
    expect(impact.gdpPct).toBeCloseTo(2.138, 2)
    expect(impact.unemploymentPp).toBeCloseTo(-0.6, 6)
    expect(impact.happinessPts).toBeCloseTo(0.9, 6)
    expect(impact.fiscalDeltaMillions).toBeCloseTo(0.0166, 6)
  })

  test('reports measuring when no later sample exists yet', () => {
    expect(impactSince(1275, histories)).toEqual({ status: 'measuring' })
    expect(impactSince(1290, histories)).toEqual({ status: 'measuring' })
  })

  test('reports measuring when a series has no baseline', () => {
    expect(impactSince(1249, { ...histories, gdp: [{ tick: 1260, value: 4 }] })).toEqual({ status: 'measuring' })
    expect(impactSince(1249, { ...histories, fiscal: [] })).toEqual({ status: 'measuring' })
  })

  test('guards a zero GDP baseline', () => {
    const zero = { ...histories, gdp: [{ tick: 1, value: 0 }, { tick: 1275, value: 4.3 }] }
    expect(impactSince(1000, zero).gdpPct).toBeNull()
  })
})

describe('describeEvidenceAudit', () => {
  test('maps each backend status to a mark', () => {
    expect(describeEvidenceAudit({ status: 'matched_metric' }).mark).toBe('matched')
    expect(describeEvidenceAudit({ status: 'matched_policy' }).mark).toBe('matched')
    expect(describeEvidenceAudit({ status: 'value_mismatch', actual_value: -388100 })).toEqual({ mark: 'mismatch', note: 'shown -388,100' })
    expect(describeEvidenceAudit({ status: 'unknown_key' }).mark).toBe('unverified')
    expect(describeEvidenceAudit({ status: 'format_issue', issue: 'no equals sign' })).toEqual({ mark: 'unverified', note: 'no equals sign' })
    expect(describeEvidenceAudit({}).mark).toBe('unverified')
  })
})

describe('labels', () => {
  test('goal headlines and fiscal modes', () => {
    expect(goalHeadline('essential_sector_support')).toBe('Supporting essential sectors')
    expect(goalHeadline('hold')).toBe('Holding course')
    expect(goalHeadline('nonsense')).toBe('Policy assessment')
    expect(fiscalModeLabel('LOW_CASH')).toBe('Low cash')
    expect(fiscalModeLabel('STRONG_SURPLUS')).toBe('Strong surplus')
    expect(fiscalModeLabel(undefined)).toBeNull()
  })
})
