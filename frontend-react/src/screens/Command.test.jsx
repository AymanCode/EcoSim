import { screen } from '@testing-library/react'
import { describe, expect, test, vi } from 'vitest'
import { renderScreen } from '../test/renderScreen.jsx'
import Command from './Command.jsx'

vi.mock('../charts/useMeasured.js', () => ({ default: () => [{ current: null }, { width: 600, height: 200 }] }))

describe('Command screen', () => {
  test('renders the six tiles, the GDP chart, the meter and the wealth bar from the fixture', () => {
    const { container } = renderScreen(Command)
    for (const label of ['GDP output', 'Unemployment', 'Employment', 'Average wage', 'Macro stress', 'Fiscal balance']) expect(screen.getAllByText(label).length).toBeGreaterThan(0)
    expect(container.querySelectorAll('.meter').length).toBe(1)
    expect(container.querySelectorAll('.stack > div').length).toBe(3)
    expect(container.querySelectorAll('.chart').length).toBeGreaterThanOrEqual(8)
    expect(container.textContent).toContain('Sector prices')
  })

  test('no .chart .chart nesting remains so charts fill their panels', () => {
    const { container } = renderScreen(Command)
    expect(container.querySelectorAll('.chart .chart').length).toBe(0)
  })

  test('renders policy markers when policyChanges is non-empty', () => {
    const policyChanges = [
      { tick: 25, policy: 'wage_tax_rate', value: 0.18, reason: 'User updated wage_tax_rate from 0.15 to 0.18' },
    ]
    const { container } = renderScreen(Command, { policyChanges })
    expect(container.querySelectorAll('.recharts-reference-line').length).toBeGreaterThan(0)
  })
})
