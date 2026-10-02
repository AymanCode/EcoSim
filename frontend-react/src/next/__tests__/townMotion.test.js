import { beforeAll, describe, expect, test } from 'vitest'
import { COIN_DOLLARS, coinsDue, easeToward, isStep, weekMoments, weekWalkers } from '../town/motion.js'
import { townAt } from '../town/model.js'
import { scenePalette } from '../town/mood.js'
import { paintWeather, weatherOf } from '../town/weather.js'
import { demoArms } from './fixture.js'

let A
beforeAll(() => { [A] = demoArms() })

describe('motion helpers', () => {
  test('coins follow the money and calm down with speed and more towns', () => {
    const flows = { spend: COIN_DOLLARS * 10, pay: 0, tax: 0, help: 0 }
    const one = coinsDue({ spend: 0, pay: 0, tax: 0, help: 0 }, flows, 0.5, 1, 2)
    expect(one.launches.spend).toBe(5)
    const fast = coinsDue({ spend: 0, pay: 0, tax: 0, help: 0 }, flows, 0.5, 4, 2)
    expect(fast.launches.spend).toBe(1)
    const four = coinsDue({ spend: 0, pay: 0, tax: 0, help: 0 }, flows, 0.5, 1, 4)
    expect(four.launches.spend).toBe(2)
    expect(four.debt.spend).toBeCloseTo(0.5)
  })

  test('caps launches per call', () => {
    const flows = { spend: COIN_DOLLARS * 1000, pay: 0, tax: 0, help: 0 }
    expect(coinsDue({ spend: 0, pay: 0, tax: 0, help: 0 }, flows, 1, 1, 1).launches.spend).toBe(8)
  })

  test('only a single forward step while playing counts as a step', () => {
    expect(isStep(40, 41, true)).toBe(true)
    expect(isStep(40, 41, false)).toBe(false)
    expect(isStep(40, 45, true)).toBe(false)
    expect(isStep(41, 40, true)).toBe(false)
    expect(isStep(null, 1, true)).toBe(false)
  })

  test('a closing week pops the closure and the bad loans, within the limit', () => {
    const list = weekMoments(townAt(A, 70))
    expect(list.map(item => item.kind)).toEqual(['closed', 'bad'])
    expect(weekMoments(townAt(A, 70), 1)).toHaveLength(1)
  })

  test('layoff walkers: at most two per firm and six a week', () => {
    const model = { week: { hires: [[1, 5]], layoffs: [[2, 3], [3, 1], [4, 9]], opened: [], closed: [], bad: 0 } }
    const walkers = weekWalkers(model)
    expect(walkers.filter(w => w.firmId === 4)).toHaveLength(2)
    expect(walkers.length).toBeLessThanOrEqual(6)
    expect(walkers[0]).toEqual({ firmId: 4, kind: 'lay' })
  })

  test('easing moves part of the way and settles', () => {
    const next = easeToward(0, 1, 0.1)
    expect(next).toBeGreaterThan(0)
    expect(next).toBeLessThan(1)
    expect(easeToward(0.999, 1, 0.1)).toBe(1)
  })
})

describe('weather painter', () => {
  const scene = () => {
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg')
    svg.innerHTML = '<g data-weather="sky"></g><g data-weather="grass"></g><g data-weather=""></g><g data-layer="rain"></g><g data-cloud="0"></g><g data-cloud="5"></g>'
    return svg
  }

  test('each part gets what it reads; a bare part gets every variable', () => {
    const svg = scene()
    paintWeather(weatherOf(svg), 0.3, 'summer')
    const [sky, grass, all] = svg.querySelectorAll('[data-weather]')
    const names = part => [...part.style].sort()
    expect(names(sky)).toEqual(['--lt-sky-bottom', '--lt-sky-top'])
    expect(names(grass)).toEqual(['--lt-grass-a', '--lt-grass-b'])
    expect(names(all)).toHaveLength(12)
    expect(all.style.getPropertyValue('--lt-sky-top')).toBe(scenePalette(0.3, 'summer').skyTop)
  })

  test('painting again writes only what changed', () => {
    const svg = scene()
    const weather = weatherOf(svg)
    paintWeather(weather, 0.8, 'summer')
    const writes = []
    for (const part of svg.querySelectorAll('[data-weather]')) {
      const set = part.style.setProperty.bind(part.style)
      part.style.setProperty = (name, value) => { writes.push(name); set(name, value) }
    }
    paintWeather(weather, 0.8, 'summer')
    expect(writes).toHaveLength(0)
    // Above 0.62 the grass is fully green, so a sunnier sky leaves it alone.
    paintWeather(weather, 0.9, 'summer')
    expect(writes).toContain('--lt-sky-top')
    expect(writes).not.toContain('--lt-grass-a')
  })
})
