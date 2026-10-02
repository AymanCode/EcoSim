import { beforeAll, describe, expect, test } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import TownCard from '../town/TownCard.jsx'
import RunScreen from '../RunScreen.jsx'
import { COPY } from '../catalog.js'
import { townAt } from '../town/model.js'
import { scenePalette } from '../town/mood.js'
import { demoArms, fixtureArm } from './fixture.js'

let A, B
beforeAll(() => { [A, B] = demoArms() })

const houseIndexes = (container, state) => new Set(
  [...container.querySelectorAll('[data-kind="house"]')]
    .filter(house => house.classList.contains(`is-${state}`))
    .map(house => Number(house.dataset.index)),
)

describe('TownCard', () => {
  test('draws 100 houses in their states and every shop on a lot', () => {
    const { container } = render(<TownCard arm={A} tick={70} towns={2} />)
    const houses = container.querySelectorAll('[data-kind="house"]')
    expect(houses).toHaveLength(100)
    const dark = [...houses].filter(house => house.classList.contains('is-look'))
    expect(dark.length).toBe(34)
    expect(container.querySelectorAll('[data-kind="shop"]').length).toBeGreaterThan(15)
    expect(container.querySelectorAll('[data-slot]')).toHaveLength(256)
  })

  test('the mood chip and the summary name how the town is doing', () => {
    render(<TownCard arm={A} tick={100} towns={2} />)
    expect(screen.getByText('Hard times')).toBeInTheDocument()
    expect(screen.getByText('The town is going through hard times.')).toBeInTheDocument()
  })

  test('winter puts snow on the roofs, summer does not', () => {
    const { container, rerender } = render(<TownCard arm={A} tick={102} towns={2} />)
    expect(container.querySelector('svg.lt-scene').classList.contains('season-winter')).toBe(true)
    rerender(<TownCard arm={A} tick={80} towns={2} />)
    expect(container.querySelector('svg.lt-scene').classList.contains('season-summer')).toBe(true)
  })

  test('shop signs: CLOSED in the first weeks after closing, a crown on the richest shop', () => {
    const { container } = render(<TownCard arm={A} tick={70} towns={2} />)
    expect(container.textContent).toContain('CLOSED')
    expect(container.querySelectorAll('.lt-crown')).toHaveLength(1)
  })

  test('Enlarge asks to focus the town', () => {
    const calls = []
    render(<TownCard arm={A} tick={70} towns={2} canFocus onFocus={() => calls.push('focus')} />)
    fireEvent.click(screen.getByRole('button', { name: 'Enlarge' }))
    expect(calls).toEqual(['focus'])
  })
})

// What the old flat town drawing showed and its tests protected, now in the diorama.
describe('TownCard keeps what the old town drawing showed', () => {
  test('houses keep their place, so only the houses at the edge change', () => {
    const arm = fixtureArm()
    const { container, rerender } = render(<TownCard arm={arm} tick={12} towns={1} />)
    const before = houseIndexes(container, 'look')
    rerender(<TownCard arm={arm} tick={13} towns={1} />)
    const after = houseIndexes(container, 'look')
    expect(before.size).toBe(18)
    expect(after.size).toBe(27)
    for (const index of before) expect(after.has(index)).toBe(true)
  })

  test('working homes glow, dark ones do not; a lost home carries a FOR SALE sign', () => {
    const { container } = render(<TownCard arm={fixtureArm()} tick={11} towns={1} />)
    // Week 11: 41.67 in 100 out of work, nobody homeless.
    expect(houseIndexes(container, 'work').size).toBe(58)
    expect(houseIndexes(container, 'look').size).toBe(42)
    expect(container.querySelectorAll('.lt-glow.is-on')).toHaveLength(58)
    const house = container.querySelector('[data-kind="house"]')
    expect(house.querySelector('.lt-sale')).toHaveTextContent('FOR SALE')
    expect(house.querySelector('.lt-win')).not.toBeNull()
  })

  test('a struggling shop has SALE on its window and a flag; a closed one is boarded up', () => {
    const { container } = render(<TownCard arm={A} tick={70} towns={2} />)
    const struggling = container.querySelectorAll('.lt-shop.is-struggling')
    expect(struggling.length).toBeGreaterThan(0)
    struggling.forEach(shop => {
      expect(shop).toHaveTextContent('SALE')
      expect(shop.querySelector('.lt-flag-wave')).not.toBeNull()
    })
    const closed = container.querySelectorAll('.lt-shop.is-closed')
    expect(closed.length).toBeGreaterThan(0)
    closed.forEach(shop => expect(shop.querySelectorAll('.lt-board')).toHaveLength(2))
  })

  test('a shop being built is scaffolded; a new one has balloons and a NEW sign; a growing one a crane and HIRING', () => {
    const seen = { fresh: 0, isNew: 0, growing: 0 }
    for (const tick of [11, 14, 30]) {
      const { container, unmount } = render(<TownCard arm={A} tick={tick} towns={2} />)
      for (const shop of townAt(A, tick).shops) {
        const drawn = container.querySelector(`[data-kind="shop"][data-id="${shop.id}"]`)
        const sign = container.querySelector(`[data-sign="${shop.id}"]`)
        if (shop.fresh) {
          seen.fresh += 1
          expect(drawn.querySelector('polyline')).not.toBeNull()
          expect(drawn.querySelector('.lt-win')).toBeNull()
        } else if (shop.isNew) {
          seen.isNew += 1
          expect(drawn.querySelector('.lt-balloons')).not.toBeNull()
          if (shop.state !== 'growing') expect(sign).toHaveTextContent('NEW')
        }
        if (shop.state === 'growing') {
          seen.growing += 1
          expect(sign).toHaveTextContent('HIRING')
          if (!shop.fresh) expect(drawn.querySelector('.lt-crane-hook')).not.toBeNull()
        }
      }
      unmount()
    }
    expect(seen.fresh).toBeGreaterThan(0)
    expect(seen.isNew).toBeGreaterThan(0)
    expect(seen.growing).toBeGreaterThan(0)
  })

  test('more businesses than lots: the extra ones are counted in a sign and the summary', () => {
    const arm = fixtureArm()
    const snap = arm.snapshots[24]
    const extra = Array.from({ length: 55 }, (_, i) => ({
      id: 100 + i, name: `FoodProduct${100 + i}`, sector: 'Food', cash: 500, staff: 2,
      price: 5, lastRevenue: 0, lastProfit: 0, state: 'steady', isBaseline: false,
    }))
    arm.snapshots[24] = { ...snap, firms: [...snap.firms, ...extra] }
    const { container } = render(<TownCard arm={arm} tick={24} towns={1} />)
    const overflow = townAt(arm, 24).overflow
    expect(overflow).toBeGreaterThan(0)
    expect(container.querySelectorAll('[data-kind="shop"]')).toHaveLength(50)
    expect(container.querySelector('.lt-more')).toHaveTextContent(`+${overflow} more`)
    expect(container.querySelector('.nx-sr')).toHaveTextContent('than lots')
  })

  test('the town hall pulses a ring in the town colour for four weeks after the rules change', () => {
    const arm = fixtureArm()
    arm.policyChanges = [{ id: 'c1', tick: 15, policy: 'minimum_wage_policy', value: 'high' }]
    const { container, rerender } = render(<TownCard arm={arm} tick={17} towns={1} />)
    const ring = () => container.querySelector('[data-kind="hall"] .lt-hall-ring')
    expect(ring()).not.toBeNull()
    expect(ring().getAttribute('stroke')).toBe('#2E6FE0')
    expect(container.querySelector('.nx-sr')).toHaveTextContent('Town hall: new rules this month')
    expect(container.querySelector('[data-kind="hall"]')).toHaveTextContent('NEW MIN. WAGE')
    rerender(<TownCard arm={arm} tick={21} towns={1} />)
    expect(ring()).toBeNull()
    expect(container.querySelector('.nx-sr')).not.toHaveTextContent('new rules')
    rerender(<TownCard arm={arm} tick={14} towns={1} />)
    expect(ring()).toBeNull()
  })

  test('four facts and a text alternative for the drawing', () => {
    const { container } = render(<TownCard arm={fixtureArm()} tick={11} towns={1} />)
    const facts = [...container.querySelectorAll('.lt-facts > div')].map(fact => [fact.querySelector('dd').textContent, fact.querySelector('dt').textContent])
    expect(facts).toHaveLength(4)
    expect(facts[0]).toEqual(['42 in 100', 'out of work'])
    expect(facts[1]).toEqual(['$36', 'typical weekly pay'])
    expect(facts[2]).toEqual(['9', 'shops open'])
    container.querySelectorAll('.lt-facts dt').forEach(label => expect(label).toHaveAttribute('data-fits'))
    expect(container.querySelector('svg.lt-scene')).toHaveAttribute('aria-hidden', 'true')
    const alt = container.querySelector('.nx-sr')
    expect(alt).toHaveTextContent('Out of every 100 households: 58 working, 42 looking for work, 0 lost their home.')
    expect(alt).toHaveTextContent('9 firms open: 0 struggling. 0 closed in the last year.')
    const model = townAt(fixtureArm(), 11)
    expect(alt).toHaveTextContent(COPY.diorama.summary.weather(model.season, model.band))
    expect(alt).toHaveTextContent(COPY.diorama.summary.mood(model.band))
  })

  test('the town hall\'s money: a coin stack with the amount, an IOU when it owes, nothing when unmeasured', () => {
    const owing = fixtureArm()
    const at = owing.ticks.indexOf(20)
    owing.series.townHallCash = owing.ticks.map(() => 5000)
    owing.series.townHallCash[at] = -23000
    const { container, rerender } = render(<TownCard arm={owing} tick={19} towns={1} />)
    const hall = () => container.querySelector('.lt-treasury')
    const amount = () => container.querySelector('.lt-amount')
    const hallFact = () => container.querySelectorAll('.lt-facts > div')[3]
    expect(hall().querySelectorAll('.lt-coin')).toHaveLength(1)
    expect(amount()).toHaveTextContent('$5k')
    expect(hallFact().querySelector('dt')).toHaveTextContent('in the town hall')
    rerender(<TownCard arm={owing} tick={20} towns={1} />)
    expect(hall().querySelectorAll('.lt-coin')).toHaveLength(0)
    expect(hall()).toHaveClass('is-owed')
    expect(amount()).toHaveTextContent('owes $23k')
    expect(hallFact().querySelector('dd')).toHaveTextContent('$23k')
    expect(hallFact().querySelector('dd')).toHaveClass('is-owed')
    expect(hallFact().querySelector('dt')).toHaveTextContent('the town hall owes')
    owing.series.townHallCash = owing.ticks.map(() => null)
    rerender(<TownCard arm={{ ...owing }} tick={20} towns={1} />)
    expect(hall().childNodes).toHaveLength(0)
    expect(amount()).toBeNull()
    expect(hallFact().querySelector('dd')).toHaveTextContent('not measured')
  })

  test('a pin for each followed household, coloured by how they are doing', () => {
    const { container } = render(<TownCard arm={A} tick={70} towns={2} />)
    const model = townAt(A, 70)
    const pins = [...container.querySelectorAll('[data-kind="person"]')]
    expect(pins).toHaveLength(model.people.length)
    pins.forEach((pin, i) => {
      expect(pin.dataset.index).toBe(String(i))
      expect(pin.querySelector('.lt-pin')).toHaveClass(`is-${model.people[i].tone}`)
      expect(pin).toHaveTextContent(model.people[i].name.charAt(0))
    })
  })

  test('the hooks the motion and the cards need are in the drawing', () => {
    const { container } = render(<TownCard arm={A} tick={70} towns={2} />)
    for (const layer of ['coins', 'pings', 'moments', 'clouds', 'rain']) expect(container.querySelector(`[data-layer="${layer}"]`), layer).not.toBeNull()
    expect(container.querySelectorAll('[data-cloud]')).toHaveLength(6)
    expect(container.querySelector('[data-flash="bank"]')).not.toBeNull()
    expect(container.querySelectorAll('[data-kind="hall"]')).toHaveLength(1)
    expect(container.querySelectorAll('[data-kind="bank"]')).toHaveLength(1)
    const ids = [...container.querySelectorAll('[data-kind="shop"]')].map(shop => Number(shop.dataset.id))
    expect(new Set(ids).size).toBe(ids.length)
    for (const layer of ['coins', 'pings', 'moments']) expect(container.querySelector(`[data-layer="${layer}"]`).childNodes).toHaveLength(0)
  })

  test('the weather follows the mood: sky colours, cloud count, rain or snow', () => {
    const { container, rerender } = render(<TownCard arm={A} tick={100} towns={2} />)
    const model = townAt(A, 100)
    const palette = scenePalette(model.mood, model.season)
    // The variables sit on the parts that read them: sky, sun, clouds, ground, shade, glows and rain.
    const parts = [...container.querySelectorAll('[data-weather]')]
    expect(parts).toHaveLength(7)
    parts.forEach(part => {
      expect(part.style.getPropertyValue('--lt-sky-top')).toBe(palette.skyTop)
      expect(part.style.getPropertyValue('--lt-rain')).toBe(palette.rain.toFixed(2))
    })
    expect(container.querySelector('svg.lt-scene').style.length).toBe(0)
    expect(container.querySelector('[data-layer="rain"]')).not.toHaveClass('is-dry')
    const shown = () => [...container.querySelectorAll('[data-cloud]')].filter(cloud => cloud.style.opacity !== '0').length
    expect(shown()).toBe(palette.cloudCount)
    expect(container.querySelector('[data-layer="rain"]')).not.toHaveClass('is-snow')
    rerender(<TownCard arm={A} tick={102} towns={2} />)
    expect(container.querySelector('[data-layer="rain"]')).toHaveClass('is-snow')
    // A dry week takes the rain out altogether, so its drops stop animating.
    const dry = townAt(B, 40)
    expect(scenePalette(dry.mood, dry.season).rain).toBe(0)
    rerender(<TownCard arm={B} tick={40} towns={2} />)
    expect(container.querySelector('[data-layer="rain"]')).toHaveClass('is-dry')
  })
})

describe('Run screen towns', () => {
  const props = { tick: 70, maxTick: 104, playing: false, onToggle() {}, onScrub() {}, speed: 1, onSpeed() {} }

  test('one card per town, side by side, with the shared legend', () => {
    const { container } = render(<RunScreen arms={[A, B]} {...props} />)
    expect(container.querySelectorAll('.lt-card')).toHaveLength(2)
    expect(container.querySelector('.lt-towns').classList.contains('is-2')).toBe(true)
    expect(container.querySelector('.lt-legend')).toBeInTheDocument()
  })

  test('one town fills the row; four towns make a 2 × 2 grid', () => {
    const { container, rerender } = render(<RunScreen arms={[A]} {...props} />)
    expect(container.querySelector('.lt-towns').classList.contains('is-1')).toBe(true)
    expect(screen.queryByRole('button', { name: 'Enlarge' })).toBeNull()
    const [C, D] = demoArms()
    rerender(<RunScreen arms={[A, B, { ...C, label: 'Town C', color: '#199E70' }, { ...D, label: 'Town D', color: '#9085E9' }]} {...props} />)
    expect(container.querySelector('.lt-towns').classList.contains('is-4')).toBe(true)
  })

  test('Enlarge shows only that town; Show both brings the other back', () => {
    const { container } = render(<RunScreen arms={[A, B]} {...props} />)
    fireEvent.click(screen.getAllByRole('button', { name: 'Enlarge' })[1])
    expect(container.querySelectorAll('.lt-card:not([hidden])')).toHaveLength(1)
    expect(container.querySelector('.lt-card:not([hidden])')).toHaveTextContent('Town B')
    expect(container.querySelector('.lt-towns')).toHaveClass('is-focus')
    fireEvent.click(screen.getByRole('button', { name: 'Show both' }))
    expect(container.querySelectorAll('.lt-card:not([hidden])')).toHaveLength(2)
    expect(container.querySelector('.lt-towns')).not.toHaveClass('is-focus')
  })

  test('the Businesses and Households panels are still there for each town', () => {
    render(<RunScreen arms={[A, B]} {...props} />)
    expect(screen.getAllByText('Businesses')).toHaveLength(2)
    expect(screen.getAllByText('Households')).toHaveLength(2)
  })
})
