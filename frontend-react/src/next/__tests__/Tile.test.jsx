import { beforeAll, describe, expect, test, vi } from 'vitest'
import { fireEvent, render, screen, within } from '@testing-library/react'
import Tile from '../numbers/Tile.jsx'
import SeeItBig from '../numbers/SeeItBig.jsx'
import { METRICS, NUMBER_GROUPS, formatMetric } from '../catalog.js'
import { countedSeriesUpTo, valueAt } from '../data/derive.js'
import { demoArms, fixtureArm, TOWN_A, TOWN_B } from './fixture.js'

const OUT = 'peopleOutOfWorkPer100'

let arms
beforeAll(() => { arms = demoArms() })

function draw(props = {}) {
  return render(<div className="nx"><Tile metricKey={OUT} arms={arms} tick={72} onSeeBig={() => {}} {...props} /></div>)
}

// The chart's week scale, read off the "setting up" band (weeks 0 to 10).
function weekScale(container) {
  const band = container.querySelector('.nx-twarm-band')
  const x0 = Number(band.getAttribute('x'))
  const perWeek = Number(band.getAttribute('width')) / 10
  return week => x0 + week * perWeek
}

const points = d => d.split(/[ML]/).map(part => part.trim()).filter(Boolean).map(pair => pair.split(' ').map(Number))

describe('Tile', () => {
  test('the name, each town\'s value with its colour dot, and the meaning', () => {
    const { container } = draw()
    const tile = screen.getByRole('article', { name: 'People out of work' })
    arms.forEach(arm => expect(tile).toHaveTextContent(formatMetric(OUT, valueAt(arm, OUT, 72))))
    expect(tile).toHaveTextContent(METRICS[OUT].meaning)
    const dots = [...container.querySelectorAll('.nx-pv b i')]
    expect(dots.map(dot => dot.style.background)).toEqual(['rgb(46, 111, 224)', 'rgb(224, 118, 44)'])
  })

  test('the cursor sits at the week shown, with the weeks to come shaded after it', () => {
    const { container } = draw()
    const x = weekScale(container)
    const now = container.querySelector('.nx-tnow')
    expect(Number(now.getAttribute('x1'))).toBeCloseTo(x(72), 0)
    const future = container.querySelector('.nx-tfuture')
    expect(Number(future.getAttribute('x'))).toBeCloseTo(x(72), 0)
    expect(Number(future.getAttribute('x')) + Number(future.getAttribute('width'))).toBeCloseTo(x(104), 0)
    // Every town's line runs up to this week and no further.
    const lines = [...container.querySelectorAll('path.nx-tline')]
    expect(lines).toHaveLength(2)
    lines.forEach(line => expect(points(line.getAttribute('d')).at(-1)[0]).toBeCloseTo(x(72), 0))
  })

  test('the setting-up weeks are a hatched band with the lines dashed in it', () => {
    const { container } = draw()
    const x = weekScale(container)
    expect(Number(container.querySelector('.nx-twarm-band').getAttribute('width'))).toBeGreaterThan(0)
    const warm = [...container.querySelectorAll('path.nx-twarm')]
    expect(warm).toHaveLength(2)
    // The dashed part joins the solid part at the first real week.
    expect(points(warm[0].getAttribute('d')).at(-1)[0]).toBeCloseTo(x(11), 0)
  })

  test('a counted-every-5-weeks number is drawn only at its counts and says when it was last counted', () => {
    const { container } = draw({ metricKey: 'gini' })
    const tile = screen.getByRole('article', { name: 'Gap between rich and poor' })
    expect(tile).toHaveTextContent('Counted every 5 weeks; last count Year 2, week 18.')
    const x = weekScale(container)
    const counts = countedSeriesUpTo(arms[0], 'gini', 72).map(point => point.tick)
    expect(counts.at(-1)).toBe(70)
    const drawn = [...container.querySelectorAll('path.nx-twarm, path.nx-tline')].slice(0, 2)
      .flatMap(path => points(path.getAttribute('d')).map(([px]) => px))
    const weeks = [...new Set(drawn.map(px => Math.round((px - x(0)) / (x(1) - x(0)))))]
    expect(weeks).toEqual(counts)
    // The end dot is at the week-70 count, not at week 72.
    const dot = container.querySelector('.nx-tdot')
    expect(Number(dot.getAttribute('cx'))).toBeCloseTo(x(70), 0)
  })

  test('a text alternative gives each town\'s first real week and this week', () => {
    draw()
    const alt = screen.getByRole('article', { name: 'People out of work' }).querySelector('.nx-sr')
    expect(alt).toHaveTextContent(`Town A: ${formatMetric(OUT, valueAt(arms[0], OUT, 11))} in Year 1, week 11, ${formatMetric(OUT, valueAt(arms[0], OUT, 72))} in Year 2, week 20.`)
    expect(alt).toHaveTextContent('Town B:')
  })

  test('two towns with the same line: the second is dashed so both show', () => {
    const { container } = render(<div className="nx"><Tile metricKey={OUT} arms={[fixtureArm(TOWN_A), fixtureArm(TOWN_B)]} tick={20} onSeeBig={() => {}} /></div>)
    const lines = [...container.querySelectorAll('path.nx-tline')]
    expect(lines[0]).not.toHaveClass('is-same')
    expect(lines[1]).toHaveClass('is-same')
  })

  test('a number the recording never carried says "Not measured in this run" and opens nothing', () => {
    const onSeeBig = vi.fn()
    const { container } = render(<div className="nx"><Tile metricKey="happiness" arms={[fixtureArm(TOWN_A), fixtureArm(TOWN_B)]} tick={20} onSeeBig={onSeeBig} /></div>)
    const tile = screen.getByRole('article', { name: 'How people feel' })
    expect(tile).toHaveTextContent('Not measured in this run')
    expect(tile).not.toHaveTextContent('0 of 100')
    expect(container.querySelector('.nx-tchart')).toBeNull()
    expect(tile).not.toHaveAttribute('tabindex')
    fireEvent.click(tile)
    fireEvent.keyDown(tile, { key: 'Enter' })
    expect(onSeeBig).not.toHaveBeenCalled()
  })

  test('clicking the tile, or Enter or Space on it, asks to see it big', () => {
    const onSeeBig = vi.fn()
    draw({ onSeeBig })
    const tile = screen.getByRole('article', { name: 'People out of work' })
    expect(tile).toHaveAttribute('tabindex', '0')
    expect(tile).toHaveAccessibleDescription('See it big')
    fireEvent.keyDown(tile, { key: 'Enter' })
    expect(onSeeBig).toHaveBeenLastCalledWith(OUT)
    fireEvent.keyDown(tile, { key: ' ' })
    fireEvent.click(tile)
    expect(onSeeBig).toHaveBeenCalledTimes(3)
    fireEvent.keyDown(tile, { key: 'a' })
    expect(onSeeBig).toHaveBeenCalledTimes(3)
  })
})

describe('SeeItBig', () => {
  test('the story chart for any number, with its group\'s numbers as chips, and a way back', () => {
    const onClose = vi.fn()
    render(<div className="nx"><SeeItBig metricKey="happiness" arms={arms} tick={72} onClose={onClose} /></div>)
    expect(screen.getByRole('heading', { name: METRICS.happiness.name })).toBeInTheDocument()
    const back = screen.getByRole('button', { name: 'Back to all the numbers' })
    expect(back).toHaveFocus()
    const chips = within(screen.getByRole('group', { name: 'Chart a different number' })).getAllByRole('button')
    const wellbeing = NUMBER_GROUPS.find(group => group.id === 'wellbeing').keys
    expect(chips.map(chip => chip.textContent)).toEqual(wellbeing.map(key => METRICS[key].name))
    expect(screen.getByRole('button', { name: METRICS.happiness.name })).toHaveAttribute('aria-pressed', 'true')
    fireEvent.click(screen.getByRole('button', { name: METRICS.careDenials.name }))
    expect(screen.getByRole('heading', { name: METRICS.careDenials.name })).toBeInTheDocument()
    fireEvent.click(back)
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  test('a counted-every-5-weeks number says when it was last counted', () => {
    render(<div className="nx"><SeeItBig metricKey="gini" arms={arms} tick={72} onClose={() => {}} /></div>)
    expect(screen.getByText('Counted every 5 weeks; last count Year 2, week 18.')).toBeInTheDocument()
  })

  test('a number the recording never carried says so instead of drawing a chart', () => {
    const { container } = render(<div className="nx"><SeeItBig metricKey="happiness" arms={[fixtureArm(TOWN_A), fixtureArm(TOWN_B)]} tick={20} onClose={() => {}} /></div>)
    expect(screen.getByRole('heading', { name: METRICS.happiness.name })).toBeInTheDocument()
    expect(screen.getByText('Not measured in this run')).toBeInTheDocument()
    expect(container.querySelector('.nx-chart')).toBeNull()
  })
})
