import { fireEvent, screen } from '@testing-library/react'
import { describe, expect, test, vi } from 'vitest'
import { renderScreen } from '../test/renderScreen.jsx'
import Logs from './Logs.jsx'

const logs = [
  { tick: 1, type: 'SYS', txt: 'INITIALIZING KERNEL...' },
  { tick: 2, type: 'SYS', txt: 'Tick 2 completed in 0.05s (50 ms).' },
  { tick: 3, type: 'FIRM', txt: 'Food Firm #3 entered distress' },
]

describe('Logs screen', () => {
  test('filters by type, lists rows, and shows the selected event', () => {
    const onTypeFilter = vi.fn(); const onSelectLog = vi.fn()
    const { container } = renderScreen(Logs, { logs, logIndex: 0, onSelectLog, typeFilter: 'All', onTypeFilter, severityFilter: 'All', onSeverityFilter: () => {}, search: '', onSearch: () => {}, density: 'comfortable', onDensity: () => {}, autoScroll: false, onAutoScroll: () => {} })
    expect(container.querySelectorAll('.tablefill tbody tr').length).toBe(3)
    expect(screen.getAllByText('INITIALIZING KERNEL...').length).toBeGreaterThan(0)
    fireEvent.click(container.querySelectorAll('.tablefill tbody tr')[2])
    expect(onSelectLog).toHaveBeenCalledWith(2)
    fireEvent.click(screen.getByText(/^Firm/))
    expect(onTypeFilter).toHaveBeenCalled()
  })

  test('no .chart .chart nesting remains so charts fill their panels', () => {
    const { container } = renderScreen(Logs)
    expect(container.querySelectorAll('.chart .chart').length).toBe(0)
  })
})
