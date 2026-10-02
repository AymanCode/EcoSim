import { afterEach, beforeAll, beforeEach, describe, expect, test, vi } from 'vitest'
import { fireEvent, render, screen, within } from '@testing-library/react'
import MainStreetCard from '../town/MainStreetCard.jsx'
import RunScreen from '../RunScreen.jsx'
import { COPY, formatMoneyShort } from '../catalog.js'
import { snapshotAt } from '../data/derive.js'
import { STREET, STREET_CAPACITY } from '../town/geometry.js'
import { townAt } from '../town/model.js'
import { scenePalette } from '../town/mood.js'
import { STREET_PLACES } from '../town/streetPlaces.js'
import { StreetTreasury } from '../town/streetParts.jsx'
import { streetHeight, streetModel } from '../town/streetShape.js'
import useSceneMotion from '../town/useSceneMotion.js'
import { demoArms } from './fixture.js'

// Counts the drawings' renders: each scene calls the motion hook once per render.
vi.mock('../town/useSceneMotion.js', async importOriginal => {
  const actual = await importOriginal()
  return { ...actual, default: vi.fn(actual.default) }
})

let A, B
beforeAll(() => { [A, B] = demoArms() })

const D = COPY.diorama
const SIGNS = D.signs
const street = (props = {}) => <MainStreetCard arms={[A, B]} tick={70} selected={0} onSelect={() => {}} {...props} />
const onStreet = model => model.shops.filter(shop => shop.lot < STREET_CAPACITY)
const shopNode = (container, id) => container.querySelector(`[data-kind="shop"][data-id="${id}"]`)

describe('Main Street', () => {
  test('shows the shops nearest the crossing with their signs written out', () => {
    const { container } = render(<MainStreetCard arms={[A, B]} tick={70} selected={0} onSelect={() => {}} />)
    expect(container.querySelectorAll('[data-kind="shop"]').length).toBeGreaterThan(10)
    expect(container.textContent).toMatch(/CLOSED|FOR LEASE/)
    expect(container.textContent).toContain('TOWN HALL')
    expect(container.querySelectorAll('[data-kind="house"]')).toHaveLength(100)
  })

  test('the picker switches towns', () => {
    const picks = []
    render(<MainStreetCard arms={[A, B]} tick={70} selected={0} onSelect={n => picks.push(n)} />)
    fireEvent.click(screen.getByRole('button', { name: 'Town B' }))
    expect(picks).toEqual([1])
  })

  test('one town: no picker', () => {
    render(<MainStreetCard arms={[A]} tick={70} selected={0} onSelect={() => {}} />)
    expect(screen.queryByRole('group')).toBeNull()
  })

  test('Enlarge on a town moves Main Street to it', () => {
    const props = { tick: 70, maxTick: 104, playing: false, onToggle() {}, onScrub() {}, speed: 1, onSpeed() {} }
    const { container } = render(<RunScreen arms={[A, B]} {...props} />)
    fireEvent.click(screen.getAllByRole('button', { name: 'Enlarge' })[1])
    expect(container.querySelector('.lt-street')).toHaveTextContent('Town B')
  })
})

describe('Main Street card', () => {
  test('a fixed header: the title, the town and its rules (cut short, the full words in the title), and a picker', () => {
    const { container } = render(street({ selected: 1 }))
    const card = container.querySelector('article.nx-card.lt-street')
    expect(card).toHaveAttribute('data-stable', 'main-street')
    expect(within(card).getByRole('heading', { level: 2 })).toHaveTextContent(D.mainStreet)
    const sub = card.querySelector('.lt-street-sub')
    expect(sub.textContent).toMatch(/^Town B · /)
    expect(sub).toHaveAttribute('title', sub.textContent)
    const group = within(card).getByRole('group', { name: D.streetPicker })
    const buttons = within(group).getAllByRole('button')
    expect(buttons.map(button => button.textContent)).toEqual(['Town A', 'Town B'])
    expect(buttons.map(button => button.getAttribute('aria-pressed'))).toEqual(['false', 'true'])
  })

  test('Enlarge moves the picker and the street to that town; Show both leaves the street there', () => {
    const props = { tick: 70, maxTick: 104, playing: false, onToggle() {}, onScrub() {}, speed: 1, onSpeed() {} }
    const { container } = render(<RunScreen arms={[A, B]} {...props} />)
    const card = () => container.querySelector('.lt-street')
    const pressed = () => within(card()).getAllByRole('button').filter(button => button.getAttribute('aria-pressed') === 'true').map(button => button.textContent)
    expect(pressed()).toEqual(['Town A'])
    fireEvent.click(screen.getAllByRole('button', { name: 'Enlarge' })[1])
    expect(pressed()).toEqual(['Town B'])
    expect(card().querySelector('.lt-street-sub').textContent).toMatch(/^Town B · /)
    fireEvent.click(screen.getByRole('button', { name: 'Show both' }))
    expect(pressed()).toEqual(['Town B'])
    fireEvent.click(within(card()).getByRole('button', { name: 'Town A' }))
    expect(pressed()).toEqual(['Town A'])
  })

  test('on the Run screen it comes after the town cards and the legend', () => {
    const props = { tick: 70, maxTick: 104, playing: false, onToggle() {}, onScrub() {}, speed: 1, onSpeed() {} }
    const { container } = render(<RunScreen arms={[A, B]} {...props} />)
    const order = [...container.querySelector('main.nx-wrap').children].map(child => child.className.split(' ').find(name => /^(lt-towns|lt-legend|lt-street)$/.test(name))).filter(Boolean)
    expect(order).toEqual(['lt-towns', 'lt-legend', 'lt-street'])
  })

  test('a summary for screen readers: how many shops the street shows, and how many are hiring or closed', () => {
    const { container } = render(street({ selected: 1, tick: 100 }))
    const shops = onStreet(townAt(B, 100))
    const hiring = shops.filter(shop => shop.state === 'growing').length
    const closed = shops.filter(shop => shop.state === 'closed').length
    expect(closed).toBeGreaterThan(0)
    expect(container.querySelector('.lt-street .nx-sr')).toHaveTextContent(D.streetSummary(shops.length, hiring, closed))
  })
})

describe('Main Street drawing', () => {
  test('three stacked layers that share one viewBox, hidden from screen readers', () => {
    const { container } = render(street())
    const stage = container.querySelector('.lt-street .lt-canvas > .lt-stage')
    expect(stage).toHaveAttribute('aria-hidden', 'true')
    const layers = [...stage.children]
    expect(layers.map(layer => layer.dataset.layer)).toEqual(['back', 'world', 'motion'])
    for (const layer of layers) expect(layer.getAttribute('viewBox')).toBe(STREET.viewBox)
    const [back, world, motion] = layers
    expect(back).toHaveClass('lt-layer')
    expect(motion).toHaveClass('lt-layer')
    expect(world).toHaveClass('lt-scene')
    const kinds = [...container.querySelectorAll('[data-kind]')]
    expect(kinds.every(node => world.contains(node))).toBe(true)
    expect(world.querySelectorAll('[data-kind="hall"]')).toHaveLength(1)
    expect(world.querySelectorAll('[data-kind="bank"]')).toHaveLength(1)
    expect(world.querySelector('[data-flash="bank"]')).not.toBeNull()
    // The walk group holds only the people the motion loop puts there.
    const walk = world.querySelector('[data-layer="walk"]')
    expect([...walk.children].every(node => node.classList.contains('lt-walker'))).toBe(true)
    for (const name of ['rain', 'pings', 'coins', 'moments']) expect(motion.querySelector(`[data-layer="${name}"]`), name).not.toBeNull()
  })

  test('every shop on Main Street is one of the model\'s shops on the first 26 lots, standing on its lot', () => {
    const { container } = render(street({ tick: 100 }))
    const shops = onStreet(townAt(A, 100))
    const drawn = [...container.querySelectorAll('[data-kind="shop"]')].map(node => Number(node.dataset.id))
    expect(drawn.sort((a, b) => a - b)).toEqual(shops.map(shop => shop.id).sort((a, b) => a - b))
    for (const shop of shops) {
      const wall = shopNode(container, shop.id).querySelector('.lt-shop-l').getAttribute('points').split(' ').map(point => point.split(',').map(Number))
      const lot = STREET.lots[shop.lot]
      expect(wall[0]).toEqual([lot.x, STREET.base - streetHeight(shop)])
      expect(wall[2][0]).toBeCloseTo(lot.x + lot.w, 5)
      expect(wall[2][1]).toBe(STREET.base)
    }
  })

  test('only shops on the first 26 lots: a firm on a later lot is not drawn on the street', () => {
    const model = townAt(A, 70)
    const far = { ...model.shops[0], id: 'far', lot: STREET_CAPACITY + 3 }
    const scene = streetModel({ ...model, shops: [...model.shops, far] })
    expect(scene.shops.some(shop => shop.id === 'far')).toBe(false)
    expect(scene.shops).toHaveLength(onStreet(model).length)
  })

  test('signs are written out: HIRING, SALE, CLOSED, FOR LEASE and NEW, and the crown on the richest shop', () => {
    const { container, rerender } = render(street({ tick: 70 }))
    let model = townAt(A, 70)
    const text = id => shopNode(container, id).textContent
    for (const shop of onStreet(model)) {
      if (shop.state === 'struggling') expect(text(shop.id)).toContain(SIGNS.sale)
      if (shop.state === 'closed') expect(text(shop.id)).toBe(shop.closedFor >= 8 ? SIGNS.lease : SIGNS.closed)
    }
    expect(onStreet(model).some(shop => shop.state === 'closed' && shop.closedFor >= 8)).toBe(true)
    expect(onStreet(model).some(shop => shop.state === 'closed' && shop.closedFor < 8)).toBe(true)
    const richest = onStreet(model).find(shop => shop.richest)
    expect(shopNode(container, richest.id).querySelector('.lt-crown')).not.toBeNull()
    expect(container.querySelectorAll('.lt-crown')).toHaveLength(1)
    // Week 40: three shops grow and hire.
    rerender(street({ tick: 40 }))
    model = townAt(A, 40)
    const growing = onStreet(model).filter(shop => shop.state === 'growing')
    expect(growing.length).toBeGreaterThan(0)
    for (const shop of growing) expect(text(shop.id)).toContain(SIGNS.hiring)
    // Week 15: the shops that opened in week 11 are new (HIRING wins over NEW
    // on a new shop that is already growing, as in mockup 08).
    rerender(street({ tick: 15 }))
    model = townAt(A, 15)
    const fresh = onStreet(model).filter(shop => shop.isNew && shop.state !== 'closed')
    expect(fresh.filter(shop => shop.state !== 'growing').length).toBeGreaterThan(0)
    for (const shop of fresh) expect(text(shop.id)).toContain(shop.state === 'growing' ? SIGNS.hiring : SIGNS.fresh)
  })

  test('a shop being built is scaffolding with no windows yet; a closed one is boarded up', () => {
    const { container, rerender } = render(street({ tick: 12 }))
    const building = onStreet(townAt(A, 12)).filter(shop => shop.fresh)
    expect(building.length).toBeGreaterThan(0)
    for (const shop of building) {
      const node = shopNode(container, shop.id)
      expect(node.querySelector('.lt-pole')).not.toBeNull()
      expect(node.querySelector('.lt-shop-l')).toHaveAttribute('stroke-dasharray')
      expect(node.querySelector('.lt-win')).toBeNull()
    }
    rerender(street({ tick: 70 }))
    for (const shop of onStreet(townAt(A, 70)).filter(s => s.state === 'closed')) {
      expect(shopNode(container, shop.id)).toHaveClass('lt-shop', 'is-closed')
      expect(shopNode(container, shop.id).querySelectorAll('.lt-board')).toHaveLength(2)
    }
  })

  test('a shop up for lease stands as a lower shell, as on the island', () => {
    const model = townAt(A, 100)
    const leased = onStreet(model).find(shop => shop.state === 'closed' && shop.closedFor >= 8)
    expect(streetHeight(leased)).toBe(40)
    const open = onStreet(model).find(shop => shop.state !== 'closed')
    expect(streetHeight(open)).toBe(30 + 10 * open.floors)
  })

  test('the houses on the hill show who has work, as the town\'s houses do', () => {
    const { container } = render(street({ tick: 100 }))
    const model = townAt(A, 100)
    const houses = [...container.querySelectorAll('[data-kind="house"]')]
    expect(houses.map(house => Number(house.dataset.index))).toEqual(model.houses.map((_, i) => i))
    houses.forEach((house, i) => {
      expect(house).toHaveClass(`is-${model.houses[i].state}`)
      expect(house.classList.contains('is-long')).toBe(model.houses[i].state === 'look' && model.houses[i].weeks >= 12)
      const spot = STREET.houses[i]
      expect(house.getAttribute('transform')).toBe(`translate(${spot.x} ${spot.y}) scale(${spot.s})`)
    })
  })

  test('the town hall with its banner, its money and its queue; the bank', () => {
    const { container, rerender } = render(street({ selected: 1, tick: 70 }))
    let model = townAt(B, 70)
    expect(container.querySelector('[data-kind="hall"]')).toHaveTextContent(SIGNS.hall)
    expect(container.querySelector('[data-kind="hall"] .lt-banner')).toHaveTextContent(D.banner.minimum_wage_policy)
    expect(container.querySelector('[data-kind="bank"]')).toHaveTextContent(SIGNS.bank)
    // Savings: a stack of coins, one per $10,000 (1 to 10), with the amount.
    expect(model.hall.cash).toBeGreaterThan(0)
    expect(container.querySelectorAll('.lt-street-treasury .lt-coin')).toHaveLength(Math.min(10, Math.ceil(model.hall.cash / 10000)))
    expect(container.querySelector('.lt-street-treasury')).toHaveTextContent(formatMoneyShort(model.hall.cash))
    expect(container.querySelectorAll('.lt-street-queue .lt-walker')).toHaveLength(model.hall.queue)
    // Town A owes: a red slip with what it owes, and no banner.
    rerender(street({ selected: 0, tick: 70 }))
    model = townAt(A, 70)
    expect(model.hall.cash).toBeLessThan(0)
    expect(container.querySelector('.lt-street-treasury')).toHaveClass('is-owed')
    expect(container.querySelector('.lt-street-treasury')).toHaveTextContent(formatMoneyShort(-model.hall.cash))
    expect(container.querySelectorAll('.lt-street-treasury .lt-coin')).toHaveLength(0)
    expect(container.querySelector('[data-kind="hall"] .lt-banner')).toBeNull()
  })

  test('an unmeasured town hall draws no money at all, not an empty purse', () => {
    const { container, rerender } = render(<svg><StreetTreasury cash={null} /></svg>)
    expect(container.querySelector('.lt-street-treasury').childNodes).toHaveLength(0)
    rerender(<svg><StreetTreasury cash={0} /></svg>)
    expect(container.querySelectorAll('.lt-street-treasury .lt-coin')).toHaveLength(1)
    rerender(<svg><StreetTreasury cash={250000} /></svg>)
    expect(container.querySelectorAll('.lt-street-treasury .lt-coin')).toHaveLength(10)
  })

  test('a pin over the house of each followed household, with a wide hit area for a finger', () => {
    const { container } = render(street({ tick: 70 }))
    const model = townAt(A, 70)
    const pins = [...container.querySelectorAll('[data-kind="person"]')]
    expect(pins).toHaveLength(model.people.length)
    pins.forEach((pin, i) => {
      const person = model.people[i]
      expect(pin.querySelector('.lt-pin')).toHaveClass(`is-${person.tone}`)
      expect(pin.textContent).toBe(person.name.charAt(0))
      const spot = STREET.houses[person.house]
      expect(Number(pin.querySelector('.lt-pin').getAttribute('cx'))).toBeCloseTo(spot.x, 1)
      const hit = pin.querySelector('.lt-pin-hit')
      expect(Number(hit.getAttribute('r'))).toBeGreaterThanOrEqual(2.5 * Number(pin.querySelector('.lt-pin').getAttribute('r')))
    })
  })

  test('the weather parts each name what they read: sky, sun, hills, shade and rain', () => {
    const { container } = render(street({ tick: 100 }))
    const model = townAt(A, 100)
    const palette = scenePalette(model.mood, model.season)
    const parts = [...container.querySelectorAll('.lt-street [data-weather]')]
    expect(parts.map(part => part.dataset.weather).sort()).toEqual(['hills', 'rain', 'shade', 'sky', 'sun'])
    const part = kind => container.querySelector(`.lt-street [data-weather="${kind}"]`)
    expect(part('sky').style.getPropertyValue('--lt-sky-top')).toBe(palette.skyTop)
    expect(part('hills').style.getPropertyValue('--lt-hill-a')).toBe(palette.hillA)
    expect(part('hills').style.getPropertyValue('--lt-hill-b')).toBe(palette.hillB)
    expect(part('hills').style.getPropertyValue('--lt-meadow')).toBe(palette.meadow)
    expect(part('shade').style.getPropertyValue('--lt-shade')).toBe(palette.shade.toFixed(3))
    expect(part('rain').style.getPropertyValue('--lt-rain')).toBe(palette.rain.toFixed(2))
    expect(part('sun').style.getPropertyValue('--lt-sun')).toBe(palette.sun.toFixed(2))
    expect(container.querySelector('.lt-street [data-layer="rain"]')).not.toHaveClass('is-dry')
  })

  test('the places the loop uses stand inside the picture: homes, shop doors, the town hall and the bank', () => {
    const inside = ([x, y]) => x >= 0 && x <= 1200 && y >= 0 && y <= 340
    for (let i = 0; i < 100; i += 1) expect(inside(STREET_PLACES.house(i)), `house ${i}`).toBe(true)
    for (const shop of onStreet(townAt(A, 100))) {
      expect(inside(STREET_PLACES.shop(shop))).toBe(true)
      expect(inside(STREET_PLACES.shopTop(shop))).toBe(true)
      expect(STREET_PLACES.shopTop(shop)[1]).toBeLessThan(STREET.base - streetHeight(shop))
    }
    expect(inside(STREET_PLACES.hall)).toBe(true)
    expect(inside(STREET_PLACES.bankTop)).toBe(true)
  })
})

describe('Main Street place cards', () => {
  const card = container => container.querySelector('.lt-street .lt-place')

  test('pointing at a shop shows its card with its name', () => {
    const { container } = render(street())
    const shop = onStreet(townAt(A, 70)).find(s => s.state !== 'closed')
    fireEvent.mouseMove(shopNode(container, shop.id), { clientX: 10, clientY: 10 })
    expect(card(container)).toHaveClass('is-on')
    expect(card(container)).toHaveTextContent(shop.name)
    fireEvent.mouseMove(container.querySelector('[data-kind="hall"]'))
    expect(card(container)).toHaveTextContent(D.card.hall)
    fireEvent.mouseMove(container.querySelector('[data-kind="person"]'))
    expect(card(container)).toHaveTextContent(D.card.person)
  })

  test('pointing and clicking never render the street\'s drawing again', () => {
    const { container } = render(street())
    const renders = useSceneMotion.mock.calls.length
    for (const house of [...container.querySelectorAll('[data-kind="house"]')].slice(0, 12)) fireEvent.mouseMove(house, { clientX: 40, clientY: 40 })
    fireEvent.click(container.querySelector('[data-kind="hall"]'))
    fireEvent.click(container.querySelector('.lt-street svg.lt-scene'))
    fireEvent.mouseLeave(container.querySelector('.lt-street .lt-canvas'))
    expect(useSceneMotion.mock.calls.length).toBe(renders)
  })

  test('a kept card goes when the picker shows another town', () => {
    const { container, rerender } = render(street())
    fireEvent.click(container.querySelector('[data-kind="hall"]'))
    expect(card(container)).toHaveClass('is-on', 'is-pinned')
    rerender(street({ selected: 1 }))
    expect(card(container)).not.toHaveClass('is-on')
  })
})

describe('Main Street in motion', () => {
  const realMatchMedia = window.matchMedia
  beforeEach(() => { vi.useFakeTimers({ toFake: ['requestAnimationFrame', 'cancelAnimationFrame', 'performance'] }) })
  afterEach(() => {
    vi.useRealTimers()
    window.matchMedia = realMatchMedia
  })
  const frames = ms => vi.advanceTimersByTime(ms)
  const layer = (container, name) => container.querySelector(`.lt-street [data-layer="${name}"]`)
  const walkers = container => [...layer(container, 'walk').querySelectorAll(':scope > .lt-walker:not(.is-moving)')]
  const flying = container => [...layer(container, 'coins').querySelectorAll('circle')].filter(coin => coin.style.display !== 'none')

  test('people stroll the pavement: one for every 15 staff in town, 2 to 24 (3 in the warm-up weeks)', () => {
    const model = townAt(A, 70)
    const staff = snapshotAt(A, 70).firms.reduce((sum, firm) => sum + (firm.staff ?? 0), 0)
    expect(model.facts.staff).toBe(staff)
    const want = Math.min(24, Math.max(2, Math.round(staff / 15)))
    expect(streetModel(model).traffic).toEqual({ cars: 0, walkers: want })
    expect(streetModel(townAt(A, 5)).traffic).toEqual({ cars: 0, walkers: 3 })
    const { container } = render(street({ playing: true }))
    expect(walkers(container)).toHaveLength(want)
    const first = walkers(container)[0]
    const where = () => first.getAttribute('transform')
    const before = where()
    expect(before).toMatch(/^translate\(\S+ (29[89]|30[01])(\.\d)?\) scale\(1\.3\)$/)
    frames(500)
    expect(where()).not.toBe(before)
  })

  test('coins fly between the homes on the hill, the shops and the town hall while playing; none while paused', () => {
    const { container, rerender } = render(street({ playing: false }))
    frames(1000)
    expect(flying(container)).toHaveLength(0)
    rerender(street({ playing: true }))
    frames(1500)
    expect(flying(container).length).toBeGreaterThan(0)
    for (const coin of flying(container)) {
      expect(Number(coin.getAttribute('cx'))).toBeGreaterThanOrEqual(-50)
      expect(Number(coin.getAttribute('cx'))).toBeLessThanOrEqual(1250)
    }
  })

  test('a single step forward while playing pops the week\'s moments over the street\'s shops; a scrub does not', () => {
    const { container, rerender } = render(street({ tick: 69, playing: true }))
    rerender(street({ tick: 70, playing: true }))
    expect(layer(container, 'moments').textContent).toContain(D.moments.closed)
    const scrubbed = render(street({ tick: 69, playing: true, scrubs: 1 }))
    scrubbed.rerender(street({ tick: 70, playing: true, scrubs: 2 }))
    expect(scrubbed.container.querySelector('.lt-street [data-layer="moments"]').childNodes).toHaveLength(0)
  })

  test('people laid off walk off along the pavement carrying a box', () => {
    // Week 11: firm 1 lets 5 go; two of them are drawn walking home.
    const { container, rerender } = render(street({ tick: 10, playing: true }))
    rerender(street({ tick: 11, playing: true }))
    const moving = [...layer(container, 'walk').querySelectorAll('.lt-walker.is-moving')]
    expect(moving).toHaveLength(2)
    moving.forEach(walker => expect(walker.querySelector('rect')).not.toBeNull())
    frames(1500)
    const y = Number(moving[0].getAttribute('transform').match(/translate\(\S+ (\S+)\)/)[1])
    expect(y).toBeGreaterThan(STREET.base)
    expect(y).toBeLessThan(STREET.base + 14)
  })

  test('a shop that loses a floor eases down to its new height on the street', () => {
    // Firm 9 (on the street) goes from four floors to three in week 30.
    const { container, rerender } = render(street({ tick: 29, playing: true }))
    const top = () => Number(shopNode(container, 9).querySelector('.lt-shop-l').getAttribute('points').split(' ')[0].split(',')[1])
    expect(top()).toBe(STREET.base - 70)
    rerender(street({ tick: 30, playing: true }))
    expect(top()).toBe(STREET.base - 70)
    frames(150)
    expect(top()).toBeGreaterThan(STREET.base - 70)
    expect(top()).toBeLessThan(STREET.base - 60)
    frames(600)
    expect(top()).toBe(STREET.base - 60)
    expect(shopNode(container, 9).querySelector('.lt-shop-top')).not.toHaveAttribute('transform')
  })

  test('the hall\'s flag waves while playing and stands still when paused', () => {
    const { container, rerender } = render(street({ playing: true }))
    const flag = container.querySelector('[data-kind="hall"] .lt-flag-wave')
    frames(300)
    const moving = flag.getAttribute('transform')
    frames(300)
    expect(flag.getAttribute('transform')).not.toBe(moving)
    rerender(street({ playing: false }))
    const paused = flag.getAttribute('transform')
    frames(1000)
    expect(flag.getAttribute('transform')).toBe(paused)
    expect(vi.getTimerCount()).toBe(0)
  })

  test('with reduced motion nobody walks and no coins fly, but the weather still changes', () => {
    window.matchMedia = query => ({ ...realMatchMedia(query), matches: query.includes('prefers-reduced-motion: reduce') })
    const { container, rerender } = render(street({ tick: 69, playing: true }))
    const first = walkers(container)[0]
    const before = first.getAttribute('transform')
    rerender(street({ tick: 70, playing: true }))
    frames(1500)
    expect(first.getAttribute('transform')).toBe(before)
    expect(flying(container)).toHaveLength(0)
    expect(layer(container, 'moments').childNodes).toHaveLength(0)
    const model = townAt(A, 70)
    expect(container.querySelector('.lt-street [data-weather="sky"]').style.getPropertyValue('--lt-sky-top')).toBe(scenePalette(model.mood, model.season).skyTop)
  })
})
