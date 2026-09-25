// Numbers and events into plain sentences. Pure functions over arms from
// data/session.js; all wording lives here or in catalog.js.

import {
  COPY, METRICS, NO_CHANGES, WARMUP_TICKS, describePolicy, formatMetric, formatMoney, joinPhrases, leverName, leverValuePhrase, shownValue,
} from './catalog.js'
import { firmDisplayName, householdName as defaultHouseholdName } from './names.js'
import { householdState, rulesAt, rulesDiff, snapshotAt, tickIndexAt, valueAt } from './data/derive.js'

const WEEKS_PER_YEAR = 52
const OUT = 'peopleOutOfWorkPer100'
const PAY = 'typicalWeeklyPay'
const FIRST_REAL_WEEK = WARMUP_TICKS + 1

export function weekLabel(tick) {
  const t = Math.floor(Number(tick))
  if (!(t >= 1)) return 'The start'
  return `Year ${Math.floor((t - 1) / WEEKS_PER_YEAR) + 1}, week ${((t - 1) % WEEKS_PER_YEAR) + 1}`
}

const known = value => value !== null && value !== undefined
const inWarmUp = tick => tick <= WARMUP_TICKS
const towns = count => (count === 2 ? 'Both towns' : 'All the towns')
const hasReported = (arm, tick) => known(arm?.ticks?.[0]) && arm.ticks[0] <= tick

// The lead compares figures as the page shows them, so "42 in 100 vs 42 in 100"
// always reads "about the same".
function outClause(town, first, value, base) {
  const pair = `(${formatMetric(OUT, value)} vs ${formatMetric(OUT, base)})`
  const [shown, shownBase] = [shownValue(OUT, value), shownValue(OUT, base)]
  if (shown === shownBase) return { tone: 0, text: `${town} has about the same number of people out of work as ${first} ${pair}` }
  if (shown < shownBase) return { tone: 1, text: `${town} has fewer people out of work than ${first} ${pair}` }
  return { tone: -1, text: `${town} has more people out of work than ${first} ${pair}` }
}

function payClause(value, base) {
  const pair = `(${formatMetric(PAY, value)} vs ${formatMetric(PAY, base)})`
  const [shown, shownBase] = [shownValue(PAY, value), shownValue(PAY, base)]
  if (shown === shownBase) return { tone: 0, text: `pays about the same ${pair}` }
  if (shown > shownBase) return { tone: 1, text: `pays more ${pair}` }
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

// How a sentence names a figure: `plain` before "went from", `measure` before "is".
const SUBJECTS = {
  [OUT]: { plain: 'people out of work', measure: 'the number of people out of work' },
  [PAY]: { plain: 'typical weekly pay', measure: 'typical weekly pay' },
}
const capitalise = text => `${text.charAt(0).toUpperCase()}${text.slice(1)}`

function currentPhrase(key, value) {
  if (!known(value)) return `${SUBJECTS[key].measure} is not measured yet`
  return key === OUT ? `${formatMetric(OUT, value)} people are out of work` : `${SUBJECTS[key].measure} is ${formatMetric(key, value)}`
}

export function leadSentence(arms, tick) {
  if (!arms?.length) return ''
  if (arms.length === 1) {
    const [arm] = arms
    const out = valueAt(arm, OUT, tick)
    const pay = valueAt(arm, PAY, tick)
    if (!hasReported(arm, tick) || (!known(out) && !known(pay))) return `${weekLabel(tick)}. ${arm.label} hasn't reported yet.`
    if (inWarmUp(tick)) return `${weekLabel(tick)}. ${arm.label} is still being set up; the real economy starts in week ${FIRST_REAL_WEEK}.`
    return `${weekLabel(tick)}. ${capitalise(currentPhrase(OUT, out))} and ${currentPhrase(PAY, pay)}.`
  }
  if (!arms.every(arm => hasReported(arm, tick))) return `${weekLabel(tick)}. The towns haven't reported yet.`
  if (inWarmUp(tick)) {
    return `${weekLabel(tick)}. ${towns(arms.length)} are still being set up and start the same; the real economy starts in week ${FIRST_REAL_WEEK}.`
  }
  const [first, ...rest] = arms
  const sentences = rest.map(arm => compareSentence(first, arm, tick)).filter(Boolean)
  if (!sentences.length) return `${weekLabel(tick)}. The towns haven't reported yet.`
  return sentences.join(' ')
}

// The verdict weighs averages over the last three months of the real economy.
const WINDOW = 13
const OUT_SAME = 0.5
const PAY_SAME = 0.01

// What the verdict weighs, most important first. `threshold` is absolute, or
// relative to the first town's average when `relative` is set, or a function
// of the town's households.
const FINDINGS = [
  { key: OUT, threshold: OUT_SAME, more: 'more people out of work', less: 'fewer people out of work' },
  { key: PAY, threshold: PAY_SAME, relative: true, more: 'higher pay', less: 'lower pay' },
  { key: 'priceFood', threshold: 0.01, relative: true, more: 'higher food prices', less: 'lower food prices' },
  { key: 'gini', threshold: 0.01, more: 'a wider gap between rich and poor', less: 'a smaller gap between rich and poor' },
  {
    key: 'homelessHouseholds',
    threshold: ({ households }) => (known(households) ? 0.01 * households : 1),
    more: 'more households without a home',
    less: 'fewer households without a home',
  },
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

function windowTicks(arm, tick) {
  return (arm.ticks ?? []).filter(t => t > WARMUP_TICKS && t <= tick && t > tick - WINDOW)
}

function average(read, arm, ticks) {
  const values = ticks.map(t => read(arm, t)).filter(known)
  return values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : null
}

const readKey = key => (arm, tick) => valueAt(arm, key, tick)

function findings(first, arm, ticks) {
  const goods = []
  const bads = []
  const households = average(readKey('householdsTotal'), first, ticks) ?? first.setup?.num_households ?? null
  for (const finding of FINDINGS) {
    const read = finding.read ?? readKey(finding.key)
    const value = average(read, arm, ticks)
    const base = average(read, first, ticks)
    if (!known(value) || !known(base)) continue
    const diff = value - base
    const threshold = typeof finding.threshold === 'function'
      ? finding.threshold({ households })
      : finding.relative ? finding.threshold * Math.abs(base) : finding.threshold
    if (diff === 0 || Math.abs(diff) < threshold) continue
    const better = finding.better ?? METRICS[finding.key]?.better
    if (!better) continue
    const good = better === 'lower' ? diff < 0 : diff > 0
    ;(good ? goods : bads).push(diff > 0 ? finding.more : finding.less)
  }
  return { goods: goods.slice(0, MAX_PER_SIDE), bads: bads.slice(0, MAX_PER_SIDE) }
}

function movement(key, from, to) {
  if (!known(to)) return `${SUBJECTS[key].measure} is not measured yet`
  const b = formatMetric(key, to)
  if (!known(from)) return `${SUBJECTS[key].measure} is ${b}`
  const a = formatMetric(key, from)
  return a === b ? `${SUBJECTS[key].plain} stayed at ${b}` : `${SUBJECTS[key].plain} went from ${a} to ${b}`
}

function singleTownVerdict(arm, tick) {
  if (!hasReported(arm, tick)) return `${arm.label} has just started.`
  if (inWarmUp(tick)) return `${arm.label} is still being set up. Its economy starts in week ${FIRST_REAL_WEEK}.`
  const start = (arm.ticks ?? []).find(t => t > WARMUP_TICKS)
  if (!known(start) || tick <= start) return `${arm.label}'s economy has just started.`
  return `So far in ${arm.label}, ${movement(OUT, valueAt(arm, OUT, start), valueAt(arm, OUT, tick))}`
    + ` and ${movement(PAY, valueAt(arm, PAY, start), valueAt(arm, PAY, tick))}.`
}

// How one town compares with the first over `ticks`; `when` opens the
// sentence ("Over the last three months, ...") or is null.
function townSummary(when, first, arm, ticks) {
  const { goods, bads } = findings(first, arm, ticks)
  const lead = when ? `${when}, ` : ''
  if (!goods.length && !bads.length) return `${lead}${arm.label} and ${first.label} look about the same.`
  if (!goods.length || !bads.length) return `${lead}${arm.label} has ${joinPhrases(goods.length ? goods : bads)} than ${first.label}.`
  return `${lead}${arm.label} has ${joinPhrases(goods)} than ${first.label}, but ${joinPhrases(bads)}.`
}

// The weeks after warm-up, up to `tick`, in which a town's hall changed its rules.
function changeWeeks(arm, tick) {
  const weeks = new Set()
  for (const change of arm.policyChanges ?? []) {
    if (change.tick > tick) break
    if (!inWarmUp(change.tick)) weeks.add(change.tick)
  }
  return [...weeks]
}

// "Town A changed its rules in Year 2, week 5." for a town whose rules changed
// while the real economy ran, or null.
function changedClause(arm, tick) {
  const weeks = changeWeeks(arm, tick)
  if (!weeks.length) return null
  const last = weekLabel(weeks[weeks.length - 1])
  if (weeks.length === 1) return `${arm.label} changed its rules in ${last}.`
  const times = weeks.length === 2 ? 'twice' : `${weeks.length} times`
  return `${arm.label} changed its rules ${times}, most recently in ${last}.`
}

// Plain-words verdict on each town against the first over the last three
// months. With two towns it ends with a question about the rules the second
// town has in force at `tick` that the first does not; with more, a general
// question. A town whose rules changed during the run says so. One town gets
// a summary instead.
export function verdict(arms, tick) {
  if (!arms?.length) return ''
  if (arms.length === 1) return singleTownVerdict(arms[0], tick)
  const [first, ...rest] = arms
  const gap = arms.length === 2 ? describePolicy(rulesDiff(rulesAt(rest[0], tick), rulesAt(first, tick))) : NO_CHANGES
  if (inWarmUp(tick)) {
    const next = gap === NO_CHANGES ? 'how they compare' : `what ${gap} does`
    return `${towns(arms.length)} are still being set up and start the same. From week ${FIRST_REAL_WEEK} you can see ${next}.`
  }
  const ticks = windowTicks(first, tick)
  const when = ticks.length >= WINDOW ? 'Over the last three months' : 'So far'
  const summaries = rest.map((arm, i) => townSummary(i === 0 ? when : null, first, arm, ticks))
  const changed = arms.map(arm => changedClause(arm, tick)).filter(Boolean)
  let question
  if (arms.length > 2) question = "Which town's rules would you keep?"
  else question = gap === NO_CHANGES ? 'Would you change anything?' : `Would you keep ${gap}?`
  return [...summaries, ...changed, question].join(' ')
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
  eviction: ({ household, lostHome }) => (lostHome
    ? `${household ?? 'A household'} lost their home.`
    : `${household ?? 'A household'} had to move after falling behind on rent.`),
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

// names = { householdName: id => string, firmName: firm => string, lostHome },
// each optional (a plain string also works for a name); defaults are the
// names.js names. An eviction only reads "lost their home" with `lostHome`
// set, when the household has no home at that week.
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
      return REGIMES[event.text]?.({ household, firm, sector, lostHome: names.lostHome === true }) ?? readAloud(event.text)
    }
    default:
      return FALLBACK
  }
}

// Several events of one kind in the same week read as one counted sentence.
// Counts go by distinct household or business where the events name one.
// Household events only reach the browser for the tracked sample.
const FAMILIES = {
  hired: 'found work',
  laid_off: 'lost their jobs',
  care_denied: "couldn't afford a doctor",
  care_completed: 'saw a doctor',
  loan_default: "couldn't repay a loan",
}
const FAMILY_REGIMES = {
  eviction: 'had to move after falling behind on rent',
}
const families = (n, verb) => `${n} of the families we follow ${verb}.`

const COUNTED = {
  firm_opened: n => `${n} new businesses opened.`,
  firm_closed: n => `${n} businesses closed.`,
  loan_default: n => `${n} loans went unpaid.`,
}

const COUNTED_REGIMES = {
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
  const family = first.type === 'regime' ? FAMILY_REGIMES[first.text] : FAMILIES[first.type]
  if (family && list.every(event => known(event.householdId))) return families(n, family)
  const counted = first.type === 'regime' ? COUNTED_REGIMES[first.text] : COUNTED[first.type]
  if (counted) return counted(n)
  if (first.type === 'policy_changed' || first.type === 'shock') return eventSentence(first, names)
  return `${eventSentence(first, names).replace(/\.$/, '')}, ${n} times.`
}

// Town-wide hires and lay-offs, from a week's `eventCounts`, when at least
// `threshold` people were involved; otherwise null.
export function townWideSentence(counts, threshold = 20) {
  const hired = Number(counts?.hired) || 0
  const laidOff = Number(counts?.laidOff) || 0
  const found = hired >= threshold
  const lost = laidOff >= threshold
  if (found && lost) return `Across town, ${hired} people found work and ${laidOff} lost their jobs this week.`
  if (found) return `Across town, ${hired} people found work this week.`
  if (lost) return `Across town, ${laidOff} people lost their jobs this week.`
  return null
}

const COUNT_WORDS = ['no', 'one', 'two', 'three', 'four']

// The question the header asks about an experiment: its rules as set up, so
// it stays the same when the town hall changes rules during the run.
export function experimentQuestion(arms) {
  if (!arms?.length) return ''
  if (arms.length === 1) return `What happens in ${arms[0].label}?`
  const count = COUNT_WORDS[arms.length] ?? String(arms.length)
  if (arms.length > 2) {
    const rules = arms.map(arm => describePolicy(arm.setup?.initial_policy))
    return rules.every(rule => rule === rules[0])
      ? `What happens when ${count} towns keep the same rules?`
      : `What happens when ${count} towns try different rules?`
  }
  const policy = describePolicy(arms[1].setup?.initial_policy)
  if (policy === NO_CHANGES) return `What happens when ${count} towns keep the same rules?`
  return `What happens with ${policy}?`
}

// Policy change records ({ policy, value }, the value as the event's text) as
// one noun phrase; a later record for the same lever wins.
function changesPhrase(changes) {
  return describePolicy(Object.fromEntries(changes.map(change => [change.policy, change.value])))
}

// A town's policy change records that pass `keep`, grouped by the week they
// took effect, as [week, changes] in order: one town hall change can move
// several levers in one week, and it reads as one change.
export function policyChangesByWeek(arm, keep = () => true) {
  const byWeek = new Map()
  for (const change of arm?.policyChanges ?? []) {
    if (keep(change)) byWeek.set(change.tick, [...(byWeek.get(change.tick) ?? []), change])
  }
  return [...byWeek]
}

// A policy marker's label on the story chart, as short lines, for the
// changes of one week.
export function policyMarkerLabel(arm, changes) {
  return [`${arm?.label ?? 'The town'} switched to`, changesPhrase(changes)]
}

// Moments: something notable in a town lately, as one line each. Only the
// real economy counts, so a warm-up week is never the change nor the week it
// is compared with.
const MOMENTS_SHOWN = 3
const RULE_WEEKS = 6
const LOOK_BACK = 4
const MARKS = [10, 20, 30]
const KINDS = ['rule', 'richest', 'milestone']

// The id names the week of the change, so a moment keeps its id (and its
// chip) for as long as it lasts.
const moment = (kind, arm, tick, text) => ({ id: `${kind}:${arm.label}:${tick}`, kind, label: arm.label, color: arm.color, tick, text })

// One moment per week the town hall changed rules in the last six weeks.
function ruleMoments(arm, tick) {
  const recent = change => !inWarmUp(change.tick) && change.tick <= tick && change.tick > tick - RULE_WEEKS
  return policyChangesByWeek(arm, recent)
    .map(([week, changes]) => moment('rule', arm, week, COPY.moments.rule(arm.label, changesPhrase(changes))))
}

// The recorded weeks to compare at `tick`: the week in force four weeks
// earlier (the first real week at the earliest), then every recorded week
// after it up to `tick`. Empty when there is nothing to compare yet.
function lookBack(arm, tick) {
  const from = Math.max(tick - LOOK_BACK, FIRST_REAL_WEEK)
  const ticks = arm.ticks ?? []
  const weeks = []
  for (let i = ticks.length - 1; i >= 0; i -= 1) {
    if (ticks[i] > tick) continue
    weeks.unshift(ticks[i])
    if (ticks[i] <= from) break
  }
  return weeks.length >= 2 && weeks[0] <= from && !inWarmUp(weeks[0]) ? weeks : []
}

const cashOf = firm => (typeof firm?.cash === 'number' && Number.isFinite(firm.cash) ? firm.cash : null)

// The richest open business in a week; on a tie the one before keeps the lead.
function leaderOf(snapshot, before) {
  const firms = (snapshot?.firms ?? []).filter(firm => known(cashOf(firm)))
  if (!firms.length) return null
  const most = Math.max(...firms.map(cashOf))
  const kept = before ? firms.find(firm => firm.id === before.id) : null
  return kept && cashOf(kept) === most ? kept : firms.find(firm => cashOf(firm) === most)
}

// A different richest business now than four weeks ago, dated to the week it
// took the lead.
function richestMoment(arm, weeks) {
  const first = leaderOf(arm.snapshots?.[weeks[0]], null)
  let leader = first
  let since = null
  for (const week of weeks.slice(1)) {
    const next = leaderOf(arm.snapshots?.[week], leader)
    if (next?.id !== leader?.id) since = week
    leader = next
  }
  if (!first || !leader || leader.id === first.id) return null
  return moment('richest', arm, since, COPY.moments.richest(firmDisplayName(leader), arm.label))
}

// Where a figure sits against a mark.
const side = (value, mark) => (!known(value) ? null : value > mark ? 'above' : value < mark ? 'below' : 'at')

// A crossing is ignored when the figure left the side it crossed to within
// this many recorded weeks before it, so a figure hovering at a mark gives
// one moment, not one at every flip.
const SETTLE_WEEKS = 12

// Whether the shown figure left `to` (the side of `mark` it has just crossed
// to) in the SETTLE_WEEKS recorded weeks before the week `since`. Only real
// economy weeks count. Reads recorded weeks up to `since` only, so the answer
// is the same at every later tick.
function leftRecently(arm, since, mark, to) {
  const ticks = arm.ticks ?? []
  const at = tickIndexAt(arm, since)
  const shownAt = i => shownValue(OUT, arm.series?.[OUT]?.[i] ?? null)
  for (let i = at - 1; i >= 1 && i >= at - SETTLE_WEEKS; i -= 1) {
    if (inWarmUp(ticks[i - 1])) break
    if (side(shownAt(i - 1), mark) === to && side(shownAt(i), mark) !== to) return true
  }
  return false
}

// People out of work per 100, as the page shows them, now past a mark it was
// not past four weeks ago (or now under one it was not under). A jump across
// several marks names the furthest. Dated to the week it last crossed, and
// dropped when the figure had left that side of the mark in the 12 recorded
// weeks before that crossing.
function milestoneMoment(arm, weeks) {
  const shown = weeks.map(week => shownValue(OUT, valueAt(arm, OUT, week)))
  const [before, after] = [shown[0], shown[shown.length - 1]]
  if (!known(before) || !known(after)) return null
  const passed = MARKS.filter(mark => side(before, mark) !== 'above' && side(after, mark) === 'above')
  const fell = MARKS.filter(mark => side(before, mark) !== 'below' && side(after, mark) === 'below')
  if (!passed.length && !fell.length) return null
  const [mark, to, sentence] = passed.length
    ? [Math.max(...passed), 'above', COPY.moments.passed]
    : [Math.min(...fell), 'below', COPY.moments.fellBelow]
  let since = weeks[weeks.length - 1]
  for (let i = shown.length - 1; i >= 1; i -= 1) {
    if (side(shown[i], mark) === to && side(shown[i - 1], mark) !== to) {
      since = weeks[i]
      break
    }
  }
  if (leftRecently(arm, since, mark, to)) return null
  return moment('milestone', arm, since, sentence(arm.label, mark))
}

// What just happened across the towns at `tick`, newest first, at most three.
// Moment = { id, kind: 'rule'|'richest'|'milestone', label, color, tick, text }
export function moments(arms, tick) {
  const found = []
  ;(arms ?? []).forEach((arm, order) => {
    if (!arm) return
    const weeks = lookBack(arm, tick)
    const own = [...ruleMoments(arm, tick), ...(weeks.length ? [richestMoment(arm, weeks), milestoneMoment(arm, weeks)] : [])]
    for (const item of own) if (item) found.push({ item, order })
  })
  return found
    .sort((a, b) => (b.item.tick - a.item.tick) || (KINDS.indexOf(a.item.kind) - KINDS.indexOf(b.item.kind)) || (a.order - b.order))
    .slice(0, MOMENTS_SHOWN)
    .map(({ item }) => item)
}

// How one town's figure compares with the first town's, in neutral words: no
// better or worse, no colour. Figures are compared as the page shows them, so
// "42 in 100" against "42 in 100" is "about the same". During warm-up the
// towns are still being set up, and their figures say nothing yet. Null when
// either figure is missing (its own cell says it was not measured).
// options = { tick, baseLabel }: the week shown, and the first town's name.
const countWords = new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 })
const points = (n, unit) => `${n} ${unit}${n === 1 ? '' : 's'}`
const DIFFERENCES = {
  per100: (n, up) => `${n} ${up ? 'more' : 'fewer'} in 100`,
  money: (n, up) => `${formatMoney(n)} ${up ? 'more' : 'less'}`,
  price: (n, up) => `$${n.toFixed(2)} ${up ? 'more' : 'less'}`,
  ratio: (n, up) => `${n.toFixed(2)} ${up ? 'higher' : 'lower'}`,
  count: (n, up) => `${countWords.format(n)} ${up ? 'more' : 'fewer'}`,
  outOf100: (n, up) => `${points(n, 'point')} ${up ? 'higher' : 'lower'}`,
  percent: (n, up) => `${points(n, 'percentage point')} ${up ? 'higher' : 'lower'}`,
}
const isFiniteNumber = value => typeof value === 'number' && Number.isFinite(value)

export function differencePhrase(key, value, base, { tick = null, baseLabel = 'Town A' } = {}) {
  if (known(tick) && inWarmUp(tick)) return 'still being set up'
  if (!isFiniteNumber(value) || !isFiniteNumber(base)) return null
  const gap = shownValue(key, value) - shownValue(key, base)
  const format = METRICS[key]?.format
  const size = format === 'price' || format === 'ratio' ? Math.round(Math.abs(gap) * 100) / 100 : Math.round(Math.abs(gap))
  if (formatMetric(key, value) === formatMetric(key, base) || size === 0) return `about the same as ${baseLabel}`
  const phrase = DIFFERENCES[format] ?? DIFFERENCES.count
  return `${phrase(size, gap > 0)} than ${baseLabel}`
}

// Under a counted-every-5-weeks figure: when it was last counted.
export function countedNote(asOfTick) {
  const week = Math.floor(Number(asOfTick))
  if (!known(asOfTick) || !(week >= 1)) return 'Counted every 5 weeks.'
  return `Counted every 5 weeks; last count ${weekLabel(week)}.`
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
