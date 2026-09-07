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

  test('no .chart .chart nesting remains so charts fill their panels', () => {
    const { container } = renderScreen(Finance)
    expect(container.querySelectorAll('.chart .chart').length).toBe(0)
  })
})
