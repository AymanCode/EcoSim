import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'

import App from '../App.jsx'
import Government from './Government.jsx'
import { DEFAULT_CONFIG, frame, renderScreen } from '../test/renderScreen.jsx'
import { formatMillionsAdaptive } from '../format.js'

vi.mock('../NeuralGovernment.jsx', () => ({ default: () => <div data-canvas="government" /> }))

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

const canvasStub = () => new Proxy({}, { get: () => () => ({}) })

const baseMetrics = () => ({
  unemployment: 11.2, gdp: 4.3, govDebt: 0.388, govProfit: -0.0214, govRevenue: 0.1428, govTransfers: 0.1016, govInvestments: 0.0626,
  govOwnedFirms: 2, activeLoans: 7, bondPurchases: 0.0626, happiness: 55, avgWage: 30,
  gdpHistory: [{ tick: 1, value: 3.9 }, { tick: 1225, value: 4.21 }, { tick: 1250, value: 4.26 }, { tick: 1275, value: 4.3 }],
  unemploymentHistory: [{ tick: 1, value: 20 }, { tick: 1225, value: 11.8 }, { tick: 1250, value: 11.5 }, { tick: 1275, value: 11.2 }],
  happinessHistory: [{ tick: 1, value: 50 }, { tick: 1225, value: 54.1 }, { tick: 1250, value: 54.6 }, { tick: 1275, value: 55 }],
  govProfitHistory: [{ tick: 1, value: 0 }, { tick: 1225, value: -0.038 }, { tick: 1250, value: -0.03 }, { tick: 1275, value: -0.0214 }],
  govDebtHistory: [{ tick: 1, value: 0 }, { tick: 1275, value: 0.388 }],
  governmentPolicy: {
    wage_tax_rate: 0.18, profit_tax_rate: 0.2, investment_tax_rate: 0.1, benefit_level: 'high', public_works: 'on', minimum_wage_policy: 'neutral',
    sector_subsidy_target: 'food', sector_subsidy_level: 25, infrastructure_spending: 'none', technology_spending: 'none', social_spending: 'medium',
    price_stabilization_target: 'none', price_stabilization_level: 'off', rent_stabilization_level: 'off', bailout_policy: 'off', bailout_target: 'none', bailout_budget: 0,
  },
  policyChanges: [
    { tick: 1249, policy: 'sector_subsidy_level', value: 25, reason: 'LLM government set sector_subsidy_level from 0 to 25. Food firms are short on stock.' },
    { tick: 1249, policy: 'benefit_level', value: 'high', reason: 'LLM government set benefit_level from neutral to high. Food firms are short on stock.' },
    { tick: 1100, policy: 'public_works', value: 'on', reason: 'User updated public_works to on' },
    { tick: 900, policy: 'wage_tax_rate', value: 0.18, reason: 'User updated wage_tax_rate to 0.18' },
  ],
  llmGovernment: { enabled: false, status: 'disabled', latestDecision: null },
  trackedSubjects: [], trackedFirms: [],
  priceHistory: { food: [], housing: [], services: [], healthcare: [] },
  supplyHistory: { food: [], housing: [], services: [], healthcare: [] },
})

const aiDecision = () => ({
  primary_goal: 'essential_sector_support', fiscal_mode: 'LOW_CASH', computed_fiscal_mode: 'LOW_CASH',
  rationale: 'Food firms are short on stock.',
  evidence: ['unemployment_rate=0.118', 'government_cash=-412000'],
  evidence_audit: [
    { evidence: 'unemployment_rate=0.118', status: 'matched_metric', key: 'unemployment_rate', actual_value: 0.118 },
    { evidence: 'government_cash=-412000', status: 'value_mismatch', key: 'government_cash', actual_value: -388100 },
  ],
  accepted_llm_changes: { benefit_level: 'high', sector_subsidy_level: 25 }, mechanical_corrections: {},
  applied_changes: { benefit_level: 'high', sector_subsidy_level: 25 }, decisions: { benefit_level: 'high', sector_subsidy_level: 25 },
  rejected_changes: [{ lever: 'bailout_budget', value: 50000, reason: 'exceeds affordable reserve' }],
  parse_ok: true, elapsed_ms: 4200, snapshotTick: 1248, appliedTick: 1249,
})

async function openGovernment(metrics) {
  render(<App />)
  await screen.findByText('Ready')
  const socket = MockWebSocket.instances[0]
  await act(async () => {
    socket.emit({ type: 'SESSION', sessionId: 'session-12345678' })
    socket.emit({ type: 'SETUP_COMPLETE' })
  })
  await act(async () => {
    socket.emit({ tick: 1275, metrics, logs: [], firm_stats: null })
  })
  fireEvent.click(screen.getByRole('button', { name: 'Government' }))
  return socket
}

describe('Government Console', () => {
  beforeEach(() => {
    MockWebSocket.instances = []
    globalThis.WebSocket = MockWebSocket
    vi.spyOn(console, 'log').mockImplementation(() => {})
    vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockImplementation(canvasStub)
  })

  afterEach(() => {
    vi.useRealTimers()
    cleanup()
    vi.restoreAllMocks()
  })

  test('renders the AI decision, lever provenance, and impact since each change', async () => {
    const metrics = baseMetrics()
    metrics.llmGovernment = {
      enabled: true, status: 'ready', provider: 'lmstudio', model: 'microsoft/phi-4-mini-reasoning',
      snapshotTick: 1248, appliedTick: 1249, acceptedChangeCount: 2, rejectedChangeCount: 1, latestDecision: aiDecision(),
    }
    await openGovernment(metrics)

    expect(screen.getByRole('heading', { name: 'Government Console' })).toBeInTheDocument()
    expect(screen.getByText('Policy stance')).toBeInTheDocument()
    expect(screen.getAllByText('Supporting essential sectors').length).toBeGreaterThan(0)
    expect(screen.getAllByText(/Low cash/).length).toBeGreaterThan(0)
    expect(screen.getByText('Refused')).toBeInTheDocument()
    expect(screen.getByText('exceeds affordable reserve')).toBeInTheDocument()
    expect(screen.getByText(/You · tick 900/)).toBeInTheDocument()
    expect(screen.getAllByText(/AI · tick 1[,.]?249/)).toHaveLength(2)
    expect(screen.getByText(/\$50K refused · tick 1[,.]?249/)).toBeInTheDocument()
    expect(screen.getByText('matches observation')).toBeInTheDocument()
    expect(screen.getByText(/shown -388,100/)).toBeInTheDocument()
    expect(screen.getAllByText('+2.1%').length).toBeGreaterThanOrEqual(2)
    expect(screen.getAllByText('+10.3%')).toHaveLength(2)
    expect(screen.queryByText(/Previous run history/)).toBeNull()
    expect(screen.queryByText('AI government is off')).toBeNull()
  })

  test('shows the manual state, keeps the timeline, and offers to enable the AI', async () => {
    const socket = await openGovernment(baseMetrics())

    expect(screen.getByText('AI government is off')).toBeInTheDocument()
    expect(screen.queryByText('Latest decision')).toBeNull()
    expect(screen.getByText(/5 interventions active, treasury in deficit/)).toBeInTheDocument()
    expect(screen.getByText(/You · tick 900/)).toBeInTheDocument()
    expect(screen.getAllByText(/Wage tax/).length).toBeGreaterThan(0)

    fireEvent.click(screen.getByRole('button', { name: 'Enable AI government' }))
    await act(async () => {
      await new Promise(resolve => setTimeout(resolve, 450))
    })
    expect(socket.sent.some(message => message.command === 'CONFIG' && message.config?.enableLlmGovernment === true)).toBe(true)
  })

  test('slider changes are sent as runtime CONFIG updates', async () => {
    const socket = await openGovernment(baseMetrics())
    fireEvent.change(screen.getByLabelText('Wage tax'), { target: { value: '0.22' } })
    await act(async () => {
      await new Promise(resolve => setTimeout(resolve, 450))
    })
    const update = socket.sent.find(message => message.command === 'CONFIG' && message.config?.wageTax === 0.22)
    expect(update).toBeTruthy()
    // Only the changed lever travels, so the server's change log records one user action, not seventeen.
    expect(Object.keys(update.config)).toEqual(['wageTax'])
  })

  test('grocery benefit and weekly cap send canonical changes and follow confirmed policy, including reopening and zero', async () => {
    const metrics = baseMetrics()
    metrics.governmentPolicy = { ...metrics.governmentPolicy, food_credit_policy: 'off', food_credit_weekly_budget: 500 }
    const socket = await openGovernment(metrics)
    fireEvent.click(screen.getByText('Grocery benefit'))
    const status = screen.getByRole('combobox', { name: 'Grocery benefit' })
    const budget = screen.getByRole('textbox', { name: 'Grocery benefit weekly cap' })
    expect(status).toHaveValue('off')
    expect(budget).toHaveValue('500')
    expect(screen.getByText(/Each eligible household can receive up to \$2.50/)).toBeInTheDocument()
    expect(screen.getByText(/Closing the program stops new awards/)).toBeInTheDocument()
    vi.useFakeTimers()
    const flush = () => act(() => vi.advanceTimersByTime(400))
    const snapshot = (tick, policy, amount) => act(() => socket.emit({
      tick, metrics: { ...metrics, governmentPolicy: { ...metrics.governmentPolicy, food_credit_policy: policy, food_credit_weekly_budget: amount } },
    }))

    fireEvent.change(status, { target: { value: 'on' } })
    flush()
    expect(socket.sent.at(-1)).toEqual({ command: 'CONFIG', config: { food_credit_policy: 'on' } })
    expect(status).toHaveValue('off')
    snapshot(1276, 'on', 500)
    expect(status).toHaveValue('on')
    fireEvent.change(status, { target: { value: 'off' } })
    flush()
    expect(socket.sent.at(-1)).toEqual({ command: 'CONFIG', config: { food_credit_policy: 'off' } })
    snapshot(1277, 'off', 500)
    fireEvent.change(status, { target: { value: 'on' } })
    flush()
    expect(socket.sent.at(-1)).toEqual({ command: 'CONFIG', config: { food_credit_policy: 'on' } })

    snapshot(1278, 'on', 500)
    const beforeBudget = socket.sent.length
    fireEvent.focus(budget)
    fireEvent.change(budget, { target: { value: '3' } })
    act(() => vi.advanceTimersByTime(1000))
    expect(socket.sent).toHaveLength(beforeBudget)
    fireEvent.change(budget, { target: { value: '123.45' } })
    fireEvent.blur(budget)
    flush()
    expect(socket.sent.at(-1)).toEqual({ command: 'CONFIG', config: { food_credit_weekly_budget: 123.45 } })
    snapshot(1279, 'on', 123.45)
    expect(budget).toHaveValue('123.45')
    fireEvent.focus(budget)
    fireEvent.change(budget, { target: { value: '9' } })
    fireEvent.change(budget, { target: { value: '9.999' } })
    fireEvent.blur(budget)
    flush()
    expect(socket.sent.at(-1)).toEqual({ command: 'CONFIG', config: { food_credit_weekly_budget: 123.45 } })
    expect(budget).toHaveAttribute('aria-invalid', 'true')
    act(() => budget.focus())
    fireEvent.change(budget, { target: { value: '0' } })
    fireEvent.keyDown(budget, { key: 'Enter' })
    flush()
    expect(socket.sent.at(-1)).toEqual({ command: 'CONFIG', config: { food_credit_weekly_budget: 0 } })
    snapshot(1280, 'off', 0)
    expect(status).toHaveValue('off')
    expect(budget).toHaveValue('0')
    vi.useRealTimers()
  })

  test.each(['income_late', 'legacy'])('does not offer grocery benefit opening for %s', async timing => {
    render(<App />)
    await screen.findByText('Ready')
    fireEvent.change(screen.getByRole('combobox', { name: 'Payment timing' }), { target: { value: timing } })
    fireEvent.click(screen.getByRole('button', { name: 'Launch Simulation' }))
    const socket = MockWebSocket.instances[0]
    await act(async () => socket.emit({ type: 'SETUP_COMPLETE' }))
    await act(async () => socket.emit({ tick: 1, metrics: { ...baseMetrics(), governmentPolicy: { food_credit_policy: 'off', food_credit_weekly_budget: 0 } } }))
    fireEvent.click(screen.getByRole('button', { name: 'Government' }))
    fireEvent.click(screen.getByText('Grocery benefit'))
    const status = screen.getByRole('combobox', { name: 'Grocery benefit' })
    expect(screen.getByRole('option', { name: 'On' })).toBeDisabled()
    expect(screen.getByRole('textbox', { name: 'Grocery benefit weekly cap' })).toBeDisabled()
    fireEvent.change(status, { target: { value: 'on' } })
    expect(status).toHaveValue('off')
    expect(socket.sent.some(message => message.command === 'CONFIG')).toBe(false)
  })

  test('an untouched focused cap follows a server change and does not write the old value on blur', async () => {
    const metrics = baseMetrics()
    metrics.governmentPolicy = { ...metrics.governmentPolicy, food_credit_policy: 'on', food_credit_weekly_budget: 500 }
    const socket = await openGovernment(metrics)
    const budget = screen.getByRole('textbox', { name: 'Grocery benefit weekly cap' })
    act(() => budget.focus())
    expect(budget).toHaveValue('500')
    vi.useFakeTimers()
    act(() => socket.emit({ tick: 1276, metrics: { ...metrics, governmentPolicy: { ...metrics.governmentPolicy, food_credit_weekly_budget: 300 } } }))
    expect(budget).toHaveValue('300')
    fireEvent.blur(budget)
    act(() => vi.advanceTimersByTime(1000))
    expect(socket.sent.some(message => message.command === 'CONFIG')).toBe(false)
  })

  test('uses the server-confirmed payment sequence to gate opening', async () => {
    render(<App />)
    await screen.findByText('Ready')
    fireEvent.click(screen.getByRole('button', { name: 'Launch Simulation' }))
    const socket = MockWebSocket.instances[0]
    await act(async () => socket.emit({ type: 'SETUP_COMPLETE', config: { payment_sequence: 'legacy' } }))
    await act(async () => socket.emit({ tick: 1, metrics: { ...baseMetrics(), governmentPolicy: { food_credit_policy: 'off', food_credit_weekly_budget: 0 } } }))
    fireEvent.click(screen.getByRole('button', { name: 'Government' }))
    expect(screen.getByRole('option', { name: 'On' })).toBeDisabled()
    expect(screen.getByRole('textbox', { name: 'Grocery benefit weekly cap' })).toBeDisabled()
  })

  test('government screen renders lever groups, the timeline, and the effects pane from the fixture', () => {
    const { container } = renderScreen(Government, { config: DEFAULT_CONFIG, onConfigChange: () => {}, enumOptions: {}, isAiActive: false, llmGov: frame.metrics.llmGovernment, latestDecision: null, llmStatusLabel: 'Assistant off', llmActivityLevel: 0, friendlyModelName: 'phi-4-mini' })
    expect(container.querySelectorAll('.lv').length).toBe(18)
    expect(container.querySelector('.tlwrap')).toBeTruthy()
    expect(container.querySelector('.effpane')).toBeTruthy()
    expect(container.querySelectorAll('.ledger .lr').length).toBe(5)
  })

  test('effects pane header for GDP includes live point at current tick', () => {
    const policyChanges = [
      { tick: 25, policy: 'wage_tax_rate', value: 0.18, reason: 'User updated wage_tax_rate from 0.15 to 0.18' },
    ]
    const { container } = renderScreen(Government, {
      metrics: {
        ...frame.metrics,
        policyChanges,
      },
      tick: 60,
    })
    const gdpHeader = container.querySelector('.effh')
    const formattedLiveGdp = formatMillionsAdaptive(frame.metrics.gdp)
    expect(gdpHeader.textContent).toContain(formattedLiveGdp)
  })

  test('profit tax lever tile reflects refusal from latest decision', () => {
    const latestDecision = {
      rejected_changes: [{ lever: 'profit_tax_rate', value: 0.28, reason: 'window' }],
      appliedTick: 50,
      primary_goal: 'hold',
    }
    const { container } = renderScreen(Government, {
      latestDecision,
      isAiActive: true,
    })
    const tiles = Array.from(container.querySelectorAll('.lv'))
    const profitTaxTile = tiles.find((t) => t.textContent.includes('Profit tax'))
    expect(profitTaxTile).toBeTruthy()
    expect(profitTaxTile.textContent).toContain('refused')
  })

  test('no .chart .chart nesting remains so charts fill their panels', () => {
    const { container } = renderScreen(Government)
    expect(container.querySelectorAll('.chart .chart').length).toBe(0)
  })
})

