import fs from 'node:fs'
import { afterEach, beforeAll, beforeEach, describe, expect, test, vi } from 'vitest'
import { fireEvent, render } from '@testing-library/react'
import TownCard from '../town/TownCard.jsx'
import { COPY, householdsPerHouse } from '../catalog.js'
import { valueAt } from '../data/derive.js'
import { cardSpot } from '../town/cards.js'
import { townAt } from '../town/model.js'
import { FLOW_COLOURS } from '../town/nodes.js'
import useSceneMotion from '../town/useSceneMotion.js'
import { demoArms } from './fixture.js'

// Counts the drawing's renders: Diorama calls the motion hook once per render.
vi.mock('../town/useSceneMotion.js', async importOriginal => {
  const actual = await importOriginal()
  return { ...actual, default: vi.fn(actual.default) }
})

let A
beforeAll(() => { [A] = demoArms() })

const T = COPY.diorama.card
const card = container => container.querySelector('.lt-place')
const canvas = container => container.querySelector('.lt-canvas')

describe('place cards', () => {
  test('pointing at a shop shows its card; leaving hides it', () => {
    const { container } = render(<TownCard arm={A} tick={70} towns={2} />)
    const shop = container.querySelector('[data-kind="shop"]')
    fireEvent.mouseMove(shop, { clientX: 10, clientY: 10 })
    const card = container.querySelector('.lt-place')
    expect(card).toHaveClass('is-on')
    expect(card).toHaveTextContent('Staff')
    fireEvent.mouseLeave(container.querySelector('.lt-canvas'))
    expect(container.querySelector('.lt-place')).not.toHaveClass('is-on')
  })

  test('clicking keeps the card; clicking the ground closes it', () => {
    const { container } = render(<TownCard arm={A} tick={70} towns={2} />)
    fireEvent.click(container.querySelector('[data-kind="hall"]'), { clientX: 20, clientY: 20 })
    fireEvent.mouseLeave(container.querySelector('.lt-canvas'))
    expect(container.querySelector('.lt-place')).toHaveClass('is-on')
    expect(container.querySelector('.lt-place')).toHaveTextContent('Town hall')
    fireEvent.click(container.querySelector('svg.lt-scene'))
    expect(container.querySelector('.lt-place')).not.toHaveClass('is-on')
  })

  test('a kept card follows the week', () => {
    const { container, rerender } = render(<TownCard arm={A} tick={69} towns={2} />)
    fireEvent.click(container.querySelector('[data-kind="bank"]'), { clientX: 5, clientY: 5 })
    rerender(<TownCard arm={A} tick={70} towns={2} />)
    expect(container.querySelector('.lt-place')).toHaveTextContent('Loans going unpaid')
  })

  test('every kind of place has its card: a house, a shop, the town hall, the bank and a person you follow', () => {
    const { container } = render(<TownCard arm={A} tick={70} towns={2} />)
    const model = townAt(A, 70)
    const point = selector => {
      fireEvent.mouseMove(container.querySelector(selector), { clientX: 30, clientY: 30 })
      return card(container)
    }

    const house = point('[data-kind="house"][data-index="0"]')
    expect(house).toHaveClass('is-on')
    expect(house).toHaveTextContent(T.house[model.houses[0].state])
    // The house stands for its share of the town's households this week.
    expect(house).toHaveTextContent(T.house.sub(householdsPerHouse(valueAt(A, 'householdsTotal', 70))))

    const shop = model.shops.find(s => s.state !== 'closed')
    expect(point(`[data-kind="shop"][data-id="${shop.id}"]`)).toHaveTextContent(shop.name)
    expect(point('[data-kind="hall"]')).toHaveTextContent(T.taxes)
    expect(point('[data-kind="bank"]')).toHaveTextContent(T.loans)

    expect(model.people.length).toBeGreaterThan(0)
    const person = point('[data-kind="person"][data-index="0"]')
    expect(person).toHaveTextContent(model.people[0].name)
    expect(person).toHaveTextContent(T.person)
  })

  test('a kept card stays put while the pointer moves, and a click on another place keeps that one instead', () => {
    const { container } = render(<TownCard arm={A} tick={70} towns={2} />)
    fireEvent.click(container.querySelector('[data-kind="hall"]'))
    expect(card(container)).toHaveClass('is-on', 'is-pinned')
    fireEvent.mouseMove(container.querySelector('[data-kind="bank"]'))
    expect(card(container)).toHaveTextContent(T.hall)
    fireEvent.mouseMove(container.querySelector('svg.lt-scene'))
    expect(card(container)).toHaveClass('is-on')

    fireEvent.click(container.querySelector('[data-kind="bank"]'))
    expect(card(container)).toHaveClass('is-on', 'is-pinned')
    expect(card(container)).toHaveTextContent(T.bank)
  })

  test('a click or tap on a kept card closes it, so what lay under it can be reached (on a phone the card covers much of the drawing)', () => {
    const { container } = render(<TownCard arm={A} tick={70} towns={2} />)
    fireEvent.click(container.querySelector('[data-kind="hall"]'))
    expect(card(container)).toHaveClass('is-on', 'is-pinned')
    fireEvent.click(card(container).querySelector('.lt-place-title'))
    expect(card(container)).not.toHaveClass('is-on')
  })

  test('pointing at the ground hides a card that was only pointed at; it is not kept', () => {
    const { container } = render(<TownCard arm={A} tick={70} towns={2} />)
    fireEvent.mouseMove(container.querySelector('[data-kind="bank"]'))
    expect(card(container)).toHaveClass('is-on')
    expect(card(container)).not.toHaveClass('is-pinned')
    fireEvent.mouseMove(container.querySelector('svg.lt-scene'))
    expect(card(container)).not.toHaveClass('is-on')
  })

  test('a kept shop that leaves the town takes its card with it, and pointing works again', () => {
    // The first week whose next week no longer has one of its shops.
    let found = null
    for (let tick = 10; tick < 150 && !found; tick += 1) {
      const later = new Set(townAt(A, tick + 1).shops.map(shop => shop.id))
      const gone = townAt(A, tick).shops.find(shop => !later.has(shop.id))
      if (gone) found = { tick, id: gone.id }
    }
    expect(found).not.toBeNull()
    const { container, rerender } = render(<TownCard arm={A} tick={found.tick} towns={2} />)
    fireEvent.click(container.querySelector(`[data-kind="shop"][data-id="${found.id}"]`))
    expect(card(container)).toHaveClass('is-on', 'is-pinned')
    rerender(<TownCard arm={A} tick={found.tick + 1} towns={2} />)
    expect(card(container)).not.toHaveClass('is-on')
    fireEvent.mouseMove(container.querySelector('[data-kind="hall"]'))
    expect(card(container)).toHaveClass('is-on')
    expect(card(container)).toHaveTextContent(T.hall)
  })

  test('a tap opens and keeps a card: the mouse move a touch screen sends before the click is skipped', () => {
    const { container } = render(<TownCard arm={A} tick={70} towns={2} />)
    const hall = container.querySelector('[data-kind="hall"]')
    fireEvent.touchStart(hall)
    fireEvent.touchEnd(hall)
    fireEvent.mouseMove(hall)
    expect(card(container)).not.toHaveClass('is-on')
    fireEvent.click(hall)
    expect(card(container)).toHaveClass('is-on', 'is-pinned')
    expect(card(container)).toHaveTextContent(T.hall)
    // A tap on empty ground closes it.
    const ground = container.querySelector('svg.lt-scene')
    fireEvent.touchStart(ground)
    fireEvent.touchEnd(ground)
    fireEvent.mouseMove(ground)
    fireEvent.click(ground)
    expect(card(container)).not.toHaveClass('is-on')
  })

  test('the card is decoration: hidden from screen readers, nothing to focus, and the summary list is unchanged', () => {
    const { container } = render(<TownCard arm={A} tick={70} towns={2} />)
    const before = container.querySelector('.nx-sr').textContent
    fireEvent.click(container.querySelector('[data-kind="hall"]'))
    expect(card(container)).toHaveAttribute('aria-hidden', 'true')
    expect(card(container).querySelectorAll('a, button, input, [tabindex]')).toHaveLength(0)
    expect(canvas(container)).not.toHaveAttribute('tabindex')
    expect(card(container).querySelectorAll('h1, h2, h3, h4, h5, h6')).toHaveLength(0)
    expect(container.querySelector('.nx-sr').textContent).toBe(before)
  })

  test('pointing and clicking never render the drawing again', () => {
    const { container } = render(<TownCard arm={A} tick={70} towns={2} />)
    const renders = useSceneMotion.mock.calls.length
    const houses = container.querySelectorAll('[data-kind="house"]')
    for (const house of [...houses].slice(0, 12)) fireEvent.mouseMove(house, { clientX: 40, clientY: 40 })
    fireEvent.click(container.querySelector('[data-kind="hall"]'))
    fireEvent.click(container.querySelector('svg.lt-scene'))
    fireEvent.mouseLeave(canvas(container))
    expect(useSceneMotion.mock.calls.length).toBe(renders)
  })
})

// jsdom has no layout: these tests give the drawing (.lt-canvas) and the card
// (.lt-place) sizes through the HTMLElement getters, and the drawing a box
// for the pointer, and put the getters back afterwards.
describe('placing the card in a drawing that has a size', () => {
  const NAMES = ['offsetParent', 'offsetWidth', 'offsetHeight']
  const saved = {}
  let room
  let measure
  beforeEach(() => {
    room = { width: 600, height: 360 }
    measure = { width: () => 200, height: () => 120, parent: vi.fn() }
    for (const name of NAMES) saved[name] = Object.getOwnPropertyDescriptor(HTMLElement.prototype, name)
    for (const name of ['clientWidth', 'clientHeight']) saved[name] = Object.getOwnPropertyDescriptor(Element.prototype, name)
    saved.box = Element.prototype.getBoundingClientRect
    const isCard = el => el.classList?.contains('lt-place')
    const isRoom = el => el.classList?.contains('lt-canvas')
    Object.defineProperty(HTMLElement.prototype, 'offsetParent', {
      configurable: true,
      get() { measure.parent(); return isCard(this) ? this.parentElement : saved.offsetParent.get.call(this) },
    })
    Object.defineProperty(HTMLElement.prototype, 'offsetWidth', { configurable: true, get() { return isCard(this) ? measure.width(this) : 0 } })
    Object.defineProperty(HTMLElement.prototype, 'offsetHeight', { configurable: true, get() { return isCard(this) ? measure.height(this) : 0 } })
    Object.defineProperty(Element.prototype, 'clientWidth', { configurable: true, get() { return isRoom(this) ? room.width : 0 } })
    Object.defineProperty(Element.prototype, 'clientHeight', { configurable: true, get() { return isRoom(this) ? room.height : 0 } })
    Element.prototype.getBoundingClientRect = function box() {
      return isRoom(this) ? { left: 0, top: 0, right: room.width, bottom: room.height, width: room.width, height: room.height, x: 0, y: 0 } : saved.box.call(this)
    }
  })
  afterEach(() => {
    for (const name of NAMES) Object.defineProperty(HTMLElement.prototype, name, saved[name])
    for (const name of ['clientWidth', 'clientHeight']) Object.defineProperty(Element.prototype, name, saved[name])
    Element.prototype.getBoundingClientRect = saved.box
  })

  test('a week change with no card shown reads no layout (the card is checked first)', () => {
    const { container, rerender } = render(<TownCard arm={A} tick={69} towns={2} />)
    measure.parent.mockClear()
    rerender(<TownCard arm={A} tick={70} towns={2} />)
    rerender(<TownCard arm={A} tick={71} towns={2} />)
    expect(measure.parent).not.toHaveBeenCalled()
    fireEvent.mouseMove(container.querySelector('[data-kind="hall"]'), { clientX: 100, clientY: 100 })
    expect(measure.parent).toHaveBeenCalled()
  })

  test('a kept card is placed again when the drawing changes size (a window resized or a phone turned)', () => {
    const observers = []
    const RealObserver = globalThis.ResizeObserver
    globalThis.ResizeObserver = class {
      constructor(callback) { this.callback = callback; this.targets = []; observers.push(this) }
      observe(target) { this.targets.push(target) }
      unobserve() {}
      disconnect() { this.targets = [] }
    }
    try {
      const { container } = render(<TownCard arm={A} tick={70} towns={2} />)
      fireEvent.click(container.querySelector('[data-kind="hall"]'), { clientX: 500, clientY: 100 })
      expect(card(container).style.left).toBe('286px')
      // The drawing halves in width with no new render: the card moves in.
      room = { width: 300, height: 180 }
      const watching = observers.filter(observer => observer.targets.includes(canvas(container)))
      expect(watching.length).toBeGreaterThan(0)
      watching.forEach(observer => observer.callback([]))
      expect(card(container).style.left).toBe('36px')
      // Closing the card stops watching the drawing.
      fireEvent.click(container.querySelector('svg.lt-scene'))
      expect(observers.filter(observer => observer.targets.includes(canvas(container)))).toHaveLength(0)
    } finally {
      globalThis.ResizeObserver = RealObserver
    }
  })

  test('the card is measured where it starts, not where the last card stood (a card by the right edge wraps narrower)', () => {
    // Placed far to the right, a card has less room and wraps taller.
    measure.height = el => (parseFloat(el.style.left) > 100 ? 300 : 120)
    const { container } = render(<TownCard arm={A} tick={70} towns={2} />)
    fireEvent.mouseMove(container.querySelector('[data-kind="hall"]'), { clientX: 500, clientY: 100 })
    expect(card(container).style.left).toBe('286px')
    fireEvent.mouseMove(container.querySelector('[data-kind="bank"]'), { clientX: 100, clientY: 200 })
    expect(card(container).style.left).toBe('114px')
    expect(card(container).style.top).toBe('214px')
  })
})

describe('place card details', () => {
  test('a card only pointed at goes when Enlarge hides its town, so it does not come back stale; a kept card stays', () => {
    const { container, rerender } = render(<TownCard arm={A} tick={70} towns={2} />)
    fireEvent.mouseMove(container.querySelector('[data-kind="hall"]'))
    expect(card(container)).toHaveClass('is-on')
    rerender(<TownCard arm={A} tick={70} towns={2} hidden />)
    rerender(<TownCard arm={A} tick={80} towns={2} />)
    expect(card(container)).not.toHaveClass('is-on')
    fireEvent.click(container.querySelector('[data-kind="bank"]'))
    rerender(<TownCard arm={A} tick={80} towns={2} hidden />)
    rerender(<TownCard arm={A} tick={80} towns={2} />)
    expect(card(container)).toHaveClass('is-on', 'is-pinned')
  })

  test('a pin has a wide, invisible circle to tap, well beyond the drawn pin', () => {
    const { container } = render(<TownCard arm={A} tick={70} towns={2} />)
    const pin = container.querySelector('[data-kind="person"]')
    const hit = pin.querySelector('.lt-pin-hit')
    expect(Number(hit.getAttribute('r'))).toBeGreaterThanOrEqual(2 * Number(pin.querySelector('.lt-pin').getAttribute('r')))
    expect(hit.getAttribute('cx')).toBe(pin.querySelector('.lt-pin').getAttribute('cx'))
    fireEvent.mouseMove(hit)
    expect(card(container)).toHaveTextContent(T.person)
  })

  test('only places inside the drawing count: a marked box around the town card is not one', () => {
    const { container } = render(<div data-kind="house" data-index="0"><TownCard arm={A} tick={70} towns={2} /></div>)
    fireEvent.mouseMove(container.querySelector('svg.lt-scene'))
    expect(card(container)).not.toHaveClass('is-on')
    fireEvent.click(container.querySelector('svg.lt-scene'))
    expect(card(container)).not.toHaveClass('is-on')
  })
})

describe('where the card sits', () => {
  test('14 px right of (or below) the pointer when it fits', () => {
    expect(cardSpot(100, 200, 600)).toBe(114)
  })

  test('on the other side of the pointer near the far edge', () => {
    expect(cardSpot(500, 200, 600)).toBe(286)
  })

  test('never past an edge of the drawing, 6 px clear', () => {
    expect(cardSpot(330, 100, 358)).toBe(216)
    expect(cardSpot(2, 50, 358)).toBe(16)
  })

  test('at the edge farthest from the pointer when it fits on neither side', () => {
    expect(cardSpot(100, 244, 356)).toBe(106)
    expect(cardSpot(250, 244, 356)).toBe(6)
    expect(cardSpot(120, 166, 215)).toBe(6)
    expect(cardSpot(90, 166, 215)).toBe(43)
  })

  test('at the near edge when the card is bigger than the drawing', () => {
    expect(cardSpot(120, 400, 300)).toBe(6)
    expect(cardSpot(200, 400, 300)).toBe(6)
  })
})

// See fixture.js: keep import.meta.url in a variable so Vite leaves it a file: URL.
const here = import.meta.url

function luminance(hex) {
  const [r, g, b] = [1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16) / 255)
    .map(c => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4))
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}

function contrast(a, b) {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x)
  return (hi + 0.05) / (lo + 0.05)
}

const rulesOf = css => [...css.replace(/\/\*[\s\S]*?\*\//g, '').replace(/@import\s+url\([^)]*\)\s*;/g, '').matchAll(/([^{}]+)\{([^{}]*)\}/g)]
  .map(([, selector, body]) => ({
    selector: selector.trim(),
    decls: Object.fromEntries(body.split(';').map(d => d.trim()).filter(Boolean).map(d => {
      const at = d.indexOf(':')
      return [d.slice(0, at).trim(), d.slice(at + 1).trim()]
    })),
  }))

const hexOf = rgb => `#${rgb.map(v => Math.round(v).toString(16).padStart(2, '0')).join('').toUpperCase()}`
const rgbOf = hex => [1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16))

describe('place card colours', () => {
  const tokens = Object.fromEntries(Object.entries(rulesOf(fs.readFileSync(new URL('../next.css', here), 'utf8'))
    .find(rule => rule.selector === '.nx').decls).filter(([name]) => name.startsWith('--nx-')))
  const resolve = value => {
    const ref = value.match(/^var\((--nx-[\w-]+)\)$/)
    if (ref) return resolve(tokens[ref[1]])
    if (/^#[0-9a-f]{6}$/i.test(value)) return value.toUpperCase()
    throw new Error(`not a colour this test reads: ${value}`)
  }
  const read = () => {
    const rules = rulesOf(fs.readFileSync(new URL('../town/town.css', here), 'utf8')).filter(rule => rule.selector.includes('.lt-place'))
    const base = rules.find(rule => rule.selector === '.nx .lt-place')
    expect(base, 'a .nx .lt-place rule in town.css').toBeTruthy()
    return { rules, base, surface: resolve(base.decls.background) }
  }

  test('the card is the page\'s ink, and its text reads at 4.5:1 or better on it', () => {
    const { rules, base, surface } = read()
    expect(base.decls.background).toBe('var(--nx-ink)')
    const texts = rules.filter(rule => rule.decls.color && !rule.selector.includes('lt-place-tag'))
    expect(texts.length).toBeGreaterThanOrEqual(5)
    for (const { selector, decls } of texts) {
      expect(decls.color, selector).toMatch(/^var\(--nx-/)
      expect(contrast(resolve(decls.color), surface), selector).toBeGreaterThanOrEqual(4.5)
    }
  })

  test('each tag is its tone over the card, with text that reads at 4.5:1 or better on it', () => {
    const { rules, surface } = read()
    const tones = { good: '--nx-work', warn: '--nx-look', bad: '--nx-home', quiet: '--nx-ink3', info: FLOW_COLOURS.help }
    for (const [tone, colour] of Object.entries(tones)) {
      const tag = rules.find(rule => rule.selector === `.nx .lt-place-tag.is-${tone}`)
      expect(tag, tone).toBeTruthy()
      const [, r, g, b, alpha] = tag.decls.background.match(/^rgba\((\d+),\s*(\d+),\s*(\d+),\s*([\d.]+)\)$/)
      expect(hexOf([r, g, b].map(Number)), tone).toBe(colour.startsWith('--') ? tokens[colour].toUpperCase() : colour.toUpperCase())
      const under = rgbOf(surface)
      const over = hexOf([r, g, b].map((v, i) => under[i] * (1 - alpha) + Number(v) * alpha))
      expect(contrast(resolve(tag.decls.color), over), tone).toBeGreaterThanOrEqual(4.5)
    }
  })
})
