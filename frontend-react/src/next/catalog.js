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
    meaning: 'What the town hall has in the bank; negative means it owes.',
    format: 'money',
    better: null,
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
    name: 'Firms open',
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
}

export function formatMetric(key, value) {
  if (!isNumber(value)) return NOT_MEASURED
  const format = FORMATTERS[METRICS[key]?.format] ?? FORMATTERS.count
  return format(value)
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
// Rate levers take any value within their bounds, so they phrase it as a percent.
export const LEVERS = {
  wage_tax_rate: { name: 'the tax on wages', kind: 'rate', values: {}, policy: rate => `a ${percent(rate)} tax on wages` },
  profit_tax_rate: { name: 'the tax on profits', kind: 'rate', values: {}, policy: rate => `a ${percent(rate)} tax on profits` },
  investment_tax_rate: { name: 'the tax on investment', kind: 'rate', values: {}, policy: rate => `a ${percent(rate)} tax on investment` },
  benefit_level: {
    name: 'help for people out of work',
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
    values: { off: 'off', on: 'on' },
    policy: { off: 'no public works jobs', on: 'public works jobs' },
  },
  minimum_wage_policy: {
    name: 'the minimum wage',
    values: { low: 'low', neutral: 'normal', high: 'high' },
    policy: { low: 'a lower minimum wage', neutral: 'the usual minimum wage', high: 'a higher minimum wage' },
  },
  sector_subsidy_target: {
    name: 'the subsidy target',
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
    values: { 0: 'none', 10: '10%', 25: '25%', 50: '50%' },
    policy: { 0: 'no business subsidy', 10: 'a 10% business subsidy', 25: 'a 25% business subsidy', 50: 'a 50% business subsidy' },
  },
  price_stabilization_target: {
    name: 'the price-control target',
    values: { none: 'nothing', food: 'food', services: 'services', healthcare: 'healthcare' },
    policy: {
      none: 'no price-control target',
      food: 'price controls on food',
      services: 'price controls on services',
      healthcare: 'price controls on healthcare',
    },
  },
  price_stabilization_level: { name: 'price controls', values: STABILISATION, policy: controlPolicy('price') },
  rent_stabilization_level: { name: 'rent controls', values: STABILISATION, policy: controlPolicy('rent') },
  infrastructure_spending: {
    name: 'spending on roads and buildings', values: SPENDING, policy: spendingPolicy('spending on roads and buildings'),
  },
  technology_spending: { name: 'spending on technology', values: SPENDING, policy: spendingPolicy('spending on technology') },
  social_spending: { name: 'social spending', values: SPENDING, policy: spendingPolicy('social spending') },
  bailout_policy: {
    name: 'bailouts',
    values: { off: 'off', sector: 'one sector only', all: 'any business' },
    policy: { off: 'no bailouts', sector: 'bailouts for one sector', all: 'bailouts for any business' },
  },
  bailout_target: {
    name: 'the bailout target',
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
    levers: ['bailout_policy', 'bailout_target', 'bailout_budget'],
    applies: p => p.bailout_policy !== 'off' && p.bailout_target != null,
    phrase: p => {
      const who = p.bailout_policy === 'all' ? 'any business' : (FIRM_TARGETS[p.bailout_target] ?? p.bailout_target)
      const budget = Number(p.bailout_budget)
      return `bailouts for ${who}${budget > 0 ? ` up to ${formatMoney(budget)}` : ''}`
    },
  },
]

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
    const group = GROUPS.find(g => g.levers.includes(lever) && g.levers.every(l => l === 'bailout_budget' || policy[l] !== undefined))
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

const counted = (n, one, many = `${one}s`) => `${n} ${n === 1 ? one : many}`

// Notes use **word** for the bold lead-in the panel renders.
function howToNotes(armCount) {
  const tick = armCount >= 2
    ? `A **tick** is one week. ${armCount === 2 ? 'Both towns' : 'All the towns'} run the same week at the same time, from the same starting point, so any difference you see is caused by the rules.`
    : 'A **tick** is one week. The town moves forward a week at a time, and the timeline takes you back to any week you have already seen.'
  const rules = armCount >= 2
    ? `The **first town** keeps the usual rules. ${armCount === 2 ? 'The second changes' : 'Each of the others changes'} the ones named under its title, and that change is what the towns are testing.`
    : "The **town hall** sets the rules: taxes, benefits, the minimum wage. The ones in force are named under the town's title."
  return [
    tick,
    rules,
    'Every **house** is 1 in 100 households. Green ones have someone working, amber ones are looking for work, red ones have lost their home. The household cards introduce a few of the families.',
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
    moreBuildings: n => `+${n} more`,
    outOfWork: 'out of work',
    typicalPay: 'typical weekly pay',
    firms: n => counted(n, 'firm'),
    firmStates: (struggling, closed) => `${struggling} struggling, ${closed} closed`,
    altHouses: (work, look, home) => `Out of every 100 households: ${work} working, ${look} looking for work, ${home} lost their home.`,
    altFirms: (open, struggling, closed) => `${counted(open, 'firm')} open: ${struggling} struggling. ${closed} closed in the last year.`,
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
    following: 'Following',
    followLabel: (visible, name) => `${visible} ${name}`,
    showOthers: 'Show me four others',
    empty: 'No households in the sample yet.',
  },
  feed: {
    title: "What's happening",
    subtitle: 'newest first',
    when: (week, town) => `${week}, ${town}`,
    empty: 'Nothing has happened yet.',
  },
  howTo: {
    title: 'How to read this',
    subtitle: 'for first-timers',
    notes: howToNotes,
  },
}
