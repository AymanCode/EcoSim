// Numbers and events into plain sentences. Pure functions over arms from
// data/session.js; all wording lives here or in catalog.js.

import { METRICS, NO_CHANGES, describePolicy, formatMetric, formatMoney, joinPhrases, leverName, leverValuePhrase } from './catalog.js'
import { firmDisplayName, householdName as defaultHouseholdName } from './names.js'
import { householdState, snapshotAt, valueAt } from './data/derive.js'

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

// Several events of one kind in the same week read as one counted sentence.
// Counts go by distinct household or business where the events name one.
const COUNTED = {
  firm_opened: n => `${n} new businesses opened.`,
  firm_closed: n => `${n} businesses closed.`,
  hired: n => `${n} people found work.`,
  laid_off: n => `${n} people lost their jobs.`,
  care_denied: n => `${n} people couldn't afford a doctor.`,
  care_completed: n => `${n} people saw a doctor.`,
  loan_default: n => `${n} loans went unpaid.`,
}

const COUNTED_REGIMES = {
  eviction: n => `${n} households lost their home.`,
  failed_hiring: n => `${n} businesses couldn't fill their open jobs.`,
  firm_distress_enter: n => `${n} businesses are struggling to pay their bills.`,
  firm_distress_exit: n => `${n} businesses are back on their feet.`,
  firm_bankrupt: n => `${n} businesses went bankrupt.`,
}

const SHORTAGES = {
  shortage_regime_enter: goods => `The town started running short of ${goods}.`,
  shortage_regime_exit: goods => `The shortages of ${goods} eased.`,
}

function distinctCount(events) {
  const who = (event, i) => (known(event.householdId) ? `h${event.householdId}` : known(event.firmId) ? `f${event.firmId}` : `e${i}`)
  return new Set(events.map(who)).size
}

export function eventGroupSentence(events, names = {}) {
  const list = (events ?? []).filter(Boolean)
  if (list.length <= 1) return eventSentence(list[0], names)
  const [first] = list
  if (first.type === 'regime' && SHORTAGES[first.text]) {
    const goods = [...new Set(list.map(event => SECTOR_NOUNS[event.sector] ?? (event.sector ? String(event.sector).toLowerCase() : null)).filter(Boolean))]
    return goods.length > 1 ? SHORTAGES[first.text](joinPhrases(goods)) : eventSentence(first, names)
  }
  const n = distinctCount(list)
  if (n <= 1) return eventSentence(first, names)
  const counted = first.type === 'regime' ? COUNTED_REGIMES[first.text] : COUNTED[first.type]
  if (counted) return counted(n)
  if (first.type === 'policy_changed' || first.type === 'shock') return eventSentence(first, names)
  return `${eventSentence(first, names).replace(/\.$/, '')}, ${n} times.`
}

// The question the header asks about an experiment.
export function experimentQuestion(arms) {
  if (!arms?.length) return ''
  if (arms.length === 1) return `What happens in ${arms[0].label}?`
  const policy = describePolicy(arms[1].setup?.initial_policy)
  if (policy === NO_CHANGES) return `What happens when ${arms.length === 2 ? 'two' : 'several'} towns keep the same rules?`
  return `What happens with ${policy}?`
}

// A policy marker's label on the story chart, as short lines.
export function policyMarkerLabel(arm, change) {
  return [`${arm?.label ?? 'The town'} switched to`, describePolicy({ [change.policy]: change.value })]
}

// The story chart's opening note for matched towns.
export function startNote(armCount) {
  if (armCount < 2) return null
  return armCount === 2 ? 'Both towns start from the same place' : 'All the towns start from the same place'
}

const weeks = n => `${n} week${n === 1 ? '' : 's'}`

// What a household card says when nothing has happened to it lately.
export function householdStateSentence(subject, { employerName } = {}) {
  const arrears = Number(subject?.rentArrears) || 0
  switch (householdState(subject)) {
    case 'home':
      return 'Has no home right now.'
    case 'work':
      if (arrears >= 1) return `Working, but ${formatMoney(arrears)} behind on rent.`
      return employerName ? `Steady work at ${employerName}.` : 'In steady work.'
    case 'look': {
      const duration = Math.round(Number(subject?.unemploymentDuration) || 0)
      return duration > 0 ? `Has been looking for work for ${weeks(duration)}.` : 'Just started looking for work.'
    }
    default:
      return 'Not working right now.'
  }
}
