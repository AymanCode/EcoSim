import { beforeAll, describe, expect, test, vi } from 'vitest'
import { fireEvent, render, screen, within } from '@testing-library/react'
import HiresAndLayoffs from '../numbers/HiresAndLayoffs.jsx'
import PriceTag from '../numbers/PriceTag.jsx'
import WealthLadder from '../numbers/WealthLadder.jsx'
import ShareBars from '../numbers/ShareBars.jsx'
import FirmStates from '../numbers/FirmStates.jsx'
import OpenedClosed from '../numbers/OpenedClosed.jsx'
import MoneyInOut from '../numbers/MoneyInOut.jsx'
import CashChart from '../numbers/CashChart.jsx'
import FeelMeter from '../numbers/FeelMeter.jsx'
import LoansWrittenOff from '../numbers/LoansWrittenOff.jsx'
import NumbersSheet from '../numbers/NumbersSheet.jsx'
import { COPY, METRICS, TOWN_COLORS, formatMetric, formatMoney } from '../catalog.js'
import { countedAt, cumulativeUpTo, valueAt, weeklyCounts } from '../data/derive.js'
import { hardshipNote, weekLabel } from '../narration.js'
import { demoArms, fixtureArm, TOWN_A, TOWN_B } from './fixture.js'

// The recorded demo (Town B has a higher minimum wage). At week 72 (Year 2,
// week 20) Town A's town hall owes money and Town B's does not.
let arms
beforeAll(() => { arms = demoArms() })

const draw = node => render(<div className="nx">{node}</div>)
const oldArms = () => [fixtureArm(TOWN_A), fixtureArm(TOWN_B)]
const TOWN_C = { label: 'Town C', color: TOWN_COLORS[2] }

// A hand-built arm: weeks 1..n, each series an array indexed by week - 1.
function handArm(meta, series, { eventCounts = {}, horizon } = {}) {
  const weeks = Math.max(...Object.values(series).map(values => values.length))
  return {
    ...meta,
    ticks: Array.from({ length: weeks }, (_, i) => i + 1),
    series,
    eventCounts,
    horizon: horizon ?? weeks,
    setup: {},
    policyChanges: [],
    events: [],
  }
}

const sum = values => values.reduce((total, value) => total + (value ?? 0), 0)
const num = (node, name) => Number(node.getAttribute(name))
const points = d => d.split(/[ML]/).map(part => part.trim()).filter(Boolean).map(pair => pair.split(' ').map(Number))

describe('HiresAndLayoffs', () => {
  test('the last 26 weeks per town: hires above the line, lay-offs below, this week and the totals', () => {
    const { container } = draw(<HiresAndLayoffs arms={arms} tick={72} />)
    const card = screen.getByRole('article', { name: COPY.numbers.hires.title })
    expect(card).toHaveTextContent('The last 26 weeks.')
    const panels = container.querySelectorAll('.nx-vpanel')
    expect(panels).toHaveLength(2)
    arms.forEach((arm, i) => {
      const rows = weeklyCounts(arm, ['hired', 'laidOff'], 72, 26)
      const svg = panels[i].querySelector('svg')
      const mid = num(svg.querySelector('.nx-vmid'), 'y1')
      const up = [...svg.querySelectorAll('rect.nx-hl-up')]
      const down = [...svg.querySelectorAll('rect.nx-hl-down')]
      expect(up).toHaveLength(rows.filter(row => row.hired > 0).length)
      expect(down).toHaveLength(rows.filter(row => row.laidOff > 0).length)
      up.forEach(bar => expect(num(bar, 'y') + num(bar, 'height')).toBeLessThanOrEqual(mid))
      down.forEach(bar => expect(num(bar, 'y')).toBeGreaterThanOrEqual(mid))
      const now = rows.at(-1)
      expect(panels[i]).toHaveTextContent(`this week ${now.hired} hired, ${now.laidOff} laid off`)
      expect(panels[i]).toHaveTextContent(`In these weeks: ${sum(rows.map(row => row.hired))} hired, ${sum(rows.map(row => row.laidOff))} laid off.`)
    })
    expect(panels[0]).toHaveTextContent('this week 6 hired, 18 laid off')
    expect(panels[1]).toHaveTextContent('this week 23 hired, 5 laid off')
  })

  test('a bigger week draws a taller bar, on one scale for every town', () => {
    const { container } = draw(<HiresAndLayoffs arms={arms} tick={72} />)
    const tallest = [...container.querySelectorAll('rect.nx-hl-up, rect.nx-hl-down')].map(bar => num(bar, 'height'))
    const counts = arms.flatMap(arm => weeklyCounts(arm, ['hired', 'laidOff'], 72, 26).flatMap(row => [row.hired, row.laidOff]))
    const biggest = Math.max(...counts)
    // The biggest week in either town fills its half of the chart.
    expect(Math.max(...tallest)).toBeCloseTo(43, 0)
    expect(tallest.length).toBe(counts.filter(n => n > 0).length)
    expect(biggest).toBeGreaterThan(0)
  })

  test('a hidden table gives every week\'s numbers for each town', () => {
    const { container } = draw(<HiresAndLayoffs arms={arms} tick={72} />)
    const table = container.querySelector('.nx-sr table')
    expect(table).not.toBeNull()
    // Hidden inside a block: a table grows to fit its cells whatever its width.
    expect(table.parentElement.tagName).toBe('DIV')
    expect(container.querySelector('table.nx-sr')).toBeNull()
    expect(within(table).getAllByRole('columnheader').map(head => head.textContent))
      .toEqual(['Week', 'Town A, hired', 'Town A, laid off', 'Town B, hired', 'Town B, laid off'])
    const rows = within(table).getAllByRole('row').slice(1)
    expect(rows).toHaveLength(26)
    expect([...rows.at(-1).children].map(cell => cell.textContent)).toEqual(['Year 2, week 20', '6', '18', '23', '5'])
  })

  test('before 26 weeks have passed, the weeks to come are shaded and the right edge is named', () => {
    const early = draw(<HiresAndLayoffs arms={arms} tick={20} />)
    const panel = early.container.querySelector('.nx-vpanel')
    const future = panel.querySelector('rect.nx-vfuture')
    expect(future).not.toBeNull()
    const width = num(panel.querySelector('svg'), 'width')
    // Slots 21 to 26 of 26 are still to come.
    expect(num(future, 'x')).toBeCloseTo((20 / 26) * width, 0)
    expect(num(future, 'x') + num(future, 'width')).toBeCloseTo(width, 0)
    expect(num(panel.querySelector('line.nx-vnow'), 'x1')).toBeCloseTo((20 / 26) * width, 0)
    expect([...panel.querySelectorAll('.nx-vaxis span')].map(span => span.textContent)).toEqual(['Year 1, week 1', 'Year 1, week 26'])
    early.unmount()
    const full = draw(<HiresAndLayoffs arms={arms} tick={72} />)
    expect(full.container.querySelector('rect.nx-vfuture')).toBeNull()
    expect([...full.container.querySelectorAll('.nx-vpanel')[0].querySelectorAll('.nx-vaxis span')].map(span => span.textContent))
      .toEqual(['Year 1, week 47', 'this week'])
  })

  test('warm-up weeks in the window are shaded as setting up', () => {
    const early = draw(<HiresAndLayoffs arms={arms} tick={20} />)
    expect(early.container.querySelectorAll('rect.nx-vwarm')).toHaveLength(2)
    // The window starts at week 1 while fewer than 26 weeks have passed.
    expect(early.container.querySelector('.nx-vaxis')).toHaveTextContent('Year 1, week 1')
    early.unmount()
    const late = draw(<HiresAndLayoffs arms={arms} tick={72} />)
    expect(late.container.querySelectorAll('rect.nx-vwarm')).toHaveLength(0)
  })
})

describe('PriceTag', () => {
  test('a price the same in every town and unchanged since warm-up says so instead of a flat line', () => {
    const { container } = draw(<PriceTag metricKey="priceHousing" arms={arms} tick={72} onSeeBig={() => {}} />)
    const tag = screen.getByRole('article', { name: METRICS.priceHousing.name })
    expect(tag).toHaveTextContent('$5.00')
    expect(tag).toHaveTextContent('Same in both towns, and unchanged since Year 1, week 1.')
    expect(container.querySelector('.nx-tchart')).toBeNull()
    expect(container.querySelector('.nx-ptag')).toContainElement(tag)
  })

  test('healthcare moved at the end of warm-up, and has not moved since', () => {
    draw(<PriceTag metricKey="priceHealthcare" arms={arms} tick={72} onSeeBig={() => {}} />)
    expect(screen.getByRole('article', { name: METRICS.priceHealthcare.name }))
      .toHaveTextContent('Same in both towns, and unchanged since Year 1, week 11.')
  })

  test('a price that moves gets its sparkline and no sentence', () => {
    const { container } = draw(<PriceTag metricKey="priceFood" arms={arms} tick={72} onSeeBig={() => {}} />)
    expect(container.querySelector('.nx-tchart')).not.toBeNull()
    expect(screen.getByRole('article', { name: METRICS.priceFood.name })).not.toHaveTextContent('unchanged')
  })

  test('flat but different between towns, or changed after warm-up: drawn, not summed up', () => {
    const flat = Array(40).fill(5)
    const apart = draw(<PriceTag metricKey="priceHousing" arms={[handArm(TOWN_A, { priceHousing: flat }), handArm(TOWN_B, { priceHousing: Array(40).fill(6) })]} tick={40} />)
    expect(apart.container.querySelector('.nx-tchart')).not.toBeNull()
    expect(apart.container).not.toHaveTextContent('unchanged')
    apart.unmount()
    const moved = [...Array(30).fill(4), ...Array(10).fill(5)]
    const late = draw(<PriceTag metricKey="priceHousing" arms={[handArm(TOWN_A, { priceHousing: moved }), handArm(TOWN_B, { priceHousing: moved })]} tick={40} />)
    expect(late.container.querySelector('.nx-tchart')).not.toBeNull()
    expect(late.container).not.toHaveTextContent('unchanged')
  })

  test('prices that differ by less than a cent are not "the same": drawn as usual', () => {
    const near = draw(<PriceTag metricKey="priceHealthcare" arms={[handArm(TOWN_A, { priceHealthcare: Array(40).fill(10.801) }), handArm(TOWN_B, { priceHealthcare: Array(40).fill(10.799) })]} tick={40} />)
    const tag = screen.getByRole('article', { name: METRICS.priceHealthcare.name })
    expect(tag).toHaveTextContent('$10.80')
    expect(tag).not.toHaveTextContent('unchanged')
    expect(near.container.querySelector('.nx-tchart')).not.toBeNull()
    near.unmount()
    // A float's last digits are not a change.
    const twin = draw(<PriceTag metricKey="priceHealthcare" arms={[handArm(TOWN_A, { priceHealthcare: Array(40).fill(5) }), handArm(TOWN_B, { priceHealthcare: Array(40).fill(5 + 1e-12) })]} tick={40} />)
    expect(twin.container).toHaveTextContent('Same in both towns, and unchanged since Year 1, week 1.')
  })

  test('only a price flat for at least 13 weeks is summed up: healthcare jumps in week 11', () => {
    const at = tick => {
      const view = draw(<PriceTag metricKey="priceHealthcare" arms={arms} tick={tick} />)
      const said = view.container.textContent.includes('unchanged since Year 1, week 11')
      const drawn = view.container.querySelector('.nx-tchart') !== null
      view.unmount()
      return { said, drawn }
    }
    expect(at(11)).toEqual({ said: false, drawn: true })
    expect(at(23)).toEqual({ said: false, drawn: true })
    expect(at(24)).toEqual({ said: true, drawn: false })
  })

  test('three towns read "every town"; it opens big for its own price', () => {
    const onSeeBig = vi.fn()
    const three = [...arms, { ...arms[0], ...TOWN_C }]
    draw(<PriceTag metricKey="priceHousing" arms={three} tick={72} onSeeBig={onSeeBig} />)
    const tag = screen.getByRole('article', { name: METRICS.priceHousing.name })
    expect(tag).toHaveTextContent('Same in every town, and unchanged since Year 1, week 1.')
    fireEvent.click(tag)
    expect(onSeeBig).toHaveBeenCalledWith('priceHousing')
  })
})

describe('WealthLadder', () => {
  test('a bar per town from the poorest tenth to the richest, the middle household\'s dot between its ends', () => {
    const { container } = draw(<WealthLadder arms={arms} tick={72} onSeeBig={() => {}} />)
    const card = screen.getByRole('article', { name: COPY.numbers.ladder.title })
    const bars = [...container.querySelectorAll('rect.nx-wbar')]
    const dots = [...container.querySelectorAll('circle.nx-wdot')]
    expect(bars).toHaveLength(2)
    expect(dots).toHaveLength(2)
    bars.forEach((bar, i) => {
      const cx = num(dots[i], 'cx')
      expect(cx).toBeGreaterThan(num(bar, 'x'))
      expect(cx).toBeLessThan(num(bar, 'x') + num(bar, 'width'))
    })
    // One shared axis: Town B's middle household has more, so its dot sits further right.
    expect(num(dots[1], 'cx')).toBeGreaterThan(num(dots[0], 'cx'))
    expect(card).toHaveTextContent('Counted every 5 weeks; last count Year 2, week 18.')
    const [p10, p50, p90] = ['wealthP10', 'wealthP50', 'wealthP90'].map(key => countedAt(arms[0], key, 72).value)
    expect(card.querySelector('.nx-sr')).toHaveTextContent(
      `Town A: nine in ten households have more than ${formatMoney(p10)}, the household in the middle has ${formatMoney(p50)}, and one in ten has more than ${formatMoney(p90)}.`,
    )
  })

  test('it opens big on typical savings', () => {
    const onSeeBig = vi.fn()
    draw(<WealthLadder arms={arms} tick={72} onSeeBig={onSeeBig} />)
    fireEvent.click(screen.getByRole('article', { name: COPY.numbers.ladder.title }))
    expect(onSeeBig).toHaveBeenCalledWith('wealthP50')
  })
})

describe('ShareBars', () => {
  test('out of every $100 saved: the poorest half, the next 40% and the richest tenth add up to 100', () => {
    const { container } = draw(<ShareBars arms={arms} tick={72} onSeeBig={() => {}} />)
    const card = screen.getByRole('article', { name: COPY.numbers.shares.title })
    const panels = [...container.querySelectorAll('.nx-vpanel')]
    expect(panels).toHaveLength(2)
    panels.forEach((panel, i) => {
      const dollars = [...panel.querySelectorAll('p b')].map(b => Number(b.textContent.replace('$', '')))
      expect(dollars).toHaveLength(3)
      expect(sum(dollars)).toBe(100)
      expect(dollars[0]).toBe(Math.round(valueAt(arms[i], 'bottomHalfShare', 72)))
      expect(dollars[2]).toBe(Math.round(valueAt(arms[i], 'topTenthShare', 72)))
      const widths = [...panel.querySelectorAll('.nx-sbar > b')].map(b => parseFloat(b.style.width))
      expect(sum(widths)).toBeCloseTo(100, 5)
    })
    expect(panels[0]).toHaveTextContent('Poorest half $19 · the next 40% $39 · richest tenth $42')
    expect(card).toHaveTextContent('Counted every 5 weeks; last count Year 2, week 18.')
  })

  test('either share missing: "Not measured in this run", never a zero', () => {
    const shares = { topTenthShare: Array(20).fill(40), bottomHalfShare: Array(20).fill(20) }
    const partial = [handArm(TOWN_A, shares), handArm(TOWN_B, { ...shares, bottomHalfShare: Array(20).fill(null) })]
    const first = draw(<ShareBars arms={partial} tick={20} onSeeBig={() => {}} />)
    const panels = first.container.querySelectorAll('.nx-vpanel')
    expect(panels[0]).toHaveTextContent('Poorest half $20 · the next 40% $40 · richest tenth $40')
    expect(panels[1]).toHaveTextContent('Not measured in this run')
    expect(panels[1].querySelector('.nx-sbar')).toBeNull()
    first.unmount()
    const onSeeBig = vi.fn()
    draw(<ShareBars arms={oldArms()} tick={20} onSeeBig={onSeeBig} />)
    const card = screen.getByRole('article', { name: COPY.numbers.shares.title })
    expect(card).toHaveTextContent('Not measured in this run')
    expect(card).not.toHaveTextContent('$0')
    expect(card).not.toHaveAttribute('tabindex')
    fireEvent.click(card)
    expect(onSeeBig).not.toHaveBeenCalled()
  })
})

describe('ShareBars, when the savings cannot be split', () => {
  const armsWith = (top, bottom) => [
    handArm(TOWN_A, { topTenthShare: Array(20).fill(42), bottomHalfShare: Array(20).fill(19) }),
    handArm(TOWN_B, { topTenthShare: Array(20).fill(top), bottomHalfShare: Array(20).fill(bottom) }),
  ]
  const townB = container => container.querySelectorAll('.nx-vpanel')[1]

  test('households\' cash adding up to nothing or less (both shares 0): a sentence, no bar and no dollars', () => {
    const { container } = draw(<ShareBars arms={armsWith(0, 0)} tick={20} onSeeBig={() => {}} />)
    expect(townB(container)).toHaveTextContent(COPY.numbers.shares.none)
    expect(COPY.numbers.shares.none).toBe('Added together, households had no savings at the last count, so there is nothing to share out.')
    expect(townB(container).querySelector('.nx-sbar')).toBeNull()
    expect(townB(container)).not.toHaveTextContent('$')
    expect(container.querySelectorAll('.nx-vpanel')[0]).toHaveTextContent('Poorest half $19 · the next 40% $39 · richest tenth $42')
  })

  test('a group owing more than it has (a share below 0, or the rest below 0): a sentence, no bar', () => {
    for (const [top, bottom] of [[113, -3], [60.5, 40], [101, 0.2]]) {
      const view = draw(<ShareBars arms={armsWith(top, bottom)} tick={20} onSeeBig={() => {}} />)
      expect(townB(view.container), `${top}/${bottom}`).toHaveTextContent(COPY.numbers.shares.owing)
      expect(townB(view.container).querySelector('.nx-sbar')).toBeNull()
      expect(townB(view.container)).not.toHaveTextContent('$-')
      view.unmount()
    }
    expect(COPY.numbers.shares.owing).toBe("Some households owed more than they had at the last count, so the savings can't be split this way.")
  })

  test('whole dollars always add up to 100, none below 0', () => {
    const { container } = draw(<ShareBars arms={armsWith(60.5, 39.5)} tick={20} onSeeBig={() => {}} />)
    const dollars = [...townB(container).querySelectorAll('p b')].map(b => Number(b.textContent.replace('$', '')))
    expect(sum(dollars)).toBe(100)
    dollars.forEach(value => expect(value).toBeGreaterThanOrEqual(0))
  })
})

describe('FirmStates', () => {
  test('a stacked bar per town whose growing, steady and struggling counts add up to the businesses open', () => {
    const { container } = draw(<FirmStates arms={arms} tick={72} onSeeBig={() => {}} />)
    screen.getByRole('article', { name: COPY.numbers.states.title })
    const panels = [...container.querySelectorAll('.nx-vpanel')]
    expect(panels).toHaveLength(2)
    panels.forEach((panel, i) => {
      const open = valueAt(arms[i], 'firmsOpen', 72)
      const counts = [...panel.querySelectorAll('p b')].map(b => Number(b.textContent))
      expect(counts).toHaveLength(3)
      expect(sum(counts)).toBe(open)
      expect(panel).toHaveTextContent(`${open} open`)
      const widths = [...panel.querySelectorAll('.nx-sbar > b')].map(b => parseFloat(b.style.width))
      expect(sum(widths)).toBeCloseTo(100, 5)
    })
    expect(panels[0]).toHaveTextContent('2 growing · 6 steady · 9 struggling')
    // The town with more businesses open draws the longer bar.
    const lengths = panels.map(panel => parseFloat(panel.querySelector('.nx-sbar').style.width))
    expect(lengths[1]).toBe(100)
    expect(lengths[0]).toBeCloseTo((17 / 19) * 100, 5)
  })
})

describe('OpenedClosed', () => {
  test('a strip of the last 26 weeks: a mark above for each opening, below for each closing, and the totals', () => {
    const { container } = draw(<OpenedClosed arms={arms} tick={72} />)
    const card = screen.getByRole('article', { name: COPY.numbers.openClose.title })
    const panels = [...container.querySelectorAll('.nx-vpanel')]
    expect(panels).toHaveLength(2)
    panels.forEach((panel, i) => {
      const rows = weeklyCounts(arms[i], ['firmsOpened', 'firmsClosed'], 72, 26)
      const all = weeklyCounts(arms[i], ['firmsOpened', 'firmsClosed'], 72, 72)
      const svg = panel.querySelector('svg')
      const mid = num(svg.querySelector('.nx-vmid'), 'y1')
      const opened = [...svg.querySelectorAll('line.nx-oc-open')]
      const closed = [...svg.querySelectorAll('line.nx-oc-close')]
      expect(opened).toHaveLength(rows.filter(row => row.firmsOpened > 0).length)
      expect(closed).toHaveLength(rows.filter(row => row.firmsClosed > 0).length)
      opened.forEach(mark => expect(Math.max(num(mark, 'y1'), num(mark, 'y2'))).toBeLessThan(mid))
      closed.forEach(mark => expect(Math.min(num(mark, 'y1'), num(mark, 'y2'))).toBeGreaterThan(mid))
      expect(panel).toHaveTextContent(`so far ${sum(all.map(row => row.firmsOpened))} opened, ${sum(all.map(row => row.firmsClosed))} closed`)
      expect(panel).toHaveTextContent(`In these weeks: ${sum(rows.map(row => row.firmsOpened))} opened, ${sum(rows.map(row => row.firmsClosed))} closed.`)
    })
    // The weeks with an opening or a closing, for screen readers.
    const alt = card.querySelector('p.nx-sr')
    expect(alt).toHaveTextContent('Town A, in these weeks. Opened: Year 2, week 20. Closed: Year 1, week 49; Year 2, week 13; Year 2, week 18; Year 2, week 19; Year 2, week 20.')
    expect(alt).toHaveTextContent('Town B, in these weeks. Opened: none. Closed: Year 2, week 10; Year 2, week 17.')
  })
})

describe('the other 26-week charts before 26 weeks have passed', () => {
  test('the strip and the paired bars shade the weeks to come and name the right edge', () => {
    for (const node of [<OpenedClosed key="oc" arms={arms} tick={20} />, <MoneyInOut key="io" arms={arms} tick={20} onSeeBig={() => {}} />]) {
      const view = draw(node)
      const panel = view.container.querySelector('.nx-vpanel')
      expect(panel.querySelector('rect.nx-vfuture')).not.toBeNull()
      expect([...panel.querySelectorAll('.nx-vaxis span')].map(span => span.textContent)).toEqual(['Year 1, week 1', 'Year 1, week 26'])
      view.unmount()
    }
  })
})

describe('MoneyInOut', () => {
  test('26 weeks of taxes collected against help paid to families, this week, and what is left out', () => {
    const { container } = draw(<MoneyInOut arms={arms} tick={72} onSeeBig={() => {}} />)
    const card = screen.getByRole('article', { name: COPY.numbers.inOut.title })
    expect(card).toHaveTextContent('in: taxes collected')
    expect(card).toHaveTextContent('out: help paid to families, including the welcome payments in the first weeks')
    expect(card).toHaveTextContent("Other town hall spending isn't included")
    expect(card.textContent).not.toMatch(/\bnet\b/i)
    const panels = [...container.querySelectorAll('.nx-vpanel')]
    panels.forEach((panel, i) => {
      expect(panel.querySelectorAll('rect.nx-io-in')).toHaveLength(26)
      expect(panel.querySelectorAll('rect.nx-io-out')).toHaveLength(26)
      expect(panel).toHaveTextContent(`this week in ${formatMoney(valueAt(arms[i], 'townHallIncome', 72))}, out ${formatMoney(valueAt(arms[i], 'familySupportPaid', 72))}`)
    })
    expect(panels[0]).toHaveTextContent('this week in $3,768, out $7,661')
    const table = card.querySelector('.nx-sr table')
    expect(within(table).getAllByRole('row').slice(1)).toHaveLength(26)
    expect([...within(table).getAllByRole('row').at(-1).children].map(cell => cell.textContent))
      .toEqual(['Year 2, week 20', '$3,768', '$7,661', '$9,877', '$5,851'])
  })

  test('an older recording without the two flows: "Not measured in this run"', () => {
    const onSeeBig = vi.fn()
    draw(<MoneyInOut arms={oldArms()} tick={20} onSeeBig={onSeeBig} />)
    const card = screen.getByRole('article', { name: COPY.numbers.inOut.title })
    expect(card).toHaveTextContent('Not measured in this run')
    expect(card.querySelector('svg')).toBeNull()
    fireEvent.click(card)
    expect(onSeeBig).not.toHaveBeenCalled()
  })
})

describe('CashChart', () => {
  // The chart's week scale, read off Town A's line: one point a week.
  function lineOf(container, index) {
    return points(container.querySelectorAll('path.nx-cline')[index].getAttribute('d'))
  }

  test('the last 52 weeks with an "owes" band below zero and the first week below zero ringed', () => {
    const { container } = draw(<CashChart arms={arms} tick={72} onSeeBig={() => {}} />)
    const card = screen.getByRole('article', { name: METRICS.townHallCash.name })
    expect(card).toHaveTextContent('owes $11,276')
    expect(card).toHaveTextContent('$80,603')
    const band = container.querySelector('rect.nx-owes')
    expect(band).not.toBeNull()
    expect(card).toHaveTextContent('below the line: owes money')
    // Weeks 21 to 72: 52 points for each town.
    const line = lineOf(container, 0)
    expect(line).toHaveLength(52)
    // The band starts at the zero line: the ring (week 62, Year 2, week 10) sits just under it.
    const rings = [...container.querySelectorAll('circle.nx-cring')]
    expect(rings).toHaveLength(1)
    const [ringX] = line[62 - 21]
    expect(num(rings[0], 'cx')).toBeCloseTo(ringX, 0)
    expect(num(rings[0], 'cy')).toBeGreaterThanOrEqual(num(band, 'y') - 0.5)
    expect(card).toHaveTextContent('Town A has owed money since Year 2, week 10, the ring on its line.')
    expect(card).not.toHaveTextContent('Town B has owed')
  })

  test('no band and no ring while every town has money in the window', () => {
    const { container } = draw(<CashChart arms={arms} tick={40} onSeeBig={() => {}} />)
    expect(container.querySelector('rect.nx-owes')).toBeNull()
    expect(container.querySelector('circle.nx-cring')).toBeNull()
    expect(screen.getByRole('article', { name: METRICS.townHallCash.name })).not.toHaveTextContent('below the line')
  })

  test('a debt before the window draws no band', () => {
    const cash = [-500, -200, ...Array(78).fill(1000)]
    const { container } = draw(<CashChart arms={[handArm(TOWN_A, { townHallCash: cash }), handArm(TOWN_B, { townHallCash: cash })]} tick={80} onSeeBig={() => {}} />)
    expect(container.querySelector('rect.nx-owes')).toBeNull()
  })

  test('a starting balance that would flatten the scale becomes a note, not a point', () => {
    const late = draw(<CashChart arms={arms} tick={72} onSeeBig={() => {}} />)
    expect(screen.getByRole('article', { name: METRICS.townHallCash.name }))
      .toHaveTextContent('The chart shows the last year; both towns started with about $1.35 million.')
    late.unmount()
    const { container } = draw(<CashChart arms={arms} tick={30} onSeeBig={() => {}} />)
    const card = screen.getByRole('article', { name: METRICS.townHallCash.name })
    expect(card).toHaveTextContent('Both towns started with about $1.35 million, above the top of this chart.')
    // The scale is set by the weeks after setting up: its top is far under the start.
    const top = Math.max(...[...container.querySelectorAll('text.nx-cy')].map(label => {
      const text = label.textContent.replace(/[$,]/g, '')
      return text.endsWith('k') ? Number(text.slice(0, -1)) * 1e3 : text.endsWith('m') ? Number(text.slice(0, -1)) * 1e6 : Number(text)
    }))
    expect(top).toBeLessThanOrEqual(500000)
    expect(top).toBeLessThan(valueAt(arms[0], 'townHallCash', 1) / 2)
    expect(top).toBeGreaterThanOrEqual(valueAt(arms[1], 'townHallCash', 11))
  })

  test('a debt that began while the towns were being set up is dated from its first week', () => {
    const cash = [100, -5, ...Array(38).fill(-10)]
    draw(<CashChart arms={[handArm(TOWN_A, { townHallCash: cash }), handArm(TOWN_B, { townHallCash: Array(40).fill(50) })]} tick={40} onSeeBig={() => {}} />)
    expect(screen.getByRole('article', { name: METRICS.townHallCash.name })).toHaveTextContent('Town A has owed money since Year 1, week 2, the ring on its line.')
  })

  test('the year boundary falls between week 52 and week 53', () => {
    const { container } = draw(<CashChart arms={arms} tick={72} onSeeBig={() => {}} />)
    const line = lineOf(container, 0)
    const bound = num(container.querySelector('line.nx-vbound'), 'x1')
    expect(bound).toBeCloseTo((line[52 - 21][0] + line[53 - 21][0]) / 2, 0)
  })

  test('Enter or Space on the card opens it big, as a click does', () => {
    const onSeeBig = vi.fn()
    draw(<CashChart arms={arms} tick={72} onSeeBig={onSeeBig} />)
    const card = screen.getByRole('article', { name: METRICS.townHallCash.name })
    expect(card).toHaveAttribute('tabindex', '0')
    fireEvent.keyDown(card, { key: 'Enter' })
    fireEvent.keyDown(card, { key: ' ' })
    expect(onSeeBig).toHaveBeenCalledTimes(2)
    expect(onSeeBig).toHaveBeenLastCalledWith('townHallCash')
  })

  test('a text alternative for each town and it opens big', () => {
    const onSeeBig = vi.fn()
    draw(<CashChart arms={arms} tick={72} onSeeBig={onSeeBig} />)
    const card = screen.getByRole('article', { name: METRICS.townHallCash.name })
    const alt = card.querySelector('.nx-sr')
    expect(alt).toHaveTextContent(`Town A: ${formatMetric('townHallCash', valueAt(arms[0], 'townHallCash', 21))} in Year 1, week 21, owes $11,276 in Year 2, week 20.`)
    expect(alt).toHaveTextContent('Town B:')
    fireEvent.click(card)
    expect(onSeeBig).toHaveBeenCalledWith('townHallCash')
  })
})

describe('FeelMeter', () => {
  test('a 0 to 100 meter per town whose fill follows the value, with the meaning', () => {
    const { container, rerender } = draw(<FeelMeter arms={arms} tick={72} onSeeBig={() => {}} />)
    const card = screen.getByRole('article', { name: METRICS.happiness.name })
    expect(card).toHaveTextContent(METRICS.happiness.meaning)
    const fills = () => [...container.querySelectorAll('.nx-meter-fill')].map(fill => parseFloat(fill.style.width))
    expect(fills()).toHaveLength(2)
    arms.forEach((arm, i) => {
      expect(fills()[i]).toBeCloseTo(valueAt(arm, 'happiness', 72), 1)
      expect(card).toHaveTextContent(`${arm.label}${formatMetric('happiness', valueAt(arm, 'happiness', 72))}`)
    })
    expect(card).toHaveTextContent('Town A22 of 100')
    expect(card).toHaveTextContent('The mark on each bar is where both towns started, at 69.')
    rerender(<div className="nx"><FeelMeter arms={arms} tick={30} onSeeBig={() => {}} /></div>)
    expect(fills()[0]).toBeCloseTo(valueAt(arms[0], 'happiness', 30), 1)
  })

  test('an older recording: "Not measured in this run", no meter, opens nothing', () => {
    const onSeeBig = vi.fn()
    const { container } = draw(<FeelMeter arms={oldArms()} tick={20} onSeeBig={onSeeBig} />)
    const card = screen.getByRole('article', { name: METRICS.happiness.name })
    expect(card).toHaveTextContent('Not measured in this run')
    expect(container.querySelector('.nx-meter-fill')).toBeNull()
    fireEvent.click(card)
    expect(onSeeBig).not.toHaveBeenCalled()
  })
})

describe('LoansWrittenOff', () => {
  test('the money written off so far in each town, and that the number of loans is not recorded', () => {
    const { container } = draw(<LoansWrittenOff arms={arms} tick={72} />)
    const card = screen.getByRole('article', { name: COPY.numbers.writtenOff.title })
    arms.forEach(arm => expect(card).toHaveTextContent(formatMoney(cumulativeUpTo(arm, 'bankDefaultAmountThisTick', 72))))
    expect(card).toHaveTextContent("The number of unpaid loans isn't recorded in this run, so this shows the money instead.")
    // One block for each week the bank wrote money off.
    const piles = [...container.querySelectorAll('.nx-pile')]
    piles.forEach((pile, i) => {
      const weeks = arms[i].series.bankDefaultAmountThisTick.slice(0, 72).filter(value => value > 0)
      expect(pile.querySelectorAll('b')).toHaveLength(weeks.length)
    })
    expect(card.querySelector('.nx-sr')).toHaveTextContent(`Town A: ${formatMoney(cumulativeUpTo(arms[0], 'bankDefaultAmountThisTick', 72))} so far.`)
  })

  test('before anything is written off it says so; a recorded count replaces the sentence', () => {
    const early = draw(<LoansWrittenOff arms={arms} tick={40} />)
    expect(screen.getByRole('article', { name: COPY.numbers.writtenOff.title })).toHaveTextContent('Nothing has been written off yet in either town.')
    early.unmount()
    const counted = [
      handArm(TOWN_A, { bankDefaultAmountThisTick: [0, 100, 0, 50], bankDefaultsTotal: [0, 1, 1, 2] }),
      handArm(TOWN_B, { bankDefaultAmountThisTick: [0, 0, 0, 0], bankDefaultsTotal: [0, 0, 0, 0] }),
    ]
    draw(<LoansWrittenOff arms={counted} tick={4} />)
    const card = screen.getByRole('article', { name: COPY.numbers.writtenOff.title })
    expect(card).toHaveTextContent('Loans that went unpaid so far: 2 in Town A, 0 in Town B.')
    expect(card).not.toHaveTextContent("isn't recorded")
  })
})

describe('the numbers sheet with its special visuals', () => {
  const sheet = (props = {}) => draw(<NumbersSheet arms={arms} tick={72} onClose={() => {}} {...props} />)
  const titles = region => within(region).getAllByRole('article').map(card => card.querySelector('h4').textContent)

  test('each group\'s tiles and special visuals, in the sheet\'s order', () => {
    sheet()
    const group = name => screen.getByRole('region', { name })
    expect(titles(group('Work and pay'))).toEqual(['People out of work', 'Typical weekly pay', 'Public works jobs', COPY.numbers.hires.title])
    expect(titles(group('Prices'))).toEqual(['Price of food', 'Price of housing', 'Price of services', 'Price of healthcare', 'A week of groceries'])
    expect(titles(group('Rich and poor'))).toEqual(['Gap between rich and poor', COPY.numbers.ladder.title, COPY.numbers.shares.title])
    expect(titles(group('Businesses'))).toEqual(['Businesses open', COPY.numbers.states.title, COPY.numbers.openClose.title])
    expect(titles(group('Money'))).toEqual(['Town hall cash', COPY.numbers.inOut.title, 'Sales this week, not counting rent', 'Bank loans', COPY.numbers.writtenOff.title])
    expect(titles(group('Wellbeing'))).toEqual(['Homes without a roof', 'Doctor visits turned away', 'How people feel'])
    expect(group('Prices').querySelectorAll('.nx-ptag')).toHaveLength(4)
    expect(group('Money').querySelector('rect.nx-owes')).not.toBeNull()
    expect(group('Wellbeing').querySelectorAll('.nx-meter-fill')).toHaveLength(2)
  })

  test('the line under the groups says which charts open big, and each of those does', () => {
    sheet()
    expect(screen.getByText(COPY.numbers.tap)).toBeInTheDocument()
    expect(COPY.numbers.tap).toBe('Tap any chart to see it big, apart from the hires and lay-offs, the openings and closings, and the loans written off.')
    const closed = [COPY.numbers.hires.title, COPY.numbers.openClose.title, COPY.numbers.writtenOff.title]
    const cards = screen.getAllByRole('article')
    for (const card of cards) {
      const title = card.querySelector('h4').textContent
      if (closed.includes(title)) expect(card, title).not.toHaveAttribute('tabindex')
      else expect(card, title).toHaveAttribute('tabindex', '0')
    }
    const opens = {
      [METRICS.townHallCash.name]: METRICS.townHallCash.name,
      [METRICS.happiness.name]: METRICS.happiness.name,
      [METRICS.priceHousing.name]: METRICS.priceHousing.name,
      [COPY.numbers.ladder.title]: METRICS.wealthP50.name,
      [COPY.numbers.shares.title]: METRICS.topTenthShare.name,
      [COPY.numbers.states.title]: METRICS.firmsGrowing.name,
      [COPY.numbers.inOut.title]: METRICS.townHallIncome.name,
    }
    for (const [title, heading] of Object.entries(opens)) {
      const card = screen.getAllByRole('article').find(node => node.querySelector('h4').textContent === title)
      fireEvent.click(card)
      expect(screen.getByRole('heading', { level: 3, name: heading })).toBeInTheDocument()
      fireEvent.keyDown(document.activeElement, { key: 'Escape' })
      expect(screen.getAllByRole('article').find(node => node.querySelector('h4').textContent === title)).toHaveFocus()
    }
  })

  test('the ladder, the business states and money in and out open with their own numbers as chips', () => {
    sheet()
    const chipsFor = title => {
      fireEvent.click(screen.getAllByRole('article').find(node => node.querySelector('h4').textContent === title))
      const chips = within(screen.getByRole('group', { name: 'Chart a different number' })).getAllByRole('button').map(chip => chip.textContent)
      fireEvent.keyDown(document.activeElement, { key: 'Escape' })
      return chips
    }
    expect(chipsFor(COPY.numbers.ladder.title)).toEqual(['wealthP10', 'wealthP50', 'wealthP90'].map(key => METRICS[key].name))
    expect(chipsFor(COPY.numbers.states.title)).toEqual(['Businesses growing', 'Businesses steady', 'Businesses struggling'])
    expect(chipsFor(COPY.numbers.inOut.title)).toEqual(['townHallIncome', 'familySupportPaid'].map(key => METRICS[key].name))
  })

  test('hardship empty states: nobody has lost a home, nobody turned away; later, the visits turned away so far', () => {
    const { rerender } = sheet()
    const wellbeing = () => screen.getByRole('region', { name: 'Wellbeing' })
    const card = name => within(wellbeing()).getByRole('article', { name })
    expect(card('Homes without a roof')).toHaveTextContent('No household has lost its home in either town so far.')
    expect(card('Doctor visits turned away')).toHaveTextContent('Nobody has been turned away yet in either town.')
    rerender(<div className="nx"><NumbersSheet arms={arms} tick={104} onClose={() => {}} /></div>)
    expect(card('Homes without a roof')).toHaveTextContent('No household has lost its home in either town so far.')
    expect(card('Doctor visits turned away')).toHaveTextContent('So far: 4 in Town A, 1 in Town B.')
    expect(card('Doctor visits turned away')).not.toHaveTextContent('Nobody has been turned away')
  })

  test('once a household has lost its home the sentence goes, and a town with no record of the number gets none', () => {
    const towns = [handArm(TOWN_A, { homelessHouseholds: [0, 0, 1, 0] }), handArm(TOWN_B, { homelessHouseholds: [0, 0, 0, 0] })]
    expect(hardshipNote('homelessHouseholds', towns, 2)).toBe('No household has lost its home in either town so far.')
    expect(hardshipNote('homelessHouseholds', towns, 3)).toBeNull()
    expect(hardshipNote('homelessHouseholds', towns, 4)).toBeNull()
    const unrecorded = [towns[1], handArm(TOWN_B, { homelessHouseholds: [null, null, null, null] })]
    expect(hardshipNote('homelessHouseholds', unrecorded, 4)).toBeNull()
    expect(hardshipNote('careDenials', towns, 4)).toBeNull()
    expect(weekLabel(4)).toBe('Year 1, week 4')
  })

  test('an older recording without the new numbers: they say "Not measured in this run" and nothing breaks', () => {
    draw(<NumbersSheet arms={oldArms()} tick={20} onClose={() => {}} />)
    for (const title of [COPY.numbers.shares.title, COPY.numbers.inOut.title, METRICS.happiness.name, METRICS.salesExceptRentThisWeek.name]) {
      const card = screen.getAllByRole('article').find(node => node.querySelector('h4').textContent === title)
      expect(card, title).toHaveTextContent('Not measured in this run')
    }
    // The older numbers still draw.
    expect(document.querySelector('rect.nx-wbar')).not.toBeNull()
    expect(document.querySelectorAll('.nx-ptag')).toHaveLength(4)
  })
})
