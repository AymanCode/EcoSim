// Pure helpers for the Government Console. No React, no network: everything here
// derives from fields the WebSocket frame already carries (governmentPolicy,
// policyChanges, llmGovernment, and the 25-tick history samples).

// Mirrors backend/config.py:828 (government_decision_interval)
export const DECISION_INTERVAL = 26

export const LEVER_DEFAULTS = Object.freeze({
  wage_tax_rate: 0.15,
  profit_tax_rate: 0.2,
  investment_tax_rate: 0.1,
  benefit_level: 'neutral',
  public_works: 'off',
  minimum_wage_policy: 'neutral',
  sector_subsidy_target: 'none',
  sector_subsidy_level: 0,
  infrastructure_spending: 'none',
  technology_spending: 'none',
  social_spending: 'medium',
  price_stabilization_target: 'none',
  price_stabilization_level: 'off',
  rent_stabilization_level: 'off',
  bailout_policy: 'off',
  bailout_target: 'none',
  bailout_budget: 0,
})

export const LEVER_GROUPS = [
  {
    id: 'taxes',
    label: 'Taxes',
    levers: [
      { key: 'wage_tax_rate', configKey: 'wageTax', label: 'Wage tax', kind: 'percent', min: 0, max: 0.5, step: 0.01 },
      { key: 'profit_tax_rate', configKey: 'profitTax', label: 'Profit tax', kind: 'percent', min: 0, max: 0.5, step: 0.01 },
      { key: 'investment_tax_rate', label: 'Investment tax', kind: 'readonly-percent' },
    ],
  },
  {
    id: 'welfare',
    label: 'Welfare & labor',
    levers: [
      { key: 'benefit_level', configKey: 'benefitLevel', label: 'Benefit level', kind: 'enum', options: 'benefit' },
      { key: 'minimum_wage_policy', configKey: 'minimumWagePolicy', label: 'Minimum wage policy', kind: 'enum', options: 'wagePolicy' },
      { key: 'public_works', configKey: 'publicWorks', label: 'Public works', kind: 'toggle' },
    ],
  },
  {
    id: 'spending',
    label: 'Public spending',
    levers: [
      { key: 'infrastructure_spending', configKey: 'infrastructureSpending', label: 'Infrastructure', kind: 'enum', options: 'level4' },
      { key: 'technology_spending', configKey: 'technologySpending', label: 'Technology', kind: 'enum', options: 'level4' },
      { key: 'social_spending', configKey: 'socialSpending', label: 'Social spending', kind: 'enum', options: 'level4' },
    ],
  },
  {
    id: 'markets',
    label: 'Market interventions',
    levers: [
      {
        key: 'sector_subsidy_target', configKey: 'sectorSubsidyTarget', label: 'Sector subsidy', kind: 'enum', options: 'sectors',
        pair: { key: 'sector_subsidy_level', configKey: 'sectorSubsidyLevel', label: 'Sector subsidy level', kind: 'enum-number', options: 'subsidyLevels' },
      },
      {
        key: 'price_stabilization_target', configKey: 'priceStabilizationTarget', label: 'Price stabilization', kind: 'enum', options: 'sectors',
        pair: { key: 'price_stabilization_level', configKey: 'priceStabilizationLevel', label: 'Price stabilization level', kind: 'enum', options: 'stabilization' },
      },
      { key: 'rent_stabilization_level', configKey: 'rentStabilizationLevel', label: 'Rent stabilization', kind: 'enum', options: 'stabilization' },
    ],
  },
  {
    id: 'bailouts',
    label: 'Bailouts',
    levers: [
      { key: 'bailout_policy', configKey: 'bailoutPolicy', label: 'Bailout policy', kind: 'enum', options: 'bailoutPolicy' },
      { key: 'bailout_target', configKey: 'bailoutTarget', label: 'Bailout target', kind: 'enum', options: 'sectors' },
      { key: 'bailout_budget', configKey: 'bailoutBudget', label: 'Bailout budget', kind: 'enum-number', options: 'bailoutBudgets' },
    ],
  },
]

const LEVER_LABELS = LEVER_GROUPS.reduce((acc, group) => {
  group.levers.forEach(lever => {
    acc[lever.key] = lever.label
    if (lever.pair) acc[lever.pair.key] = lever.pair.label
  })
  return acc
}, {})

const titleCase = (value) => String(value ?? '')
  .replace(/_/g, ' ')
  .replace(/([a-z])([A-Z])/g, '$1 $2')
  .trim()
  .replace(/^\w/, c => c.toUpperCase())

export function leverLabel(key) {
  return LEVER_LABELS[key] || titleCase(key || 'policy')
}

const normalizeToggle = (value) => {
  if (value === true) return 'on'
  if (value === false) return 'off'
  return String(value ?? '').toLowerCase()
}

export function formatLeverValue(key, value) {
  if (value === undefined || value === null || value === '') return '—'
  if (String(key).endsWith('_rate')) {
    const num = Number(value)
    return Number.isFinite(num) ? `${(num * 100).toFixed(1)}%` : String(value)
  }
  if (key === 'sector_subsidy_level') return `${Number(value)}%`
  if (key === 'bailout_budget') {
    const num = Number(value) || 0
    if (num >= 1000 && num % 1000 === 0) return `$${num / 1000}K`
    return `$${num.toLocaleString()}`
  }
  if (key === 'public_works') return normalizeToggle(value) === 'on' ? 'On' : 'Off'
  return titleCase(String(value))
}

export function classifyActor(reason) {
  const text = String(reason || '')
  if (text.startsWith('LLM government set')) return 'ai'
  if (text.startsWith('User updated')) return 'you'
  if (text.startsWith('Automatic government adjustment')) return 'auto'
  return 'unknown'
}

export function parsePreviousValue(reason) {
  const match = String(reason || '').match(/\bfrom (\S+) to (\S+)/)
  return match ? match[1] : null
}

export function changeNarrative(reason) {
  const text = String(reason || '')
  if (classifyActor(text) !== 'ai') return ''
  const match = text.match(/^LLM government set \S+ from \S+ to \S+?\.?(?:\s+|$)([\s\S]*)$/)
  return match ? match[1].trim() : ''
}

export function isLeverActive(key, liveValue) {
  if (!(key in LEVER_DEFAULTS)) return false
  if (liveValue === undefined || liveValue === null) return false
  const fallback = LEVER_DEFAULTS[key]
  if (key === 'public_works') return normalizeToggle(liveValue) !== fallback
  if (typeof fallback === 'number') {
    const num = Number(liveValue)
    return Number.isFinite(num) && Math.abs(num - fallback) > 1e-6
  }
  return String(liveValue).toLowerCase() !== String(fallback).toLowerCase()
}

export function countActiveInterventions(governmentPolicy) {
  const policy = governmentPolicy || {}
  return Object.keys(LEVER_DEFAULTS).filter(key => key in policy && isLeverActive(key, policy[key])).length
}

export function latestChangeByLever(policyChanges, currentTick) {
  const latest = new Map()
  const limit = Number(currentTick || 0)
  ;(Array.isArray(policyChanges) ? policyChanges : []).forEach(change => {
    const tick = Number(change?.tick || 0)
    if (tick > limit) return
    const key = change?.policy || change?.lever || change?.type || change?.key
    if (!key || latest.has(key)) return
    latest.set(key, {
      tick,
      actor: classifyActor(change.reason),
      value: change.value ?? change.new_value ?? change.level ?? change.target ?? null,
      previous: parsePreviousValue(change.reason),
      reason: change.reason || '',
    })
  })
  return latest
}

export function splitPolicyChanges(policyChanges, currentTick) {
  const list = Array.isArray(policyChanges) ? policyChanges : []
  const limit = Number(currentTick || 0)
  return {
    current: list.filter(change => Number(change?.tick || 0) <= limit),
    previous: list.filter(change => Number(change?.tick || 0) > limit),
  }
}

const lastSampleAtOrBefore = (series, tick) => {
  if (!Array.isArray(series)) return null
  let found = null
  for (const point of series) {
    if (Number(point?.tick) <= tick) found = point
    else break
  }
  return found
}

const lastSample = (series) => (Array.isArray(series) && series.length ? series[series.length - 1] : null)

export function impactSince(changeTick, histories) {
  const tick = Number(changeTick || 0)
  const series = histories || {}
  const names = ['gdp', 'unemployment', 'happiness', 'fiscal']
  const pairs = {}
  for (const name of names) {
    const base = lastSampleAtOrBefore(series[name], tick)
    const latest = lastSample(series[name])
    if (!base || !latest) return { status: 'measuring' }
    pairs[name] = { base: Number(base.value || 0), latest: Number(latest.value || 0), baseTick: Number(base.tick), latestTick: Number(latest.tick) }
  }
  if (pairs.gdp.latestTick <= pairs.gdp.baseTick) return { status: 'measuring' }
  const gdpPct = pairs.gdp.base === 0 ? null : ((pairs.gdp.latest - pairs.gdp.base) / Math.abs(pairs.gdp.base)) * 100
  return {
    status: 'ready',
    ticks: pairs.gdp.latestTick - pairs.gdp.baseTick,
    gdpPct,
    unemploymentPp: pairs.unemployment.latest - pairs.unemployment.base,
    happinessPts: pairs.happiness.latest - pairs.happiness.base,
    fiscalDeltaMillions: pairs.fiscal.latest - pairs.fiscal.base,
  }
}

const formatActual = (value) => {
  if (typeof value === 'number') return value.toLocaleString(undefined, { maximumFractionDigits: 3 })
  return String(value ?? '')
}

export function describeEvidenceAudit(entry) {
  const status = String(entry?.status || '')
  if (status === 'matched_metric' || status === 'matched_policy') return { mark: 'matched', note: 'matches observation' }
  if (status === 'value_mismatch') return { mark: 'mismatch', note: `shown ${formatActual(entry.actual_value)}` }
  if (status === 'format_issue') return { mark: 'unverified', note: entry?.issue || 'could not be checked' }
  if (status === 'unknown_key') return { mark: 'unverified', note: 'not in what the model saw' }
  return { mark: 'unverified', note: 'unchecked' }
}

const GOAL_HEADLINES = {
  hold: 'Holding course',
  stabilize_cash: 'Stabilizing the treasury',
  essential_sector_support: 'Supporting essential sectors',
  reduce_unemployment: 'Pushing unemployment down',
  support_growth: 'Backing growth',
  unwind_spending: 'Unwinding spending',
}

export function goalHeadline(primaryGoal) {
  return GOAL_HEADLINES[String(primaryGoal || '')] || 'Policy assessment'
}

const FISCAL_MODES = {
  CASH_CRISIS: 'Cash crisis',
  LOW_CASH: 'Low cash',
  NORMAL: 'Normal',
  STRONG_SURPLUS: 'Strong surplus',
}

export function fiscalModeLabel(mode) {
  return FISCAL_MODES[String(mode || '').toUpperCase()] || null
}
