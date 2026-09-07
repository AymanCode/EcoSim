import { useMemo } from 'react'
import PageHeader from '../ui/PageHeader.jsx'
import Panel from '../ui/Panel.jsx'
import SectionTitle from '../ui/SectionTitle.jsx'
import StatTile from '../ui/StatTile.jsx'
import Pill from '../ui/Pill.jsx'
import Delta from '../ui/Delta.jsx'
import TimeSeries from '../charts/TimeSeries.jsx'
import Meter from '../charts/Meter.jsx'
import CompositionBar from '../charts/CompositionBar.jsx'
import { classifyActor } from '../governmentInsights.js'
import {
  appendCurrent,
  backN,
  deltaVs,
  employment,
  latest,
  stress,
} from '../telemetry.js'
import {
  dec1,
  dec3,
  formatInteger,
  formatMillionsAdaptive,
  formatPolicyMessage,
  ms,
  pct1,
  score,
  signedMillions,
  usd2,
} from '../format.js'

const SECTORS = [
  { name: 'Food', key: 'food', tone: 's1' },
  { name: 'Housing', key: 'housing', tone: 's2' },
  { name: 'Services', key: 'services', tone: 's3' },
  { name: 'Healthcare', key: 'healthcare', tone: 's4' },
]

export default function Command({
  metrics = {},
  firmStats = {},
  tick = 0,
  policyChanges = metrics.policyChanges || [],
  llmGov = metrics.llmGovernment || {},
  latestDecision = metrics.latestGovernmentDecision || llmGov?.latestDecision || null,
  llmStatusLabel = llmGov?.enabled ? 'Policy assistant ready' : 'Inactive',
  histories = {},
}) {
  const stressVal = stress(metrics)
  const empVal = employment(metrics)
  const empHistory = useMemo(
    () => (metrics.unemploymentHistory || []).map((d) => ({ tick: d.tick, value: 100 - Number(d.value) })),
    [metrics.unemploymentHistory]
  )

  const tickHist = histories || {}
  const stressHistory = tickHist.stress || [{ tick, value: stressVal }]
  const tickMsHistory = tickHist.tickMs || []

  const policyMarkers = useMemo(() => {
    return (policyChanges || []).map((c) => ({
      tick: c.tick,
      label: formatPolicyMessage(c),
      ai: classifyActor(c.reason) === 'ai',
      ok: true,
    }))
  }, [policyChanges])

  // Ticker strip items
  const firmsVal = firmStats?.total_firms ?? latest(metrics.firmCountHistory, 0)
  const tickerItems = [
    { label: 'GDP', value: formatMillionsAdaptive(metrics.gdp), diff: deltaVs(metrics.gdp, metrics.gdpHistory, 1).diff },
    { label: 'Unemployment', value: pct1(metrics.unemployment || 0), diff: deltaVs(metrics.unemployment || 0, metrics.unemploymentHistory, 1).diff },
    { label: 'Wage', value: usd2(metrics.avgWage || 0), diff: deltaVs(metrics.avgWage || 0, metrics.wageHistory, 1).diff },
    { label: 'Happiness', value: dec1(metrics.happiness || 0), diff: deltaVs(metrics.happiness || 0, metrics.happinessHistory, 1).diff },
    { label: 'Fiscal', value: signedMillions(metrics.govProfit || 0), diff: deltaVs(metrics.govProfit || 0, metrics.govProfitHistory, 1).diff },
    { label: 'Gini', value: dec3(metrics.giniCoefficient || 0), diff: deltaVs(metrics.giniCoefficient || 0, metrics.giniHistory, 1).diff },
    { label: 'Food', value: usd2(latest(metrics.priceHistory?.food, 0)), diff: deltaVs(latest(metrics.priceHistory?.food, 0), metrics.priceHistory?.food, 1).diff },
    { label: 'Housing', value: usd2(latest(metrics.priceHistory?.housing, 0)), diff: deltaVs(latest(metrics.priceHistory?.housing, 0), metrics.priceHistory?.housing, 1).diff },
    { label: 'Firms', value: formatInteger(firmsVal), diff: deltaVs(firmsVal, metrics.firmCountHistory, 1).diff },
    { label: 'Tick time', value: ms(metrics.tickComputeMs || 0), diff: deltaVs(metrics.tickComputeMs || 0, tickMsHistory, 1).diff },
  ]

  // Wealth distribution
  const bottom50 = Number(metrics.bottom50Share || 0)
  const top10 = Number(metrics.top10Share || 0)
  const middle = Math.max(0, 100 - top10 - bottom50)
  const wealthSegments = [
    { label: 'Bottom 50%', value: bottom50, tone: 'ink4' },
    { label: 'Middle 40%', value: middle, tone: 's1' },
    { label: 'Top 10%', value: top10, tone: 'acc' },
  ]

  const giniVal = Number(metrics.giniCoefficient || 0)
  const giniDelta = deltaVs(giniVal, metrics.giniHistory, 1)
  const giniTone = giniVal > 0.6 ? 'crit' : giniVal > 0.45 ? 'warn' : 'good'
  const giniLabel = giniVal > 0.6 ? 'High inequality' : giniVal > 0.45 ? 'Elevated inequality' : 'Moderate inequality'

  // Policy assistant before -> now
  const latestDecisionTick = Number(
    latestDecision?.appliedTick ??
    latestDecision?.tick ??
    latestDecision?.snapshotTick ??
    llmGov?.appliedTick ??
    0
  )
  const unempBefore = backN(metrics.unemploymentHistory, 1)
  const unempNow = metrics.unemployment || 0
  const profitBefore = backN(metrics.govProfitHistory, 1)
  const profitNow = metrics.govProfit || 0

  return (
    <div>
      <PageHeader
        eyebrow="Command"
        title="Economic Command Deck"
        summary={`GDP ${formatMillionsAdaptive(metrics.gdp)} this tick, unemployment ${pct1(metrics.unemployment || 0)}, fiscal balance ${signedMillions(metrics.govProfit || 0)}.`}
        action={
          <span className="legend">
            <span>
              <i style={{ background: 'var(--acc)' }} />
              Primary series
            </span>
            <span>
              <i style={{ background: 'var(--ai)', width: 2, height: 10 }} />
              Policy change
            </span>
          </span>
        }
      />

      <div className="ticker">
        <span className="lbl">LIVE</span>
        <div className="track">
          {[...tickerItems, ...tickerItems].map((item, idx) => (
            <span key={`${item.label}-${idx}`}>
              {item.label}
              <b>{item.value}</b>{' '}
              <span className={item.diff >= 0 ? 'up' : 'dn'}>
                {item.diff >= 0 ? '▲' : '▼'}
              </span>
            </span>
          ))}
        </div>
      </div>

      <div className="g12">
        <div className="s12" style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 10 }}>
          <StatTile
            label="GDP output"
            value={metrics.gdp || 0}
            format={formatMillionsAdaptive}
            history={metrics.gdpHistory}
            tick={tick}
            caption="per tick"
          />
          <StatTile
            label="Unemployment"
            value={metrics.unemployment || 0}
            format={pct1}
            history={metrics.unemploymentHistory}
            tick={tick}
            tone={(metrics.unemployment || 0) > 35 ? 'crit' : (metrics.unemployment || 0) > 25 ? 'warn' : undefined}
            upBad
            unit="pts"
            caption="share of labour force"
          />
          <StatTile
            label="Employment"
            value={empVal}
            format={pct1}
            history={empHistory}
            tick={tick}
            unit="pts"
            caption="share of labour force"
          />
          <StatTile
            label="Average wage"
            value={metrics.avgWage || 0}
            format={usd2}
            history={metrics.wageHistory}
            tick={tick}
            caption="worker mean"
          />
          <StatTile
            label="Macro stress"
            value={stressVal}
            format={score}
            history={stressHistory}
            tick={tick}
            tone={stressVal > 70 ? 'crit' : stressVal > 45 ? 'warn' : undefined}
            upBad
            unit="pts"
            caption="composite /100"
          />
          <StatTile
            label="Fiscal balance"
            value={metrics.govProfit || 0}
            format={signedMillions}
            history={metrics.govProfitHistory}
            tick={tick}
            tone={(metrics.govProfit || 0) < 0 ? 'crit' : undefined}
            caption="net flow per tick"
          />
        </div>

        {/* GDP TimeSeries panel */}
        <Panel className="s8">
          <SectionTitle
            title="Economic pulse · GDP output"
            meta="last 250 ticks · hover for values"
          />
          <TimeSeries
            series={[{
              data: appendCurrent(metrics.gdpHistory, tick, metrics.gdp || 0),
              tone: 'acc',
              name: 'GDP',
            }]}
            format={formatMillionsAdaptive}
            axes
            endLabel
            markers={policyMarkers}
            height={250}
          />
        </Panel>

        {/* Population stress panel */}
        <Panel className="s4">
          <SectionTitle
            title="Population stress"
            meta="45% unemployment · 40% unhappiness · 15% firm pressure"
          />
          <div style={{ display: 'flex', alignItems: 'flex-end', gap: 14 }}>
            <div className="hero" style={{ margin: 0 }}>
              <div className="v num" style={{ fontSize: 46 }}>{score(stressVal)}</div>
            </div>
            <div style={{ paddingBottom: 8 }}>
              <div className="lbl">
                {`${stressVal > 70 ? 'Critical' : stressVal > 45 ? 'Elevated' : 'Nominal'} · composite /100`}
              </div>
              <div className="muted" style={{ fontSize: 11 }}>
                0–45 nominal · 45–70 elevated · 70+ critical
              </div>
            </div>
          </div>
          <Meter value={stressVal} zones={[45, 70]} tones={['good', 'warn', 'crit']} />
          <TimeSeries
            series={[{
              data: stressHistory,
              tone: stressVal > 70 ? 'crit' : stressVal > 45 ? 'warn' : 'good',
              name: 'Stress',
            }]}
            format={score}
            axes={false}
            n={80}
            height={64}
          />
          <div className="g2" style={{ marginTop: 10 }}>
            <StatTile
              label="Happiness"
              value={metrics.happiness || 0}
              format={dec1}
              history={metrics.happinessHistory}
              tick={tick}
              tone={(metrics.happiness || 0) < 30 ? 'warn' : undefined}
              caption="population mean /100"
            />
            <StatTile
              label="Health index"
              value={latest(metrics.healthHistory, 0)}
              format={dec1}
              history={metrics.healthHistory}
              tick={tick}
              caption="latest sample /100"
            />
          </div>
        </Panel>

        {/* Sector prices panel */}
        <Panel className="s8">
          <SectionTitle
            title="Sector prices"
            meta="one chart per sector · last 120 ticks"
          />
          <div className="g4">
            {SECTORS.map((s) => {
              const hist = metrics.priceHistory?.[s.key] || []
              const livePrice = latest(hist, 0)
              return (
                <div key={s.key}>
                  <div className="lbl" style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span>
                      <i style={{
                        display: 'inline-block',
                        width: 8,
                        height: 8,
                        borderRadius: 2,
                        background: `var(--${s.tone})`,
                        marginRight: 6,
                      }} />
                      {s.name}
                    </span>
                    <span className="mono" style={{ color: 'var(--ink)' }}>
                      {usd2(livePrice)}
                    </span>
                  </div>
                  <TimeSeries
                    series={[{ data: hist, tone: s.tone, name: s.name }]}
                    format={usd2}
                    endLabel
                    axes={false}
                    n={120}
                    height={84}
                  />
                </div>
              )
            })}
          </div>
        </Panel>

        {/* Wealth distribution panel */}
        <Panel className="s4">
          <SectionTitle
            title="Wealth distribution"
            meta="share of wealth by cohort"
          />
          <CompositionBar segments={wealthSegments} />
          <SectionTitle
            title="Gini coefficient"
            right={<Delta diff={giniDelta.diff} pct={giniDelta.pct} unit="pts" upBad />}
          />
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span className="kpi">
              <span className="n" style={{ fontSize: 28 }}>{dec3(giniVal)}</span>
            </span>
            <Pill tone={giniTone}>{giniLabel}</Pill>
          </div>
          <TimeSeries
            series={[{ data: metrics.giniHistory || [], tone: 'acc', name: 'Gini' }]}
            format={dec3}
            axes={false}
            n={250}
            height={66}
          />
        </Panel>

        {/* Wages panel */}
        <Panel className="s4">
          <SectionTitle title="Wages" meta="mean vs median" />
          <TimeSeries
            series={[
              { data: metrics.wageHistory || [], tone: 'acc', name: 'Mean' },
              { data: metrics.medianWageHistory || [], tone: 's1', name: 'Median' },
            ]}
            format={usd2}
            endLabel
            axes
            height={150}
          />
        </Panel>

        {/* Policy assistant panel */}
        <Panel className="s4">
          <SectionTitle
            title="Policy assistant"
            meta={llmGov?.enabled ? 'AI policy active' : 'manual controls active'}
          />
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            {latestDecisionTick > 0 && (
              <Pill tone="ai">Last acted t{latestDecisionTick}</Pill>
            )}
            <Pill tone={llmGov?.enabled ? 'ai' : 'muted'}>
              {llmStatusLabel || (llmGov?.enabled ? 'Policy assistant ready' : 'Inactive')}
            </Pill>
          </div>
          <p style={{ fontSize: 12, color: 'var(--ink2)', margin: '10px 0 6px' }}>
            {latestDecision?.rationale ||
              latestDecision?.reasoning ||
              latestDecision?.decision_summary ||
              'Manual controls are active. Enable the AI Policy Engine from Government once policy-run history is available.'}
          </p>
          <div className="ba" style={{ marginTop: 'auto' }}>
            <div className="b">
              <div className="k">Unemployment since</div>
              <div className="v">
                {pct1(unempBefore)}
                <span className="arrow">→</span>
                {pct1(unempNow)}
              </div>
            </div>
            <div className="b">
              <div className="k">Fiscal balance</div>
              <div className="v">
                {signedMillions(profitBefore)}
                <span className="arrow">→</span>
                {signedMillions(profitNow)}
              </div>
            </div>
          </div>
        </Panel>

        {/* Unemployment panel */}
        <Panel className="s4">
          <SectionTitle
            title="Unemployment"
            meta="band above 25% · policy markers"
          />
          <TimeSeries
            series={[{
              data: appendCurrent(metrics.unemploymentHistory, tick, metrics.unemployment || 0),
              tone: 'crit',
              name: 'Unemployment',
            }]}
            format={pct1}
            band={[25, 100]}
            markers={policyMarkers}
            axes
            height={150}
          />
        </Panel>
      </div>
    </div>
  )
}
