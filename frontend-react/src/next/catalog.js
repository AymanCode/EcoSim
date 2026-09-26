// Every viewer-facing name, meaning and value phrase for metrics and levers.
// Wording follows the friendly vocabulary in the redesign spec (section 2.1).

export const METRICS = {
  peopleOutOfWorkPer100: {
    name: 'People out of work',
    meaning: "Working-age people who want a job and can't find one, per 100.",
    format: 'per100',
    better: 'lower',
  },
  typicalWeeklyPay: {
    name: 'Typical weekly pay',
    meaning: "The middle earner's weekly pay before tax.",
    format: 'money',
    better: 'higher',
  },
  priceFood: {
    name: 'Price of food',
    meaning: 'What a unit of food costs in the shops this week.',
    format: 'price',
    better: 'lower',
  },
  priceHousing: {
    name: 'Price of housing',
    meaning: "The average price the town's housing businesses ask this week.",
    format: 'price',
    better: 'lower',
  },
  priceServices: {
    name: 'Price of services',
    meaning: "The average price the town's service businesses ask this week.",
    format: 'price',
    better: 'lower',
  },
  priceHealthcare: {
    name: 'Price of healthcare',
    meaning: "The average price the town's healthcare businesses ask this week.",
    format: 'price',
    better: 'lower',
  },
  foodSpendPerHousehold: {
    name: 'A week of groceries',
    meaning: 'What a household paid for food this week, after any help from the town hall.',
    format: 'price',
    better: null,
  },
  gini: {
    name: 'Gap between rich and poor',
    meaning: '0 means everyone has the same, 1 means one person has it all.',
    format: 'ratio',
    better: 'lower',
  },
  townHallCash: {
    name: 'Town hall cash',
    meaning: 'What the town hall has in the bank; below zero, it owes.',
    format: 'money',
    better: null,
    // A balance below zero reads "owes $11,276" (formatMetric).
    owes: true,
  },
  homelessHouseholds: {
    name: 'Homes without a roof',
    meaning: 'Households that lost their home.',
    format: 'count',
    better: 'lower',
  },
  householdsTotal: {
    name: 'Households',
    meaning: 'Every household living in the town.',
    format: 'count',
    better: null,
  },
  firmsOpen: {
    name: 'Businesses open',
    meaning: 'Businesses trading this week.',
    format: 'count',
    better: 'higher',
  },
  firmsStruggling: {
    name: 'Firms struggling',
    meaning: 'Open businesses out of cash or cutting back to survive.',
    format: 'count',
    better: 'lower',
  },
  firmsGrowing: {
    name: 'Firms growing',
    meaning: 'Open businesses that plan to hire.',
    format: 'count',
    better: 'higher',
  },
  firmsSteady: {
    name: 'Firms holding steady',
    meaning: 'Open businesses neither hiring nor struggling.',
    format: 'count',
    better: null,
  },
  careDenials: {
    name: 'Doctor visits turned away',
    meaning: "Visits to a doctor refused this week because the household couldn't afford them.",
    format: 'count',
    better: 'lower',
  },
  bankActiveLoans: {
    name: 'Bank loans',
    meaning: 'Loans the bank has out right now.',
    format: 'count',
    better: null,
  },
  bankDefaultsTotal: {
    name: 'Unpaid loans',
    meaning: 'Bank loans that went unpaid so far.',
    format: 'count',
    better: 'lower',
  },
  publicWorksJobs: {
    name: 'Public works jobs',
    meaning: 'People the town hall employs directly.',
    format: 'count',
    better: null,
  },
  wealthP10: {
    name: 'Savings of the poorest tenth',
    meaning: 'Nine in ten households have more cash than this.',
    format: 'money',
    better: 'higher',
  },
  wealthP50: {
    name: 'Typical savings',
    meaning: "The middle household's cash.",
    format: 'money',
    better: 'higher',
  },
  wealthP90: {
    name: 'Savings of the richest tenth',
    meaning: 'One in ten households has more cash than this.',
    format: 'money',
    better: null,
  },
  // The meanings below say no more than docs/WEBSOCKET_PROTOCOL.md's curated
  // table. Sales leave out rent, the town hall's income is only the taxes it
  // collected, and the help it paid is only what went to families: the two
  // flows together are not the change in its cash.
  bankDefaultAmountThisTick: {
    name: 'Loans written off this week',
    meaning: 'Money the bank wrote off this week on loans that went unpaid.',
    format: 'money',
    better: 'lower',
  },
  happiness: {
    name: 'How people feel',
    meaning: 'Average happiness across every household this week, from 0 to 100.',
    format: 'outOf100',
    better: 'higher',
  },
  salesExceptRentThisWeek: {
    name: 'Sales this week, not counting rent',
    meaning: 'What the open businesses sold this week in food, services and healthcare visits; rent is not counted.',
    format: 'money',
    better: null,
  },
  townHallIncome: {
    name: 'Taxes collected this week',
    meaning: 'The taxes on wages, profits, property and investment that the town hall collected this week.',
    format: 'money',
    better: null,
  },
  familySupportPaid: {
    name: 'Help paid to families this week',
    meaning: 'Benefits and top-ups the town hall paid to families out of work this week, plus the welcome payment every household gets in the six weeks after the town is set up.',
    format: 'money',
    better: null,
  },
  topTenthShare: {
    name: 'Share held by the richest tenth',
    meaning: 'Of all the cash households have, the percent held by the richest tenth of households.',
    format: 'percent',
    better: null,
  },
  bottomHalfShare: {
    name: 'Share held by the poorer half',
    meaning: 'Of all the cash households have, the percent held by the poorer half of households.',
    format: 'percent',
    better: null,
  },
}

export const NOT_MEASURED = 'not measured'

const isNumber = value => typeof value === 'number' && Number.isFinite(value)
const grouped = new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 })

export function formatMoney(value) {
  if (!isNumber(value)) return NOT_MEASURED
  const rounded = Math.round(value)
  return `${rounded < 0 ? '-' : ''}$${grouped.format(Math.abs(rounded))}`
}

// Compact money for bars and tight rows: $850, $6.9k, $28k, $1.3m.
export function formatMoneyShort(value) {
  if (!isNumber(value)) return NOT_MEASURED
  const sign = value < 0 ? '-' : ''
  const abs = Math.abs(value)
  if (abs >= 1e6) return `${sign}$${(abs / 1e6).toFixed(1).replace(/\.0$/, '')}m`
  if (abs >= 1e4) return `${sign}$${Math.round(abs / 1e3)}k`
  if (abs >= 1e3) return `${sign}$${(abs / 1e3).toFixed(1).replace(/\.0$/, '')}k`
  return `${sign}$${Math.round(abs)}`
}

const FORMATTERS = {
  per100: value => `${Math.round(value)} in 100`,
  money: formatMoney,
  price: value => `${value < 0 ? '-' : ''}$${Math.abs(value).toFixed(2)}`,
  ratio: value => value.toFixed(2),
  count: value => grouped.format(Math.round(value)),
  outOf100: value => `${Math.round(value)} of 100`,
  percent: value => `${Math.round(value)}%`,
}

export function formatMetric(key, value) {
  if (!isNumber(value)) return NOT_MEASURED
  if (METRICS[key]?.owes && Math.round(value) < 0) return `owes ${formatMoney(-Math.round(value))}`
  const format = FORMATTERS[METRICS[key]?.format] ?? FORMATTERS.count
  return format(value)
}

// Weeks 1 to 10 set the town up (the server's `warmup_ticks`); the real
// economy starts in week 11.
export const WARMUP_TICKS = 10

// A figure rounded the way formatMetric shows it, as a number. Prices and
// ratios round as toFixed does, so 10.795 (stored just below it) is 10.79 as
// on the page, not 10.8.
export function shownValue(key, value) {
  if (!isNumber(value)) return null
  const format = METRICS[key]?.format
  if (format === 'price' || format === 'ratio') return Number(value.toFixed(2))
  return Math.round(value)
}

// Tight labels for chart axes: big sums of money go short ("$1.3m") and money
// keeps its sign ("-$5,000", never "owes"); everything else reads as
// formatMetric. End labels use formatEndLabel below.
export function formatMetricShort(key, value) {
  if (!isNumber(value)) return NOT_MEASURED
  if (METRICS[key]?.format === 'money') return Math.abs(value) >= 1e4 ? formatMoneyShort(value) : formatMoney(value)
  return formatMetric(key, value)
}

// A chart's end label: formatMetricShort, except that a balance below zero
// reads "owes $11k" as the values do. Axis labels stay signed.
export function formatEndLabel(key, value) {
  if (isNumber(value) && METRICS[key]?.owes && Math.round(value) < 0) return `owes ${formatMetricShort(key, -Math.round(value))}`
  return formatMetricShort(key, value)
}

// The "Show me all the numbers" sheet. Each group lists the metrics drawn as
// tiles (`keys`) and the special visuals beside them (`extras`), in order;
// titles and blurbs are in COPY.numbers.groups.
export const NUMBER_GROUPS = [
  { id: 'work', keys: ['peopleOutOfWorkPer100', 'typicalWeeklyPay', 'publicWorksJobs'], extras: ['hiresAndLayoffs'] },
  { id: 'prices', keys: ['priceFood', 'priceHousing', 'priceServices', 'priceHealthcare', 'foodSpendPerHousehold'] },
  { id: 'richpoor', keys: ['gini', 'topTenthShare', 'bottomHalfShare'], extras: ['wealthLadder'] },
  { id: 'business', keys: ['firmsOpen'], extras: ['firmStates', 'openedClosed'] },
  { id: 'money', keys: ['townHallCash', 'salesExceptRentThisWeek', 'bankActiveLoans'], extras: ['moneyInOut', 'loansWrittenOff'] },
  { id: 'wellbeing', keys: ['homelessHouseholds', 'careDenials', 'happiness'] },
]

// The sheet's "This week at a glance" rows, in order.
export const GLANCE_KEYS = [
  'peopleOutOfWorkPer100', 'typicalWeeklyPay', 'foodSpendPerHousehold', 'gini', 'townHallCash', 'firmsOpen', 'happiness', 'salesExceptRentThisWeek',
]

// Figures the server counts every 5 weeks (and on the first week) and repeats
// in between; `wealthAsOfTick` says when (docs/WEBSOCKET_PROTOCOL.md). They
// are drawn only at the weeks they were counted (data/derive.js `countedAt`).
export const COUNTED_EVERY_5 = ['gini', 'wealthP10', 'wealthP50', 'wealthP90', 'topTenthShare', 'bottomHalfShare']

// The numbers the story chart can show, and the four stat cards beside it.
export const STORY_METRICS = ['peopleOutOfWorkPer100', 'typicalWeeklyPay', 'foodSpendPerHousehold', 'gini', 'townHallCash']
export const STAT_METRICS = ['peopleOutOfWorkPer100', 'typicalWeeklyPay', 'foodSpendPerHousehold', 'gini']

// Town colours, in arm order (the spec's town A to D tokens), for lines,
// swatches and drawings. Text in a town's colour uses its darker text tone
// from next.css, which reads at 4.5:1 on the page and the panels.
export const TOWN_COLORS = ['#2E6FE0', '#E0762C', '#199E70', '#9085E9']
const TOWN_TEXT = ['var(--nx-a-text)', 'var(--nx-b-text)', 'var(--nx-c-text)', 'var(--nx-d-text)']

export function townTextColor(color) {
  const index = TOWN_COLORS.findIndex(town => town.toLowerCase() === String(color ?? '').toLowerCase())
  return index < 0 ? 'var(--nx-ink)' : TOWN_TEXT[index]
}

// Percent with at most one decimal: 0.2 -> "20%", 0.225 -> "22.5%".
function percent(rate) {
  const value = Number(rate)
  if (!Number.isFinite(value)) return String(rate)
  return `${Number((value * 100).toFixed(1))}%`
}

const SPENDING = {
  none: 'nothing', low: 'low', medium: 'medium', high: 'high',
}
const STABILISATION = {
  off: 'off', monitor: 'watch only', soft: 'gentle', strict: 'strict',
}
const FIRM_TARGETS = {
  none: 'no one', food: 'food firms', housing: 'housing firms', services: 'service firms', healthcare: 'healthcare firms',
}

const spendingPolicy = subject => ({
  none: `no ${subject}`, low: `light ${subject}`, medium: `moderate ${subject}`, high: `heavy ${subject}`,
})
const controlPolicy = subject => ({
  off: `no ${subject} controls`, monitor: `${subject} monitoring`, soft: `gentle ${subject} controls`, strict: `strict ${subject} controls`,
})

// name: how a sentence refers to the lever; values: the phrase for each value;
// policy: the lever set to that value, as a noun phrase ("a higher minimum wage").
// help: one sentence on what the town hall directly does with the lever, checked
// against the backend code that reads it (backend/agents.py GovernmentAgent and
// backend/economy.py); it names the mechanism, never an outcome.
// Rate levers take any value within their bounds, so they phrase it as a percent.
export const LEVERS = {
  wage_tax_rate: {
    name: 'the tax on wages',
    help: 'Sets the tax taken from every paycheque, with bigger paycheques paying a larger share.',
    kind: 'rate',
    values: {},
    policy: rate => `a ${percent(rate)} tax on wages`,
  },
  profit_tax_rate: {
    name: 'the tax on profits',
    help: 'Sets the tax on business profits, with richer businesses paying a larger share.',
    kind: 'rate',
    values: {},
    policy: rate => `a ${percent(rate)} tax on profits`,
  },
  investment_tax_rate: {
    name: 'the tax on investment',
    help: 'Taxes the money businesses spend on improving what they sell.',
    kind: 'rate',
    values: {},
    policy: rate => `a ${percent(rate)} tax on investment`,
  },
  benefit_level: {
    name: 'help for people out of work',
    help: 'Sets the weekly payment for families out of work, plus a top-up for those running low on cash.',
    values: { low: 'low', neutral: 'normal', high: 'high', crisis: 'emergency level' },
    policy: {
      low: 'less help for people out of work',
      neutral: 'the usual help for people out of work',
      high: 'more help for people out of work',
      crisis: 'emergency help for people out of work',
    },
  },
  public_works: {
    name: 'public works jobs',
    help: 'When on, the town hall runs its own business and hires people to work in it, if it can afford to start one.',
    values: { off: 'off', on: 'on' },
    policy: { off: 'no public works jobs', on: 'public works jobs' },
  },
  minimum_wage_policy: {
    name: 'the minimum wage',
    help: 'Sets the lowest weekly wage a business is allowed to pay.',
    values: { low: 'low', neutral: 'normal', high: 'high' },
    policy: { low: 'a lower minimum wage', neutral: 'the usual minimum wage', high: 'a higher minimum wage' },
  },
  sector_subsidy_target: {
    name: 'the subsidy target',
    help: 'Chooses which kind of business the town hall helps families buy from.',
    values: FIRM_TARGETS,
    policy: {
      none: 'no business subsidy',
      food: 'a subsidy for food firms',
      housing: 'a subsidy for housing firms',
      services: 'a subsidy for service firms',
      healthcare: 'a subsidy for healthcare firms',
    },
  },
  sector_subsidy_level: {
    name: 'the business subsidy',
    help: 'Sets the share of the price the town hall pays when families buy from the chosen kind of business.',
    values: { 0: 'none', 10: '10%', 25: '25%', 50: '50%' },
    policy: { 0: 'no business subsidy', 10: 'a 10% business subsidy', 25: 'a 25% business subsidy', 50: 'a 50% business subsidy' },
  },
  price_stabilization_target: {
    name: 'the price-control target',
    help: 'Chooses which kind of business the price limit applies to.',
    values: { none: 'nothing', food: 'food', services: 'services', healthcare: 'healthcare' },
    policy: {
      none: 'no price-control target',
      food: 'price controls on food',
      services: 'price controls on services',
      healthcare: 'price controls on healthcare',
    },
  },
  price_stabilization_level: {
    name: 'price controls',
    help: 'Limits how much the chosen kind of business may raise its prices at a time; “watch only” sets no limit.',
    values: STABILISATION,
    policy: controlPolicy('price'),
  },
  rent_stabilization_level: {
    name: 'rent controls',
    help: 'Limits how much landlords may raise the rent at a time; “watch only” sets no limit.',
    values: STABILISATION,
    policy: controlPolicy('rent'),
  },
  infrastructure_spending: {
    name: 'spending on roads and buildings',
    help: 'Sets how much the town hall spends on roads and buildings in each week it has the cash to cover it.',
    values: SPENDING,
    policy: spendingPolicy('spending on roads and buildings'),
  },
  technology_spending: {
    name: 'spending on technology',
    help: 'Sets how much the town hall spends on new technology in each week it has the cash to cover it.',
    values: SPENDING,
    policy: spendingPolicy('spending on technology'),
  },
  social_spending: {
    name: 'social spending',
    help: 'Sets how much the town hall spends each week on community programmes, up to the cash it has.',
    values: SPENDING,
    policy: spendingPolicy('social spending'),
  },
  bailout_policy: {
    name: 'bailouts',
    help: 'Decides whether the town hall lends emergency money to struggling businesses, and to which ones.',
    values: { off: 'off', sector: 'one sector only', all: 'any business' },
    policy: { off: 'no bailouts', sector: 'bailouts for one sector', all: 'bailouts for any business' },
  },
  bailout_target: {
    name: 'the bailout target',
    help: 'Chooses which kind of business can get emergency loans when bailouts cover one sector only.',
    values: FIRM_TARGETS,
    policy: {
      none: 'no bailout target',
      food: 'bailouts for food firms',
      housing: 'bailouts for housing firms',
      services: 'bailouts for service firms',
      healthcare: 'bailouts for healthcare firms',
    },
  },
  bailout_budget: {
    name: 'the bailout budget',
    help: 'Sets the pot of money the town hall can lend to struggling businesses.',
    values: { 0: '$0', 5000: '$5,000', 10000: '$10,000', 25000: '$25,000', 50000: '$50,000' },
    policy: {
      0: 'no bailout budget',
      5000: 'a $5,000 bailout budget',
      10000: 'a $10,000 bailout budget',
      25000: 'a $25,000 bailout budget',
      50000: 'a $50,000 bailout budget',
    },
  },
}

// The rules of a town nobody has changed: the tick-1 `metrics.governmentPolicy`
// of a run whose SETUP sends an empty `initial_policy`.
export const DEFAULT_POLICY = {
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
}

// The values each lever accepts, copied from backend/policy_schema.py: the tax
// rates (TAX_LIMITS) as { min, max }, the ordered levers (ORDERED_LEVERS) in
// schema order. The four plain enums (SIMPLE_ENUM_LEVERS, which the schema
// sorts) are in display order, "off" or "none" first. Numbers stay numbers.
export const LEVER_OPTIONS = {
  wage_tax_rate: { min: 0, max: 0.5 },
  profit_tax_rate: { min: 0, max: 0.5 },
  investment_tax_rate: { min: 0, max: 0.3 },
  benefit_level: ['low', 'neutral', 'high', 'crisis'],
  minimum_wage_policy: ['low', 'neutral', 'high'],
  sector_subsidy_level: [0, 10, 25, 50],
  infrastructure_spending: ['none', 'low', 'medium', 'high'],
  technology_spending: ['none', 'low', 'medium', 'high'],
  social_spending: ['none', 'low', 'medium', 'high'],
  price_stabilization_level: ['off', 'monitor', 'soft', 'strict'],
  rent_stabilization_level: ['off', 'monitor', 'soft', 'strict'],
  bailout_policy: ['off', 'sector', 'all'],
  bailout_budget: [0, 5000, 10000, 25000, 50000],
  public_works: ['off', 'on'],
  sector_subsidy_target: ['none', 'food', 'housing', 'services', 'healthcare'],
  price_stabilization_target: ['none', 'food', 'services', 'healthcare'],
  bailout_target: ['none', 'food', 'housing', 'services', 'healthcare'],
}

// The lever editor's sections, in order; every lever sits in exactly one.
// Titles and blurbs are in COPY.levers.groups.
export const LEVER_GROUPS = [
  { id: 'taxes', levers: ['wage_tax_rate', 'profit_tax_rate', 'investment_tax_rate'] },
  { id: 'people', levers: ['minimum_wage_policy', 'benefit_level', 'social_spending'] },
  { id: 'spending', levers: ['public_works', 'infrastructure_spending', 'technology_spending'] },
  { id: 'business', levers: ['sector_subsidy_target', 'sector_subsidy_level', 'bailout_policy', 'bailout_target', 'bailout_budget'] },
  { id: 'prices', levers: ['price_stabilization_target', 'price_stabilization_level', 'rent_stabilization_level'] },
]

// The question cards on Set up. Each town is the levers it changes from
// DEFAULT_POLICY; the first town is the control. Only the two questions the
// newcomer-scale smoke runs support ship (spec section 5.1).
export const QUESTIONS = [
  {
    id: 'minimum-wage',
    title: 'What happens if we raise the minimum wage?',
    blurb: 'Higher pay for the lowest earners, higher costs for businesses. Which wins?',
    towns: [{}, { minimum_wage_policy: 'high' }],
  },
  {
    id: 'benefits',
    title: 'Do generous benefits keep people out of work?',
    blurb: 'More money for people without a job. Does it help them or make work less tempting?',
    towns: [{}, { benefit_level: 'high' }],
  },
]

export function capitalise(text) {
  const value = String(text ?? '')
  return `${value.charAt(0).toUpperCase()}${value.slice(1)}`
}

export function leverName(lever) {
  return LEVERS[lever]?.name ?? String(lever).replace(/_/g, ' ')
}

export function leverValuePhrase(lever, value) {
  const spec = LEVERS[lever]
  if (spec?.kind === 'rate') return percent(value)
  return spec?.values?.[String(value)] ?? String(value)
}

function leverPolicy(lever, value) {
  const policy = LEVERS[lever]?.policy
  if (typeof policy === 'function') return policy(value)
  return policy?.[String(value)] ?? `${leverName(lever)} set to ${leverValuePhrase(lever, value)}`
}

// Levers that only make sense together read as one phrase.
const GROUPS = [
  {
    levers: ['sector_subsidy_target', 'sector_subsidy_level'],
    applies: p => p.sector_subsidy_target !== 'none' && Number(p.sector_subsidy_level) > 0,
    phrase: p => `a ${Number(p.sector_subsidy_level)}% subsidy for ${FIRM_TARGETS[p.sector_subsidy_target] ?? p.sector_subsidy_target}`,
  },
  {
    levers: ['price_stabilization_target', 'price_stabilization_level'],
    applies: p => p.price_stabilization_target !== 'none' && p.price_stabilization_level !== 'off',
    phrase: p => `${leverPolicy('price_stabilization_level', p.price_stabilization_level)} on ${leverValuePhrase('price_stabilization_target', p.price_stabilization_target)}`,
  },
  {
    // Only the choice itself must be there: the sector and budget join the
    // phrase when they fit the bailout rule (policyRules.js).
    levers: ['bailout_policy', 'bailout_target', 'bailout_budget'],
    needs: ['bailout_policy'],
    applies: p => bailoutPhrase(p) !== null,
    phrase: p => bailoutPhrase(p),
  },
]

// The bailout levers as one phrase, or null when they break the bailout rule:
// off with no sector or budget, one sector with its sector, any business with
// none. A budget left out of the vector is left out of the phrase.
function bailoutPhrase(p) {
  const target = p.bailout_target ?? 'none'
  const budget = p.bailout_budget === undefined ? null : Number(p.bailout_budget)
  if (p.bailout_policy === 'off') return target === 'none' && !budget ? 'no bailouts' : null
  if (budget === 0) return null
  const withBudget = budget ? ` with a ${formatMoney(budget)} budget` : ''
  if (p.bailout_policy === 'all') return target === 'none' ? `bailouts for any business${withBudget}` : null
  if (p.bailout_policy === 'sector' && target !== 'none' && FIRM_TARGETS[target]) return `bailouts for ${FIRM_TARGETS[target]}${withBudget}`
  return null
}

export const NO_CHANGES = 'no changes'

export function joinPhrases(phrases) {
  if (phrases.length <= 1) return phrases[0] ?? ''
  return `${phrases.slice(0, -1).join(', ')} and ${phrases[phrases.length - 1]}`
}

// An initial policy (lever vector, schema names) as a noun phrase, in the
// schema's lever order.
export function describePolicy(initialPolicy) {
  const policy = initialPolicy ?? {}
  const present = Object.keys(LEVERS).filter(lever => policy[lever] !== undefined)
  const unknown = Object.keys(policy).filter(lever => !LEVERS[lever])
  if (!present.length && !unknown.length) return NO_CHANGES
  const used = new Set()
  const phrases = []
  for (const lever of [...present, ...unknown]) {
    if (used.has(lever)) continue
    const group = GROUPS.find(g => g.levers.includes(lever) && (g.needs ?? g.levers).every(l => policy[l] !== undefined))
    if (group && group.applies(policy)) {
      group.levers.forEach(l => used.add(l))
      phrases.push(group.phrase(policy))
      continue
    }
    used.add(lever)
    phrases.push(leverPolicy(lever, policy[lever]))
  }
  return joinPhrases(phrases)
}

// Panel copy for the Run screen.

export const SECTORS = {
  Food: 'Food', Housing: 'Housing', Services: 'Services', Healthcare: 'Healthcare', PublicWorks: 'Public works',
}

export function sectorName(sector) {
  return SECTORS[sector] ?? sector ?? ''
}

export const HOUSEHOLD_STATES = {
  work: { legend: 'working', chip: 'Working' },
  look: { legend: 'looking for work', chip: 'Looking for work' },
  home: { legend: 'lost their home', chip: 'Lost their home' },
  idle: { legend: 'not working', chip: 'Not working' },
}

export const FIRM_STATES = {
  growing: 'Growing', steady: 'Steady', struggling: 'Struggling', closed: 'Closed',
}

const counted = (n, one, many = `${one}s`, format = String) => `${format(n)} ${n === 1 ? one : many}`

// Small counts read as words in sentences: 2 -> "two".
const NUMBER_WORDS = ['zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten']
const numberWord = n => NUMBER_WORDS[n] ?? grouped.format(n)

// A phrase for one town, two towns or more: everyTown(2, 'the town', 'either town', 'any town').
const everyTown = (townCount, one, two, more) => (townCount < 2 ? one : townCount === 2 ? two : more)

// How many households one house in the drawing stands for, as a phrase.
export function householdsPerHouse(total) {
  if (!isNumber(total) || total <= 0) return '1 in 100 households'
  const per = total / 100
  const shown = Math.max(1, Math.round(per))
  return `${Number.isInteger(per) ? '' : 'about '}${counted(shown, 'household')}`
}

// Notes use **word** for the bold lead-in the panel renders.
function howToNotes({ armCount = 2, perHouse = householdsPerHouse(null), firstPolicy = NO_CHANGES } = {}) {
  const tick = armCount >= 2
    ? `A **tick** is one week. ${armCount === 2 ? 'Both towns' : 'All the towns'} run the same week at the same time, from the same starting point, so any difference you see is caused by the rules.`
    : 'A **tick** is one week. The town moves forward a week at a time, and the timeline takes you back to any week you have already seen.'
  const first = firstPolicy === NO_CHANGES ? 'keeps the usual rules' : `runs with ${firstPolicy}`
  const rules = armCount >= 2
    ? `The **first town** ${first}. The rules each town has in force are named under its title; where they differ from the first town's, that difference is what the towns are testing.`
    : "The **town hall** sets the rules: taxes, benefits, the minimum wage. The ones in force are named under the town's title."
  return [
    tick,
    rules,
    `Every **house** stands for ${perHouse}. Amber houses, with an empty window, show the share of working-age people looking for work. Red houses, with a dashed outline, are households that lost their home. Green houses are the rest.`,
    "Every building on **Main street** is a firm. Taller means more staff. A flag means it's struggling to pay wages or rent, a cross means it closed.",
  ]
}

export const COPY = {
  town: {
    hall: 'Town hall',
    bank: 'Bank',
    mainStreet: 'Main street',
    houseScale: total => {
      const per = Number(total) / 100
      if (Number.isInteger(per) && per >= 1) return `each house is ${counted(per, 'household')}`
      return 'each house is 1 in 100 households'
    },
    hallChanged: 'Town hall: new rules this month',
    moreBuildings: n => `+${n} more`,
    outOfWork: 'out of work',
    typicalPay: 'typical weekly pay',
    firms: n => counted(n, 'firm'),
    firmStates: (struggling, closed) => `${struggling} struggling, ${closed} closed`,
    altHouses: (work, look, home) => `Out of every 100 households: ${work} working, ${look} looking for work, ${home} lost their home.`,
    altFirms: (open, struggling, closed) => `${counted(open, 'firm')} open: ${struggling} struggling. ${closed} closed in the last year.`,
  },
  // Short lines under the lead when something notable just happened
  // (narration.js `moments`, components/Moments.jsx).
  moments: {
    label: 'What just happened',
    rule: (town, policy) => `${town}'s town hall brought in ${policy}.`,
    richest: (business, town) => `${business} is now ${town}'s richest business.`,
    passed: (town, level) => `${town} passed ${level} in 100 people out of work.`,
    fellBelow: (town, level) => `${town} fell below ${level} in 100 people out of work.`,
  },
  businesses: {
    title: 'Businesses',
    subtitle: 'richest first, cash in the bank',
    staff: n => `${n} staff`,
    closedWhen: when => `closed ${when}`,
    seeAll: n => `See all ${n}`,
    showFewer: 'Show fewer',
    empty: 'No businesses are open yet.',
  },
  households: {
    title: 'Households',
    subtitle: 'four from the sample, follow one to keep it here',
    nameAge: (name, age) => (age == null ? name : `${name}, ${age}`),
    worksAt: firm => `Works at ${firm}`,
    looking: 'Looking for work',
    notWorking: 'Not working',
    saved: 'saved',
    follow: 'Follow',
    followLabel: name => `Follow ${name}`,
    showOthers: 'Show me four others',
    empty: 'No households in the sample yet.',
  },
  feed: {
    title: "What's happening",
    subtitle: 'newest first',
    when: (week, town) => `${week}, ${town}`,
    empty: 'Nothing has happened yet.',
  },
  chart: {
    chips: 'Chart a different number',
    weeksAhead: 'the weeks ahead',
    settingUp: 'setting up',
    year: n => `Year ${n}`,
    week: n => `Week ${n}`,
    endLabel: (town, value) => `${town}  ${value}`,
    tableCaption: name => `${name}, every 13 weeks`,
    // The same table for a number counted every 5 weeks: its counts, not every week.
    countedCaption: name => `${name}, as counted every 5 weeks`,
    weekColumn: 'Week',
  },
  horizon: {
    region: 'Timeline',
    play: 'Play',
    pause: 'Pause',
    again: 'Play again',
    scrub: 'Week of the run',
    speed: 'Speed',
    speedValue: speed => `${speed}×`,
    speedLabel: speed => `Play at ${speed}× speed`,
    length: horizon => {
      const weeks = Math.max(0, Math.round(Number(horizon) || 0))
      if (weeks >= 52 && weeks % 52 === 0) return `of ${counted(weeks / 52, 'year')}`
      return `of ${counted(weeks, 'week')}`
    },
    year: n => `Year ${n}`,
  },
  app: {
    brand: 'EcoSim',
    townLabel: index => `Town ${String.fromCharCode(65 + index)}`,
    classic: 'Classic dashboard',
    loading: 'Loading the demo towns…',
    missing: 'Demo data missing: run the recorder commands in docs/superpowers/plans/2026-09-25-frontend-redesign-phase2-slice1.md',
    detail: reason => `Details: ${reason}`,
  },
  howTo: {
    title: 'How to read this',
    subtitle: 'for first-timers',
    notes: howToNotes,
  },
  // How long a run should take, from live/plan.js `estimatePhrase`.
  estimate: {
    underMinute: 'Under a minute.',
    aboutMinute: 'About a minute.',
    minutes: n => `About ${n} minutes.`,
  },
  // The lever editor (components/LeverEditor.jsx).
  levers: {
    groups: {
      taxes: { title: 'Taxes', blurb: 'How the town hall raises money.' },
      people: { title: 'Families and work', blurb: 'Pay, help for people out of work, and community programmes.' },
      spending: { title: 'Town hall projects', blurb: 'Jobs, roads and technology the town hall pays for.' },
      business: { title: 'Help for businesses', blurb: 'Subsidies and emergency loans.' },
      prices: { title: 'Prices and rent', blurb: 'Limits on how fast prices and rents can rise.' },
    },
    // The group rules of backend/policy_vectors.py `policy_group_errors`, for a
    // newcomer (policyRules.js). Bailouts that are off lend nothing, bailouts
    // for one sector name it, bailouts for any business name none, and both
    // need a budget.
    rules: {
      sector_subsidy: 'The subsidy needs a kind of business to go to. Pick one, or set the subsidy to none.',
      bailout_off: 'Turn bailouts on before setting a sector or budget.',
      bailout_target: 'Pick which kind of business to help.',
      bailout_all: "Bailouts for any business don't need a sector.",
      bailout_budget: "Set a budget, or the town hall can't lend anything.",
    },
    changed: '(changed)',
  },
  // The Set up screen (setup/SetupScreen.jsx).
  setup: {
    title: 'What do you want to find out?',
    subhead: 'EcoSim runs a small town of families, businesses, a bank and a town hall, one week at a time. Set up a question, press start, and watch it play out.',
    watchFirst: 'Or watch a recorded example first',
    steps: {
      mode: 'Pick a kind of experiment',
      question: 'Choose a question',
      towns: 'Your towns',
      town: 'Your town',
      world: 'The world',
    },
    worldNote: 'these are shared by every town, so the comparison is fair',
    modes: {
      compare: {
        title: 'Compare policies',
        blurb: 'Run the same town two to four times with different rules and watch where they part ways.',
      },
      ai: {
        title: 'Test an AI mayor',
        blurb: 'Let a language model run the town hall and see how it does against a town where nothing changes.',
      },
      play: {
        title: 'Just play',
        blurb: 'One town, every rule, no comparison. Change things while it runs and see what happens.',
      },
    },
    comingSoon: 'Coming soon',
    noChanges: 'No changes',
    custom: { title: 'Build my own', blurb: 'Pick every rule for every town' },
    // A question card's towns, read out in one go: "Town A: No changes. Town B: A higher minimum wage."
    cardTowns: towns => towns.map(town => `${town.label}: ${town.text}.`).join(' '),
    control: 'No changes. The control.',
    usual: 'The usual rules.',
    townRules: phrase => `${capitalise(phrase)}.`,
    changeRules: 'Change rules',
    changeRulesFor: label => `Change rules for ${label}`,
    remove: 'Remove',
    removeTown: label => `Remove ${label}`,
    addTown: 'Add a town',
    addTownNote: 'up to 4. Each town gets an equal share of 10,000 households.',
    editorTitle: label => `${label}'s rules`,
    done: 'Done',
    households: 'Households per town',
    householdsValue: n => grouped.format(n),
    householdsCap: (cap, towns) => `up to ${grouped.format(cap)} with ${counted(towns, 'town')}`,
    householdsNote: 'More households, more realistic, slower.',
    years: 'How long',
    yearsValue: n => counted(n, 'year'),
    yearsNote: "You can add a year at the end if it's getting interesting.",
    town: 'Which town',
    townNumber: seed => `Town #${seed}`,
    reroll: 'Try a different town',
    seedLabel: 'Town number',
    townNote: 'The same town number and size always build the same town with the same people. Change it for a different town, keep it to repeat an experiment.',
    start: 'Start the experiment',
    startPlay: 'Start playing',
    // "Two towns, 1,000 households each, five years."
    estimate: ({ towns, households, years }) => {
      const size = `${grouped.format(households)} households${towns === 1 ? '' : ' each'}`
      return `${capitalise(counted(towns, 'town', 'towns', numberWord))}, ${size}, ${counted(years, 'year', 'years', numberWord)}.`
    },
    anyTime: 'You can pause, change the rules, or stop at any time.',
    needsFix: 'Needs a fix',
    fixFirst: labels => `Fix the rules marked in ${joinPhrases(labels)} before you start.`,
    problems: {
      unreachable: "The simulation isn't running on this computer.",
      full: 'The simulation is already running as many towns as it can. Close another EcoSim tab, or try again in a moment.',
      setup: "The simulation couldn't build these towns.",
      dropped: 'The simulation stopped answering while it built the towns. Press Start to try again.',
    },
    startWith: 'To start it, run this in the EcoSim folder, then press Start again:',
    command: 'python -m uvicorn backend.server:app --port 8002',
    watchInstead: 'Watch the recorded example instead',
  },
  // The live Run screen and the app bar around it (NextApp.jsx, RunScreen.jsx,
  // components/HorizonBar.jsx, components/HouseholdCards.jsx, components/LostPanel.jsx).
  live: {
    setUp: 'Set up',
    newExperiment: 'New experiment',
    watchExample: 'Watch the example',
    building: 'Building the towns…',
    resume: 'Resume',
    backToLive: 'Back to live',
    meetOthers: 'Meet other families',
    // "Town B lost its connection to the simulation in Year 1, week 12. The other towns are paused."
    lost: (town, week, others) => {
      const when = week ? `in ${week}` : 'before its first week'
      return `${town} lost its connection to the simulation ${when}.${others ? ' The other towns are paused.' : ''}`
    },
    // The server stopped a town's run with an error, or could not start or finish it.
    crashed: (town, week, others) => {
      const when = week ? `in ${week}` : 'before its first week'
      return `${town} stopped because the simulation hit an error ${when}.${others ? ' The other towns are paused.' : ''}`
    },
    restart: townCount => (townCount > 1 ? 'Start these towns again' : 'Start this town again'),
    // Shown beside the restart once the town hall has applied a change.
    notRepeated: 'Starting again uses the rules you set up. Your rule changes will not be repeated.',
    // Under a town's name when the server could not do something it was asked
    // (the server's words follow in a "Details:" line).
    notice: "The simulation couldn't carry out the last request for this town.",
    newSetup: 'Set up something new',
  },
  // The Town hall drawer (components/TownHall.jsx).
  hall: {
    title: 'Town hall',
    close: 'Close',
    closeLabel: 'Close the town hall',
    towns: 'Which town',
    note: townCount => (townCount > 1
      ? 'Changes start at the next week. The other towns keep their own rules.'
      : 'Changes start at the next week.'),
    apply: 'Change from next week',
    receipts: 'Your changes',
    waiting: 'Waiting for next week…',
    applied: (week, phrase) => `${week}: ${capitalise(phrase)}.`,
    rejected: (lever, reason) => `${capitalise(lever)} was not changed: ${reason}`,
    failed: message => `Couldn't change the rules: ${message}`,
    // Why the rules cannot change right now, by experiment phase.
    locked: {
      connecting: 'You can change the rules as soon as the run starts.',
      over: 'The run is over. Add a year to change the rules again.',
      lost: 'The run has stopped. Start it again to change the rules.',
    },
  },
  // The end of the run (components/EndPanel.jsx).
  end: {
    // "5 years are up." from the horizon in weeks.
    up: horizon => {
      const weeks = Math.max(0, Math.round(Number(horizon) || 0))
      if (weeks >= 52 && weeks % 52 === 0) return `${counted(weeks / 52, 'year')} ${weeks === 52 ? 'is' : 'are'} up.`
      return `${counted(weeks, 'week')} ${weeks === 1 ? 'is' : 'are'} up.`
    },
    finishing: 'Wrapping up the run…',
    addYear: 'Add a year',
    backToEnd: 'Back to the end',
    another: 'Try another question',
  },
  // The "Show me all the numbers" sheet (numbers/). Differences between towns
  // and the counted-every-5-weeks note are narration.js `differencePhrase` and
  // `countedNote`. Wording follows mockup 06.
  numbers: {
    // A tile whose number this recording never carried, never a zero.
    notMeasured: 'Not measured in this run',
    title: 'All the numbers',
    // "Everything we measure in both towns, in Year 2, week 20."
    lead: (townCount, week) => `Everything we measure ${everyTown(townCount, 'in the town', 'in both towns', 'in every town')}, in ${week}.`,
    hint: 'The timeline above still works: drag it and every number here follows.',
    towns: 'The towns and their rules',
    back: 'Back to the towns',
    // Under a live town's name once its connection is gone; its numbers stay as they were.
    lost: week => (week ? `lost its connection in ${week}` : 'lost its connection before its first week'),
    jump: 'Jump to a group',
    jumpRules: 'Rules in force',
    jumpGlance: 'This week',
    key: {
      label: 'How to read the charts',
      warm: `Setting up: weeks 1 to ${WARMUP_TICKS}`,
      now: 'This week',
      future: 'Weeks still to come',
    },
    tap: 'Tap any chart to see it big.',
    seeBig: 'See it big',
    backToNumbers: 'Back to all the numbers',
    // A tile chart's text alternative, one sentence per town: its first real
    // week (or first week) and the week shown.
    trend: (town, from, fromWeek, to, toWeek) => `${town}: ${from} in ${fromWeek}, ${to} in ${toWeek}.`,
    trendOne: (town, value, week) => `${town}: ${value} in ${week}.`,
    rules: {
      title: 'Rules in force',
      lead: (townCount, differences) => {
        if (townCount < 2) return "The town hall's rules this week."
        const intro = "The town hall's rules in each town this week."
        if (!differences.length) return `${intro} ${townCount === 2 ? 'Both towns run' : 'Every town runs'} the same rules.`
        const count = differences.length === 1 ? 'one rule' : `${numberWord(differences.length)} rules`
        return `${intro} The towns differ in ${count}: ${joinPhrases(differences)}.`
      },
      rule: 'Rule',
      // Each lever's row name, from mockup 06; its help is LEVERS[lever].help.
      names: {
        wage_tax_rate: 'Tax on wages',
        profit_tax_rate: 'Tax on profits',
        investment_tax_rate: 'Tax on investment',
        minimum_wage_policy: 'Minimum wage',
        benefit_level: 'Help for people out of work',
        social_spending: 'Social spending',
        public_works: 'Public works jobs',
        infrastructure_spending: 'Spending on roads and buildings',
        technology_spending: 'Spending on technology',
        sector_subsidy_target: 'Subsidy goes to',
        sector_subsidy_level: 'Business subsidy',
        bailout_policy: 'Bailouts',
        bailout_target: 'Bailouts go to',
        bailout_budget: 'Bailout budget',
        price_stabilization_target: 'Price controls apply to',
        price_stabilization_level: 'Price controls',
        rent_stabilization_level: 'Rent controls',
      },
      // A folded group: "Same in both towns:" then "Tax on wages: 15% · …".
      same: townCount => (townCount === 2 ? 'Same in both towns:' : 'Same in every town:'),
      setting: (name, value) => `${name}: ${value}`,
      settingsJoin: ' · ',
      differ: n => (n === 1 ? '1 rule is different' : `${n} rules are different`),
      show: 'Show',
      hide: 'Hide',
      differentFrom: town => `different from ${town}`,
      // A change during warm-up is a real change; the story skips it, the table does not.
      changed: (week, was, settingUp) => (settingUp
        ? `changed in ${week}, while the towns were being set up (was ${was})`
        : `changed in ${week} (was ${was})`),
    },
    glance: {
      title: 'This week at a glance',
      // "Eight headline numbers for Year 2, week 20. Town B's differences are
      // counted from Town A, the town with no changes."
      lead: (week, labels, firstUnchanged) => {
        const intro = `${capitalise(numberWord(GLANCE_KEYS.length))} headline numbers for ${week}.`
        if (labels.length < 2) return intro
        const others = labels.length === 2 ? `${labels[1]}'s` : "The other towns'"
        return `${intro} ${others} differences are counted from ${labels[0]}${firstUnchanged ? ', the town with no changes' : ''}.`
      },
      number: 'Number',
      track: townCount => `Where this week sits, from the lowest to the highest ${everyTown(townCount, 'the town', 'either town', 'any town')} has seen`,
      // The track for screen readers: the range, then where each town sits in it.
      trackAlt: (low, high, towns = []) => [
        `The lowest so far is ${low} and the highest is ${high}.`,
        ...towns.map(town => `${town.label}: ${town.value}, ${town.where}.`),
      ].join(' '),
      // `at` is the town's place in the range, 0 (lowest) to 100 (highest).
      where: (at, flat) => {
        if (flat) return 'unchanged so far'
        if (at <= 0) return 'the lowest so far'
        if (at >= 100) return 'the highest so far'
        if (at < 34) return 'near the bottom of the range so far'
        if (at > 66) return 'near the top of the range so far'
        return 'in the middle of the range so far'
      },
      trackWait: 'Shown once the towns are set up.',
    },
    // Titles and blurbs of NUMBER_GROUPS, from mockup 06.
    groups: {
      work: { title: 'Work and pay', blurb: 'Who has a job, what it pays, and how many people were hired or let go.' },
      prices: { title: 'Prices', blurb: 'What things cost in the shops this week, and what a household spent on food.' },
      richpoor: { title: 'Rich and poor', blurb: 'How evenly savings are spread between households.' },
      business: { title: 'Businesses', blurb: 'How many businesses are open, how they are doing, and when they opened or closed.' },
      money: {
        title: 'Money',
        blurb: "The town hall's bank balance, the main taxes it collects and the help it pays families, what businesses sell apart from rent, and the bank's loans.",
      },
      wellbeing: { title: 'Wellbeing', blurb: 'Signs of hardship, and how people feel.' },
    },
  },
}
