/* eslint-disable no-unused-labels */
// frontend-react/src/screens/Config.test.jsx
import { fireEvent, screen } from '@testing-library/react'
import { describe, expect, test, vi } from 'vitest'
import { renderScreen, DEFAULT_SETUP } from '../test/renderScreen.jsx'
import Config from './Config.jsx'

describe('Config screen', () => {
  test('launches, edits the population, and shows the session in the checklist', () => {
    const onLaunch = vi.fn(); const onSetupChange = vi.fn()
    render: {
      const { container } = renderScreen(Config, { setupConfig: DEFAULT_SETUP, onSetupChange, onConfigChange: () => {}, isInitialized: false, isInitializing: false, wsConnected: true, wsEndpoint: 'ws://localhost/ws', sessionId: 'd9b78c2e065242838c19ff058bc4de07', onLaunch, onResetDefaults: () => {}, onApply: () => {}, stabilizerAgentOptions: [{ key: 'households', label: 'Households' }], enumOptions: { benefit: [{ value: 'neutral', label: 'Neutral' }] } })
      fireEvent.click(screen.getByText('Launch Simulation'))
      expect(onLaunch).toHaveBeenCalled()
      fireEvent.change(container.querySelectorAll('input[type="range"]')[0], { target: { value: '2000' } })
      expect(onSetupChange).toHaveBeenCalledWith('num_households', 2000)
      expect(screen.getByText('d9b78c2e')).toBeInTheDocument()
    }
  })

  test('no .chart .chart nesting remains so charts fill their panels', () => {
    const { container } = renderScreen(Config)
    expect(container.querySelectorAll('.chart .chart').length).toBe(0)
  })
})
