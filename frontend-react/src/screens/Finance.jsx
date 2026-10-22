import { useMemo } from 'react'
import PageHeader from '../ui/PageHeader.jsx'
import Panel from '../ui/Panel.jsx'
import SectionTitle from '../ui/SectionTitle.jsx'
import HeroMetric from '../ui/HeroMetric.jsx'
import ChartTile from '../ui/ChartTile.jsx'
import StatTile from '../ui/StatTile.jsx'
import KeyValue from '../ui/KeyValue.jsx'
import TimeSeries from '../charts/TimeSeries.jsx'
import Ledger from '../charts/Ledger.jsx'
import { appendCurrent } from '../telemetry.js'
import {
  formatInteger,
  formatMillionsAdaptive,
  formatPolicyMessage,
  signedMillions,
} from '../format.js'
import { classifyActor } from '../governmentInsights.js'

export default function Finance({
  metrics = {},
  tick = 0,
  policyChanges = metrics?.policyChanges || [],
  histories = {},
}) {
  const govProfit = Number(metrics.govProfit || 0)
  const govDebt = Number(metrics.govDebt || 0)
  const govRevenue = Number(metrics.govRevenue || 0)
  const govTransfers = Number(metrics.govTransfers || 0)
  const govInvestments = Number(metrics.govInvestments || 0)
  const bondPurchases = Number(metrics.bondPurchases || 0)
  const activeLoans = Number(metrics.activeLoans || 0)
  const govOwnedFirms = Number(metrics.govOwnedFirms || 0)
  const netWorth = Number(metrics.netWorth || 0)

  const govProfitHistory = metrics.govProfitHistory || []
  const govDebtHistory = metrics.govDebtHistory || []
  const netWorthHistory = metrics.netWorthHistory || []

  const transfersAndInvestments = govTransfers + govInvestments

  const tickHist = histories || {}

  const transfersInvestmentsHistory = useMemo(() => {
    const outArr = tickHist.out || []
    const bondArr = tickHist.bonds || []
    return outArr.map((d, i) => ({
      tick: d.tick,
      value: Math.max(0, d.value - (bondArr[i]?.value ?? bondPurchases)),
    }))
  }, [tickHist.out, tickHist.bonds, bondPurchases])

  const bondsRising8 = useMemo(() => {
    const bondsHistory = tickHist.bonds || []
    if (bondsHistory.length < 8) return false
    const slice = bondsHistory.slice(-8)
    for (let i = 1; i < slice.length; i++) {
      if (slice[i].value <= slice[i - 1].value) return false
    }
    return true
  }, [tickHist.bonds])

  const policyMarkers = useMemo(() => {
    return (policyChanges || []).map((c) => ({
      tick: c.tick,
      label: formatPolicyMessage(c),
      ai: classifyActor(c.reason) === 'ai',
      ok: true,
    }))
  }, [policyChanges])

  const profitTone = govProfit >= 0 ? 'good' : 'crit'
  const profitPillLabel = govProfit >= 0 ? 'Surplus' : 'Deficit'

  const heroHistory = useMemo(
    () => appendCurrent(metrics.govProfitHistory || [], tick, govProfit),
    [metrics.govProfitHistory, tick, govProfit]
  )

  const ledgerRows = [
    { label: 'Revenue', value: govRevenue, sign: '+', tone: 'acc' },
    { label: 'Transfers', value: govTransfers, sign: '−', tone: 's1' },
    { label: 'Investments', value: govInvestments, sign: '−', tone: 's1' },
    { label: 'Bond purchases', value: bondPurchases, sign: '−', tone: 's1' },
  ]

  const ledgerNet = {
    label: 'Net flow',
    value: govProfit,
  }

  return (
    <div>
      <PageHeader
        eyebrow="Finance"
        title="Treasury & Credit"
        summary={`${govProfit >= 0 ? 'Revenue is covering outlays this tick.' : 'Outlays exceed revenue this tick.'} ${govDebt === 0 ? 'Treasury debt has been flat at zero.' : `Treasury debt stands at ${formatMillionsAdaptive(govDebt)}.`}`}
        action={
          <span className="legend">
            <span>
              <i style={{ background: 'var(--acc)' }} />
              Revenue
            </span>
            <span>
              <i style={{ background: 'var(--s1)' }} />
              Outlays
            </span>
            <span>
              <i style={{ background: 'var(--ai)', width: 2, height: 10 }} />
              Policy change
            </span>
          </span>
        }
      />

      <div className="g12">
        <Panel hot className="hero s3">
          <HeroMetric
            label="Net fiscal balance · per tick"
            value={govProfit}
            format={signedMillions}
            history={govProfitHistory}
            tone={profitTone}
            tick={tick}
            pill={{ tone: profitTone, label: profitPillLabel }}
          >
            <TimeSeries
              series={[{ data: heroHistory, tone: profitTone }]}
              axes={false}
              height={56}
            />
          </HeroMetric>
        </Panel>

        <div className="s9 g4">
          <ChartTile
            label="Revenue"
            value={govRevenue}
            format={formatMillionsAdaptive}
            history={tickHist.rev}
            tick={tick}
            caption="wage + profit tax"
          />
          <ChartTile
            label="Transfers + investment"
            value={transfersAndInvestments}
            format={formatMillionsAdaptive}
            history={transfersInvestmentsHistory}
            tick={tick}
            caption="benefits · public works"
          />
          <ChartTile
            label="Bond purchases"
            value={bondPurchases}
            format={formatMillionsAdaptive}
            history={tickHist.bonds}
            tick={tick}
            tone={bondsRising8 ? 'warn' : undefined}
            upBad
            caption={bondsRising8 ? 'rising for 8 ticks' : 'open-market purchases'}
          />
          <ChartTile
            label="Household net worth"
            value={netWorth}
            format={formatMillionsAdaptive}
            history={netWorthHistory}
            tick={tick}
            caption="mean per household"
          />
        </div>

        <Panel className="s8">
          <SectionTitle title="Fiscal flows" meta="last 250 ticks · hover for values" />
          <TimeSeries
            series={[
              { data: tickHist.rev || [], tone: 'acc', name: 'Revenue' },
              { data: tickHist.out || [], tone: 's1', name: 'Outlays' },
            ]}
            format={formatMillionsAdaptive}
            endLabel
            axes
            markers={policyMarkers}
            height={232}
          />
        </Panel>

        <Panel className="s4">
          <SectionTitle title="Fiscal flow this tick" meta="where the money came from and went" />
          <Ledger
            rows={ledgerRows}
            net={ledgerNet}
            format={formatMillionsAdaptive}
          />
          <div className="g2" style={{ marginTop: 12 }}>
            <StatTile
              label="Government-backed loans"
              value={activeLoans}
              format={formatInteger}
              history={tickHist.loans}
              tick={tick}
              caption="firms holding credit"
            />
            <StatTile
              label="Treasury debt"
              value={govDebt}
              format={formatMillionsAdaptive}
              history={govDebtHistory}
              tick={tick}
              tone={govDebt > 0 ? 'crit' : undefined}
              upBad
              caption={govDebt === 0 ? 'none recorded' : 'current exposure'}
            />
          </div>
        </Panel>

        <Panel className="s7">
          <SectionTitle title="Government-backed loans" meta="firms holding treasury credit · 250 ticks" />
          <TimeSeries
            series={[{ data: tickHist.loans || [], tone: 's1', name: 'Active loans' }]}
            format={formatInteger}
            axes
            height={110}
          />
        </Panel>

        <Panel className="s5">
          <SectionTitle title="State capacity" meta="what the treasury holds" />
          <KeyValue label="Government-owned firms" value={formatInteger(govOwnedFirms)} />
          <KeyValue label="Government-backed loans" value={formatInteger(activeLoans)} />
          <KeyValue label="Bond purchases" value={formatMillionsAdaptive(bondPurchases)} />
          <KeyValue label="Investments" value={formatMillionsAdaptive(govInvestments)} />
          <KeyValue
            label="Treasury debt"
            value={govDebt === 0 ? '$0 · none recorded' : formatMillionsAdaptive(govDebt)}
            tone={govDebt === 0 ? 'good' : 'crit'}
          />
        </Panel>
      </div>
    </div>
  )
}
