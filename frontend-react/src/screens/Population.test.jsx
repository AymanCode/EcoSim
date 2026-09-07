import { fireEvent, screen } from '@testing-library/react'
import { describe, expect, test, vi } from 'vitest'
import { renderScreen, frame } from '../test/renderScreen.jsx'
import { readableName } from '../format.js'
import Population from './Population.jsx'

vi.mock('../NeuralAvatar.jsx', () => ({ default: () => <div data-canvas="avatar" /> }))

describe('Population screen', () => {
  test('renders the roster, the radar, and the selected household from the fixture', () => {
    const onSelectSubject = vi.fn()
    const { container } = renderScreen(Population, { subjectIndex: 0, onSelectSubject, search: '', onSearch: () => {}, filter: 'All', onFilter: () => {} })
    expect(container.querySelectorAll('.roster .r').length).toBe(frame.metrics.trackedSubjects.length)
    expect(container.querySelectorAll('svg.radar circle').length).toBeGreaterThanOrEqual(10)
    expect(screen.getAllByText(readableName(frame.metrics.trackedSubjects[0].name)).length).toBeGreaterThan(0)
    expect(container.querySelector('[data-canvas="avatar"]')).toBeTruthy()
    fireEvent.click(container.querySelectorAll('.roster .r')[2])
    expect(onSelectSubject).toHaveBeenCalledWith(2)
  })

  test('filters roster by Stretched cohort using the unified definition', () => {
    const expectedCount = frame.metrics.trackedSubjects.filter(
      (s) => s.state === 'UNEMPLOYED' || (s.cash || 0) < 150
    ).length
    const { container } = renderScreen(Population, {
      subjectIndex: 0,
      onSelectSubject: () => {},
      search: '',
      onSearch: () => {},
      filter: 'Stretched',
      onFilter: () => {},
    })
    expect(container.querySelectorAll('.roster .r').length).toBe(expectedCount)
  })

  test('no .chart .chart nesting remains so charts fill their panels', () => {
    const { container } = renderScreen(Population)
    expect(container.querySelectorAll('.chart .chart').length).toBe(0)
  })

})
