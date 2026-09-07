import { fireEvent, screen } from '@testing-library/react'
import { describe, expect, test, vi } from 'vitest'
import { renderScreen, frame } from '../test/renderScreen.jsx'
import Markets from './Markets.jsx'

vi.mock('../NeuralBuilding.jsx', () => ({ default: () => <div data-canvas="building" /> }))

describe('Markets screen', () => {
  test('renders sectors, the sortable table, and the selected firm from the fixture', () => {
    const onSelectFirm = vi.fn()
    const { container } = renderScreen(Markets, { firmIndex: 0, onSelectFirm })
    for (const s of ['Food', 'Housing', 'Services', 'Healthcare']) expect(screen.getAllByText(s).length).toBeGreaterThan(0)
    const rows = () => container.querySelectorAll('.tablefill tbody tr')
    expect(rows().length).toBeGreaterThanOrEqual(7)
    const firstBefore = rows()[0].textContent
    fireEvent.click(screen.getByText(/^Firm/))
    expect(rows()[0].textContent).not.toBe(firstBefore)
    expect(screen.getAllByText(frame.metrics.trackedFirms[0].name).length).toBeGreaterThan(0)
    expect(container.querySelector('[data-canvas="building"]')).toBeTruthy()
  })

  test('no .chart .chart nesting remains so charts fill their panels', () => {
    const { container } = renderScreen(Markets)
    expect(container.querySelectorAll('.chart .chart').length).toBe(0)
  })
})
