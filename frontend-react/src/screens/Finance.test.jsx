// frontend-react/src/screens/Finance.test.jsx
import { describe, expect, test } from 'vitest'
import { renderScreen } from '../test/renderScreen.jsx'
import Finance from './Finance.jsx'

describe('Finance screen', () => {
  test('renders the hero, four chart tiles, the ledger, and no placeholder panels', () => {
    const { container } = renderScreen(Finance, { policyChanges: [] })
    expect(container.querySelector('.hero .v')).toBeTruthy()
    expect(container.querySelectorAll('.ctile').length).toBe(4)
    expect(container.querySelectorAll('.ledger .lr').length).toBe(5)
    expect(container.querySelector('.ledger .lr.net')).toBeTruthy()
    expect(container.textContent).not.toMatch(/N\/A|Bank inspector|hologram/i)
    expect(container.textContent).toContain('State capacity')
  })

  test('shows public-debt borrowing and repayment as financing lines', () => {
    const { container } = renderScreen(Finance, {
      metrics: { govProfit: -0.005243, govDebt: 1.2, govBorrowed: 0.005, govRepaid: 0 },
      policyChanges: [],
    })
    expect(container.textContent).toContain('Borrowed from bank · this tick')
    expect(container.textContent).toContain('Repaid to bank · this tick')
    expect(container.textContent).toContain('Outlays exceed revenue this tick.')
    expect(container.querySelectorAll('.ledger .lr').length).toBe(5)
  })

  test('hides the borrowing and repayment lines when the server sends none (public debt off)', () => {
    const { container } = renderScreen(Finance, {
      metrics: { govProfit: -0.005243, govDebt: 0 },
      policyChanges: [],
    })
    expect(container.textContent).not.toContain('Borrowed from bank')
    expect(container.textContent).not.toContain('Repaid to bank')
  })

  test('no .chart .chart nesting remains so charts fill their panels', () => {
    const { container } = renderScreen(Finance)
    expect(container.querySelectorAll('.chart .chart').length).toBe(0)
  })
})
