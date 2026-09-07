import { useState } from 'react'
import { appendCurrent } from '../telemetry.js'
import NeuralGovernment from '../NeuralGovernment.jsx'
import PageHeader from '../ui/PageHeader.jsx'
import Panel from '../ui/Panel.jsx'
import SectionTitle from '../ui/SectionTitle.jsx'
import KeyValue from '../ui/KeyValue.jsx'
import Ledger from '../charts/Ledger.jsx'
import {
  formatInteger,
  formatMillionsAdaptive,
} from '../format.js'
import {
  DECISION_INTERVAL,
  LEVER_DEFAULTS,
  LEVER_GROUPS,
  classifyActor,
  countActiveInterventions,
  fiscalModeLabel,
  formatLeverValue,
  goalHeadline,
  isLeverActive,
  latestChangeByLever,
  leverLabel,
  parsePreviousValue,
  splitPolicyChanges,
} from '../governmentInsights.js'
import Timeline from './government/Timeline.jsx'
import EffectsPanel from './government/EffectsPanel.jsx'
import LeverTile from './government/LeverTile.jsx'

const LEVER_COUNT = Object.keys(LEVER_DEFAULTS).length

const tickText = (value) =>
  value === undefined || value === null || value === '' || Number.isNaN(Number(value))
    ? '—'
    : formatInteger(value)

const plural = (n, word) => `${n} ${word}${n === 1 ? '' : 's'}`

export default function Government({
  metrics = {},
  tick = 0,
  histories: propHistories,
  config = {},
  onConfigChange = () => {},
  enumOptions = {},
  isAiActive = false,
  llmGov,
  latestDecision,
  llmStatusLabel = 'Assistant off',
  llmActivityLevel = 0,
  friendlyModelName = 'phi-4-mini',
}) {
  const policy = metrics.governmentPolicy || {}
  const status = llmGov || { status: 'disabled' }
  const decision = isAiActive ? latestDecision : null
  const activeCount = countActiveInterventions(policy)
  const { current: currentChanges } = splitPolicyChanges(
    metrics.policyChanges,
    tick
  )
  const latestByLever = latestChangeByLever(metrics.policyChanges, tick)
  const histories = {
    gdp: appendCurrent(metrics.gdpHistory, tick, metrics.gdp),
    unemployment: appendCurrent(metrics.unemploymentHistory, tick, metrics.unemployment),
    happiness: appendCurrent(metrics.happinessHistory, tick, metrics.happiness),
    fiscal: appendCurrent(metrics.govProfitHistory, tick, metrics.govProfit),
    ...(propHistories || {}),
  }

  const netFlow = Number(metrics.govProfit || 0)
  const govRevenue = Number(metrics.govRevenue || 0)
  const govTransfers = Number(metrics.govTransfers || 0)
  const govInvestments = Number(metrics.govInvestments || 0)
  const bondPurchases = Number(metrics.bondPurchases || 0)
  const activeLoans = Number(metrics.activeLoans || 0)
  const govOwnedFirms = Number(metrics.govOwnedFirms || 0)
  const govDebt = Number(metrics.govDebt || 0)

  const acceptedCount = Object.keys(
    decision?.accepted_llm_changes || decision?.decisions || {}
  ).length
  const rejectedList = Array.isArray(decision?.rejected_changes)
    ? decision.rejected_changes
    : []
  const appliedTick =
    decision?.appliedTick ?? status.appliedTick ?? decision?.snapshotTick ?? tick

  // Build unified changes: accepted current changes + rejected changes at appliedTick
  const refusedChanges = rejectedList.map((item, idx) => ({
    tick: appliedTick,
    policy: item.lever || item.group || 'bailout_budget',
    key: item.lever || item.group || 'bailout_budget',
    value: item.value,
    reason: item.reason,
    ok: false,
    actor: 'ai',
    id: `refused-${idx}`,
  }))

  const acceptedChanges = currentChanges.map((c) => ({
    ...c,
    ok: true,
    key: c.policy || c.type || c.key || c.lever || 'policy',
    actor: classifyActor(c.reason),
    previous: parsePreviousValue(c.reason),
  }))

  const allChanges = [...refusedChanges, ...acceptedChanges].sort(
    (a, b) => (b.tick || 0) - (a.tick || 0)
  )

  const changeIdentity = (c) => (c ? `${c.tick}:${c.key || c.policy || 'policy'}` : null)
  const [selectedIdentity, setSelectedIdentity] = useState(null)
  const [openLeverKey, setOpenLeverKey] = useState(null)

  const newestAccepted = allChanges.find((c) => c.ok) || null
  const selectedChange =
    (selectedIdentity
      ? allChanges.find((c) => changeIdentity(c) === selectedIdentity)
      : null) || newestAccepted

  const handleSelectChange = (idOrIndex) => {
    if (typeof idOrIndex === 'number') {
      const c = allChanges[idOrIndex]
      setSelectedIdentity(changeIdentity(c))
    } else {
      setSelectedIdentity(idOrIndex)
    }
  }

  const newest = currentChanges[0]
  const newestActor = newest
    ? classifyActor(newest.reason) === 'you'
      ? 'you'
      : classifyActor(newest.reason) === 'ai'
        ? 'AI'
        : 'auto'
    : null

  const modelMode = fiscalModeLabel(decision?.fiscal_mode || decision?.llm_fiscal_mode)
  const providerTrouble =
    status.status === 'error' || status.status === 'provider_unavailable'

  const headline = isAiActive
    ? decision
      ? goalHeadline(decision.primary_goal)
      : 'Waiting for the first decision cycle'
    : `${activeCount === 0 ? 'No interventions' : plural(activeCount, 'intervention')} active, treasury in ${netFlow < 0 ? 'deficit' : 'surplus'}`

  const subline = isAiActive
    ? decision
      ? `The model observed tick ${tickText(decision.snapshotTick ?? status.snapshotTick)} and its changes were applied at tick ${tickText(decision.appliedTick ?? status.appliedTick)}. It moved ${plural(acceptedCount, 'instrument')} and ${plural(rejectedList.length, 'request')} ${rejectedList.length === 1 ? 'was' : 'were'} refused by the fiscal guard.`
      : `${llmStatusLabel}. The model reads the same telemetry shown here and proposes lever changes on its cadence; every proposal is checked by the fiscal guard first.`
    : newest
      ? `Last change: ${leverLabel(newest.policy || newest.type || 'policy')} → ${formatLeverValue(newest.policy, newest.value)} at tick ${tickText(newest.tick)} by ${newestActor}.`
      : 'No policy changes yet this run. Every lever below is yours to move.'

  const ledgerRows = [
    { label: 'Revenue', value: govRevenue, sign: '+', tone: 'acc' },
    { label: 'Transfers', value: govTransfers, sign: '−', tone: 's1' },
    { label: 'Investments', value: govInvestments, sign: '−', tone: 's1' },
    { label: 'Bond purchases', value: bondPurchases, sign: '−', tone: 's1' },
  ]
  const ledgerNet = { label: 'Net flow', value: netFlow }

  const decisionsCount =
    (status.acceptedChangeCount ?? acceptedCount) +
    (status.rejectedChangeCount ?? rejectedList.length)
  const acceptedRefusedText = `${status.acceptedChangeCount ?? acceptedCount} · ${status.rejectedChangeCount ?? rejectedList.length}`
  const parsedOkText = decision
    ? decision.parse_ok !== false
      ? 'Yes'
      : 'No'
    : '—'
  const latencyText = decision?.elapsed_ms
    ? (Number(decision.elapsed_ms) / 1000).toFixed(1)
    : '—'
  const nextReviewTick = decision?.appliedTick
    ? decision.appliedTick + DECISION_INTERVAL
    : tick > 0
      ? Math.ceil(tick / DECISION_INTERVAL) * DECISION_INTERVAL
      : DECISION_INTERVAL

  const selectedKey = selectedChange?.key || selectedChange?.policy
  const hitColor = selectedChange
    ? selectedChange.ok
      ? selectedChange.actor === 'ai'
        ? 'var(--ai)'
        : selectedChange.actor === 'you'
          ? 'var(--acc)'
          : 'var(--ink4)'
      : 'var(--crit)'
    : 'var(--acc)'

  return (
    <div>
      <PageHeader
        eyebrow="Government"
        title="Government Console"
        summary="What changed, who changed it, and how the economy moved afterwards. Levers sit around the changes, not in front of them."
      />

      <Panel
        hot
        style={{
          display: 'grid',
          gridTemplateColumns: 'minmax(0, 1.25fr) 180px minmax(0, 0.75fr)',
          gap: 16,
          padding: '12px 16px',
        }}
      >
        <div>
          <div className="chips">
            {isAiActive ? (
              <>
                <span className="pill ai">
                  <i />
                  AI government · {friendlyModelName}
                </span>
                {modelMode && (
                  <span className="pill good">
                    <i />
                    Fiscal mode {modelMode}
                  </span>
                )}
                {decision && (
                  <span className="pill acc">
                    <i />
                    Goal · {goalHeadline(decision.primary_goal)}
                  </span>
                )}
              </>
            ) : (
              <>
                <span className="pill acc">
                  <i />
                  Manual administration
                </span>
                <span className="pill muted">
                  <i />
                  AI government off
                </span>
              </>
            )}
          </div>
          <div
            style={{
              fontSize: 24,
              fontWeight: 600,
              color: 'var(--ink)',
              letterSpacing: '-.01em',
              marginTop: 6,
              lineHeight: 1.1,
            }}
          >
            {headline}
          </div>
          <p
            style={{
              margin: '4px 0 0',
              fontSize: 12,
              color: 'var(--ink3)',
              maxWidth: '60ch',
            }}
          >
            {subline}
          </p>
          {providerTrouble && status.lastError && (
            <p
              style={{
                margin: '4px 0 0',
                fontSize: 11,
                color: 'var(--crit)',
              }}
            >
              {String(status.lastError)}
            </p>
          )}
          <div className="facts" style={{ marginTop: 8 }}>
            <div className="fact">
              <div className="k">Observed → applied</div>
              <div className="v">
                {isAiActive
                  ? `${tickText(decision?.snapshotTick ?? status.snapshotTick)} → ${tickText(decision?.appliedTick ?? status.appliedTick)}`
                  : '—'}
              </div>
            </div>
            <div className="fact">
              <div className="k">Decision latency</div>
              <div className="v">
                {latencyText}
                <small>s</small>
              </div>
            </div>
            <div className="fact">
              <div className="k">This cycle</div>
              <div className="v">
                {decision ? `${acceptedCount} · ${rejectedList.length}` : '—'}
                <small>accepted · refused</small>
              </div>
            </div>
            <div className="fact">
              <div className="k">Active interventions</div>
              <div className="v">
                {activeCount}
                <small>of {LEVER_COUNT}</small>
              </div>
            </div>
          </div>
        </div>

        <div className="canvas-slot" style={{ minHeight: 120 }}>
          <NeuralGovernment
            active
            activityLevel={llmActivityLevel}
            mode={isAiActive ? status.status || 'ready' : 'disabled'}
          />
        </div>

        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'flex-end',
          }}
        >
          <button
            type="button"
            className={`toggle${config.enableLlmGovernment ? ' on' : ''}`}
            onClick={() =>
              onConfigChange('enableLlmGovernment', !config.enableLlmGovernment)
            }
          >
            <div>
              <div className="tl">AI government</div>
              <div className="td">
                {isAiActive
                  ? 'Model proposes, the fiscal guard validates, levers apply next tick.'
                  : 'Off. Your controls below are the only policy input.'}
              </div>
            </div>
            <span className="sw" />
          </button>
        </div>
      </Panel>

      <div className="g12" style={{ marginTop: 10 }}>
        <Panel
          className="s8"
          style={{
            display: 'grid',
            gridTemplateColumns: 'minmax(0, 5.4fr) minmax(0, 6.6fr)',
            gap: 14,
          }}
        >
          <Timeline
            changes={allChanges}
            selected={changeIdentity(selectedChange)}
            onSelect={handleSelectChange}
            histories={histories}
            latestDecision={decision}
            tick={tick}
          />
          <EffectsPanel
            change={selectedChange}
            histories={histories}
            decision={decision}
            latestDecision={decision}
            llmGov={status}
            tick={tick}
          />
        </Panel>

        <Panel className="s4">
          <SectionTitle
            title="Policy stance"
            meta={`${activeCount} of 17 off default`}
          />
          {LEVER_GROUPS.map((group) => {
            const levers = group.levers.flatMap((lever) =>
              lever.pair ? [lever, lever.pair] : [lever]
            )
            return (
              <div key={group.id}>
                <div className="lgroup">
                  {group.label}
                  <i />
                </div>
                <div className="lv2">
                  {levers.map((lever) => {
                    const live = policy[lever.key] ?? config[lever.configKey]
                    const isDefault = !isLeverActive(lever.key, live)
                    const lastChange = latestByLever.get(lever.key)
                    const rejectedEntry = rejectedList.find(
                      (item) => item.lever === lever.key || item.group === lever.key
                    )
                    const refusal = rejectedEntry
                      ? { value: rejectedEntry.value, tick: appliedTick }
                      : null
                    const hit = selectedKey === lever.key

                    return (
                      <LeverTile
                        key={lever.key}
                        lever={lever}
                        live={live}
                        isDefault={isDefault}
                        lastChange={lastChange}
                        refusal={refusal}
                        hit={hit}
                        hitColor={hitColor}
                        isOpen={openLeverKey === lever.key}
                        onEdit={(k) =>
                          setOpenLeverKey((prev) => (prev === k ? null : k))
                        }
                        config={config}
                        onConfigChange={onConfigChange}
                        enumOptions={enumOptions}
                      />
                    )
                  })}
                </div>
              </div>
            )
          })}
          <div
            className="muted"
            style={{ fontSize: '10.5px', marginTop: 8 }}
          >
            Click a lever to edit it. The highlighted one is what the selected
            change moved.
          </div>
        </Panel>
      </div>

      <div className="g12" style={{ marginTop: 10 }}>
        <Panel className="s4">
          <SectionTitle
            title="Fiscal flow this tick"
            meta="per tick"
          />
          <Ledger
            rows={ledgerRows}
            net={ledgerNet}
            format={formatMillionsAdaptive}
          />
        </Panel>

        <Panel className="s5">
          <SectionTitle
            title="Assistant"
            meta={
              isAiActive
                ? `${friendlyModelName} · ${status.provider || 'local'} · reviews every ${DECISION_INTERVAL} ticks`
                : 'AI government is off'
            }
          />
          {isAiActive ? (
            <>
              <div className="facts" style={{ marginTop: 4 }}>
                <div className="fact">
                  <div className="k">Decisions</div>
                  <div className="v">{decisionsCount}</div>
                </div>
                <div className="fact">
                  <div className="k">Accepted · refused</div>
                  <div className="v">{acceptedRefusedText}</div>
                </div>
                <div className="fact">
                  <div className="k">Parsed OK</div>
                  <div className="v">{parsedOkText}</div>
                </div>
                <div className="fact">
                  <div className="k">Avg latency</div>
                  <div className="v">
                    {latencyText}
                    <small>s</small>
                  </div>
                </div>
              </div>
              <KeyValue label="Next review" value={`t${nextReviewTick}`} />
              <KeyValue label="Instrument window" value="2 per cycle" />
              <KeyValue
                label="Last error"
                value={status.lastError || 'none'}
                tone={status.lastError ? 'crit' : 'good'}
              />
            </>
          ) : (
            <>
              <p
                className="muted"
                style={{ fontSize: '11.5px', margin: '8px 0' }}
              >
                Turn it on and a model will propose bounded lever changes checked
                by the fiscal guard.
              </p>
              <div style={{ padding: '4px 0 8px' }}>
                <button
                  type="button"
                  className="btn primary"
                  onClick={() => onConfigChange('enableLlmGovernment', true)}
                >
                  Enable AI government
                </button>
              </div>
              <KeyValue label="Next review" value="—" />
              <KeyValue label="Instrument window" value="2 per cycle" />
              <KeyValue label="Last error" value="none" tone="good" />
            </>
          )}
        </Panel>

        <Panel className="s3">
          <SectionTitle
            title="State capacity"
            meta="what the treasury holds"
          />
          <KeyValue
            label="Government-owned firms"
            value={formatInteger(govOwnedFirms)}
          />
          <KeyValue
            label="Government-backed loans"
            value={formatInteger(activeLoans)}
          />
          <KeyValue
            label="Bond purchases"
            value={formatMillionsAdaptive(bondPurchases)}
          />
          <KeyValue
            label="Treasury debt"
            value={
              govDebt === 0
                ? '$0 · none recorded'
                : formatMillionsAdaptive(govDebt)
            }
            tone={govDebt === 0 ? 'good' : 'crit'}
          />
          <KeyValue
            label="Levers at default"
            value={`${LEVER_COUNT - activeCount} / ${LEVER_COUNT}`}
          />
        </Panel>
      </div>
    </div>
  )
}
