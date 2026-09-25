// Numbers and events into plain sentences. Pure functions over arms from
// data/session.js; all wording lives here or in catalog.js.

import { METRICS, NO_CHANGES, describePolicy, formatMetric, joinPhrases, leverName, leverValuePhrase } from './catalog.js'
import { firmDisplayName, householdName as defaultHouseholdName } from './names.js'
import { snapshotAt, valueAt } from './data/derive.js'

const WEEKS_PER_YEAR = 52
const OUT = 'peopleOutOfWorkPer100'
const PAY = 'typicalWeeklyPay'

export function weekLabel(tick) {
  const t = Math.floor(Number(tick))
  if (!(t >= 1)) return 'The start'
  return `Year ${Math.floor((t - 1) / WEEKS_PER_YEAR) + 1}, week ${((t - 1) % WEEKS_PER_YEAR) + 1}`
}

const known = value => value !== null && value !== undefined

// Gaps under these read as "about the same".
const OUT_SAME = 0.5
const PAY_SAME = 0.01
const isSame = (diff, threshold) => diff === 0 || Math.abs(diff) < threshold

function outClause(town, first, value, base) {
  const pair = `(${formatMetric(OUT, value)} vs ${formatMetric(OUT, base)})`
  if (isSame(value - base, OUT_SAME)) return { tone: 0, text: `${town} has about the same number of people out of work as ${first} ${pair}` }
  if (value < base) return { tone: 1, text: `${town} has fewer people out of work than ${first} ${pair}` }
  return { tone: -1, text: `${town} has more people out of work than ${first} ${pair}` }
}

function payClause(value, base) {
  const pair = `(${formatMetric(PAY, value)} vs ${formatMetric(PAY, base)})`
  if (isSame(value - base, PAY_SAME * Math.abs(base))) return { tone: 0, text: `pays about the same ${pair}` }
  if (value > base) return { tone: 1, text: `pays more ${pair}` }
  return { tone: -1, text: `pays less ${pair}` }
}

function compareSentence(first, arm, tick) {
  const out = [valueAt(arm, OUT, tick), valueAt(first, OUT, tick)]
  const pay = [valueAt(arm, PAY, tick), valueAt(first, PAY, tick)]
  const outPart = out.every(known) ? outClause(arm.label, first.label, ...out) : null
  const payPart = pay.every(known) ? payClause(...pay) : null
  if (outPart && payPart) {
    const joiner = outPart.tone * payPart.tone < 0 ? ' but ' : ' and '
    return `${outPart.text}${joiner}${payPart.text}.`
  }
  if (outPart) return `${outPart.text}.`
  if (payPart) return `${arm.label} ${payPart.text}.`
  return null
}

export function leadSentence(arms, tick) {
  if (!arms?.length) return ''
  if (arms.length === 1) {
    const [arm] = arms
    const out = valueAt(arm, OUT, tick)
    const pay = valueAt(arm, PAY, tick)
    if (!known(out) && !known(pay)) return `${weekLabel(tick)}. ${arm.label} hasn't reported yet.`
    return `${weekLabel(tick)}. ${formatMetric(OUT, out)} people are out of work and typical weekly pay is ${formatMetric(PAY, pay)}.`
  }
  const [first, ...rest] = arms
  const sentences = rest.map(arm => compareSentence(first, arm, tick)).filter(Boolean)
  if (!sentences.length) return `${weekLabel(tick)}. The towns haven't reported yet.`
  return sentences.join(' ')
}

// What the verdict weighs, most important first. `threshold` is absolute, or
// relative to the first town's value when `relative` is set.
const FINDINGS = [
  { key: OUT, threshold: OUT_SAME, more: 'more people out of work', less: 'fewer people out of work' },
  { key: PAY, threshold: PAY_SAME, relative: true, more: 'higher pay', less: 'lower pay' },
  { key: 'priceFood', threshold: 0.01, relative: true, more: 'dearer food', less: 'cheaper food' },
  { key: 'gini', threshold: 0.01, more: 'a wider gap between rich and poor', less: 'a smaller gap between rich and poor' },
  { key: 'homelessHouseholds', threshold: 1, more: 'more households without a home', less: 'fewer households without a home' },
  {
    key: 'firmsClosed',
    threshold: 1,
    better: 'lower',
    read: (arm, tick) => snapshotAt(arm, tick)?.firmsClosed?.length ?? null,
    more: 'more businesses closed',
    less: 'fewer businesses closed',
  },
]
const MAX_PER_SIDE = 3

function findings(first, arm, tick) {
  const goods = []
  const bads = []
  for (const finding of FINDINGS) {
    const read = finding.read ?? ((a, t) => valueAt(a, finding.key, t))
    const value = read(arm, tick)
    const base = read(first, tick)
    if (!known(value) || !known(base)) continue
    const diff = value - base
    const threshold = finding.relative ? finding.threshold * Math.abs(base) : finding.threshold
    if (isSame(diff, threshold)) continue
    const better = finding.better ?? METRICS[finding.key]?.better
    if (!better) continue
    const good = better === 'lower' ? diff < 0 : diff > 0
    ;(good ? goods : bads).push(diff > 0 ? finding.more : finding.less)
  }
  return { goods: goods.slice(0, MAX_PER_SIDE), bads: bads.slice(0, MAX_PER_SIDE) }
}

function movement(key, from, to) {
  const a = formatMetric(key, from)
  const b = formatMetric(key, to)
  return a === b ? `stayed at ${b}` : `went from ${a} to ${b}`
}

function singleTownVerdict(arm, tick) {
  const start = arm.ticks?.[0]
  if (!known(start) || tick <= start) return `${arm.label} has just started.`
  return `So far in ${arm.label}, people out of work ${movement(OUT, valueAt(arm, OUT, start), valueAt(arm, OUT, tick))}`
    + ` and typical weekly pay ${movement(PAY, valueAt(arm, PAY, start), valueAt(arm, PAY, tick))}.`
}

// Plain-words verdict on the second town against the first, ending with a
// question about the second town's policy. One town gets a summary instead.
export function verdict(arms, tick) {
  if (!arms?.length) return ''
  if (arms.length === 1) return singleTownVerdict(arms[0], tick)
  const [first, second] = arms
  const { goods, bads } = findings(first, second, tick)
  let summary
  if (!goods.length && !bads.length) summary = `So far, ${second.label} and ${first.label} look about the same.`
  else if (!goods.length || !bads.length) summary = `So far, ${second.label} has ${joinPhrases(goods.length ? goods : bads)} than ${first.label}.`
  else summary = `So far, ${second.label} has ${joinPhrases(goods)} than ${first.label}, but ${joinPhrases(bads)}.`
  const policy = describePolicy(second.setup?.initial_policy)
  const question = policy === NO_CHANGES ? 'Would you change anything?' : `Would you keep ${policy}?`
  return `${summary} ${question}`
}

const SHOCKS = {
  shock_demand: 'Households had an unexpected windfall or bill.',
  shock_supply: 'A supply problem hit some businesses.',
  shock_health: 'An illness went around.',
}

const SECTOR_NOUNS = {
  Food: 'food', Housing: 'housing', Services: 'services', Healthcare: 'healthcare', PublicWorks: 'public works',
}

// Friendlier sentences for the regime events the economy emits; anything else
// falls back to its type code read aloud.
const REGIMES = {
  eviction: ({ household }) => `${household ?? 'A household'} lost their home.`,
  failed_hiring: ({ firm }) => (firm ? `${firm} couldn't fill its open jobs.` : null),
  firm_distress_enter: ({ firm }) => (firm ? `${firm} is struggling to pay its bills.` : null),
  firm_distress_exit: ({ firm }) => (firm ? `${firm} is back on its feet.` : null),
  firm_bankrupt: ({ firm }) => (firm ? `${firm} went bankrupt.` : null),
  shortage_regime_enter: ({ sector }) => (sector ? `The town started running short of ${sector}.` : null),
  shortage_regime_exit: ({ sector }) => (sector ? `The shortage of ${sector} eased.` : null),
}

const FALLBACK = 'Something changed in the town.'

function readAloud(code) {
  const text = String(code ?? '').replace(/_/g, ' ').trim()
  if (!text) return FALLBACK
  return `${text.charAt(0).toUpperCase()}${text.slice(1)}.`
}

function resolve(resolver, fallback, ...args) {
  if (typeof resolver === 'function') return resolver(...args)
  if (typeof resolver === 'string') return resolver
  return fallback(...args)
}

// names = { householdName: id => string, firmName: firm => string }, each
// optional (a plain string also works); defaults are the names.js names.
export function eventSentence(event, names = {}) {
  if (!event) return FALLBACK
  const household = known(event.householdId) ? resolve(names.householdName, defaultHouseholdName, event.householdId) : null
  const hasFirm = known(event.firmId) || Boolean(event.firmName)
  const firm = hasFirm
    ? resolve(names.firmName, firmDisplayName, { id: event.firmId, name: event.firmName, sector: event.sector ?? null })
    : null
  const who = household ?? 'Someone'

  switch (event.type) {
    case 'firm_opened':
      return `${firm ?? 'A new business'} opened.`
    case 'firm_closed':
      return `${firm ?? 'A business'} closed.`
    case 'hired':
      return firm ? `${who} started work at ${firm}.` : `${who} found a job.`
    case 'laid_off':
      return firm ? `${who} lost their job at ${firm}.` : `${who} lost their job.`
    case 'care_denied':
      return `${who} couldn't afford a doctor.`
    case 'care_completed':
      return `${who} saw a doctor.`
    case 'policy_changed': {
      const raw = String(event.text ?? '')
      const at = raw.indexOf('=')
      if (at < 1) return 'The town hall changed a rule.'
      const lever = raw.slice(0, at)
      return `The town hall set ${leverName(lever)} to ${leverValuePhrase(lever, raw.slice(at + 1))}.`
    }
    case 'loan_default':
      return 'A loan went unpaid.'
    case 'shock':
      return SHOCKS[event.text] ?? 'Something unexpected happened.'
    case 'regime': {
      const sector = SECTOR_NOUNS[event.sector] ?? (event.sector ? String(event.sector).toLowerCase() : null)
      return REGIMES[event.text]?.({ household, firm, sector }) ?? readAloud(event.text)
    }
    default:
      return FALLBACK
  }
}
