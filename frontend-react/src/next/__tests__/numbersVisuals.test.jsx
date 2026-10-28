import { beforeAll, describe, expect, test, vi } from 'vitest'
import { fireEvent, render, screen, within } from '@testing-library/react'
import StoryChart from '../components/StoryChart.jsx'
import HiresAndLayoffs from '../numbers/HiresAndLayoffs.jsx'
import WealthLadder from '../numbers/WealthLadder.jsx'
import FirmStates from '../numbers/FirmStates.jsx'
import OpenedClosed from '../numbers/OpenedClosed.jsx'
import LoansWrittenOff from '../numbers/LoansWrittenOff.jsx'
import { COPY, METRICS, formatMetric, formatMoney } from '../catalog.js'
import { countedAt, cumulativeUpTo, valueAt, weeklyCounts } from '../data/derive.js'
import { weekLabel } from '../narration.js'
import { demoArms, fixtureArm, TOWN_A, TOWN_B } from './fixture.js'

// The recorded demo (Town B has a higher minimum wage). At week 72 (Year 2,
// week 20) Town A's town hall owes money and Town B's does not.
let arms
beforeAll(() => { arms = demoArms() })

const draw = node => render(<div className="nx">{node}</div>)
const oldArms = () => [fixtureArm(TOWN_A), fixtureArm(TOWN_B)]

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

describe('visuals inside a number row', () => {
  test.each([
    ['savings', WealthLadder], ['firm states', FirmStates], ['opened and closed', OpenedClosed],
    ['hires and lay-offs', HiresAndLayoffs], ['loans', LoansWrittenOff],
  ])('%s has no card, title or see-big action in inline mode', (_, Visual) => {
    const onSeeBig = vi.fn()
    const { container } = draw(<Visual arms={arms} tick={104} inline onSeeBig={onSeeBig} className="owned-visual" />)
    expect(container.querySelector('.owned-visual')).toBeInTheDocument()
    expect(screen.queryByRole('article')).toBeNull()
    expect(screen.queryByRole('heading')).toBeNull()
    expect(container.querySelector('.nx-card, .nx-tile, .nx-big, [data-metric]')).toBeNull()
    fireEvent.click(container.querySelector('.owned-visual'))
    expect(onSeeBig).not.toHaveBeenCalled()
    expect(screen.getByRole('table')).toBeInTheDocument()
  })

  test('the savings middle label goes while its dot, outer labels and table remain', () => {
    const { container } = draw(<WealthLadder arms={arms} tick={104} inline />)
    expect(container.querySelectorAll('.nx-wdot')).toHaveLength(2)
    expect(container.querySelector('.nx-vval.is-mid')).toBeNull()
    const labels = [...container.querySelectorAll('.nx-vval')].map(node => node.textContent)
    expect(labels).toEqual(arms.flatMap(arm => ['wealthP10', 'wealthP90'].map(key => formatMoney(countedAt(arm, key, 104).value))))
    const rows = within(screen.getByRole('table')).getAllByRole('row')
    expect(rows).toHaveLength(4)
    expect([...rows[2].children].map(cell => cell.textContent)).toEqual([
      METRICS.wealthP50.name, ...arms.map(arm => formatMoney(countedAt(arm, 'wealthP50', 104).value)),
    ])
    // The owning NumberRow supplies this note once.
    expect(container).not.toHaveTextContent('Counted every 5 weeks; last count Year 2, week 48.')
  })

  test('firm states keep each state count without repeating the businesses-open total', () => {
    const { container } = draw(<FirmStates arms={arms} tick={104} inline />)
    const towns = [...container.querySelectorAll('.nx-vtown')]
    expect(towns.map(node => node.textContent)).toEqual(['Town A', 'Town B'])
    expect(container.querySelectorAll('.nx-vline b')).toHaveLength(6)
    expect(container.querySelectorAll('.nx-sbar')).toHaveLength(2)
    const rows = within(screen.getByRole('table')).getAllByRole('row').slice(1)
    expect(rows.map(row => row.firstChild.textContent)).toEqual(['growing', 'steady', 'struggling'])
  })

  test('hires show gross totals and weekly bars, without the jobs-added net', () => {
    const { container } = draw(<HiresAndLayoffs arms={arms} tick={104} inline />)
    const panels = [...container.querySelectorAll('.nx-vpanel')]
    panels.forEach((panel, i) => {
      const rows = weeklyCounts(arms[i], ['hired', 'laidOff'], 104, 26)
      expect(panel.querySelector('.nx-foot')).toHaveTextContent(COPY.numbers.hires.inThese(sum(rows.map(row => row.hired)), sum(rows.map(row => row.laidOff))))
      expect(panel).not.toHaveTextContent(/net|jobs added|\+17|\+83/i)
    })
    expect(within(screen.getByRole('table')).getAllByRole('row')).toHaveLength(27)
  })

  test('openings and closings give the window totals once, including before week 26', () => {
    const town = handArm(TOWN_A, { firmsOpen: [4, 5, 5, 5] }, {
      eventCounts: { 1: { firmsOpened: 0, firmsClosed: 0 }, 2: { firmsOpened: 1, firmsClosed: 0 }, 4: { firmsOpened: 0, firmsClosed: 0 } },
    })
    const { container } = draw(<OpenedClosed arms={[town]} tick={4} inline />)
    expect(container.querySelector('.nx-vhead')).toHaveTextContent('Town A')
    expect(container.querySelector('.nx-vhead')).not.toHaveTextContent('so far')
    expect(container.querySelectorAll('.nx-foot')).toHaveLength(1)
    expect(container.querySelector('.nx-foot')).toHaveTextContent('In these weeks: 1 opened, 0 closed.')
    const table = screen.getByRole('table')
    expect(within(table).getAllByRole('columnheader').map(cell => cell.textContent)).toEqual(['Week', 'Town A, opened', 'Town A, closed'])
    const rows = within(table).getAllByRole('row').slice(1)
    expect(rows).toHaveLength(4)
    expect([...rows[0].children].map(cell => cell.textContent)).toEqual(['Year 1, week 1', '0', '0'])
    expect([...rows[2].children].map(cell => cell.textContent)).toEqual(['Year 1, week 3', 'not recorded', 'not recorded'])
    expect(container.querySelector('.nx-vfuture')).toBeInTheDocument()
  })

  test('the loans line and table use cumulative sums, carry missing weeks and respect scrubbing', () => {
    const towns = [
      handArm(TOWN_A, { bankDefaultAmountThisTick: [null, 100, null, 50] }),
      handArm(TOWN_B, { bankDefaultAmountThisTick: [0, 50, 0, 100] }),
    ]
    const original = towns.map(arm => [...arm.series.bankDefaultAmountThisTick])
    const { container, rerender } = draw(<LoansWrittenOff arms={towns} tick={4} inline />)
    expect(container.querySelectorAll('.nx-warmline')).toHaveLength(2)
    expect(container.querySelector('.nx-endl, .pair, .nx-pile')).toBeNull()
    let rows = within(screen.getByRole('table')).getAllByRole('row').slice(1)
    expect(rows.map(row => [...row.children].slice(1).map(cell => cell.textContent))).toEqual([
      [COPY.numbers.notMeasured, '$0'], ['$100', '$50'], ['$100', '$50'], ['$150', '$150'],
    ])
    rerender(<div className="nx"><LoansWrittenOff arms={towns} tick={3} inline playing /></div>)
    rows = within(screen.getByRole('table')).getAllByRole('row').slice(1)
    expect(rows).toHaveLength(3)
    expect([...rows.at(-1).children].slice(1).map(cell => cell.textContent)).toEqual(towns.map(arm => formatMoney(cumulativeUpTo(arm, 'bankDefaultAmountThisTick', 3))))
    expect(container.querySelector('.nx-chart')).toHaveClass('is-playing')
    expect(container.querySelector('.nx-endl')).toBeNull()
    expect(container.querySelector('.nx-future')).toBeInTheDocument()
    expect(towns.map(arm => arm.series.bankDefaultAmountThisTick)).toEqual(original)
    expect(towns.every(arm => !Object.hasOwn(arm.series, 'writtenOffSoFar'))).toBe(true)
  })

  test.each([WealthLadder, FirmStates, OpenedClosed, HiresAndLayoffs, LoansWrittenOff])('missing inline visual data stays unmeasured', Visual => {
    const towns = [handArm(TOWN_A, { missing: [null, null] })]
    const { container } = draw(<Visual arms={towns} tick={2} inline />)
    expect(container).toHaveTextContent(COPY.numbers.notMeasured)
    expect(container.querySelector('svg, .nx-card, .nx-tile')).toBeNull()
  })
})

describe('StoryChart sheet options', () => {
  const chart = (props = {}) => draw(<StoryChart arms={oldArms()} metricKey="peopleOutOfWorkPer100" tick={24} horizon={104} {...props} />)

  test('the default keeps its card, heading, chips, end labels and sampled table without interactions', () => {
    const { container } = chart()
    expect(container.querySelector('.nx-storyc')).toHaveClass('nx-card')
    expect(screen.getByRole('heading', { name: METRICS.peopleOutOfWorkPer100.name })).toBeInTheDocument()
    expect(screen.getByRole('group', { name: COPY.chart.chips })).toBeInTheDocument()
    expect(container.querySelectorAll('.nx-endl')).toHaveLength(2)
    expect(container.querySelector('.nx-chart')).not.toHaveAttribute('tabindex')
    fireEvent.focus(container.querySelector('.nx-chart'))
    expect(screen.queryByRole('tooltip')).toBeNull()
    expect(within(screen.getByRole('table')).getAllByRole('row')).toHaveLength(3)
  })

  test('hiding end labels retains the endpoint dots and leaves more room for the plot', () => {
    const normal = chart()
    const right = num(normal.container.querySelector('.nx-yaxis line'), 'x2')
    normal.unmount()
    const hidden = chart({ hideEndLabels: true })
    expect(hidden.container.querySelector('.nx-endl, .nx-leader')).toBeNull()
    expect(hidden.container.querySelectorAll('.nx-dot')).toHaveLength(2)
    expect(num(hidden.container.querySelector('.nx-yaxis line'), 'x2')).toBeGreaterThan(right)
  })

  test('inline output has only the chart, a local key and every recorded week in its table', () => {
    const { container, rerender } = chart({ inline: true, hideEndLabels: true })
    expect(container.querySelector('.nx-card')).toBeNull()
    expect(screen.queryByRole('heading')).toBeNull()
    expect(screen.queryByRole('group', { name: COPY.chart.chips })).toBeNull()
    const key = screen.getByRole('list', { name: COPY.numbers.chart.label })
    expect(key).toHaveTextContent(COPY.numbers.chart.warm)
    expect(key).toHaveTextContent(COPY.numbers.chart.future)
    const table = screen.getByRole('table')
    expect(table.parentElement).toHaveClass('nx-sr')
    expect(within(table).getAllByRole('row')).toHaveLength(25)
    rerender(<div className="nx"><StoryChart arms={oldArms()} metricKey="peopleOutOfWorkPer100" tick={24} horizon={24} inline hideEndLabels /></div>)
    expect(screen.getByRole('list', { name: COPY.numbers.chart.label })).not.toHaveTextContent(COPY.numbers.chart.future)
  })

  test('crosshair and tooltip opt in for keyboard inspection and never expose future values', () => {
    const { container } = chart({ inline: true, hideEndLabels: true, interactive: true })
    const plot = screen.getByRole('group', { name: COPY.numbers.chart.tooltip(METRICS.peopleOutOfWorkPer100.name) })
    fireEvent.focus(plot)
    expect(screen.getByRole('tooltip')).toHaveTextContent(weekLabel(24))
    fireEvent.keyDown(plot, { key: 'ArrowLeft' })
    expect(screen.getByRole('tooltip')).toHaveTextContent(weekLabel(23))
    expect(screen.getByRole('tooltip')).toHaveTextContent(`Town A, ${formatMetric('peopleOutOfWorkPer100', valueAt(oldArms()[0], 'peopleOutOfWorkPer100', 23))}`)
    expect(container.querySelector('.nx-crosshair line')).toBeInTheDocument()
    fireEvent.keyDown(plot, { key: 'ArrowRight' })
    fireEvent.keyDown(plot, { key: 'ArrowRight' })
    expect(screen.getByRole('tooltip')).toHaveTextContent(weekLabel(24))
    fireEvent.keyDown(plot, { key: 'Home' })
    expect(screen.getByRole('tooltip')).toHaveTextContent(weekLabel(1))
    fireEvent.keyDown(plot, { key: 'End' })
    expect(screen.getByRole('tooltip')).toHaveTextContent(weekLabel(24))
    fireEvent.blur(plot)
    expect(screen.queryByRole('tooltip')).toBeNull()
  })

  test('pointer inspection follows the week under the crosshair', () => {
    const { container } = chart({ inline: true, hideEndLabels: true, interactive: true })
    const plot = container.querySelector('.nx-chart')
    const warm = container.querySelector('.nx-warm')
    const selectedX = num(warm, 'x') + (num(warm, 'width') / 10) * 13
    const event = new MouseEvent('pointermove', { bubbles: true, clientX: selectedX, clientY: 100 })
    fireEvent(plot, event)
    expect(screen.getByRole('tooltip')).toHaveTextContent(weekLabel(13))
    fireEvent.pointerLeave(plot)
    expect(screen.queryByRole('tooltip')).toBeNull()
  })

  test('counted inline tables list counts, with the endpoint at the last count', () => {
    const { container } = draw(<StoryChart arms={arms} metricKey="gini" tick={72} horizon={104} countedWeeks inline hideEndLabels />)
    const rows = within(screen.getByRole('table')).getAllByRole('row').slice(1)
    expect(rows.at(-1).firstChild).toHaveTextContent(weekLabel(70))
    expect(rows.some(row => row.firstChild.textContent === weekLabel(72))).toBe(false)
    const warm = container.querySelector('.nx-warm')
    const weekAt = px => Math.round((px - num(warm, 'x')) / (num(warm, 'width') / 10))
    container.querySelectorAll('.nx-dot').forEach(dot => expect(weekAt(num(dot, 'cx'))).toBe(70))
  })
})
