// What a card says about the place under the pointer, for one week's model.
import { COPY, formatMoneyShort, householdsPerHouse, sectorName } from '../catalog.js'
import { weekLabel } from '../narration.js'
import { WEEKS } from './model.js'

const T = COPY.diorama.card

export function placeCard(model, target, total) {
  if (!model || !target) return null
  if (target.kind === 'house') {
    const house = model.houses[target.index]
    if (!house) return null
    const sub = T.house.sub(householdsPerHouse(total))
    if (house.state === 'work') return { title: T.house.work, sub, rows: [], note: T.houseWork(house.weeks), tag: { text: T.working, tone: 'good' } }
    if (house.state === 'look') return { title: T.house.look, sub, rows: [], note: T.houseLook(house.weeks), tag: { text: T.looking, tone: 'warn' } }
    return { title: T.house.home, sub, rows: [], note: T.houseHome, tag: { text: COPY.diorama.legend.lost, tone: 'bad' } }
  }
  if (target.kind === 'shop') {
    const shop = model.shops.find(s => s.id === target.id)
    if (!shop) return null
    const sub = `${sectorName(shop.sector)}${shop.coop ? ` · ${T.coop}` : ''}`
    if (shop.state === 'closed') {
      return {
        title: shop.name, sub, rows: [[T.closedOn, weekLabel(shop.closedTick)], [T.closedStaff, String(shop.staff)]],
        note: T.closedNote(shop.closedFor >= WEEKS.lease), tag: { text: T.states.closed, tone: 'quiet' },
      }
    }
    const notes = []
    if (shop.hired || shop.laidOff) notes.push(T.thisWeek(shop.hired, shop.laidOff))
    if (shop.richest) notes.push(T.richest)
    const state = shop.fresh ? 'building' : shop.isNew ? 'fresh' : shop.state
    const tone = { building: 'info', fresh: 'info', growing: 'good', struggling: 'warn', steady: 'quiet' }[state]
    return {
      title: shop.name, sub, rows: [[T.staff, String(shop.staff)], [T.cash, formatMoneyShort(shop.cash)]],
      note: notes.length ? notes.join(' ') : null, tag: { text: T.states[state], tone },
    }
  }
  if (target.kind === 'hall') {
    const { cash, income, support, queue } = model.hall
    return {
      title: T.hall, sub: null,
      rows: [[T.taxes, formatMoneyShort(income)], [T.help, formatMoneyShort(support)], [cash < 0 ? T.owes : T.saved, formatMoneyShort(Math.abs(cash ?? 0))]],
      note: queue ? T.queue(queue) : null, tag: cash < 0 ? { text: T.inDebt, tone: 'bad' } : { text: T.inBlack, tone: 'good' },
    }
  }
  if (target.kind === 'bank') {
    const { loans, bad, badNow } = model.bank
    return {
      title: T.bank, sub: T.bankSub, rows: [[T.loans, loans == null ? '–' : String(loans)], [T.bad, formatMoneyShort(bad)]],
      note: null, tag: badNow ? { text: T.badTag, tone: 'bad' } : { text: T.lending, tone: 'good' },
    }
  }
  if (target.kind === 'person') {
    const person = model.people[target.index]
    if (!person) return null
    const rows = [[T.savings, formatMoneyShort(person.cash)], [T.health, T.word(person.health)], [T.happiness, T.word(person.happiness)]]
    if (person.rentOwed > 0) rows.push([T.rentOwed, formatMoneyShort(person.rentOwed)])
    return {
      title: person.age == null ? person.name : `${person.name}, ${person.age}`, sub: T.person, rows,
      note: person.working ? T.worksAt(person.employer ?? '') : T.outFor(person.weeksOut),
      tag: person.working ? { text: T.working, tone: 'good' } : { text: T.looking, tone: 'warn' },
    }
  }
  return null
}
