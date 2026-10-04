import { beforeAll, describe, expect, test } from 'vitest'
import { COPY, DEFAULT_POLICY } from '../catalog.js'
import { ingest } from '../data/session.js'
import { LOT_CAPACITY, mulberry32 } from '../town/geometry.js'
import { townAt } from '../town/model.js'
import { demoArms, fixtureArm } from './fixture.js'
import { firm, frame, freshCopy, liveArm, subject } from './townFixture.js'

let A, B
beforeAll(() => { [A, B] = demoArms() })

describe('townAt', () => {
  test('warm-up weeks are neutral and quiet', () => {
    const model = townAt(A, 5)
    expect(model.warmUp).toBe(true)
    expect(model.mood).toBe(0.62)
    expect(model.hall.queue).toBe(0)
    expect(model.traffic.walkers).toBe(4)
  })

  test('houses follow out of work and homeless', () => {
    const model = townAt(A, 70)
    expect(model.houses).toHaveLength(100)
    expect(model.counts.look).toBe(Math.round(model.facts.out))
    expect(model.counts.work + model.counts.look + model.counts.home).toBe(100)
  })

  test('the demo towns part ways in mood by year 2', () => {
    const a = townAt(A, 100), b = townAt(B, 100)
    expect(a.band).toBe('hard')
    expect(b.mood).toBeGreaterThan(a.mood)
  })

  test('shops: one per lot, states, floors, the richest private shop', () => {
    const model = townAt(A, 70)
    const lots = model.shops.map(shop => shop.lot)
    expect(new Set(lots).size).toBe(lots.length)
    for (const shop of model.shops) {
      expect(['steady', 'growing', 'struggling', 'closed']).toContain(shop.state)
      expect(shop.floors).toBeGreaterThanOrEqual(1)
      expect(shop.floors).toBeLessThanOrEqual(6)
      expect(typeof shop.name).toBe('string')
    }
    const richest = model.shops.filter(shop => shop.richest)
    expect(richest).toHaveLength(1)
    const open = model.shops.filter(shop => shop.state !== 'closed' && !shop.coop)
    expect(richest[0].cash).toBe(Math.max(...open.map(shop => shop.cash)))
    expect(richest[0].coop).toBe(false)
  })

  test('a shop that closed at week 70 is closed for 0 weeks then; firms of week 1 are not new', () => {
    const model = townAt(A, 70)
    const closedNow = model.shops.find(shop => shop.state === 'closed' && shop.closedTick === 70)
    expect(closedNow?.closedFor).toBe(0)
    expect(model.week.closed).toContain(closedNow.id)
    for (const shop of townAt(A, 12).shops.filter(s => s.coop)) expect(shop.isNew || shop.fresh).toBe(false)
  })

  test('the bank and the town hall', () => {
    const model = townAt(A, 70)
    expect(model.bank.bad).toBeGreaterThan(19000)
    expect(model.bank.badNow).toBe(true)
    expect(model.bank.papers).toBeGreaterThan(0)
    expect(model.hall.cash).toBeLessThan(0)
    expect(townAt(A, 70).hall.banner).toBeNull()
    expect(townAt(B, 70).hall.banner).toBe('NEW MIN. WAGE')
  })

  test('people: the first four tracked households, each in a distinct house', () => {
    const model = townAt(A, 60)
    expect(model.people).toHaveLength(4)
    expect(new Set(model.people.map(person => person.house)).size).toBe(4)
    const nikhil = model.people.find(person => person.name === 'Nikhil')
    expect(nikhil.working).toBe(false)
    expect(nikhil.weeksOut).toBeGreaterThan(20)
    expect(['look', 'low']).toContain(nikhil.tone)
  })

  test('an arm without happiness or bank figures still builds a model', () => {
    const model = townAt(fixtureArm(), 11)
    expect(Number.isFinite(model.mood)).toBe(true)
    expect(model.bank.papers).toBe(0)
    expect(model.bank.badNow).toBe(false)
  })

  test('traffic and flows follow the money', () => {
    const model = townAt(A, 40)
    expect(model.traffic.cars).toBe(Math.max(0, Math.min(7, Math.round(model.flows.spend / 5000))))
    expect(model.flows.pay).toBeGreaterThan(0)
  })

  test('every rule lever has a short banner name', () => {
    for (const lever of Object.keys(DEFAULT_POLICY)) expect(COPY.diorama.banner[lever], lever).toEqual(expect.any(String))
  })

  test('the banner names one rule, or NEW RULES when several differ, and the pulse lasts four weeks', () => {
    const arm = demoArms()[0]
    arm.setup = { ...arm.setup, initial_policy: { sector_subsidy_target: 'Food', sector_subsidy_level: 0.2 } }
    expect(townAt(arm, 30).hall.banner).toBe('SUBSIDIES')
    arm.policyChanges = [{ tick: 50, policy: 'wage_tax_rate', value: 0.25 }]
    expect(townAt(arm, 49).hall.banner).toBe('SUBSIDIES')
    expect(townAt(arm, 50).hall.banner).toBe('NEW RULES')
    expect([49, 50, 53, 54].map(tick => townAt(arm, tick).hall.changedTick)).toEqual([null, 50, 50, null])
    arm.setup = { ...arm.setup, initial_policy: {} }
    expect(townAt(arm, 60).hall.banner).toBe('NEW WAGE TAX')
  })

  test('a town with no weeks yet is an empty, calm model', () => {
    const model = townAt({ ticks: [], snapshots: {}, series: {} }, 1)
    expect(model.shops).toEqual([])
    expect(model.people).toEqual([])
    expect(model.houses).toHaveLength(100)
    expect(model.hall.banner).toBeNull()
    expect(model.traffic).toEqual({ cars: 0, walkers: 4 })
  })
})

// Each shop's id and how new it is, for comparing one arm's answer with another's.
const ages = (arm, tick) => townAt(arm, tick).shops.map(({ id, age, fresh, isNew }) => ({ id, age, fresh, isNew }))

const homes = (arm, tick) => new Map(townAt(arm, tick).people.map(({ id, house }) => [id, house]))

describe('townAt household homes across sample changes', () => {
  const doctoredDemo = samples => {
    const arm = demoArms()[0]
    arm.ticks = arm.ticks.slice(0, samples.length)
    samples.forEach((ids, i) => {
      const tick = arm.ticks[i]
      arm.snapshots[tick] = { ...arm.snapshots[tick], subjects: ids.map(id => subject(id)) }
    })
    return arm
  }

  test('the reported sample replacement leaves household 16 at house 26', () => {
    const arm = doctoredDemo([[1, 16, 2, 3], [16, 2, 3, 4]])
    expect(homes(arm, 1).get(16)).toBe(26)
    expect(homes(arm, 2).get(16)).toBe(26)
    for (const id of [2, 3, 16]) expect(homes(arm, 2).get(id)).toBe(homes(arm, 1).get(id))
  })

  test('joins, departures and reorders keep every continuing household in its home', () => {
    const arm = doctoredDemo([[16, 2, 3], [1, 16, 2, 3], [3, 1, 16, 2], [16, 3, 4, 2]])
    expect(homes(arm, 1).get(16)).toBe(25)
    for (let i = 1; i < arm.ticks.length; i += 1) {
      const before = homes(arm, arm.ticks[i - 1]), after = homes(arm, arm.ticks[i])
      for (const [id, house] of after) if (before.has(id)) expect(house).toBe(before.get(id))
      expect(new Set(after.values()).size).toBe(after.size)
    }
  })

  test('scrubbing repeats the same homes before and after later weeks arrive', () => {
    const arm = liveArm([[20, { subjects: [1, 16, 2, 3].map(id => subject(id)) }]])
    const first = homes(arm, 20)
    expect(homes(arm, 20)).toEqual(first)
    for (const [tick, ids] of [[21, [16, 2, 3, 4]], [22, [1, 4, 16, 3]], [23, [16, 3, 4, 5]]]) {
      ingest(arm, frame(tick, { subjects: ids.map(id => subject(id)) }))
      expect(homes(arm, tick).get(16)).toBe(26)
      expect(homes({ ...arm }, 20)).toEqual(first)
    }
    const recorded = arm.ticks.map(tick => homes(arm, tick))
    for (const tick of [...arm.ticks].reverse()) {
      expect(homes(arm, tick)).toEqual(recorded[arm.ticks.indexOf(tick)])
      expect(homes(arm, tick)).toEqual(homes(freshCopy(arm), tick))
    }
  })
})

describe('townAt when weeks land late or are rewritten', () => {
  // Firm 1 is there from the start; firm 2 first opens in week 72, which arrives after weeks 73 and 74.
  const grown = () => liveArm([
    [70, { firms: [firm(1)] }], [71, { firms: [firm(1)] }],
    [73, { firms: [firm(1), firm(2)] }], [74, { firms: [firm(1), firm(2)] }],
  ])

  test('a week that lands in the middle moves a firm\'s first week', () => {
    const arm = grown()
    expect(ages(arm, 74).find(shop => shop.id === 2).age).toBe(1)
    ingest(arm, frame(72, { firms: [firm(1), firm(2)] }))
    const two = tick => ages(arm, tick).find(shop => shop.id === 2)
    expect(two(74)).toMatchObject({ age: 2, fresh: true, isNew: false })
    expect(two(72)).toMatchObject({ age: 0, fresh: true })
    expect(two(73).age).toBe(1)
    for (const tick of arm.ticks) expect(ages(arm, tick)).toEqual(ages(freshCopy(arm), tick))
  })

  test('a repeated week, overwritten in place, moves it back', () => {
    const arm = grown()
    ingest(arm, frame(72, { firms: [firm(1), firm(2)] }))
    expect(ages(arm, 74).find(shop => shop.id === 2).age).toBe(2)
    ingest(arm, frame(72, { firms: [firm(1)] }))
    expect(ages(arm, 74).find(shop => shop.id === 2).age).toBe(1)
    expect(ages(arm, 72).map(shop => shop.id)).toEqual([1])
    for (const tick of arm.ticks) expect(ages(arm, tick)).toEqual(ages(freshCopy(arm), tick))
  })

  test('matches an arm with nothing cached after any mix of new, late and repeated weeks', () => {
    const rand = mulberry32(77)
    const some = () => [1, 2, 3, 4, 5, 6].filter(() => rand() < 0.45).map(id => firm(id))
    const arm = liveArm([])
    for (let step = 0; step < 40; step += 1) {
      ingest(arm, frame(1 + Math.floor(rand() * 12), { firms: some() }))
      for (const tick of arm.ticks) expect(ages(arm, tick)).toEqual(ages(freshCopy(arm), tick))
    }
  })
})

describe('townAt town-wide figures with more firms than lots', () => {
  const PAY = 40
  // Firms 1..LOT_CAPACITY take the lots; the last two have none. Firm 1 is a co-op.
  const crowded = ({ lastCash, thirdCash }) => {
    const firms = Array.from({ length: LOT_CAPACITY + 2 }, (_, i) => {
      const id = i + 1
      if (id === 1) return firm(id, { isBaseline: true, cash: 9e7, staff: 20 })
      if (id === 3) return firm(id, { cash: thirdCash })
      if (id === LOT_CAPACITY + 2) return firm(id, { cash: lastCash, staff: 30 })
      if (id === LOT_CAPACITY + 1) return firm(id, { state: 'struggling' })
      return firm(id)
    })
    return liveArm([[1, { firms, curated: { typicalWeeklyPay: PAY } }]])
  }

  test('open, struggling and pay count every firm, drawn or not', () => {
    const model = townAt(crowded({ lastCash: 5000, thirdCash: 2000 }), 1)
    expect(model.shops).toHaveLength(LOT_CAPACITY)
    expect(model.overflow).toBe(2)
    expect(model.facts.open).toBe(LOT_CAPACITY + 2)
    expect(model.facts.struggling).toBe(1)
    // Staff: the co-op 20, the last firm 30, the other 50 firms 10 each.
    expect(model.flows.pay).toBe((20 + 30 + 10 * (LOT_CAPACITY - 1) + 10) * PAY)
  })

  test('the crown goes to the richest private firm in town, drawn only if it has a lot', () => {
    const richestIsLast = townAt(crowded({ lastCash: 5e6, thirdCash: 2000 }), 1)
    expect(richestIsLast.shops.filter(shop => shop.richest)).toEqual([])
    const richestIsDrawn = townAt(crowded({ lastCash: 1500, thirdCash: 2000 }), 1)
    expect(richestIsDrawn.shops.filter(shop => shop.richest).map(shop => shop.id)).toEqual([3])
  })
})

describe('townAt with figures the town did not report', () => {
  const arm = liveArm([[20, { firms: [firm(1, { cash: null })], curated: {} }]])

  test('a missing figure stays missing, and the drawing scales read it as nothing', () => {
    const model = townAt(arm, 20)
    expect(model.hall).toMatchObject({ cash: null, income: null, support: null, queue: 0 })
    expect(model.bank).toMatchObject({ loans: null, bad: null, papers: 0, badNow: false })
    expect(model.flows).toEqual({ spend: 0, pay: 0, tax: 0, help: 0 })
    expect(model.traffic.cars).toBe(0)
    expect(model.shops[0].cash).toBeNull()
  })

  test('no crown for a firm whose cash is not known', () => {
    expect(townAt(arm, 20).shops.filter(shop => shop.richest)).toEqual([])
  })
})

describe('townAt people follow the household rules', () => {
  const week = subjects => liveArm([[20, { firms: [firm(1)], subjects }]])
  const pins = subjects => townAt(week(subjects), 20).people

  test('working, looking, unhappy and looking, and unable to work each have a state and a pin colour', () => {
    const [working, looking, unhappy, idle] = pins([
      subject(1, { isEmployed: true, employer: 'Shop 1' }),
      subject(2, { unemploymentDuration: 6 }),
      subject(3, { unemploymentDuration: 6, happiness: 0.1 }),
      subject(4, { canWork: false }),
    ])
    expect([working.state, working.working, working.tone]).toEqual(['work', true, 'work'])
    expect([looking.state, looking.working, looking.tone]).toEqual(['look', false, 'look'])
    expect([unhappy.state, unhappy.tone]).toEqual(['look', 'low'])
    expect([idle.state, idle.working, idle.tone]).toEqual(['idle', false, 'idle'])
  })

  test('a household that lost its home is red even with a job; only the first four are pinned', () => {
    const [first] = pins([subject(5, { isEmployed: true, housingSecurity: false })])
    expect([first.state, first.working, first.tone]).toEqual(['home', false, 'low'])
    expect(pins([1, 2, 3, 4, 5].map(id => subject(id)))).toHaveLength(4)
  })

  test('an unhappy household that cannot work is red, and a content one is grey', () => {
    const [sad, content] = pins([subject(1, { canWork: false, happiness: 0.1 }), subject(2, { canWork: false, happiness: 0.9 })])
    expect([sad.tone, content.tone]).toEqual(['low', 'idle'])
  })
})
