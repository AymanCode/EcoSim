// Extract the recorded demo towns into the data block (the
// <script id="lt-data"> element) of every living-town mockup in this folder
// (07-living-town-styles.html, 08-diorama-details.html), so each mockup is one
// self-contained file.
//
// Reads frontend-react/public/demo/town-a.jsonl (no changes) and town-b.jsonl
// (higher minimum wage). Firm and household names come from the app's own
// names.js, so the mockups show the same shops and people as the Run screen.
//
// Run from the repository root:
//   node docs/superpowers/specs/2026-10-02-mockups/extract_living_town_data.mjs

import { readdirSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { firmDisplayName, householdName } from '../../../../frontend-react/src/next/names.js'

const HERE = dirname(fileURLToPath(import.meta.url))
const ROOT = join(HERE, '..', '..', '..', '..')
const DEMO = join(ROOT, 'frontend-react', 'public', 'demo')
const TOWNS = [
  { key: 'A', file: 'town-a.jsonl', label: 'Town A', rule: 'No changes', color: '#2E6FE0' },
  { key: 'B', file: 'town-b.jsonl', label: 'Town B', rule: 'A higher minimum wage', color: '#E0762C' },
]
// The four people the Run screen shows first.
const PEOPLE = ['Nikhil', 'Liam', 'Diego', 'Sami']
const STATE = { steady: 0, growing: 1, struggling: 2 }

const r0 = value => (typeof value === 'number' && Number.isFinite(value) ? Math.round(value) : null)
const r2 = value => (typeof value === 'number' && Number.isFinite(value) ? Math.round(value * 100) / 100 : null)

function frames(file) {
  const out = []
  for (const line of readFileSync(join(DEMO, file), 'utf8').split(/\r?\n/)) {
    if (!line.trim()) continue
    const row = JSON.parse(line)
    const msg = row.kind === 'message' ? row.message : null
    if (msg && typeof msg.tick === 'number' && msg.metrics && !msg.type) out.push(msg)
  }
  return out.sort((a, b) => a.tick - b.tick)
}

function town(spec) {
  const list = frames(spec.file)
  const firms = {}
  const byServerName = {}
  const note = firm => {
    if (firms[firm.id]) return
    const name = firmDisplayName(firm)
    firms[firm.id] = [name, firm.sector, Boolean(firm.isBaseline)]
    byServerName[firm.name] = firm.id
  }
  const tracked = list[list.length - 1].metrics.trackedSubjects ?? []
  const people = PEOPLE
    .map(first => tracked.find(s => householdName(s.id) === first))
    .filter(Boolean)
    .map(s => ({ id: s.id, name: householdName(s.id), age: s.age }))

  const ticks = list.map(frame => {
    for (const firm of frame.firms ?? []) note(firm)
    for (const firm of frame.firmsClosed ?? []) note(firm)
    const c = frame.curated ?? {}
    const ev = { opened: [], closed: [], laid: 0, hired: 0, care: 0, shock: 0, hire: [], lay: [] }
    const perFirm = { hire: new Map(), lay: new Map() }
    for (const e of frame.events ?? []) {
      if (e.type === 'firm_opened') ev.opened.push(e.firmId)
      else if (e.type === 'firm_closed') ev.closed.push(e.firmId)
      else if (e.type === 'laid_off') { ev.laid += 1; perFirm.lay.set(e.firmId, (perFirm.lay.get(e.firmId) ?? 0) + 1) }
      else if (e.type === 'hired') { ev.hired += 1; perFirm.hire.set(e.firmId, (perFirm.hire.get(e.firmId) ?? 0) + 1) }
      else if (e.type === 'care_completed') ev.care += 1
      else if (e.type === 'shock') ev.shock += 1
    }
    // Hires and layoffs per firm, as [firmId, count].
    ev.hire = [...perFirm.hire].filter(([id]) => id != null)
    ev.lay = [...perFirm.lay].filter(([id]) => id != null)
    const counts = frame.eventCounts ?? {}
    ev.laid = Math.max(ev.laid, counts.laidOff ?? 0)
    ev.hired = Math.max(ev.hired, counts.hired ?? 0)
    const subjects = frame.metrics.trackedSubjects ?? []
    return {
      t: frame.tick,
      out: r2(c.peopleOutOfWorkPer100),
      homeless: r0(c.homelessHouseholds),
      hh: r0(c.householdsTotal),
      pay: r2(c.typicalWeeklyPay),
      sales: r0(c.salesExceptRentThisWeek),
      hallIn: r0(c.townHallIncome),
      support: r0(c.familySupportPaid),
      hallCash: r0(c.townHallCash),
      food: r2(c.priceFood),
      happy: r2(c.happiness),
      loans: r0(c.bankActiveLoans),
      bad: r0(c.bankDefaultAmountThisTick),
      careDenied: r0(c.careDenials),
      f: (frame.firms ?? []).map(firm => [firm.id, firm.staff, r0(firm.cash), STATE[firm.state] ?? 0]),
      c: (frame.firmsClosed ?? []).map(firm => [firm.id, firm.closedTick, firm.lastStaff]),
      p: people.map(person => {
        const s = subjects.find(x => x.id === person.id)
        if (!s) return null
        // [working, cash, employer firm id, health 0-1, happiness 0-1,
        //  weeks out of work, rent owed]
        return [s.isEmployed ? 1 : 0, r0(s.cash), s.isEmployed ? (byServerName[s.employer] ?? null) : null,
          r2(s.health), r2(s.happiness), r0(s.unemploymentDuration), r0(s.rentArrears)]
      }),
      ev,
    }
  })
  return { key: spec.key, label: spec.label, rule: spec.rule, color: spec.color, firms, people, ticks }
}

const data = { maxTick: 0, towns: TOWNS.map(town) }
data.maxTick = Math.min(...data.towns.map(t => t.ticks.length))
const block = /(<script id="lt-data">)[\s\S]*?(<\/script>)/
const pages = readdirSync(HERE).filter(name => name.endsWith('.html'))
  .filter(name => block.test(readFileSync(join(HERE, name), 'utf8')))
if (!pages.length) throw new Error(`no page in ${HERE} has a <script id="lt-data"> block`)
for (const name of pages) {
  const html = join(HERE, name)
  const page = readFileSync(html, 'utf8')
  writeFileSync(html, page.replace(block, (_, open, close) => `${open}window.LT = ${JSON.stringify(data)}${close}`))
  console.log(`wrote ${name}: ${data.maxTick} weeks, ${data.towns.map(t => `${t.label} ${Object.keys(t.firms).length} firms, ${t.people.length} people`).join('; ')}`)
}
