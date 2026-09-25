import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'

import App from '../App.jsx'
import Config from './Config.jsx'
import { renderScreen, DEFAULT_SETUP } from '../test/renderScreen.jsx'

class MockWebSocket {
  static OPEN = 1
  static instances = []

  constructor() {
    this.readyState = MockWebSocket.OPEN
    this.sent = []
    MockWebSocket.instances.push(this)
    queueMicrotask(() => this.onopen?.())
  }

  send(message) { this.sent.push(JSON.parse(message)) }
  close() { this.readyState = 3; this.onclose?.() }
  emit(payload) { this.onmessage?.({ data: JSON.stringify(payload) }) }
}

describe('launch-only payment scenario', () => {
  beforeEach(() => {
    MockWebSocket.instances = []
    globalThis.WebSocket = MockWebSocket
    vi.spyOn(console, 'log').mockImplementation(() => {})
  })

  afterEach(() => {
    cleanup()
    vi.restoreAllMocks()
  })

  test('sends selected payment fields in SETUP and locks them after launch', async () => {
    render(<App />)
    await screen.findByText('Ready')
    fireEvent.change(screen.getByRole('combobox', { name: 'Payment timing' }), { target: { value: 'income_late' } })
    fireEvent.change(screen.getByRole('combobox', { name: 'Care funding' }), { target: { value: 'covered' } })
    fireEvent.change(screen.getByRole('combobox', { name: 'Use of receipts' }), { target: { value: 'mixed' } })
    fireEvent.click(screen.getByRole('button', { name: 'Launch Simulation' }))
    const socket = MockWebSocket.instances[0]
    expect(socket.sent).toContainEqual(expect.objectContaining({
      command: 'SETUP',
      config: expect.objectContaining({
        payment_sequence: 'income_late',
        payment_care_mode: 'covered',
        payment_assistance: 'mixed',
      }),
    }))
    await act(async () => socket.emit({ type: 'SETUP_COMPLETE' }))
    fireEvent.click(screen.getByRole('button', { name: 'Config' }))
    expect(screen.getByRole('combobox', { name: 'Payment timing' })).toBeDisabled()
    expect(screen.getByRole('combobox', { name: 'Care funding' })).toBeDisabled()
    expect(screen.getByRole('combobox', { name: 'Use of receipts' })).toBeDisabled()
    expect(screen.getByText(/Start a new run to change them/)).toBeInTheDocument()
  })

  test('does not offer a scenario change callback after initialization', () => {
    const onSetupChange = vi.fn()
    renderScreen(Config, {
      setupConfig: { ...DEFAULT_SETUP, payment_sequence: 'income_first' },
      onSetupChange,
      isInitialized: true,
    })
    const timing = screen.getByRole('combobox', { name: 'Payment timing' })
    expect(timing).toBeDisabled()
    fireEvent.change(timing, { target: { value: 'legacy' } })
    expect(onSetupChange).not.toHaveBeenCalled()
  })
})
