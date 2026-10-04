import { describe, expect, test, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import RunScreen from '../RunScreen.jsx'
import useLiveClock from '../live/useLiveClock.js'
import TownCard from '../town/TownCard.jsx'
import MainStreetCard from '../town/MainStreetCard.jsx'
import Diorama from '../town/Diorama.jsx'
import MainStreet from '../town/MainStreet.jsx'
import { townAt } from '../town/model.js'
import { personHouses } from '../town/geometry.js'
import { placeCard } from '../town/cards.js'
import { COPY } from '../catalog.js'
import { ingest } from '../data/session.js'
import { firm, frame, liveArm, subject } from './townFixture.js'
import { WHOLE_SCREEN_MS } from './fixture.js'
import useSceneMotion from '../town/useSceneMotion.js'

// Observe the navigation counter while retaining the real motion hook.
vi.mock('../town/useSceneMotion.js', async importOriginal => {
  const actual = await importOriginal()
  return { ...actual, default: vi.fn(actual.default) }
})

const reopened = () => liveArm([
  [1, { firms: [firm(1)] }],
  [20, { closed: [{ id: 1, closedTick: 20, lastStaff: 10 }] }],
  [21, { firms: [firm(2)], closed: [{ id: 1, closedTick: 20, lastStaff: 10 }] }],
  [22, { firms: [firm(1, { state: 'growing' }), firm(2)], closed: [{ id: 1, closedTick: 20, lastStaff: 10 }] }],
])
const drawings = [
  ['island', (arm, tick) => <TownCard arm={arm} tick={tick} towns={1} />],
  ['street', (arm, tick) => <MainStreetCard arms={[arm]} tick={tick} />],
]

describe('final review identities', () => {
  test('an ID closed and reused in the same frame starts a new lifetime and ignores the continuing archive', () => {
    const arm = liveArm([
      [1, { firms: [firm(1)] }],
      [20, { firms: [firm(1, { sector: 'Services' })], closed: [{ id: 1, sector: 'Food', closedTick: 20 }] }],
      [21, { firms: [firm(1, { sector: 'Services' })], closed: [{ id: 1, sector: 'Food', closedTick: 20 }] }],
    ])
    const model = townAt(arm, 20)
    expect(model.shops).toHaveLength(1)
    expect(model.shops[0]).toMatchObject({ sector: 'Services', age: 0, fresh: true })
    expect(townAt(arm, 21).shops[0].age).toBe(1)
    expect(townAt(arm, 1).shops[0]).toMatchObject({ sector: 'Food', age: Infinity })
    expect(model.shops[0].name).not.toBe(townAt(arm, 1).shops[0].name)
    // A rewritten closure-free week must also invalidate lifetime evidence.
    ingest(arm, frame(20, { firms: [firm(1)] }))
    expect(townAt(arm, 20).shops[0].age).toBe(Infinity)
    expect(townAt(arm, 21).shops[0].age).toBe(0)
  })

  test('reopening takes the first free lot while historical lots and ages remain unchanged', () => {
    const arm = liveArm([
      [1, { firms: [firm(0), firm(1)] }],
      [20, { closed: [{ id: 1, closedTick: 20 }] }],
      [21, { firms: [firm(1)], closed: [{ id: 1, closedTick: 20 }] }],
    ])
    expect(townAt(arm, 21).shops[0]).toMatchObject({ lot: 0, age: 0 })
    expect(townAt(arm, 20).shops[0]).toMatchObject({ lot: 1, state: 'closed' })
    expect(townAt(arm, 1).shops.find(shop => shop.id === 1)).toMatchObject({ lot: 1, age: Infinity })
  })
  test('a reopened ID has one current shop, a new age, and historical lots survive scrubbing', () => {
    const arm = reopened()
    const model = townAt(arm, 22)
    expect(model.shops.filter(shop => shop.id === 1)).toHaveLength(1)
    expect(model.shops.find(shop => shop.id === 1)).toMatchObject({ state: 'growing', age: 0, fresh: true })
    expect(new Set(model.shops.map(shop => shop.lot)).size).toBe(model.shops.length)
    expect(placeCard(model, { kind: 'shop', id: 1 }).tag.text).toBe(COPY.diorama.card.states.building)
    expect(townAt(arm, 20).shops[0]).toMatchObject({ state: 'closed', closedTick: 20 })
    expect(townAt(arm, 1).shops[0]).toMatchObject({ lot: 0, age: Infinity })
    ingest(arm, frame(23, { firms: [firm(1), firm(2)], closed: [{ id: 1, closedTick: 20 }] }))
    expect(townAt(arm, 23).shops.find(shop => shop.id === 1).age).toBe(1)
  })

  test.each(drawings)('%s drawing and its card agree that the reused ID is open', (name, draw) => {
    const arm = reopened()
    const { container } = render(draw(arm, 22))
    const shop = container.querySelector('[data-kind="shop"][data-id="1"]')
    expect(shop).not.toHaveClass('is-closed')
    fireEvent.click(shop)
    expect(container.querySelector('.lt-place')).toHaveTextContent(COPY.diorama.card.states.building)
    expect(container.querySelector('.lt-place')).not.toHaveTextContent(COPY.diorama.card.closedOn)
  })

  test.each([['island', Diorama], ['street', MainStreet]])('%s gives an open shop priority over an overlapping archived lot', (name, Scene) => {
    const model = townAt(liveArm([[1, { firms: [firm(1)] }]]), 1)
    const open = model.shops[0]
    model.shops.push({ ...open, state: 'closed', closedTick: 0, closedFor: 10 })
    const { container } = render(<Scene model={model} color="#000" />)
    expect(container.querySelector('[data-kind="shop"][data-id="1"]')).not.toHaveClass('is-closed')
  })

  test.each(drawings)('%s keeps the same household through reorder and closes on removal', (name, draw) => {
    const arm = liveArm([[20, { subjects: [subject(1, { age: 41 }), subject(16, { age: 55 })] }]])
    const { container, rerender } = render(draw(arm, 20))
    const pin = container.querySelector('[data-kind="person"]')
    expect(pin).toHaveAttribute('data-id', '1')
    fireEvent.click(pin)
    const title = container.querySelector('.lt-place-title').textContent
    ingest(arm, frame(21, { subjects: [subject(16, { age: 55 }), subject(1, { age: 41, cash: 900 })] }))
    rerender(draw(arm, 21))
    expect(container.querySelector('.lt-place-title')).toHaveTextContent(title)
    expect(container.querySelector('.lt-place')).toHaveTextContent('$900')
    ingest(arm, frame(22, { subjects: [subject(16)] }))
    rerender(draw(arm, 22))
    expect(container.querySelector('.lt-place')).not.toHaveClass('is-on')
    fireEvent.mouseMove(container.querySelector('[data-kind="hall"]'))
    expect(container.querySelector('.lt-place')).toHaveTextContent(COPY.diorama.card.hall)
  })

  test('colliding household IDs keep their houses when the input order reverses', () => {
    const ids = [1, 16, 'family']
    const houses = personHouses(ids)
    expect(personHouses([...ids].reverse())).toEqual([...houses].reverse())
  })

  test.each(drawings)('%s keeps a followed household pin and card in place through sample changes and scrubs', (name, draw) => {
    const arm = liveArm([[20, { subjects: [1, 16, 2, 3].map(id => subject(id)) }]])
    const { container, rerender } = render(draw(arm, 20))
    const pin = () => container.querySelector('[data-kind="person"][data-id="16"]')
    const position = () => [...pin().querySelectorAll('circle')].map(circle => [circle.getAttribute('cx'), circle.getAttribute('cy')])
    fireEvent.click(pin())
    const title = container.querySelector('.lt-place-title').textContent
    const originalPosition = position()
    expect(townAt(arm, 20).people.find(person => person.id === 16).house).toBe(26)
    for (const [tick, ids] of [[21, [16, 2, 3, 4]], [22, [4, 3, 16, 2]], [23, [1, 16, 3, 4]]]) {
      ingest(arm, frame(tick, { subjects: ids.map(id => subject(id, { cash: 900 })) }))
      rerender(draw(arm, tick))
      expect(position()).toEqual(originalPosition)
      expect(container.querySelector('.lt-place-title')).toHaveTextContent(title)
      expect(container.querySelector('.lt-place')).toHaveTextContent('$900')
    }
    for (const tick of [20, 22, 21, 23, 20]) {
      rerender(draw(arm, tick))
      expect(position()).toEqual(originalPosition)
      expect(container.querySelector('.lt-place-title')).toHaveTextContent(title)
    }
  })
})

function LiveClocked({ arm, phase, liveTick = 22 }) {
  const clock = useLiveClock(liveTick)
  return <RunScreen arms={[arm]} tick={clock.tick} maxTick={liveTick} playing={phase === 'running'}
    onScrub={clock.scrub} onToggle={() => {}} speed={1} onSpeed={() => {}}
    live={{ phase, following: clock.following, onFollow: clock.follow, onHall: () => {} }} />
}

describe('viewer returns are navigation', { timeout: WHOLE_SCREEN_MS }, () => {
  test.each(['running', 'finished'])('%s: one-week and multi-week returns never launch moments in either scene', phase => {
    const arm = liveArm([20, 21, 22].map(tick => [tick, { firms: [firm(1)], curated: { bankDefaultAmountThisTick: 1000 } }]))
    const { container } = render(<LiveClocked arm={arm} phase={phase} />)
    for (const held of [21, 20]) {
      fireEvent.change(screen.getByRole('slider', { name: 'Week of the run' }), { target: { value: String(held) } })
      const before = useSceneMotion.mock.calls.at(-1)[1].scrubs
      fireEvent.click(screen.getByRole('button', { name: phase === 'running' ? COPY.live.backToLive : COPY.end.backToEnd }))
      expect(useSceneMotion.mock.calls.at(-1)[1].scrubs).toBe(before + 1)
      expect(container.querySelector('.nx-clock .nx-week')).toHaveTextContent('week 22')
      expect([...container.querySelectorAll('[data-layer="moments"]')].map(layer => layer.childElementCount)).toEqual([0, 0])
    }
  })

  test('the next real live step still launches moments after a viewer return', () => {
    const arm = liveArm([21, 22, 23].map(tick => [tick, { firms: [firm(1)], curated: { bankDefaultAmountThisTick: 1000 } }]))
    const { container, rerender } = render(<LiveClocked arm={arm} phase="running" />)
    fireEvent.change(screen.getByRole('slider', { name: 'Week of the run' }), { target: { value: '21' } })
    fireEvent.click(screen.getByRole('button', { name: COPY.live.backToLive }))
    rerender(<LiveClocked arm={arm} phase="running" liveTick={23} />)
    expect([...container.querySelectorAll('[data-layer="moments"]')].map(layer => layer.childElementCount)).toEqual([1, 1])
  })
})
