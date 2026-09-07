import PageHeader from '../ui/PageHeader.jsx'
import Panel from '../ui/Panel.jsx'
import SectionTitle from '../ui/SectionTitle.jsx'
import Pill from '../ui/Pill.jsx'
import Chip from '../ui/Chip.jsx'
import KeyValue from '../ui/KeyValue.jsx'
import { Slider, NumberInput, Select, Toggle } from '../ui/Inputs.jsx'
import { formatInteger, formatPercent, formatCurrency } from '../format.js'
import { DECISION_INTERVAL } from '../governmentInsights.js'

const SECTORS = [
  { name: 'Food', tone: 's1' },
  { name: 'Housing', tone: 's2' },
  { name: 'Services', tone: 's3' },
  { name: 'Healthcare', tone: 's4' },
]

export default function Config({
  setupConfig = {},
  onSetupChange,
  config = {},
  onConfigChange,
  isInitialized = false,
  isInitializing = false,
  wsConnected = false,
  wsEndpoint = '',
  sessionId = '',
  onLaunch,
  onResetDefaults,
  onApply,
  stabilizerAgentOptions = [],
  enumOptions = {},
}) {
  const numHouseholds = setupConfig.num_households ?? 1000
  const numFirms = setupConfig.num_firms ?? 5
  const seed = setupConfig.seed ?? 42
  const wageTax = isInitialized ? (config.wageTax ?? 0.15) : (setupConfig.wage_tax ?? 0.15)
  const profitTax = isInitialized ? (config.profitTax ?? 0.20) : (setupConfig.profit_tax ?? 0.20)
  const minWage = config.minimumWage ?? 20
  const benefitLevel = config.benefitLevel || 'neutral'
  const benefitOptions = enumOptions?.benefit || [{ value: 'neutral', label: 'Neutral' }]
  const isAiGov = isInitialized
    ? Boolean(config.enableLlmGovernment)
    : Boolean(setupConfig.enable_llm_government)
  const disableStabilizers = Boolean(setupConfig.disable_stabilizers)
  const disabledAgents = setupConfig.disabled_agents || []
  const shortSession = sessionId ? sessionId.slice(0, 8) : 'pending'
  const profileValid = (setupConfig.num_households ?? 0) >= 3

  const action = isInitialized ? (
    <div style={{ display: 'flex', gap: 8 }}>
      <button
        type="button"
        className="btn big"
        onClick={onResetDefaults}
      >
        Reset defaults
      </button>
      <button
        type="button"
        className="btn primary big"
        onClick={onApply}
      >
        Apply changes
      </button>
    </div>
  ) : (
    <button
      type="button"
      className="btn primary big"
      onClick={onLaunch}
      disabled={isInitializing || !wsConnected}
    >
      Launch Simulation
    </button>
  )

  return (
    <div>
      <h2 className="sr-only">Simulation Controls</h2>
      <PageHeader
        eyebrow="Preflight"
        title="Launch a run"
        summary="Set the population, seed and opening policy. Everything here is sent once with SETUP."
        action={action}
      />

      {!wsConnected && (
        <div style={{ marginBottom: 10 }}>
          <Pill tone="crit">Backend telemetry offline. Target: {wsEndpoint}</Pill>
        </div>
      )}

      <div className="g12">
        {/* Run profile */}
        <Panel className="s4">
          <SectionTitle title="Run profile" meta="seeded, reproducible" />
          <Slider
            label="Population"
            value={numHouseholds}
            min={100}
            max={10000}
            step={100}
            format={formatInteger}
            onChange={(v) => onSetupChange?.('num_households', Math.round(v))}
            description="Household agents created at launch. 100 to 10,000."
          />
          <Slider
            label="Firms per sector"
            value={numFirms}
            min={1}
            max={20}
            step={1}
            format={formatInteger}
            onChange={(v) => onSetupChange?.('num_firms', Math.round(v))}
            description="Initial firms in each of the four sectors."
          />
          <NumberInput
            label="Seed"
            value={seed}
            min={0}
            max={2147483647}
            step={1}
            onChange={(v) => onSetupChange?.('seed', v)}
            description="Same seed, same run. Change it to get a different economy."
          />
        </Panel>

        {/* Opening policy */}
        <Panel className="s4">
          <SectionTitle title="Opening policy" meta="adjustable while running" />
          <Slider
            label="Wage tax"
            value={wageTax}
            min={0}
            max={0.5}
            step={0.01}
            format={(v) => formatPercent(v * 100, 0)}
            onChange={(v) => {
              if (isInitialized) {
                onConfigChange?.('wageTax', v)
              } else {
                onSetupChange?.('wage_tax', v)
              }
            }}
            description="Share of household wages collected each tick."
          />
          <Slider
            label="Profit tax"
            value={profitTax}
            min={0}
            max={0.6}
            step={0.01}
            format={(v) => formatPercent(v * 100, 0)}
            onChange={(v) => {
              if (isInitialized) {
                onConfigChange?.('profitTax', v)
              } else {
                onSetupChange?.('profit_tax', v)
              }
            }}
            description="Share of firm profit collected after sales."
          />
          <Slider
            label="Minimum wage"
            value={minWage}
            min={0}
            max={100}
            step={1}
            format={(v) => formatCurrency(v, 0)}
            onChange={(v) => onConfigChange?.('minimumWage', v)}
            description="Floor on posted wage offers."
          />
          <Select
            label="Benefit level"
            value={benefitLevel}
            options={benefitOptions}
            onChange={(v) => onConfigChange?.('benefitLevel', v)}
            description="Transfers income to unemployed households."
          />
        </Panel>

        {/* Policy assistant + Preflight */}
        <div className="s4 col">
          <Panel>
            <SectionTitle title="Policy assistant" meta="optional" />
            <Toggle
              label="AI government"
              description="Model proposes bounded lever changes off the tick path. Manual controls stay live."
              checked={isAiGov}
              onChange={(checked) => {
                if (isInitialized) {
                  onConfigChange?.('enableLlmGovernment', checked)
                } else {
                  onSetupChange?.('enable_llm_government', checked)
                }
              }}
            />
            <div style={{ height: 8 }} />
            <Toggle
              label="Disable automatic stabilizers"
              description="Isolate direct policy effects. Off by default."
              checked={disableStabilizers}
              onChange={(checked) => onSetupChange?.('disable_stabilizers', checked)}
            />
            {disableStabilizers && (
              <div style={{ marginTop: 8, display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {stabilizerAgentOptions.map((opt) => {
                  const active = disabledAgents.includes(opt.key)
                  return (
                    <Chip
                      key={opt.key}
                      on={active}
                      onClick={() => {
                        const next = active
                          ? disabledAgents.filter((k) => k !== opt.key)
                          : [...disabledAgents, opt.key]
                        onSetupChange?.('disabled_agents', next)
                      }}
                    >
                      {opt.label}
                    </Chip>
                  )
                })}
              </div>
            )}
          </Panel>

          <Panel style={{ flex: 1 }}>
            <SectionTitle title="Preflight" meta="ready" />
            <div className="check">
              <i>{wsConnected ? '✓' : '—'}</i>
              <span className="ck">Backend connected</span>
              <span className="cd">{wsConnected ? 'connected' : 'offline'}</span>
            </div>
            <div className="check">
              <i>{sessionId ? '✓' : '—'}</i>
              <span className="ck">Session issued</span>
              <span className="cd">{shortSession}</span>
            </div>
            <div className="check">
              <i>{profileValid ? '✓' : '—'}</i>
              <span className="ck">Profile valid</span>
              <span className="cd">≥ 3 households</span>
            </div>
            <div className="check">
              <span className="ck">Warehouse</span>
              <span className="cd">per server config</span>
            </div>
          </Panel>
        </div>

        {/* What this run creates */}
        <Panel hot className="s12">
          <SectionTitle title="What this run creates" meta="from the profile above" />
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 10, marginTop: 4 }}>
            <div className="kpi">
              <span className="n" style={{ fontSize: 34 }}>{formatInteger(numHouseholds)}</span>
              <span className="k">households</span>
            </div>
            <div className="kpi">
              <span className="n" style={{ fontSize: 34 }}>{formatInteger(numFirms * 4)}</span>
              <span className="k">firms</span>
            </div>
            <div className="kpi">
              <span className="n" style={{ fontSize: 34 }}>4</span>
              <span className="k">sectors</span>
            </div>
            <div className="kpi">
              <span className="n" style={{ fontSize: 34 }}>{seed}</span>
              <span className="k">seed</span>
            </div>
            <div className="kpi">
              <span className="n" style={{ fontSize: 34 }}>{isAiGov ? 'assistant' : 'manual'}</span>
              <span className="k">policy</span>
            </div>
          </div>
          <div className="muted" style={{ marginTop: 10, fontSize: 12 }}>
            Weekly ticks. Households work, buy food, rent or buy housing, use services and healthcare. Firms hire, price and expand. The treasury taxes and transfers. Results describe this synthetic economy only.
          </div>
        </Panel>

        {/* Run schedule */}
        <Panel className="s4">
          <SectionTitle title="Run schedule" meta="what happens when" />
          <KeyValue label="One tick" value="one week" />
          <KeyValue label="Aggregate metrics" value="every 5 ticks" />
          <KeyValue label="History samples" value="every 25 ticks" />
          <KeyValue label="Assistant review" value={`every ${DECISION_INTERVAL} ticks`} />
          <KeyValue label="Warehouse flush" value="every 50 ticks" />
        </Panel>

        {/* Sectors at launch */}
        <Panel className="s5">
          <SectionTitle title="Sectors at launch" meta="one baseline firm each, plus new entrants" />
          <div className="g4">
            {SECTORS.map((sc, i) => (
              <div
                key={sc.name}
                style={{
                  padding: `4px 0 4px ${i ? '12px' : '0'}`,
                  borderLeft: i ? '1px solid var(--line)' : '0',
                }}
              >
                <div style={{ fontWeight: 600, color: 'var(--ink)' }}>
                  <i
                    style={{
                      display: 'inline-block',
                      width: 8,
                      height: 8,
                      borderRadius: 2,
                      background: `var(--${sc.tone})`,
                      marginRight: 6,
                    }}
                  />
                  {sc.name}
                </div>
                <div className="kpi" style={{ marginTop: 6 }}>
                  <span className="n">{numFirms}</span>
                  <span className="k">firms</span>
                </div>
                <div className="muted" style={{ fontSize: 11, marginTop: 4 }}>
                  Baseline {sc.name}
                </div>
              </div>
            ))}
          </div>
        </Panel>

        {/* Assistant setup */}
        <Panel className="s3">
          <SectionTitle title="Assistant setup" meta="defaults, see server config" />
          <KeyValue label="Review cadence" value={`every ${DECISION_INTERVAL} ticks`} />
        </Panel>
      </div>
    </div>
  )
}
