import { StrictMode, useState } from 'react'
import { afterEach, beforeAll, beforeEach, describe, expect, test, vi } from 'vitest'
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
    // Each variable sits only on the part that reads it: sky, sun, clouds,
    // ground, shade, glows and rain, so a changing sky never restyles the ground.
    const parts = [...container.querySelectorAll('[data-weather]')]
    expect(parts.map(part => part.dataset.weather).sort()).toEqual(['clouds', 'glow', 'grass', 'rain', 'shade', 'sky', 'sun'])
    const part = kind => container.querySelector(`[data-weather="${kind}"]`)
    const vars = kind => [...part(kind).style].filter(name => name.startsWith('--lt-')).sort()
    expect(part('sky').style.getPropertyValue('--lt-sky-top')).toBe(palette.skyTop)
    expect(part('sky').style.getPropertyValue('--lt-sky-bottom')).toBe(palette.skyBottom)
    expect(part('rain').style.getPropertyValue('--lt-rain')).toBe(palette.rain.toFixed(2))
    expect(part('grass').style.getPropertyValue('--lt-grass-a')).toBe(palette.grassA)
    expect(part('shade').style.getPropertyValue('--lt-shade')).toBe(palette.shade.toFixed(3))
    expect(vars('grass')).toEqual(['--lt-grass-a', '--lt-grass-b'])
    expect(vars('sun')).toEqual(['--lt-sun'])
    expect(vars('clouds')).toEqual(['--lt-cloud-fill'])
    expect(vars('glow')).toEqual(['--lt-glow'])
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

// Everything that moves between weeks (useSceneMotion): the floating signs,
// walkers and coins of a week played forward, traffic, the weather easing in,
// and shop heights easing to their new floors. Animation frames and the clock
// run only when a test advances them.
describe('TownCard motion between weeks', () => {
  const realMatchMedia = window.matchMedia
  beforeEach(() => { vi.useFakeTimers({ toFake: ['requestAnimationFrame', 'cancelAnimationFrame', 'performance'] }) })
  afterEach(() => {
    vi.useRealTimers()
    window.matchMedia = realMatchMedia
  })
  const reduceMotion = () => {
    window.matchMedia = query => ({ ...realMatchMedia(query), matches: query.includes('prefers-reduced-motion: reduce') })
  }
  const frames = ms => vi.advanceTimersByTime(ms)
  const layer = (container, name) => container.querySelector(`[data-layer="${name}"]`)
  const inSlots = (container, selector) => container.querySelectorAll(`[data-slot] > ${selector}`)
  const skyTop = container => container.querySelector('[data-weather~="sky"]').style.getPropertyValue('--lt-sky-top')
  const flying = container => [...layer(container, 'coins').querySelectorAll('circle')].filter(coin => coin.style.display !== 'none')
  const card = (tick, props = {}) => <TownCard arm={A} tick={tick} towns={2} speed={1} {...props} />

  test('scrubbing to another week adds no floating signs', () => {
    const { container, rerender } = render(<TownCard arm={A} tick={69} towns={2} playing={false} speed={1} />)
    rerender(<TownCard arm={A} tick={70} towns={2} playing={false} speed={1} />)
    expect(container.querySelectorAll('[data-layer="moments"] > *')).toHaveLength(0)
  })

  test("a single forward step while playing pops the week's moments", () => {
    const { container, rerender } = render(<TownCard arm={A} tick={69} towns={2} playing speed={1} />)
    rerender(<TownCard arm={A} tick={70} towns={2} playing speed={1} />)
    expect(container.querySelector('[data-layer="moments"]').textContent).toContain('Closed')
  })

  test('a week one on that comes from a scrub while playing is not a step', () => {
    const { container, rerender } = render(card(69, { playing: true, scrubs: 3 }))
    rerender(card(70, { playing: true, scrubs: 4 }))
    expect(layer(container, 'moments').childNodes).toHaveLength(0)
    expect(container.querySelectorAll('[data-slot] > .lt-walker.is-moving')).toHaveLength(0)
    // The clock playing on from there is a step again.
    rerender(card(71, { playing: true, scrubs: 4 }))
    expect(layer(container, 'moments').textContent).toContain('Bad loans')
  })

  test('bad loans: a sign over the bank and the bank flashes red; a closure leaves a puff of dust', () => {
    const { container, rerender } = render(card(69, { playing: true }))
    rerender(card(70, { playing: true }))
    expect(layer(container, 'moments').textContent).toContain('Bad loans $19k')
    expect(layer(container, 'moments').querySelectorAll('.lt-puff').length).toBeGreaterThan(0)
    frames(50)
    expect(container.querySelector('[data-flash="bank"]')).toHaveClass('is-on')
  })

  test('a newer sign over the same place replaces the older one', () => {
    // Weeks 70 and 71: loans go bad both weeks; one sign over the bank.
    const { container, rerender } = render(card(69, { playing: true }))
    rerender(card(70, { playing: true }))
    rerender(card(71, { playing: true }))
    const bank = [...layer(container, 'moments').querySelectorAll('.lt-moment')].filter(sign => sign.textContent.startsWith('Bad loans'))
    expect(bank).toHaveLength(1)
    expect(layer(container, 'moments').querySelectorAll('.lt-moment').length).toBeGreaterThan(1)
  })

  test('dust puffs are capped like the signs', () => {
    // Weeks 70 to 75 each close a shop in Town A: three puffs a closure.
    const { container, rerender } = render(card(69, { playing: true }))
    for (let tick = 70; tick <= 75; tick += 1) rerender(card(tick, { playing: true }))
    expect(layer(container, 'moments').querySelectorAll('.lt-puff')).toHaveLength(12)
  })

  test('scrubbing away clears what the last step set moving', () => {
    const { container, rerender } = render(card(10, { playing: true }))
    rerender(card(11, { playing: true }))
    frames(300)
    expect(layer(container, 'moments').childNodes.length).toBeGreaterThan(0)
    expect(container.querySelectorAll('[data-slot] > .lt-walker.is-moving').length).toBeGreaterThan(0)
    expect(flying(container).length).toBeGreaterThan(0)
    rerender(card(40, { playing: false }))
    expect(layer(container, 'moments').childNodes).toHaveLength(0)
    expect(container.querySelectorAll('[data-slot] > .lt-walker.is-moving')).toHaveLength(0)
    expect(flying(container)).toHaveLength(0)
  })

  test('people laid off walk home carrying a box', () => {
    // Week 11: firm 1 lets 5 go; two of them are drawn walking home.
    const { container, rerender } = render(card(10, { playing: true }))
    rerender(card(11, { playing: true }))
    const moving = [...container.querySelectorAll('[data-slot] > .lt-walker.is-moving')]
    expect(moving).toHaveLength(2)
    moving.forEach(walker => expect(walker.querySelector('rect')).not.toBeNull())
  })

  test('pausing stops walkers, coins and signs where they are, and the loop sleeps', () => {
    const { container, rerender } = render(card(10, { playing: true }))
    rerender(card(11, { playing: true }))
    frames(600)
    const walker = container.querySelector('[data-slot] > .lt-walker.is-moving')
    const where = () => [walker.getAttribute('transform'), flying(container).map(coin => `${coin.getAttribute('cx')},${coin.getAttribute('cy')}`).join(' ')]
    rerender(card(11, { playing: false }))
    const paused = where()
    expect(paused[1]).not.toBe('')
    frames(2000)
    expect(where()).toEqual(paused)
    expect(walker.isConnected).toBe(true)
    expect(layer(container, 'moments')).toHaveAttribute('data-paused')
    expect(vi.getTimerCount()).toBe(0)
    rerender(card(11, { playing: true }))
    expect(layer(container, 'moments')).not.toHaveAttribute('data-paused')
    frames(100)
    expect(where()[0]).not.toBe(paused[0])
  })

  test('cars and people on the roads follow the model, in the tile slots', () => {
    const { container, rerender } = render(<TownCard arm={B} tick={11} towns={2} playing={false} speed={1} />)
    const count = tick => {
      const { traffic } = townAt(B, tick)
      expect(inSlots(container, '.lt-car')).toHaveLength(traffic.cars)
      expect(inSlots(container, '.lt-walker:not(.is-moving)')).toHaveLength(traffic.walkers)
    }
    count(11)
    rerender(<TownCard arm={B} tick={69} towns={2} playing={false} speed={1} />)
    count(69)
  })

  test('the drawing\'s structure survives a week change, and so do the things the loop added', () => {
    const { container, rerender } = render(<TownCard arm={B} tick={60} towns={2} playing={false} speed={1} />)
    const slots = [...container.querySelectorAll('[data-slot]')]
    const layers = [...container.querySelectorAll('[data-layer]')]
    const cars = [...inSlots(container, '.lt-car')]
    expect(cars.length).toBeGreaterThan(0)
    rerender(<TownCard arm={B} tick={61} towns={2} playing={false} speed={1} />)
    expect([...container.querySelectorAll('[data-slot]')].every((slot, i) => slot === slots[i])).toBe(true)
    expect([...container.querySelectorAll('[data-layer]')].every((node, i) => node === layers[i])).toBe(true)
    expect(cars.every(car => car.isConnected)).toBe(true)
  })

  test('mounting twice (StrictMode) leaves one set of cars and people, not two', () => {
    const { container } = render(<StrictMode><TownCard arm={B} tick={69} towns={2} playing={false} speed={1} /></StrictMode>)
    const { traffic } = townAt(B, 69)
    expect(inSlots(container, '.lt-car')).toHaveLength(traffic.cars)
    expect(inSlots(container, '.lt-walker')).toHaveLength(traffic.walkers)
  })

  test('coins carry money while playing, and none fly while paused', () => {
    const paused = render(<TownCard arm={B} tick={60} towns={2} playing={false} speed={1} />)
    const playing = render(<TownCard arm={B} tick={60} towns={2} playing speed={1} />)
    frames(400)
    expect(flying(playing.container).length).toBeGreaterThan(0)
    expect(flying(paused.container)).toHaveLength(0)
  })

  test('while playing the weather eases toward the new week; paused, it changes at once', () => {
    const target = tick => {
      const model = townAt(A, tick)
      return scenePalette(model.mood, model.season).skyTop
    }
    // Weeks 30 to 31: the mood falls by 0.13.
    const { container, rerender } = render(card(30, { playing: true }))
    expect(skyTop(container)).toBe(target(30))
    rerender(card(31, { playing: true }))
    expect(skyTop(container)).toBe(target(30))
    frames(200)
    expect([target(30), target(31)]).not.toContain(skyTop(container))
    frames(4000)
    expect(skyTop(container)).toBe(target(31))
    rerender(card(11, { playing: false }))
    expect(skyTop(container)).toBe(target(11))
  })

  test('a shop that gains or loses a floor eases to its new height', () => {
    // Week 71 to 72: some open shops change floors.
    const before = townAt(A, 71)
    const after = townAt(A, 72)
    const shop = after.shops.find(s => {
      const old = before.shops.find(o => o.id === s.id)
      return old && old.floors !== s.floors && s.state !== 'closed' && old.state !== 'closed' && !s.fresh
    })
    expect(shop).toBeTruthy()
    const walls = container => container.querySelector(`[data-kind="shop"][data-id="${shop.id}"] .lt-shop-l`).getAttribute('points')
    const drawn = tick => {
      const { container, unmount } = render(card(tick))
      const points = walls(container)
      unmount()
      return points
    }
    const [from, to] = [drawn(71), drawn(72)]
    expect(from).not.toBe(to)
    const { container, rerender } = render(card(71, { playing: true }))
    rerender(card(72, { playing: true }))
    expect(walls(container)).toBe(from)
    frames(200)
    expect([from, to]).not.toContain(walls(container))
    frames(300)
    expect(walls(container)).toBe(to)
  })

  test('with reduced motion: the weather changes at once, nothing travels, no floating signs', () => {
    reduceMotion()
    const { container, rerender } = render(card(69, { playing: true }))
    rerender(card(70, { playing: true }))
    const model = townAt(A, 70)
    expect(skyTop(container)).toBe(scenePalette(model.mood, model.season).skyTop)
    expect(layer(container, 'moments').childNodes).toHaveLength(0)
    frames(300)
    expect(layer(container, 'coins').querySelectorAll('circle')).toHaveLength(0)
    expect(container.querySelector('[data-flash="bank"]')).not.toHaveClass('is-on')
    expect(container.querySelectorAll('[data-slot] > .lt-walker.is-moving')).toHaveLength(0)
  })

  test('a card hidden by Enlarge keeps its week and does no work until it is shown', () => {
    const { container, rerender } = render(card(11, { playing: true }))
    rerender(card(12, { playing: true, hidden: true }))
    const dark = houseIndexes(container, 'look').size
    expect(dark).toBe(townAt(A, 12).counts.look)
    // Week 13 has far fewer dark homes; the hidden card still shows week 12.
    expect(townAt(A, 13).counts.look).not.toBe(dark)
    rerender(card(13, { playing: true, hidden: true }))
    expect(houseIndexes(container, 'look').size).toBe(dark)
    expect(layer(container, 'moments').childNodes).toHaveLength(0)
    expect(vi.getTimerCount()).toBe(0)
    rerender(card(14, { playing: true }))
    expect(houseIndexes(container, 'look').size).toBe(townAt(A, 14).counts.look)
    // Showing it again is a jump, not a step: no floating signs.
    expect(layer(container, 'moments').childNodes).toHaveLength(0)
  })
})

// The Run screen tells the drawings when to move: not on a live run held on a
// past week, and never take a week reached on the timeline for a step.
describe('Run screen towns in motion', () => {
  const props = { maxTick: 104, onToggle() {}, onSpeed() {}, speed: 1 }
  const signs = container => container.querySelectorAll('.lt-card [data-layer="moments"] > *').length

  test('playing forward a week pops its moments; the same week reached by the timeline does not', () => {
    const { container, rerender } = render(<RunScreen arms={[A, B]} tick={69} playing onScrub={() => {}} {...props} />)
    rerender(<RunScreen arms={[A, B]} tick={70} playing onScrub={() => {}} {...props} />)
    expect(signs(container)).toBeGreaterThan(0)

    function Scrubbed() {
      const [tick, setTick] = useState(69)
      return <RunScreen arms={[A, B]} tick={tick} playing onScrub={setTick} {...props} />
    }
    const scrubbed = render(<Scrubbed />)
    fireEvent.change(scrubbed.container.querySelector('input[type=range]'), { target: { value: '70' } })
    expect(scrubbed.container.querySelector('input[type=range]')).toHaveValue('70')
    expect(signs(scrubbed.container)).toBe(0)
  })

  test('a live run held on a past week does not move, though its towns run on', () => {
    const live = following => ({ phase: 'running', towns: [], following, onFollow() {}, onHall() {}, onTrack() {}, hallOpen: false })
    const held = render(<RunScreen arms={[A, B]} tick={69} playing onScrub={() => {}} live={live(false)} {...props} />)
    held.rerender(<RunScreen arms={[A, B]} tick={70} playing onScrub={() => {}} live={live(false)} {...props} />)
    expect(signs(held.container)).toBe(0)
    const following = render(<RunScreen arms={[A, B]} tick={69} playing onScrub={() => {}} live={live(true)} {...props} />)
    following.rerender(<RunScreen arms={[A, B]} tick={70} playing onScrub={() => {}} live={live(true)} {...props} />)
    expect(signs(following.container)).toBeGreaterThan(0)
  })
})
