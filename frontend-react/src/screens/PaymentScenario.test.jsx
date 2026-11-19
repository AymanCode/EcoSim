import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'

import App from '../App.jsx'
import Config from './Config.jsx'
import Government from './Government.jsx'
import Population from './Population.jsx'
import { renderScreen, DEFAULT_SETUP, frame } from '../test/renderScreen.jsx'

vi.mock('../NeuralGovernment.jsx', () => ({ default: () => null }))
vi.mock('../NeuralAvatar.jsx', () => ({ default: () => null }))

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

  test.each([['income_first', true], ['income_late', false]])('launches %s with the applicable grocery benefit', async (timing, expected) => {
    render(<App />)
    await screen.findByText('Ready')
    const benefit = screen.getByRole('combobox', { name: 'Grocery benefit (EBT)' })
    expect(benefit).toHaveValue('off')
    fireEvent.change(benefit, { target: { value: 'on' } })
    fireEvent.change(screen.getByRole('combobox', { name: 'Payment timing' }), { target: { value: timing } })
    expect(benefit).toHaveValue(expected ? 'on' : 'off')
    fireEvent.click(screen.getByRole('button', { name: 'Launch Simulation' }))
    const socket = MockWebSocket.instances[0]
    expect(socket.sent).toContainEqual(expect.objectContaining({
      command: 'SETUP',
      config: expect.objectContaining({ payment_food_credit_enabled: expected, payment_sequence: timing }),
    }))
    await act(async () => socket.emit({ type: 'SETUP_COMPLETE' }))
    fireEvent.click(screen.getByRole('button', { name: 'Config' }))
    expect(screen.getByRole('combobox', { name: 'Grocery benefit (EBT)' })).toBeDisabled()
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

  test('shows town spending and the selected household card separately', () => {
    const { unmount } = renderScreen(Government, { metrics: {
      ...frame.metrics, payment: { fiscal: { food_credit: { issued: 500, redeemed: 477.5, outstanding: 22.5 } } },
    } })
    expect(screen.getByText('$477.50')).toBeInTheDocument()
    expect(screen.getByText('$22.50')).toBeInTheDocument()
    unmount()
    const subject = { ...frame.metrics.trackedSubjects[0], groceryCardBalance: 1.35, groceryCardSpent: 1.15 }
    renderScreen(Population, { metrics: { ...frame.metrics, trackedSubjects: [subject] } })
    expect(screen.getByText('Grocery card balance')).toBeInTheDocument()
    expect(screen.getByText('$1.35')).toBeInTheDocument()
    expect(screen.getByText('$1.15')).toBeInTheDocument()
  })
})
