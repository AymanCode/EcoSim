import { describe, expect, test } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import Moments from '../components/Moments.jsx'
import RunScreen from '../RunScreen.jsx'
import { moments } from '../narration.js'
import { fixtureArm, TOWN_A, TOWN_B } from './fixture.js'

const noop = () => {}
const rgb = hex => `rgb(${[1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16)).join(', ')})`

// Week 15 of the recording: a new richest business in both towns (since week
// 14), and Town A below 30 in 100 people out of work since week 12. (Week 14's
// fall below 20 is a flip back after rising in week 13, so it is no moment.)
const WEEK = 15

describe('Moments', () => {
  test('renders the chips with each town\'s colour', () => {
    const arms = [fixtureArm(TOWN_A), fixtureArm(TOWN_B)]
    const expected = moments(arms, WEEK)
    expect(expected).toHaveLength(3)
    render(<Moments arms={arms} tick={WEEK} />)
    const chips = within(screen.getByRole('log', { name: 'What just happened' })).getAllByRole('listitem')
    expect(chips.map(chip => chip.textContent)).toEqual(expected.map(moment => moment.text))
    chips.forEach(chip => expect(chip.querySelector('i')).toHaveAttribute('aria-hidden', 'true'))
    expect(chips.map(chip => chip.querySelector('i').style.background)).toEqual(expected.map(moment => rgb(moment.color)))
    expect(new Set(expected.map(moment => moment.color))).toEqual(new Set([TOWN_A.color, TOWN_B.color]))
  })

  test('renders an empty region when nothing happened, ready for the next chip', () => {
    render(<Moments arms={[fixtureArm(TOWN_A)]} tick={24} />)
    expect(moments([fixtureArm(TOWN_A)], 24)).toEqual([])
    const region = screen.getByRole('log', { name: 'What just happened' })
    expect(region).toHaveClass('nx-moments')
    expect(within(region).queryAllByRole('listitem')).toHaveLength(0)
    expect(region.querySelector('ul')).toBeInTheDocument()
  })

  test('announces only the chips that arrive, politely', () => {
    render(<Moments arms={[fixtureArm(TOWN_A)]} tick={24} />)
    const region = screen.getByRole('log', { name: 'What just happened' })
    expect(region).toHaveAttribute('aria-live', 'polite')
    expect(region).toHaveAttribute('aria-atomic', 'false')
    expect(region).toHaveAttribute('aria-relevant', 'additions')
  })

  test('sits under the lead on the Run screen, recorded and live', () => {
    const arms = [fixtureArm(TOWN_A), fixtureArm(TOWN_B)]
    const props = { arms, tick: WEEK, maxTick: 24, playing: false, onToggle: noop, onScrub: noop, speed: 1, onSpeed: noop }
    const live = {
      phase: 'running', towns: [], error: null, following: true, onFollow: noop, hallOpen: false, onHall: noop,
      onConfigure: noop, onTrack: noop, onExtend: noop, onRestart: noop, onNewExperiment: noop,
    }
    for (const extra of [{}, { live }]) {
      const { container, unmount } = render(<div className="nx"><RunScreen {...props} {...extra} /></div>)
      const strip = container.querySelector('.nx-lead').nextElementSibling
      expect(strip).toHaveClass('nx-moments')
      expect(strip).toHaveAttribute('role', 'log')
      expect(within(strip).getAllByRole('listitem')).toHaveLength(3)
      unmount()
    }
  })
})
