// Everything the drawings need for one town in one week, from the arm alone.
import { COPY, WARMUP_TICKS } from '../catalog.js'
import { eventsAt, householdState, rulesAt, rulesDiff, snapshotAt, valueAt } from '../data/derive.js'
import { firmDisplayName, householdName } from '../names.js'
import { personHouses } from './geometry.js'
import { houseRank, houseStates, houseWeeks } from './houses.js'
import { lotAssignment } from './lots.js'
import { moodBand, moodOf, seasonOf } from './mood.js'

const clamp = (value, lo, hi) => Math.min(hi, Math.max(lo, value))
const STATES = new Set(['steady', 'growing', 'struggling'])
export const floorsOf = staff => clamp(Math.ceil(Math.max(1, staff ?? 1) / 9), 1, 6)
export const WEEKS = { fresh: 3, isNew: 9, lease: 8, longOut: 12, pulse: 4 }

// First week each firm appears, cached on the arm's shared `ticks` array. Like
// lots.js, the cache keeps the week and snapshot it read for every week, checks
// them against the arm on each call (a cheap pass, no replay) and starts over
// when one differs: a week that lands late in the middle, or a repeated week
// overwritten in place, moves a firm's first week.
const firstSeenCache = new WeakMap()
function firstSeen(arm) {
  const ticks = arm?.ticks ?? []
  let state = firstSeenCache.get(ticks)
  const holds = state && state.weeks.length <= ticks.length
    && state.weeks.every((week, i) => week.tick === ticks[i] && week.snapshot === arm.snapshots?.[ticks[i]])
  if (!holds) state = { weeks: [], seen: new Map() }
  for (let i = state.weeks.length; i < ticks.length; i += 1) {
    const snapshot = arm.snapshots?.[ticks[i]]
    for (const firm of snapshot?.firms ?? []) if (!state.seen.has(firm.id)) state.seen.set(firm.id, ticks[i])
    state.weeks.push({ tick: ticks[i], snapshot })
  }
  if (ticks.length) firstSeenCache.set(ticks, state)
  return state.seen
}

function bannerFor(diff) {
  const labels = new Set(Object.keys(diff).map(lever => COPY.diorama.banner[lever] ?? COPY.diorama.banner.many))
  if (labels.size === 0) return null
  return labels.size === 1 ? [...labels][0] : COPY.diorama.banner.many
}

function lastChange(arm, tick) {
  const changes = arm?.policyChanges ?? []
  for (let i = changes.length - 1; i >= 0; i -= 1) if (changes[i].tick <= tick) return changes[i].tick > tick - WEEKS.pulse ? changes[i].tick : null
  return null
}

const countBy = (events, type) => {
  const counts = new Map()
  for (const event of events) if (event.type === type && event.firmId != null) counts.set(event.firmId, (counts.get(event.firmId) ?? 0) + 1)
  return counts
}

export function townAt(arm, tick) {
  const warmUp = tick <= WARMUP_TICKS
  const out = valueAt(arm, 'peopleOutOfWorkPer100', tick)
  const total = valueAt(arm, 'householdsTotal', tick)
  const homeless = valueAt(arm, 'homelessHouseholds', tick)
  const pay = valueAt(arm, 'typicalWeeklyPay', tick)
  const rank = houseRank(arm?.setup?.seed)
  const { states, counts } = houseStates({ out, homeless, total }, rank)
  const weeks = houseWeeks(arm, tick, rank)
  const mood = moodOf({ out, happiness: valueAt(arm, 'happiness', tick), warmUp })

  const snapshot = snapshotAt(arm, tick)
  const byId = arm?.firmDirectory?.byId ?? {}
  const byName = arm?.firmDirectory?.byName ?? {}
  const lotOf = lotAssignment(arm)
  const seen = firstSeen(arm)
  const events = eventsAt(arm, tick)
  const hires = countBy(events, 'hired')
  const layoffs = countBy(events, 'laid_off')
  const firstTick = arm?.ticks?.[0] ?? 1

  const shops = []
  let overflow = 0
  const isCoop = firm => Boolean(firm.isBaseline ?? byId[firm.id]?.isBaseline)
  const openFirms = snapshot?.firms ?? []
  // The crown goes to the richest open private firm in the whole town (one
  // whose cash is measured); it is drawn only if that firm has a lot.
  let crowned = null
  for (const firm of openFirms) {
    if (!isCoop(firm) && firm.cash != null && (crowned == null || firm.cash > crowned.cash)) crowned = firm
  }
  for (const firm of openFirms) {
    const lot = lotOf.get(firm.id) ?? null
    if (lot == null) { overflow += 1; continue }
    const first = seen.get(firm.id) ?? tick
    const age = first <= firstTick ? Infinity : tick - first
    shops.push({
      id: firm.id, name: firmDisplayName(byId[firm.id] ?? firm), sector: firm.sector ?? byId[firm.id]?.sector ?? null,
      staff: firm.staff ?? 0, cash: firm.cash ?? null, state: STATES.has(firm.state) ? firm.state : 'steady', lot, floors: floorsOf(firm.staff),
      age, fresh: age < WEEKS.fresh, isNew: age >= WEEKS.fresh && age < WEEKS.isNew, coop: isCoop(firm),
      richest: firm === crowned, hired: hires.get(firm.id) ?? 0, laidOff: layoffs.get(firm.id) ?? 0, closedTick: null, closedFor: null,
    })
  }
  for (const firm of snapshot?.firmsClosed ?? []) {
    const lot = lotOf.get(firm.id) ?? null
    if (lot == null) { overflow += 1; continue }
    shops.push({
      id: firm.id, name: firmDisplayName(byId[firm.id] ?? firm), sector: firm.sector ?? null, staff: firm.lastStaff ?? 0, cash: null,
      state: 'closed', lot, floors: floorsOf(firm.lastStaff), age: Infinity, fresh: false, isNew: false, coop: Boolean(byId[firm.id]?.isBaseline),
      richest: false, hired: 0, laidOff: 0, closedTick: firm.closedTick, closedFor: tick - firm.closedTick,
    })
  }

  // Town-wide figures count every open firm, drawn or not.
  const support = valueAt(arm, 'familySupportPaid', tick)
  const loans = valueAt(arm, 'bankActiveLoans', tick)
  const bad = valueAt(arm, 'bankDefaultAmountThisTick', tick)
  const sales = valueAt(arm, 'salesExceptRentThisWeek', tick)
  const staffTotal = openFirms.reduce((sum, firm) => sum + (firm.staff ?? 0), 0)

  const subjects = (snapshot?.subjects ?? []).slice(0, 4)
  const houses = personHouses(subjects.map(subject => subject.id))
  // A pin is green when working, amber when looking for work, red when they
  // lost their home or are out of work and unhappy (happiness below 0.2), and
  // grey when they are not able to work and doing fine.
  const people = subjects.map((subject, i) => {
    const state = householdState(subject)
    const unhappy = (subject.happiness ?? 1) < 0.2
    return {
      id: subject.id, name: householdName(subject.id), age: subject.age ?? arm?.profiles?.[subject.id]?.age ?? null, house: houses[i],
      state, working: state === 'work', cash: subject.cash ?? null, health: subject.health ?? null, happiness: subject.happiness ?? null,
      weeksOut: subject.unemploymentDuration ?? 0, rentOwed: subject.rentArrears ?? 0,
      employer: subject.isEmployed && subject.employer ? firmDisplayName(byName[subject.employer] ?? { name: subject.employer, sector: subject.employerCategory }) : null,
      tone: state === 'work' ? 'work' : state === 'home' || unhappy ? 'low' : state === 'look' ? 'look' : 'idle',
      subject,
    }
  })

  return {
    tick, warmUp, mood, band: moodBand(mood), season: seasonOf(tick),
    houses: states.map((state, i) => ({ state, weeks: weeks[i] })), counts,
    shops, overflow,
    hall: {
      cash: valueAt(arm, 'townHallCash', tick), income: valueAt(arm, 'townHallIncome', tick), support,
      queue: warmUp ? 0 : clamp(Math.round((support ?? 0) / 2800), 0, 9),
      banner: bannerFor(rulesDiff(rulesAt(arm, tick))), changedTick: lastChange(arm, tick),
    },
    bank: { loans, bad, papers: clamp(Math.round((loans ?? 0) / 55), 0, 7), badNow: (bad ?? 0) >= 500 },
    people,
    flows: { spend: sales ?? 0, pay: staffTotal * (pay ?? 0), tax: valueAt(arm, 'townHallIncome', tick) ?? 0, help: support ?? 0 },
    traffic: { cars: clamp(Math.round((sales ?? 0) / 5000), 0, 7), walkers: warmUp ? 4 : clamp(Math.round((counts.work / 100) * 14), 1, 14) },
    week: {
      opened: events.filter(event => event.type === 'firm_opened').map(event => event.firmId),
      closed: events.filter(event => event.type === 'firm_closed').map(event => event.firmId),
      hires: [...hires], layoffs: [...layoffs], bad,
    },
    facts: {
      out, pay, open: openFirms.length, struggling: openFirms.filter(firm => firm.state === 'struggling').length, hallCash: valueAt(arm, 'townHallCash', tick),
      staff: staffTotal,
    },
  }
}
