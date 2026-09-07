import { useMemo, useState } from 'react'
import PageHeader from '../ui/PageHeader.jsx'
import Panel from '../ui/Panel.jsx'
import SectionTitle from '../ui/SectionTitle.jsx'
import StatTile from '../ui/StatTile.jsx'
import Pill from '../ui/Pill.jsx'
import KeyValue from '../ui/KeyValue.jsx'
import TimeSeries from '../charts/TimeSeries.jsx'
import NeuralBuilding from '../NeuralBuilding.jsx'
import { appendCurrent, latest } from '../telemetry.js'
import {
  compactMoney,
  formatDecimal,
  formatInteger,
  signedMoney,
  usd2,
} from '../format.js'
import { toneVar } from '../charts/tones.js'

const SECTORS = [
  { name: 'Food', key: 'food', tone: 's1' },
  { name: 'Housing', key: 'housing', tone: 's2' },
  { name: 'Services', key: 'services', tone: 's3' },
  { name: 'Healthcare', key: 'healthcare', tone: 's4' },
]

const SECTOR_TONES = {
  Food: 's1',
  Housing: 's2',
  Services: 's3',
  Healthcare: 's4',
  food: 's1',
  housing: 's2',
  services: 's3',
  healthcare: 's4',
}

const COLUMNS = [
  { key: 'name', label: 'Firm', align: '' },
  { key: 'sector', label: 'Sector', align: '' },
  { key: 'cash', label: 'Cash', align: 'ar' },
  { key: 'price', label: 'Price', align: 'ar' },
  { key: 'wage', label: 'Wage', align: 'ar' },
  { key: 'emp', label: 'Employees', align: 'ar' },
  { key: 'profit', label: 'Profit', align: 'ar' },
  { key: 'state', label: 'State', align: '' },
]

function firmTone(state) {
  const s = String(state || '').toUpperCase()
  if (s === 'ACTIVE' || s === 'SCALING') return 'good'
  if (s === 'STRUGGLING') return 'warn'
  return 'crit'
}

function formatState(state) {
  if (!state) return ''
  const s = String(state)
  return s.charAt(0).toUpperCase() + s.slice(1).toLowerCase()
}

export default function Markets({
  metrics = {},
  firmStats = {},
  tick = 0,
  firmIndex = 0,
  onSelectFirm,
  histories = {},
}) {
  const handleSelectFirm = onSelectFirm || (() => {})

  const totalFirms = Number(firmStats?.total_firms || 0)
  const totalEmployees = Number(firmStats?.total_employees || 0)
  const avgWageOffer = Number(firmStats?.avg_wage_offer || 0)
  const strugglingFirms = Number(firmStats?.struggling_firms || 0)

  const tickHist = histories || {}

  const trackedFirms = useMemo(() => metrics?.trackedFirms || [], [metrics?.trackedFirms])
  const activeIndex =
    firmIndex != null && firmIndex >= 0 && firmIndex < trackedFirms.length
      ? firmIndex
      : 0
  const selectedFirm = trackedFirms[activeIndex] || null

  const allFirms = useMemo(() => {
    const map = new Map()
    const sources = [
      ...(firmStats?.top_cash || []),
      ...(firmStats?.top_employers || []),
      ...(metrics?.trackedFirms || []),
    ]
    for (const item of sources) {
      if (!item) continue
      const key = String(item.id ?? item.name)
      if (!key) continue
      const prev = map.get(key) || {}
      map.set(key, { ...prev, ...item })
    }
    return Array.from(map.values()).map((f) => ({
      ...f,
      id: f.id,
      name: f.name,
      category: f.category || f.sector || 'Unknown',
      sector: f.category || f.sector || 'Unknown',
      cash: Number(f.cash || 0),
      price: Number(f.price || 0),
      wage: Number(f.wageOffer ?? f.wage ?? 0),
      wageOffer: Number(f.wageOffer ?? f.wage ?? 0),
      emp:
        f.category === 'Healthcare'
          ? Number(f.doctorEmployees || f.medicalEmployees || f.employees || f.emp || 0)
          : Number(f.employees ?? f.emp ?? 0),
      employees:
        f.category === 'Healthcare'
          ? Number(f.doctorEmployees || f.medicalEmployees || f.employees || f.emp || 0)
          : Number(f.employees ?? f.emp ?? 0),
      profit: Number(f.lastProfit ?? f.profit ?? 0),
      lastProfit: Number(f.lastProfit ?? f.profit ?? 0),
      state: String(f.state || 'ACTIVE').toUpperCase(),
    }))
  }, [firmStats?.top_cash, firmStats?.top_employers, metrics?.trackedFirms])

  const [sortKey, setSortKey] = useState('cash')
  const [sortDir, setSortDir] = useState('desc')

  const handleSort = (key) => {
    if (sortKey === key) {
      setSortDir((d) => (d === 'desc' ? 'asc' : 'desc'))
    } else {
      setSortKey(key)
      setSortDir('desc')
    }
  }

  const sortedFirms = useMemo(() => {
    const dir = sortDir === 'desc' ? -1 : 1
    return [...allFirms].sort((a, b) => {
      let valA = a[sortKey]
      let valB = b[sortKey]
      if (sortKey === 'sector') {
        valA = a.category || a.sector || ''
        valB = b.category || b.sector || ''
      } else if (sortKey === 'wage') {
        valA = a.wageOffer ?? a.wage ?? 0
        valB = b.wageOffer ?? b.wage ?? 0
      } else if (sortKey === 'emp') {
        valA = a.employees ?? a.emp ?? 0
        valB = b.employees ?? b.emp ?? 0
      } else if (sortKey === 'profit') {
        valA = a.lastProfit ?? a.profit ?? 0
        valB = b.lastProfit ?? b.profit ?? 0
      }
      if (typeof valA === 'string' || typeof valB === 'string') {
        const cmp = String(valA || '').localeCompare(String(valB || ''))
        if (cmp !== 0) return cmp * dir
      } else {
        const diff = (Number(valA) || 0) - (Number(valB) || 0)
        if (diff !== 0) return diff * dir
      }
      return String(a.id ?? a.name).localeCompare(String(b.id ?? b.name))
    })
  }, [allFirms, sortKey, sortDir])

  const trackedIndexById = useMemo(() => {
    const map = new Map()
    trackedFirms.forEach((f, idx) => {
      if (f.id != null) map.set(String(f.id), idx)
      if (f.name != null) map.set(String(f.name), idx)
    })
    return map
  }, [trackedFirms])

  const maxCash = useMemo(() => {
    if (!allFirms.length) return 1
    return Math.max(1, ...allFirms.map((x) => Math.abs(x.cash)))
  }, [allFirms])

  const summary = useMemo(() => {
    if (!firmStats || !firmStats.categories || firmStats.categories.length === 0) {
      return '—'
    }
    let mostCashCat = null
    let maxCash = -Infinity
    let mostEmpCat = null
    let maxEmp = -Infinity

    for (const c of firmStats.categories) {
      const cash = Number(c.avg_cash || 0) * Number(c.firm_count || 0)
      if (cash > maxCash) {
        maxCash = cash
        mostCashCat = c.category
      }
      const emp = Number(c.total_employees || 0)
      if (emp > maxEmp) {
        maxEmp = emp
        mostEmpCat = c.category
      }
    }
    if (!mostCashCat || !mostEmpCat) return '—'
    return `${totalFirms} firms across four sectors. ${mostCashCat} holds most of the cash, ${mostEmpCat.toLowerCase()} employs most of the people.`
  }, [firmStats, totalFirms])

  return (
    <>
      <PageHeader
        eyebrow="Markets"
        title="Markets & Firms"
        summary={summary}
        action={
          trackedFirms.length > 0 ? (
            <div className="chips">
              {trackedFirms.slice(0, 4).map((f, idx) => (
                <button
                  key={f.id ?? idx}
                  type="button"
                  className={`chip ${activeIndex === idx ? 'on' : ''}`}
                  onClick={() => handleSelectFirm(idx)}
                >
                  {f.name}
                </button>
              ))}
            </div>
          ) : null
        }
      />

      <div className="g12">
        <div className="s12 g4">
          <StatTile
            label="Total firms"
            value={totalFirms}
            format={formatInteger}
            history={tickHist.firms}
            tick={tick}
            caption="across 4 sectors"
          />
          <StatTile
            label="Total employees"
            value={totalEmployees}
            format={formatInteger}
            history={tickHist.employees}
            tick={tick}
            caption="on firm rosters"
          />
          <StatTile
            label="Avg wage offer"
            value={avgWageOffer}
            format={usd2}
            history={tickHist.wageOffer}
            tick={tick}
            caption="posted by firms"
          />
          <StatTile
            label="Struggling firms"
            value={strugglingFirms}
            format={formatInteger}
            history={tickHist.struggling}
            tick={tick}
            caption="cash at or below zero"
            tone={strugglingFirms >= 6 ? 'crit' : strugglingFirms >= 3 ? 'warn' : undefined}
            upBad
          />
        </div>

        <Panel className="s8">
          <SectionTitle title="Sector map" meta="firms · employees · cash · price" />
          <div className="g4">
            {SECTORS.map((s, i) => {
              const cat =
                (firmStats?.categories || []).find(
                  (c) => c.category?.toLowerCase() === s.key
                ) || {}
              const avgCash = Number(cat.avg_cash || 0)
              const isDistress = avgCash <= 0
              const priceSeries = metrics?.priceHistory?.[s.key] || []
              const livePrice = cat.avg_price ?? latest(priceSeries, 0)
              const chartData = appendCurrent(priceSeries, tick, livePrice)

              return (
                <div
                  key={s.key}
                  style={{
                    padding: i ? '4px 0 4px 14px' : '4px 0',
                    borderLeft: i ? '1px solid var(--line)' : '0',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontWeight: 700, color: 'var(--ink)' }}>
                      <i
                        style={{
                          display: 'inline-block',
                          width: 8,
                          height: 8,
                          borderRadius: 2,
                          background: toneVar(s.tone),
                          marginRight: 6,
                        }}
                      />
                      {s.name}
                    </span>
                    <Pill tone={isDistress ? 'crit' : 'good'}>
                      {isDistress ? 'Distress' : 'Stable'}
                    </Pill>
                  </div>
                  <div style={{ display: 'flex', gap: 14, marginTop: 8 }}>
                    <div className="kpi">
                      <span className="n">{formatInteger(cat.firm_count || 0)}</span>
                      <span className="k">firms</span>
                    </div>
                    <div className="kpi">
                      <span className="n">{formatInteger(cat.total_employees || 0)}</span>
                      <span className="k">employees</span>
                    </div>
                  </div>
                  <div
                    className="lbl"
                    style={{ marginTop: 8, display: 'flex', justifyContent: 'space-between' }}
                  >
                    <span>avg cash</span>
                    <span className="mono" style={{ color: isDistress ? 'var(--crit)' : 'var(--ink)' }}>
                      {compactMoney(avgCash)}
                    </span>
                  </div>
                  <div className="lbl" style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span>price</span>
                    <span className="mono" style={{ color: 'var(--ink)' }}>
                      {usd2(livePrice)}
                    </span>
                  </div>
                  <TimeSeries
                    series={[
                      {
                        data: chartData,
                        tone: s.tone,
                        name: s.name,
                      },
                    ]}
                    format={usd2}
                    endLabel
                    axes={false}
                    n={120}
                    height={54}
                  />
                </div>
              )
            })}
          </div>
        </Panel>

        <Panel hot className="s4">
          <SectionTitle
            title="Selected firm"
            right={
              selectedFirm?.state ? (
                <Pill tone={firmTone(selectedFirm.state)}>
                  {formatState(selectedFirm.state)}
                </Pill>
              ) : null
            }
          />
          <div style={{ fontSize: 22, fontWeight: 700, color: 'var(--ink)', letterSpacing: '-.02em' }}>
            {selectedFirm?.name || '—'}
          </div>
          <div className="lbl">
            <i
              style={{
                display: 'inline-block',
                width: 8,
                height: 8,
                borderRadius: 2,
                background: toneVar(SECTOR_TONES[selectedFirm?.category || selectedFirm?.sector] || 's1'),
                marginRight: 6,
              }}
            />
            {(selectedFirm?.category || selectedFirm?.sector || 'Unknown')} · id {selectedFirm?.id ?? '—'}
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '110px 1fr', gap: 12, marginTop: 10, flex: 1 }}>
            <div className="canvas-slot" style={{ minHeight: 120 }}>
              {selectedFirm ? (
                <NeuralBuilding
                  active
                  activityLevel={
                    selectedFirm.state === 'DISTRESS' || selectedFirm.state === 'BURN' ? 'high' : 'normal'
                  }
                  tier={
                    String(selectedFirm.category || '').toLowerCase().includes('housing')
                      ? 3
                      : String(selectedFirm.category || '').toLowerCase().includes('food')
                      ? 3
                      : 2
                  }
                  sector={selectedFirm.category || selectedFirm.sector}
                  status={selectedFirm.state}
                />
              ) : null}
            </div>
            <div>
              <KeyValue
                label="Cash"
                value={compactMoney(selectedFirm?.cash || 0)}
                tone={(selectedFirm?.cash || 0) <= 0 ? 'crit' : undefined}
              />
              <KeyValue
                label="Profit / tick"
                value={signedMoney(selectedFirm?.lastProfit ?? selectedFirm?.profit ?? 0)}
                tone={(selectedFirm?.lastProfit ?? selectedFirm?.profit ?? 0) < 0 ? 'crit' : 'good'}
              />
              <KeyValue
                label="Employees"
                value={formatInteger(selectedFirm?.employees ?? selectedFirm?.emp ?? 0)}
              />
              <KeyValue
                label="Wage offer"
                value={usd2(selectedFirm?.wageOffer ?? selectedFirm?.wage ?? 0)}
              />
              <KeyValue label="Price" value={usd2(selectedFirm?.price || 0)} />
              <KeyValue label="Inventory" value={formatDecimal(selectedFirm?.inventory || 0, 0)} />
              <KeyValue label="Quality" value={formatDecimal(selectedFirm?.quality || 0, 1)} />
            </div>
          </div>
        </Panel>

        <Panel className="s8">
          <SectionTitle title="All firms" meta="click a column to sort · click a row to inspect" />
          <div className="tablefill">
            <table>
              <thead>
                <tr>
                  {COLUMNS.map((col) => (
                    <th
                      key={col.key}
                      className={col.align}
                      onClick={() => handleSort(col.key)}
                    >
                      {col.label}
                      {sortKey === col.key ? (sortDir === 'desc' ? ' ↓' : ' ↑') : ''}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {sortedFirms.map((firm) => {
                  const trackedIdx =
                    trackedIndexById.get(String(firm.id)) ??
                    trackedIndexById.get(String(firm.name))
                  const isTracked = trackedIdx !== undefined
                  const isSelected = isTracked && trackedIdx === activeIndex
                  const barWidth = Math.round((Math.abs(firm.cash) / maxCash) * 40)
                  return (
                    <tr
                      key={firm.id ?? firm.name}
                      className={isSelected ? 'sel' : ''}
                      style={{ cursor: isTracked ? 'pointer' : 'default' }}
                      onClick={isTracked ? () => handleSelectFirm(trackedIdx) : undefined}
                    >
                      <td style={{ fontWeight: 600, color: 'var(--ink)' }}>{firm.name}</td>
                      <td>
                        <i
                          style={{
                            display: 'inline-block',
                            width: 8,
                            height: 8,
                            borderRadius: 2,
                            background: toneVar(SECTOR_TONES[firm.category || firm.sector] || 's1'),
                            marginRight: 6,
                          }}
                        />
                        {firm.category || firm.sector}
                      </td>
                      <td className="n ar">
                        <span
                          className="ibar"
                          style={{
                            display: 'inline-block',
                            height: 6,
                            borderRadius: 3,
                            verticalAlign: 'middle',
                            marginRight: 6,
                            opacity: 0.85,
                            width: `${barWidth}px`,
                            background: firm.cash < 0 ? 'var(--crit)' : 'var(--acc)',
                          }}
                        />
                        {compactMoney(firm.cash)}
                      </td>
                      <td className="n ar">{usd2(firm.price)}</td>
                      <td className="n ar">{usd2(firm.wageOffer ?? firm.wage ?? 0)}</td>
                      <td className="n ar">{formatInteger(firm.employees ?? firm.emp ?? 0)}</td>
                      <td
                        className="n ar"
                        style={{
                          color:
                            (firm.lastProfit ?? firm.profit ?? 0) < 0
                              ? 'var(--crit)'
                              : 'var(--good)',
                        }}
                      >
                        {signedMoney(firm.lastProfit ?? firm.profit ?? 0)}
                      </td>
                      <td>
                        <Pill tone={firmTone(firm.state)}>
                          {formatState(firm.state)}
                        </Pill>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </Panel>

        <div className="s4 col">
          <Panel style={{ flex: 1 }}>
            <SectionTitle title={`Cash · ${selectedFirm?.name || '—'}`} meta="40 ticks" />
            <TimeSeries
              series={[
                {
                  data: appendCurrent(selectedFirm?.history?.cash, tick, selectedFirm?.cash || 0),
                  tone: 'acc',
                  name: 'Cash',
                },
              ]}
              format={compactMoney}
              endLabel
              axes
              n={40}
              height={150}
            />
          </Panel>
          <Panel style={{ flex: 1 }}>
            <SectionTitle title={`Profit · ${selectedFirm?.name || '—'}`} meta="40 ticks" />
            <TimeSeries
              series={[
                {
                  data: appendCurrent(
                    selectedFirm?.history?.profit,
                    tick,
                    selectedFirm?.lastProfit ?? selectedFirm?.profit ?? 0
                  ),
                  tone: 's3',
                  name: 'Profit',
                },
              ]}
              format={signedMoney}
              endLabel
              axes
              n={40}
              height={150}
            />
          </Panel>
        </div>
      </div>
    </>
  )
}
