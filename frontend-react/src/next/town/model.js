// Everything the drawings need for one town in one week, from the arm alone.
import { COPY, WARMUP_TICKS } from '../catalog.js'
import { eventsAt, rulesAt, rulesDiff, snapshotAt, valueAt } from '../data/derive.js'
import { firmDisplayName, householdName } from '../names.js'
import { personHouses } from './geometry.js'
import { houseRank, houseStates, houseWeeks } from './houses.js'
import { lotAssignment } from './lots.js'
import { moodBand, moodOf, seasonOf } from './mood.js'

const clamp = (value, lo, hi) => Math.min(hi, Math.max(lo, value))
const STATES = new Set(['steady', 'growing', 'struggling'])
export const floorsOf = staff => clamp(Math.ceil(Math.max(1, staff ?? 1) / 9), 1, 6)
export const WEEKS = { fresh: 3, isNew: 9, lease: 8, longOut: 12, pulse: 4 }

// First week each firm appears, cached on the arm's shared `ticks` array.
const firstSeenCache = new WeakMap()
function firstSeen(arm) {
  const ticks = arm?.ticks ?? []
  let state = firstSeenCache.get(ticks)
  if (!state || state.done > ticks.length) state = { done: 0, seen: new Map() }
  for (let i = state.done; i < ticks.length; i += 1) {
    for (const firm of arm.snapshots?.[ticks[i]]?.firms ?? []) if (!state.seen.has(firm.id)) state.seen.set(firm.id, ticks[i])
    state.done = i + 1
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
  for (const firm of snapshot?.firms ?? []) {
    const lot = lotOf.get(firm.id) ?? null
    if (lot == null) { overflow += 1; continue }
    const first = seen.get(firm.id) ?? tick
    const age = first <= firstTick ? Infinity : tick - first
    shops.push({
      id: firm.id, name: firmDisplayName(byId[firm.id] ?? firm), sector: firm.sector ?? byId[firm.id]?.sector ?? null,
      staff: firm.staff ?? 0, cash: firm.cash ?? 0, state: STATES.has(firm.state) ? firm.state : 'steady', lot, floors: floorsOf(firm.staff),
      age, fresh: age < WEEKS.fresh, isNew: age >= WEEKS.fresh && age < WEEKS.isNew, coop: Boolean(firm.isBaseline ?? byId[firm.id]?.isBaseline),
      richest: false, hired: hires.get(firm.id) ?? 0, laidOff: layoffs.get(firm.id) ?? 0, closedTick: null, closedFor: null,
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
  const open = shops.filter(shop => shop.state !== 'closed')
  const contenders = open.filter(shop => !shop.coop)
  if (contenders.length) contenders.reduce((best, shop) => (shop.cash > best.cash ? shop : best)).richest = true

  const support = valueAt(arm, 'familySupportPaid', tick) ?? 0
  const loans = valueAt(arm, 'bankActiveLoans', tick)
  const bad = valueAt(arm, 'bankDefaultAmountThisTick', tick) ?? 0
  const sales = valueAt(arm, 'salesExceptRentThisWeek', tick) ?? 0
  const staffTotal = open.reduce((sum, shop) => sum + shop.staff, 0)

  const subjects = (snapshot?.subjects ?? []).slice(0, 4)
  const houses = personHouses(subjects.map(subject => subject.id))
  const people = subjects.map((subject, i) => ({
    id: subject.id, name: householdName(subject.id), age: subject.age ?? arm?.profiles?.[subject.id]?.age ?? null, house: houses[i],
    working: Boolean(subject.isEmployed), cash: subject.cash ?? null, health: subject.health ?? null, happiness: subject.happiness ?? null,
    weeksOut: subject.unemploymentDuration ?? 0, rentOwed: subject.rentArrears ?? 0,
    employer: subject.isEmployed && subject.employer ? firmDisplayName(byName[subject.employer] ?? { name: subject.employer, sector: subject.employerCategory }) : null,
    tone: subject.isEmployed ? 'work' : (subject.happiness ?? 1) < 0.2 ? 'low' : 'look',
  }))

  return {
    tick, warmUp, mood, band: moodBand(mood), season: seasonOf(tick),
    houses: states.map((state, i) => ({ state, weeks: weeks[i] })), counts,
    shops, overflow,
    hall: {
      cash: valueAt(arm, 'townHallCash', tick), income: valueAt(arm, 'townHallIncome', tick), support,
      queue: warmUp ? 0 : clamp(Math.round(support / 2800), 0, 9),
      banner: bannerFor(rulesDiff(rulesAt(arm, tick))), changedTick: lastChange(arm, tick),
    },
    bank: { loans, bad, papers: clamp(Math.round((loans ?? 0) / 55), 0, 7), badNow: bad >= 500 },
    people,
    flows: { spend: sales, pay: staffTotal * (pay ?? 0), tax: valueAt(arm, 'townHallIncome', tick) ?? 0, help: support },
    traffic: { cars: clamp(Math.round(sales / 5000), 0, 7), walkers: warmUp ? 4 : clamp(Math.round((counts.work / 100) * 14), 1, 14) },
    week: {
      opened: events.filter(event => event.type === 'firm_opened').map(event => event.firmId),
      closed: events.filter(event => event.type === 'firm_closed').map(event => event.firmId),
      hires: [...hires], layoffs: [...layoffs], bad,
    },
    facts: { out, pay, open: open.length, struggling: open.filter(shop => shop.state === 'struggling').length, hallCash: valueAt(arm, 'townHallCash', tick) },
  }
}
