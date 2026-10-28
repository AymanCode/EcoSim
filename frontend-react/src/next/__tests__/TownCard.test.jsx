import { StrictMode, useRef, useState } from 'react'
import { afterEach, beforeAll, beforeEach, describe, expect, test, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import TownCard from '../town/TownCard.jsx'
import RunScreen from '../RunScreen.jsx'
import { COPY } from '../catalog.js'
import { townAt } from '../town/model.js'
import { scenePalette } from '../town/mood.js'
import { LAYOUT } from '../town/geometry.js'
import { syncHeights, stepHeights } from '../town/heights.js'
import { ISLAND } from '../town/islandPlaces.js'
import { Shop } from '../town/shops.jsx'
import useSceneMotion from '../town/useSceneMotion.js'
import { WHOLE_SCREEN_MS, demoArms, fixtureArm } from './fixture.js'

let A, B
beforeAll(() => { [A, B] = demoArms() })

const houseIndexes = (container, state) => new Set(
  [...container.querySelectorAll('[data-kind="house"]')]
    .filter(house => house.classList.contains(`is-${state}`))
    .map(house => Number(house.dataset.index)),
)

describe('TownCard', () => {
  test('the lost marker keeps the loss week while the displayed snapshot is scrubbed back', () => {
    const { container, rerender } = render(<TownCard arm={A} tick={30} lostTick={30} />)
    expect(container.querySelector('.lt-lost')).toHaveTextContent('lost its connection in Year 1, week 30')
    rerender(<TownCard arm={A} tick={20} lostTick={30} />)
    expect(container.querySelector('.lt-lost')).toHaveTextContent('lost its connection in Year 1, week 30')
    rerender(<TownCard arm={A} tick={20} />)
    expect(container.querySelector('.lt-lost')).toBeNull()
  })

  test('a town beside a lost one keeps an empty marker line so the row stays level', () => {
    const { container, rerender } = render(<TownCard arm={A} tick={30} lostRow />)
    const line = container.querySelector('.lt-lost')
    expect(line).toHaveAttribute('aria-hidden', 'true')
    expect(line.textContent.trim()).toBe('')
    rerender(<TownCard arm={A} tick={30} />)
    expect(container.querySelector('.lt-lost')).toBeNull()
  })

  test('a town lost before its first week still has a marker', () => {
    render(<TownCard arm={A} tick={1} lostTick={0} />)
    expect(screen.getByText('lost its connection before its first week')).toBeInTheDocument()
  })

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

  // Renders the demo town at several weeks (about 2.7 s at full parallelism;
  // it timed out at 5 s once under load): it gets the whole-screen timeout.
  test('a shop being built is scaffolded; a new one has balloons and a NEW sign; a growing one a crane and HIRING', { timeout: WHOLE_SCREEN_MS }, () => {
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

  test('three stacked layers: the sky at the back, the world, and what moves on top', () => {
    const { container } = render(<TownCard arm={A} tick={70} towns={2} />)
    const stage = container.querySelector('.lt-canvas > .lt-stage')
    const layers = [...stage.children]
    expect(layers.map(layer => layer.dataset.layer)).toEqual(['back', 'world', 'motion'])
    for (const layer of layers) {
      expect(layer.tagName.toLowerCase()).toBe('svg')
      expect(layer.getAttribute('viewBox')).toBe(layers[0].getAttribute('viewBox'))
      expect(layer).toHaveAttribute('aria-hidden', 'true')
    }
    const [back, world, motion] = layers
    // The back and motion layers take no pointer events (town.css) and hold
    // nothing a viewer points at; everything with data-kind is in the world.
    expect(back).toHaveClass('lt-layer')
    expect(motion).toHaveClass('lt-layer')
    expect(world).toHaveClass('lt-scene')
    const kinds = [...container.querySelectorAll('[data-kind]')]
    expect(kinds.length).toBeGreaterThan(100)
    expect(kinds.every(node => world.contains(node))).toBe(true)
    expect(world.querySelectorAll('[data-slot]')).toHaveLength(256)
    expect(back.querySelector('[data-layer="clouds"]')).not.toBeNull()
    expect(back.querySelector('[data-weather="sky"]')).not.toBeNull()
    for (const name of ['rain', 'pings', 'coins', 'moments']) expect(motion.querySelector(`[data-layer="${name}"]`), name).not.toBeNull()
    expect(world.querySelector('[data-flash="bank"]')).not.toBeNull()
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

describe('Run screen towns', { timeout: WHOLE_SCREEN_MS }, () => {
  const props = { tick: 70, maxTick: 104, playing: false, onToggle() {}, onScrub() {} }

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
  const card = (tick, props = {}) => <TownCard arm={A} tick={tick} towns={2} {...props} />

  test('scrubbing to another week adds no floating signs', () => {
    const { container, rerender } = render(<TownCard arm={A} tick={69} towns={2} playing={false} />)
    rerender(<TownCard arm={A} tick={70} towns={2} playing={false} />)
    expect(container.querySelectorAll('[data-layer="moments"] > *')).toHaveLength(0)
  })

  test("a single forward step while playing pops the week's moments", () => {
    const { container, rerender } = render(<TownCard arm={A} tick={69} towns={2} playing />)
    rerender(<TownCard arm={A} tick={70} towns={2} playing />)
    expect(container.querySelector('[data-layer="moments"]').textContent).toContain('Closed')
  })

  test('a week one on that comes from a scrub while playing is not a step', () => {
    const { container, rerender } = render(card(69, { playing: true, scrubs: 3 }))
    rerender(card(70, { playing: true, scrubs: 4 }))
    expect(layer(container, 'moments').childNodes).toHaveLength(0)
    expect(container.querySelectorAll('[data-slot] > .lt-walker.is-moving')).toHaveLength(0)
    // The clock playing on from there is a step again.
    rerender(card(71, { playing: true, scrubs: 4 }))
    expect(layer(container, 'moments').textContent).toContain('Unpaid loans')
  })

  test('bad loans: a sign over the bank and the bank flashes red; a closure leaves a puff of dust', () => {
    const { container, rerender } = render(card(69, { playing: true }))
    rerender(card(70, { playing: true }))
    expect(layer(container, 'moments').textContent).toContain('Unpaid loans $19k')
    expect(layer(container, 'moments').querySelectorAll('.lt-puff').length).toBeGreaterThan(0)
    const flash = () => Number(container.querySelector('[data-flash="bank"]').getAttribute('opacity'))
    frames(150)
    expect(flash()).toBeGreaterThan(0.3)
    frames(1500)
    expect(flash()).toBe(0)
  })

  test('a newer sign over the same place replaces the older one', () => {
    // Weeks 70 and 71: loans go bad both weeks; one sign over the bank.
    const { container, rerender } = render(card(69, { playing: true }))
    rerender(card(70, { playing: true }))
    rerender(card(71, { playing: true }))
    const bank = [...layer(container, 'moments').querySelectorAll('.lt-moment')].filter(sign => sign.textContent.startsWith('Unpaid loans'))
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
    const sign = layer(container, 'moments').querySelector('.lt-moment')
    const where = () => [
      walker.getAttribute('transform'),
      flying(container).map(coin => `${coin.getAttribute('cx')},${coin.getAttribute('cy')}`).join(' '),
      `${sign.getAttribute('transform')} ${sign.getAttribute('opacity')}`,
    ]
    rerender(card(11, { playing: false }))
    const paused = where()
    expect(paused[1]).not.toBe('')
    frames(2000)
    expect(where()).toEqual(paused)
    expect(walker.isConnected).toBe(true)
    expect(sign.isConnected).toBe(true)
    expect(vi.getTimerCount()).toBe(0)
    rerender(card(11, { playing: true }))
    frames(100)
    expect(where()[0]).not.toBe(paused[0])
    expect(where()[2]).not.toBe(paused[2])
  })

  test('chimneys smoke, flags wave and struggling shops flicker while playing; paused or with reduced motion they stand still', () => {
    const smoke = container => container.querySelector('.lt-house.is-work.is-smoky .lt-smoke circle')
    const flag = container => container.querySelector('.lt-shop.is-struggling .lt-flag-wave')
    const lights = container => container.querySelector('.lt-shop.is-struggling .lt-wins')
    const pose = container => [smoke(container).getAttribute('transform'), smoke(container).getAttribute('opacity'), flag(container).getAttribute('transform')]
    const { container, rerender, unmount } = render(card(70, { playing: false }))
    // Drawn standing (React's pose), and nothing moves while paused.
    const drawn = pose(container)
    expect(drawn[0]).toMatch(/^translate\(.+\) scale\(.+\)$/)
    frames(1000)
    expect(pose(container)).toEqual(drawn)
    rerender(card(70, { playing: true }))
    frames(300)
    const moved = pose(container)
    expect(moved[0]).not.toBe(drawn[0])
    expect(moved[2]).not.toBe(drawn[2])
    // The lights dim for a moment twice in each 2.6 s.
    const seen = new Set()
    for (let i = 0; i < 30; i += 1) {
      frames(100)
      seen.add(lights(container).getAttribute('opacity'))
    }
    expect([...seen].sort()).toEqual(['0.25', '0.4', '1'])
    rerender(card(70, { playing: false }))
    const paused = pose(container)
    frames(1000)
    expect(pose(container)).toEqual(paused)
    unmount()

    reduceMotion()
    const reduced = render(card(70, { playing: true }))
    frames(1000)
    expect(pose(reduced.container)).toEqual(drawn)
  })

  test('switching reduced motion on mid-play puts smoke, flags and lights back in their drawn pose', () => {
    const listeners = new Set()
    const query = { matches: false, addEventListener: (type, fn) => listeners.add(fn), removeEventListener: (type, fn) => listeners.delete(fn) }
    window.matchMedia = () => query
    const pose = container => [
      container.querySelector('.lt-house.is-work.is-smoky .lt-smoke circle').getAttribute('transform'),
      container.querySelector('.lt-shop.is-struggling .lt-flag-wave').getAttribute('transform'),
      container.querySelector('.lt-shop.is-struggling .lt-wins').getAttribute('opacity'),
    ]
    const still = render(card(70, { playing: false }))
    const drawn = pose(still.container)
    still.unmount()
    const { container } = render(card(70, { playing: true }))
    let dim = false
    for (let i = 0; i < 40 && !dim; i += 1) {
      frames(50)
      dim = Number(pose(container)[2]) < 1
    }
    expect(dim).toBe(true)
    expect(pose(container)).not.toEqual(drawn)
    query.matches = true
    for (const fn of listeners) fn({ matches: true })
    expect(pose(container)).toEqual(drawn)
    frames(1000)
    expect(pose(container)).toEqual(drawn)
  })

  test('a shop that recovers keeps its lights on', () => {
    // Week 28 to 29: firm 7 stops struggling in Town A.
    const before = townAt(A, 28).shops.filter(shop => shop.state === 'struggling').map(shop => shop.id)
    const recovered = townAt(A, 29).shops.filter(shop => before.includes(shop.id) && shop.state !== 'struggling' && shop.state !== 'closed')
    expect(recovered.length).toBeGreaterThan(0)
    const { container, rerender } = render(card(28, { playing: true }))
    const wins = id => container.querySelector(`[data-kind="shop"][data-id="${id}"] .lt-wins`)
    let dim = false
    for (let i = 0; i < 30 && !dim; i += 1) {
      frames(50)
      dim = wins(recovered[0].id).getAttribute('opacity') !== '1'
    }
    expect(dim).toBe(true)
    rerender(card(29, { playing: true }))
    frames(1000)
    expect(wins(recovered[0].id)).not.toHaveAttribute('opacity')
  })

  test('cars and people on the roads follow the model, in the tile slots', () => {
    const { container, rerender } = render(<TownCard arm={B} tick={11} towns={2} playing={false} />)
    const count = tick => {
      const { traffic } = townAt(B, tick)
      expect(inSlots(container, '.lt-car')).toHaveLength(traffic.cars)
      expect(inSlots(container, '.lt-walker:not(.is-moving)')).toHaveLength(traffic.walkers)
    }
    count(11)
    rerender(<TownCard arm={B} tick={69} towns={2} playing={false} />)
    count(69)
  })

  test('the drawing\'s structure survives a week change, and so do the things the loop added', () => {
    const { container, rerender } = render(<TownCard arm={B} tick={60} towns={2} playing={false} />)
    const slots = [...container.querySelectorAll('[data-slot]')]
    const layers = [...container.querySelectorAll('[data-layer]')]
    const cars = [...inSlots(container, '.lt-car')]
    expect(cars.length).toBeGreaterThan(0)
    rerender(<TownCard arm={B} tick={61} towns={2} playing={false} />)
    expect([...container.querySelectorAll('[data-slot]')].every((slot, i) => slot === slots[i])).toBe(true)
    expect([...container.querySelectorAll('[data-layer]')].every((node, i) => node === layers[i])).toBe(true)
    expect(cars.every(car => car.isConnected)).toBe(true)
  })

  test('mounting twice (StrictMode) leaves one set of cars and people, not two', () => {
    const { container } = render(<StrictMode><TownCard arm={B} tick={69} towns={2} playing={false} /></StrictMode>)
    const { traffic } = townAt(B, 69)
    expect(inSlots(container, '.lt-car')).toHaveLength(traffic.cars)
    expect(inSlots(container, '.lt-walker')).toHaveLength(traffic.walkers)
  })

  test('coins carry money while playing, and none fly while paused', () => {
    const paused = render(<TownCard arm={B} tick={60} towns={2} playing={false} />)
    const playing = render(<TownCard arm={B} tick={60} towns={2} playing />)
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

  // Renders three demo weeks and a hidden card (about 3.5 to 4 s alone): it
  // gets the whole-screen timeout.
  test('a scrub, a paused step or Enlarge in the middle of an ease leaves walls, roof and sign at the week drawn', { timeout: WHOLE_SCREEN_MS }, () => {
    // Firm 9 in Town A is 44, 36 and 28 high in weeks 29, 30 and 31, then 28 in 32.
    const ID = 9
    const heights = [29, 30, 31].map(tick => townAt(A, tick).shops.find(shop => shop.id === ID).floors)
    expect(new Set(heights).size).toBe(3)
    const shopOf = container => container.querySelector(`[data-kind="shop"][data-id="${ID}"]`)
    const drawn = tick => {
      const { container, unmount } = render(card(tick))
      const points = shopOf(container).querySelector('.lt-shop-l').getAttribute('points')
      unmount()
      return points
    }
    const agrees = (container, tick) => {
      const shop = shopOf(container)
      expect(shop.querySelector('.lt-shop-l').getAttribute('points'), `walls at week ${tick}`).toBe(drawn(tick))
      expect(shop.querySelector('.lt-shop-top'), `roof at week ${tick}`).not.toHaveAttribute('transform')
      const sign = container.querySelector(`[data-sign="${ID}"]`)
      if (sign) expect(sign, `sign at week ${tick}`).not.toHaveAttribute('transform')
      expect([...shop.querySelectorAll('[data-z]')].filter(node => node.style.display === 'none'), `windows at week ${tick}`).toHaveLength(0)
    }
    const midEase = () => {
      const view = render(card(29, { playing: true, scrubs: 0 }))
      view.rerender(card(30, { playing: true, scrubs: 0 }))
      frames(100)
      expect(shopOf(view.container).querySelector('.lt-shop-l').getAttribute('points')).not.toBe(drawn(30))
      return view
    }
    // Scrubbed one week on while playing: a jump, not a step.
    let view = midEase()
    view.rerender(card(31, { playing: true, scrubs: 1 }))
    agrees(view.container, 31)
    frames(1000)
    agrees(view.container, 31)
    view.unmount()
    // Paused mid-ease, then one week on while paused.
    view = midEase()
    view.rerender(card(30, { playing: false, scrubs: 0 }))
    view.rerender(card(31, { playing: false, scrubs: 0 }))
    agrees(view.container, 31)
    view.unmount()
    // Hidden by Enlarge on the next week, then shown again later.
    view = midEase()
    view.rerender(card(31, { playing: true, scrubs: 0, hidden: true }))
    agrees(view.container, 31)
    view.rerender(card(32, { playing: true, scrubs: 0 }))
    agrees(view.container, 32)
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
    expect(container.querySelector('[data-flash="bank"]')).toHaveAttribute('opacity', '0')
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

  test('the town hall\'s ring pulses twice when new rules arrive while playing, and just stands when scrubbed to', () => {
    const arm = fixtureArm()
    arm.policyChanges = [{ id: 'c1', tick: 15, policy: 'minimum_wage_policy', value: 'high' }]
    const ring = container => container.querySelector('.lt-hall-ring')
    const played = render(<TownCard arm={arm} tick={14} towns={1} playing />)
    played.rerender(<TownCard arm={arm} tick={15} towns={1} playing />)
    const scales = new Set()
    for (let i = 0; i < 10; i += 1) {
      frames(100)
      scales.add(ring(played.container).getAttribute('transform'))
    }
    expect(scales.size).toBeGreaterThan(3)
    frames(500)
    expect(ring(played.container)).not.toHaveAttribute('transform')
    expect(ring(played.container)).not.toHaveAttribute('opacity')
    played.unmount()

    const scrubbed = render(<TownCard arm={arm} tick={14} towns={1} />)
    scrubbed.rerender(<TownCard arm={arm} tick={15} towns={1} />)
    frames(300)
    expect(ring(scrubbed.container)).not.toBeNull()
    expect(ring(scrubbed.container)).not.toHaveAttribute('transform')
  })

  test('when the run ends, what is in flight lands and the loop sleeps; the viewer\'s pause freezes it', () => {
    const inFlight = container => layer(container, 'moments').childNodes.length + flying(container).length
      + container.querySelectorAll('[data-slot] > .lt-walker.is-moving').length
    // The clock stops on the run's last week: that week was still a step.
    const ended = render(card(10, { playing: true }))
    ended.rerender(card(11, { playing: false, ended: true }))
    expect(layer(ended.container, 'moments').childNodes.length).toBeGreaterThan(0)
    expect(ended.container.querySelectorAll('[data-slot] > .lt-walker.is-moving').length).toBeGreaterThan(0)
    frames(5000)
    expect(inFlight(ended.container)).toBe(0)
    expect(vi.getTimerCount()).toBe(0)
    ended.unmount()

    const paused = render(card(10, { playing: true }))
    paused.rerender(card(11, { playing: true }))
    frames(300)
    paused.rerender(card(11, { playing: false }))
    const before = inFlight(paused.container)
    frames(5000)
    expect(before).toBeGreaterThan(0)
    expect(inFlight(paused.container)).toBe(before)
  })
})

// Shop heights ease in the scene loop (heights.js), with the shop's nodes
// found once, the scaffold poles growing with the walls.
describe('shop heights', () => {
  const lot = LAYOUT.lots[0]
  const shop = floors => ({ id: 7, lot: 0, sector: 'Food', state: 'growing', fresh: true, isNew: false, floors, staff: floors * 9, closedFor: 0 })
  const drawn = floors => {
    const { container, unmount } = render(<svg data-layer="world"><Shop shop={shop(floors)} lot={lot} /></svg>)
    const out = [...container.querySelectorAll('.lt-pole')].map(pole => pole.getAttribute('y2'))
    unmount()
    return out
  }

  test('a scaffolded shop\'s poles and rings follow its height as it eases', () => {
    const [low, high] = [drawn(1), drawn(4)]
    const { container, rerender } = render(<svg data-layer="world"><Shop shop={shop(1)} lot={lot} /></svg>)
    const s = { world: container.querySelector('svg'), places: ISLAND, heights: new Map(), easing: new Set(), now: 0 }
    syncHeights(s, [shop(1)], false)
    rerender(<svg data-layer="world"><Shop shop={shop(4)} lot={lot} /></svg>)
    syncHeights(s, [shop(4)], true)
    const poles = () => [...container.querySelectorAll('.lt-pole')].map(pole => pole.getAttribute('y2'))
    const shownRings = () => [...container.querySelectorAll('polyline[data-z]')].filter(ring => ring.style.display !== 'none').length
    // React drew the new height; the loop put it back where it was.
    expect(poles()).toEqual(low)
    // One floor (20 high) shows the rings at 5, 11 and 17 of the seven.
    expect(container.querySelectorAll('polyline[data-z]')).toHaveLength(7)
    expect(shownRings()).toBe(3)
    s.now = 150
    stepHeights(s)
    expect(poles()).not.toEqual(low)
    expect(poles()).not.toEqual(high)
    s.now = 450
    stepHeights(s)
    expect(poles()).toEqual(high)
    expect(shownRings()).toBe(container.querySelectorAll('polyline[data-z]').length)
    expect(s.easing.size).toBe(0)
  })
})

// Main Street (Task 8) brings its own places; the loop asks them, not the island.
describe('a scene with its own places', () => {
  beforeEach(() => { vi.useFakeTimers({ toFake: ['requestAnimationFrame', 'cancelAnimationFrame', 'performance'] }) })
  afterEach(() => { vi.useRealTimers() })

  // A made-up street: a lane for people, one shop (firm 9, which loses a
  // floor from week 29 to 30) and one cloud, drawn in its own units.
  function Strip({ model, places, playing }) {
    const ref = useRef(null)
    useSceneMotion(ref, { model, places, playing, towns: 1 })
    return (
      <div ref={ref}>
        <svg data-layer="back"><g data-layer="clouds"><g data-cloud="0" transform="translate(10 4)"><ellipse rx="3" ry="2" /></g></g></svg>
        <svg data-layer="world">
          <g data-lane="" />
          <g data-kind="shop" data-id="9">
            <polygon className="lt-shop-l" points="street" />
            <polygon className="lt-shop-r" points="street" />
            <g className="lt-shop-top" />
            <line className="lt-pole" y1="0" y2="-80" />
          </g>
          <g data-sign="9" />
        </svg>
        <svg data-layer="motion"><g data-layer="pings" /><g data-layer="coins" /><g data-layer="moments" /></svg>
      </div>
    )
  }

  const streetPlaces = calls => {
    const person = s => {
      const node = document.createElementNS('http://www.w3.org/2000/svg', 'circle')
      s.where.lane.appendChild(node)
      return { node, x: 0 }
    }
    return {
      attach: root => ({ lane: root.querySelector('[data-lane]') }),
      house: index => [index, 100],
      shop: () => [300, 50],
      shopTop: () => [300, 20],
      hall: [200, 50],
      bankTop: [250, 20],
      traffic: () => ({ cars: 0, walkers: 3 }),
      newCar: person,
      newWalker: person,
      moveCar() {},
      moveWalker(s, thing, dt) {
        thing.x += dt * 10
        thing.node.setAttribute('cx', thing.x.toFixed(2))
      },
      route: () => ({ door: [300], home: [0] }),
      mover: node => ({ node, onStreet: true }),
      put(s, thing, [x]) {
        calls.put += 1
        if ('slot' in thing || 'scale' in thing) calls.island += 1
        if (thing.node.parentNode !== s.where.lane) s.where.lane.appendChild(thing.node)
        thing.node.setAttribute('cx', x.toFixed(2))
      },
    }
  }

  test('traffic, walkers, coins and signs go where the places say', () => {
    const calls = { put: 0, island: 0 }
    const places = streetPlaces(calls)
    const { container, rerender } = render(<Strip model={townAt(A, 10)} places={places} playing />)
    const lane = container.querySelector('[data-lane]')
    expect(lane.childNodes).toHaveLength(3)
    vi.advanceTimersByTime(100)
    const walker = lane.firstChild
    const before = walker.getAttribute('cx')
    vi.advanceTimersByTime(400)
    expect(Number(walker.getAttribute('cx'))).toBeGreaterThan(Number(before))
    rerender(<Strip model={townAt(A, 11)} places={places} playing />)
    // Week 11: people laid off walk home, drawn where the places put them,
    // with no island placement (tile slots, the island's figure scale).
    expect(lane.querySelectorAll('.lt-walker.is-moving').length).toBeGreaterThan(0)
    expect(calls.put).toBeGreaterThan(0)
    expect(calls.island).toBe(0)
    expect(container.querySelector('[data-layer="moments"]').childNodes.length).toBeGreaterThan(0)
    vi.advanceTimersByTime(500)
    expect(container.querySelectorAll('[data-layer="coins"] circle').length).toBeGreaterThan(0)
  })

  test('its shops and clouds follow its own geometry, never the island\'s', () => {
    const calls = { put: 0, island: 0 }
    const heights = {
      target: shop => shop.floors * 10,
      walls: (shop, h) => ({ left: `street ${h.toFixed(1)}`, right: `street ${h.toFixed(1)}` }),
      lift: (target, h) => (target - h) * 2,
      pole: (shop, i, h) => (-2 * h).toFixed(1),
    }
    const places = { ...streetPlaces(calls), heights, clouds: { start: () => ({ x: 10, y: 4 }), to: 40, from: 0 } }
    const { container, rerender } = render(<Strip model={townAt(A, 29)} places={places} playing />)
    const shop = container.querySelector('[data-kind="shop"]')
    const wall = () => shop.querySelector('.lt-shop-l').getAttribute('points')
    rerender(<Strip model={townAt(A, 30)} places={places} playing />)
    // Four floors (40 in the street's units) easing down to three (30).
    expect(wall()).toBe('street 40.0')
    vi.advanceTimersByTime(100)
    const shown = Number(wall().split(' ')[1])
    expect(shown).toBeGreaterThan(30)
    expect(shown).toBeLessThan(40)
    expect(shop.querySelector('.lt-shop-top').getAttribute('transform')).toBe(`translate(0 ${Math.round((30 - shown) * 20) / 10})`)
    expect(shop.querySelector('.lt-pole').getAttribute('y2')).toBe((-2 * shown).toFixed(1))
    vi.advanceTimersByTime(500)
    expect(wall()).toBe('street 30.0')
    expect(shop.querySelector('.lt-shop-top')).not.toHaveAttribute('transform')
    // The cloud starts where the street says and comes back round inside its sky.
    const cloud = container.querySelector('[data-cloud]')
    const xs = []
    for (let i = 0; i < 80; i += 1) {
      vi.advanceTimersByTime(100)
      const [, x, y] = cloud.getAttribute('transform').match(/translate\((\S+) (\S+)\)/)
      xs.push(Number(x))
      expect(y).toBe('4')
    }
    expect(Math.min(...xs)).toBeGreaterThanOrEqual(0)
    expect(Math.max(...xs)).toBeLessThanOrEqual(41)
    expect(xs.some((x, i) => i > 0 && x < xs[i - 1])).toBe(true)
  })

  test('a scene whose places have no heights or clouds keeps its shops and clouds as drawn', () => {
    const calls = { put: 0, island: 0 }
    const places = streetPlaces(calls)
    const { container, rerender } = render(<Strip model={townAt(A, 29)} places={places} playing />)
    rerender(<Strip model={townAt(A, 30)} places={places} playing />)
    vi.advanceTimersByTime(1000)
    expect(container.querySelector('.lt-shop-l')).toHaveAttribute('points', 'street')
    expect(container.querySelector('.lt-pole')).toHaveAttribute('y2', '-80')
    expect(container.querySelector('[data-cloud]')).toHaveAttribute('transform', 'translate(10 4)')
  })
})

// The Run screen tells the drawings when to move: not on a live run held on a
// past week, and never take a week reached on the timeline for a step.
describe('Run screen towns in motion', { timeout: WHOLE_SCREEN_MS }, () => {
  const props = { maxTick: 104, onToggle() {} }
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

  test('the replay\'s last week is still a step, and what it set going lands', () => {
    // A replay that ends at week 70: the clock stops there as it arrives.
    const end = { ...props, maxTick: 70 }
    vi.useFakeTimers({ toFake: ['requestAnimationFrame', 'cancelAnimationFrame', 'performance'] })
    try {
      const { container, rerender } = render(<RunScreen arms={[A, B]} tick={69} playing onScrub={() => {}} {...end} />)
      rerender(<RunScreen arms={[A, B]} tick={70} playing={false} onScrub={() => {}} {...end} />)
      expect(signs(container)).toBeGreaterThan(0)
      vi.advanceTimersByTime(5000)
      expect(signs(container)).toBe(0)
    } finally {
      vi.useRealTimers()
    }
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
