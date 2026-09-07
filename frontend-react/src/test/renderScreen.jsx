import { render } from '@testing-library/react'
import frame from './fixtures/frame.json'

// Copied verbatim from the `config` useState initialiser in App.jsx.
export const DEFAULT_CONFIG = {
  wageTax: 0.05,
  profitTax: 0.30,
  inflationRate: 0.02,
  birthRate: 0.01,
  minimumWage: 20.0,
  unemploymentBenefitRate: 0.0,
  universalBasicIncome: 0.0,
  wealthTaxThreshold: 50000,
  wealthTaxRate: 0.0,
  enableLlmGovernment: false,
  benefitLevel: 'neutral',
  publicWorks: false,
  minimumWagePolicy: 'neutral',
  sectorSubsidyTarget: 'none',
  sectorSubsidyLevel: 0,
  infrastructureSpending: 'none',
  technologySpending: 'none',
  socialSpending: 'medium',
  priceStabilizationTarget: 'none',
  priceStabilizationLevel: 'off',
  rentStabilizationLevel: 'off',
  bailoutPolicy: 'off',
  bailoutTarget: 'none',
  bailoutBudget: 0
}

// Copied verbatim from the `setupConfig` useState initialiser in App.jsx.
export const DEFAULT_SETUP = {
  num_households: 1000,
  num_firms: 5,
  seed: 42,
  wage_tax: 0.15,
  profit_tax: 0.20,
  enable_llm_government: false,
  disable_stabilizers: false,
  disabled_agents: []
}

export { frame }

const noop = () => {}

const handlers = {
  onConfigChange: noop,
  onSetupChange: noop,
  onSelectSubject: noop,
  onSelectFirm: noop,
  onSelectLog: noop,
  onLaunch: noop,
  onReset: noop,
  onToggleRun: noop,
  onStabilizers: noop
}

export function renderScreen(Screen, overrides = {}) {
  const defaultProps = {
    metrics: frame.metrics,
    firmStats: frame.firm_stats,
    logs: frame.logs,
    tick: frame.tick,
    config: DEFAULT_CONFIG,
    setupConfig: DEFAULT_SETUP,
    selection: { subjectIndex: 0, firmIndex: 0, logIndex: 0 },
    handlers
  }

  return render(<Screen {...defaultProps} {...overrides} />)
}
