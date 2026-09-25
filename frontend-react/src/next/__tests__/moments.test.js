import { describe, expect, test } from 'vitest'
import { createArm, ingest } from '../data/session.js'
import { firmDisplayName } from '../names.js'
import { moments } from '../narration.js'
import { TOWN_A, TOWN_B } from './fixture.js'

const OUT = 'peopleOutOfWorkPer100'

// A town with a frame for every week from 1 to `weeks`: `out(t)` people out of
// work per 100, `firms(t)` the open firms and `events(t)` the week's events.
function town(meta, { weeks = 40, out = () => 5, firms = () => [], events = () => [] } = {}) {
  const arm = createArm(meta)
  for (let t = 1; t <= weeks; t += 1) {
    ingest(arm, { tick: t, metrics: {}, curated: { [OUT]: out(t) }, firms: firms(t), events: events(t) })
  }
  return arm
}

// Policy changes arrive as `lever=value` text, so numbers come as strings.
const rule = (tick, text, n = 0) => ({ id: `${tick}:policy_changed:${n}`, tick, type: 'policy_changed', text })
const rulesAt = (week, ...texts) => t => (t === week ? texts.map((text, n) => rule(t, text, n)) : [])
const firm = (id, name, cash) => ({ id, name, sector: 'Food', cash, staff: 3, state: 'steady', isBaseline: false })
const ofKind = (list, kind) => list.filter(moment => moment.kind === kind)

describe('moments: the town hall changes the rules', () => {
  test('a change in week 20 is a moment from week 20 to week 25, and not in week 26', () => {
    const b = town(TOWN_B, { events: rulesAt(20, 'minimum_wage_policy=high') })
    expect(moments([b], 19)).toEqual([])
    for (let t = 20; t <= 25; t += 1) {
      expect(moments([b], t)).toEqual([{
        id: 'rule:Town B:20',
        kind: 'rule',
        label: 'Town B',
        color: TOWN_B.color,
        tick: 20,
        text: "Town B's town hall brought in a higher minimum wage.",
      }])
    }
    expect(moments([b], 26)).toEqual([])
  })

  test('a change during the warm-up weeks is never a moment', () => {
    const b = town(TOWN_B, { events: rulesAt(5, 'minimum_wage_policy=high') })
    for (let t = 1; t <= 20; t += 1) expect(moments([b], t)).toEqual([])
  })

  test('phrases numbers sent as text, and reads one week\'s changes as one moment', () => {
    const tax = town(TOWN_A, { events: rulesAt(20, 'wage_tax_rate=0.2') })
    expect(moments([tax], 21).map(moment => moment.text)).toEqual(["Town A's town hall brought in a 20% tax on wages."])
    const subsidy = town(TOWN_B, { events: rulesAt(20, 'sector_subsidy_target=food', 'sector_subsidy_level=25') })
    expect(moments([subsidy], 20)).toEqual([expect.objectContaining({
      id: 'rule:Town B:20',
      text: "Town B's town hall brought in a 25% subsidy for food firms.",
    })])
  })
})

describe('moments: a new richest business', () => {
  const RICH = firm(1, 'FoodCo1', 500)
  const RIVAL = { ...firm(2, 'FoodCo2', 300) }

  test('a new leader between weeks 30 and 34 is a moment at week 34', () => {
    const a = town(TOWN_A, { firms: t => [RICH, { ...RIVAL, cash: t >= 32 ? 600 : 300 }] })
    expect(ofKind(moments([a], 31), 'richest')).toEqual([])
    expect(moments([a], 34)).toEqual([{
      id: 'richest:Town A:32',
      kind: 'richest',
      label: 'Town A',
      color: TOWN_A.color,
      tick: 32,
      text: `${firmDisplayName(RIVAL)} is now Town A's richest business.`,
    }])
    // Four weeks on, week 32's leader is the one to beat.
    expect(moments([a], 36)).toEqual([])
  })

  test('the leader closing hands the lead to the next richest', () => {
    const a = town(TOWN_A, { firms: t => (t >= 32 ? [RIVAL] : [RICH, RIVAL]) })
    expect(moments([a], 33).map(moment => moment.text)).toEqual([`${firmDisplayName(RIVAL)} is now Town A's richest business.`])
  })

  test('a tie keeps the earlier leader', () => {
    const a = town(TOWN_A, { firms: t => [RICH, { ...RIVAL, cash: t >= 32 ? 500 : 300 }] })
    expect(moments([a], 34)).toEqual([])
  })

  test('a lead taken back within the four weeks is no moment', () => {
    const a = town(TOWN_A, { firms: t => [RICH, { ...RIVAL, cash: t === 32 ? 600 : 300 }] })
    expect(ofKind(moments([a], 32), 'richest')).toHaveLength(1)
    expect(moments([a], 34)).toEqual([])
  })

  test('never compares with a warm-up week', () => {
    const a = town(TOWN_A, { firms: t => [RICH, { ...RIVAL, cash: t >= 11 ? 600 : 300 }] })
    for (let t = 1; t <= 20; t += 1) expect(moments([a], t)).toEqual([])
  })
})

describe('moments: people out of work passing 10, 20 or 30 in 100', () => {
  test('19 to 21 passes 20, and 21 to 19 falls below it', () => {
    const up = town(TOWN_A, { out: t => (t >= 30 ? 21 : 19) })
    expect(moments([up], 29)).toEqual([])
    expect(moments([up], 30)).toEqual([{
      id: 'milestone:Town A:30',
      kind: 'milestone',
      label: 'Town A',
      color: TOWN_A.color,
      tick: 30,
      text: 'Town A passed 20 in 100 people out of work.',
    }])
    expect(moments([up], 34)).toEqual([])

    const down = town(TOWN_B, { out: t => (t >= 30 ? 19 : 21) })
    expect(moments([down], 32).map(moment => moment.text)).toEqual(['Town B fell below 20 in 100 people out of work.'])
  })

  test('compares the figures as the page shows them', () => {
    // 19.4 and 20.4 both read "in 100" as whole numbers: 19, then 20, which is not past 20.
    expect(moments([town(TOWN_A, { out: t => (t >= 30 ? 20.4 : 19.4) })], 31)).toEqual([])
    expect(moments([town(TOWN_A, { out: t => (t >= 30 ? 20.6 : 19.4) })], 31).map(moment => moment.text))
      .toEqual(['Town A passed 20 in 100 people out of work.'])
  })

  test('a jump past several marks names the furthest one', () => {
    const a = town(TOWN_A, { out: t => (t >= 30 ? 31 : 8) })
    expect(moments([a], 30).map(moment => moment.text)).toEqual(['Town A passed 30 in 100 people out of work.'])
    const b = town(TOWN_B, { out: t => (t >= 30 ? 8 : 31) })
    expect(moments([b], 30).map(moment => moment.text)).toEqual(['Town B fell below 10 in 100 people out of work.'])
  })

  test('never from the warm-up weeks', () => {
    const a = town(TOWN_A, { out: t => (t >= 11 ? 25 : 5) })
    for (let t = 1; t <= 20; t += 1) expect(moments([a], t)).toEqual([])
  })
})

describe('moments across towns', () => {
  test('at most three, newest first', () => {
    const a = town(TOWN_A, {
      events: t => [...rulesAt(20, 'benefit_level=high')(t), ...rulesAt(23, 'public_works=on')(t)],
      out: t => (t >= 22 ? 21 : 19),
    })
    const b = town(TOWN_B, { firms: t => [firm(1, 'FoodCo1', 500), firm(2, 'FoodCo2', t >= 21 ? 600 : 300)] })
    const all = moments([a, b], 24)
    expect(all.map(moment => [moment.kind, moment.label, moment.tick])).toEqual([
      ['rule', 'Town A', 23],
      ['milestone', 'Town A', 22],
      ['richest', 'Town B', 21],
    ])
  })

  test('ids stay the same from week to week', () => {
    const a = town(TOWN_A, {
      events: rulesAt(30, 'benefit_level=high'),
      out: t => (t >= 31 ? 21 : 19),
      firms: t => [firm(1, 'FoodCo1', 500), firm(2, 'FoodCo2', t >= 32 ? 600 : 300)],
    })
    const idsAt = t => moments([a], t).map(moment => moment.id).sort()
    expect(idsAt(32)).toEqual(['milestone:Town A:31', 'richest:Town A:32', 'rule:Town A:30'])
    expect(idsAt(33)).toEqual(idsAt(32))
    expect(idsAt(34)).toEqual(idsAt(32))
    expect(idsAt(35)).toEqual(['richest:Town A:32', 'rule:Town A:30'])
  })

  test('nothing for no towns', () => {
    expect(moments([], 30)).toEqual([])
    expect(moments(undefined, 30)).toEqual([])
  })
})
