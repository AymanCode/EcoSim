import { act, cleanup, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'

import App from './App.jsx'

class MockWebSocket {
  static OPEN = 1
  static instances = []

  constructor(url) {
    this.url = url
    this.readyState = MockWebSocket.OPEN
    this.sent = []
    MockWebSocket.instances.push(this)
    queueMicrotask(() => this.onopen?.())
  }

  send(message) {
    this.sent.push(JSON.parse(message))
  }

  close() {
    this.readyState = 3
    this.onclose?.()
  }

  emit(payload) {
    this.onmessage?.({ data: JSON.stringify(payload) })
  }
}

describe('EcoSim dashboard session lifecycle', () => {
  beforeEach(() => {
    MockWebSocket.instances = []
    globalThis.WebSocket = MockWebSocket
    vi.spyOn(console, 'log').mockImplementation(() => {})
  })

  afterEach(() => {
    cleanup()
    vi.restoreAllMocks()
  })

  test('shows preflight controls and enters the command view after setup', async () => {
    render(<App />)

    expect(screen.getByRole('heading', { name: 'Simulation Controls' })).toBeInTheDocument()
    expect(await screen.findByText('Ready')).toBeInTheDocument()
    expect(screen.getByText('ONLINE')).toBeInTheDocument()

    const socket = MockWebSocket.instances[0]
    expect(socket.url).toBe('ws://localhost:5173/ws')
    await act(async () => {
      socket.emit({ type: 'SESSION', sessionId: 'session-12345678' })
      socket.emit({ type: 'SETUP_COMPLETE' })
    })

    expect(screen.getByRole('heading', { name: 'Economic Command Deck' })).toBeInTheDocument()
    expect(screen.getByText(/Connected to Simulation Core · Session session-/)).toBeInTheDocument()
    expect(socket.sent).toContainEqual({ command: 'START' })
  })
})
