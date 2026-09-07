import { useMemo, useState } from 'react'
import PageHeader from '../ui/PageHeader.jsx'
import Panel from '../ui/Panel.jsx'
import SectionTitle from '../ui/SectionTitle.jsx'
import HeroMetric from '../ui/HeroMetric.jsx'
import Pill from '../ui/Pill.jsx'
import Chip from '../ui/Chip.jsx'
import KeyValue from '../ui/KeyValue.jsx'
import { Search } from '../ui/Inputs.jsx'
import TimeSeries from '../charts/TimeSeries.jsx'
import Sparkline from '../charts/Sparkline.jsx'
import Radar from '../charts/Radar.jsx'
import ProfileBars from '../charts/ProfileBars.jsx'
import NeuralAvatar from '../NeuralAvatar.jsx'
import { appendCurrent, employment } from '../telemetry.js'
import { compactMoney, usd2, pct1, readableName, formatInteger } from '../format.js'

const COHORTS = ['All', 'Working', 'Unemployed', 'Stretched', 'No housing']

function medianOf(arr) {
  if (!arr || arr.length === 0) return 0
  const sorted = [...arr].sort((a, b) => a - b)
  const mid = Math.floor(sorted.length / 2)
  return sorted.length % 2 !== 0
    ? sorted[mid]
    : (sorted[mid - 1] + sorted[mid]) / 2
}

const norm01 = (v) => (v > 1 ? v / 100 : Math.max(0, Math.min(1, Number(v) || 0)))

const hasHousingSecurity = (s) => Boolean(
  s?.housingSecurity ??
  s?.needs?.housing ??
  s?.ownsHousing ??
  s?.hasRental ??
  s?.metHousingNeed
)

function humaniseKey(key) {
  const map = {
    mode: 'Mode',
    gapToCurrentWage: 'Gap vs current',
    wageExpectationAlpha: 'Wage alpha',
    durationPressure: 'Duration pressure',
    cashPressure: 'Cash pressure',
    healthPressure: 'Health pressure',
    decayFactor: 'Decay factor',
    marketAnchorEstimate: 'Market anchor',
    unemploymentDuration: 'Unemployment duration',
    tags: 'Tags',
  }
  if (map[key]) return map[key]
  return key
    .replace(/([a-z])([A-Z])/g, '$1 $2')
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase())
}

function formatWageDriverValue(key, value) {
  if (value === null || value === undefined) return '—'
  if (Array.isArray(value)) return value.length ? value.join(', ') : 'None'
  if (typeof value === 'boolean') return value ? 'Yes' : 'No'
  if (typeof value === 'number') {
    if (key.toLowerCase().includes('wage') || key.toLowerCase().includes('estimate') || key.toLowerCase().includes('anchor')) {
      return usd2(value)
    }
    if (key.toLowerCase().includes('gap')) {
      return Math.abs(value) < 1e-4 ? '$0.00' : usd2(value)
    }
    if (key.toLowerCase().includes('duration')) {
      return `${Math.round(value)} ticks`
    }
    if (Number.isInteger(value)) return String(value)
    return value.toFixed(3)
  }
  if (typeof value === 'string') {
    return value.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
  }
  return String(value)
}

function wageDriverTone(key, value) {
  if (key === 'gapToCurrentWage') {
    return value >= 0 ? 'good' : 'warn'
  }
  if (key === 'unemploymentDuration' && Number(value) > 0) {
    return 'crit'
  }
  if ((key === 'durationPressure' || key === 'cashPressure' || key === 'healthPressure') && Number(value) > 0.5) {
    return 'warn'
  }
  return undefined
}

export default function Population({
  metrics = {},
  tick = 0,
  population,
  subjectIndex = 0,
  onSelectSubject,
  search = '',
  onSearch,
  filter = 'All',
  onFilter,
  _histories = {},
}) {
  const tracked = useMemo(() => metrics.trackedSubjects || [], [metrics.trackedSubjects])
  const [profileMode, setProfileMode] = useState('radar')

  const empRate = employment(metrics)
  const riskCount = tracked.filter((x) => x.state === 'UNEMPLOYED' || (x.cash || 0) < 150).length
  const unempCount = tracked.filter((x) => x.state === 'UNEMPLOYED').length
  const medianCash = medianOf(tracked.map((x) => x.cash || 0))

  const handleSelect = (idx) => {
    if (onSelectSubject) onSelectSubject(idx)
  }

  const handleSearch = (val) => {
    if (onSearch) onSearch(val)
  }

  const handleFilter = (val) => {
    if (onFilter) onFilter(val)
  }

  const filteredSubjects = useMemo(() => {
    return tracked
      .map((s, idx) => ({ subject: s, origIdx: idx }))
      .filter(({ subject: s }) => {
        const text = `${s.id} ${s.name} ${readableName(s.name)} ${s.state} ${s.employer || ''}`.toLowerCase()
        const matchesSearch = !search || !search.trim() || text.includes(search.toLowerCase().trim())

        const norm = (filter || 'All').toLowerCase()
        let matchesCohort = true
        if (norm === 'working') {
          matchesCohort = s.state === 'WORKING'
        } else if (norm === 'unemployed') {
          matchesCohort = s.state === 'UNEMPLOYED'
        } else if (norm === 'stretched') {
          matchesCohort = s.state === 'UNEMPLOYED' || (s.cash || 0) < 150
        } else if (norm === 'no housing' || norm === 'lacking housing') {
          matchesCohort = !hasHousingSecurity(s)
        }
        return matchesSearch && matchesCohort
      })
  }, [tracked, search, filter])

  const selectedSubject = tracked[subjectIndex] || tracked[0] || null

  const needsKeys = useMemo(() => {
    const keys = new Set(['food', 'housing', 'healthcare'])
    tracked.forEach((s) => {
      if (s.needs) {
        Object.keys(s.needs).forEach((k) => keys.add(k))
      }
    })
    return Array.from(keys)
  }, [tracked])

  const medians = useMemo(() => {
    if (!tracked.length) return [0.5, 0.5, 0.5, 0.5, ...needsKeys.map(() => 0.5)]
    return [
      medianOf(tracked.map((s) => norm01(s.health ?? 1))),
      medianOf(tracked.map((s) => norm01(s.happiness ?? 0.5))),
      medianOf(tracked.map((s) => norm01(s.morale ?? 1))),
      medianOf(tracked.map((s) => norm01(s.skills ?? 0.5))),
      ...needsKeys.map((k) => medianOf(tracked.map((s) => norm01(s.needs?.[k] ?? 0)))),
    ]
  }, [tracked, needsKeys])

  const dims = useMemo(() => {
    if (!selectedSubject) return []
    return [
      { label: 'Health', value: norm01(selectedSubject.health ?? 1) },
      { label: 'Happiness', value: norm01(selectedSubject.happiness ?? 0.5) },
      { label: 'Morale', value: norm01(selectedSubject.morale ?? 1) },
      { label: 'Skills', value: norm01(selectedSubject.skills ?? 0.5) },
      ...needsKeys.map((k) => ({
        label: k.charAt(0).toUpperCase() + k.slice(1),
        value: norm01(selectedSubject.needs?.[k] ?? 0),
      })),
    ]
  }, [selectedSubject, needsKeys])

  // Expected wage entries
  const wageDriverEntries = useMemo(() => {
    if (!selectedSubject) return []
    if (selectedSubject.expectedWageReason && Object.keys(selectedSubject.expectedWageReason).length > 0) {
      return Object.entries(selectedSubject.expectedWageReason)
    }
    return [
      ['mode', selectedSubject.state === 'UNEMPLOYED' ? 'Unemployed floor' : 'Employed wage'],
      ['reservationWage', usd2(selectedSubject.reservationWage ?? ((selectedSubject.wage || 39) - 0.05))],
      ['gapToCurrentWage', selectedSubject.state === 'UNEMPLOYED' ? '—' : '$0.05'],
      ['unemploymentDuration', selectedSubject.state === 'UNEMPLOYED' ? `${selectedSubject.unemploymentDuration || 0} ticks` : '0 ticks'],
      ['skills', Number(selectedSubject.skills || 0).toFixed(2)],
    ]
  }, [selectedSubject])

  const housingSecurityLabel = selectedSubject?.ownsHousing
    ? 'Owns home'
    : (selectedSubject?.cash || 0) > 150
      ? 'Rented · secure'
      : 'Rented · tight'

  const housingSecurityTone = selectedSubject?.ownsHousing || (selectedSubject?.cash || 0) > 150
    ? 'good'
    : 'warn'

  const netWorthVal = selectedSubject?.netWorth ?? selectedSubject?.cash ?? 0
  const netWorthHistory = selectedSubject
    ? appendCurrent(selectedSubject.history?.netWorth || selectedSubject.history?.cash || [], tick, netWorthVal)
    : []
  const wageVal = selectedSubject?.wage ?? 0
  const wageHistory = selectedSubject
    ? appendCurrent(selectedSubject.history?.wage || [], tick, wageVal)
    : []

  return (
    <div>
      <PageHeader
        eyebrow="Population"
        title="Households"
        summary={`${tracked.length} tracked households of ${population != null && population !== '' ? formatInteger(population) : '—'}. ${riskCount} stretched, ${unempCount} unemployed.`}
        action={
          <div style={{ display: 'flex', gap: 8, alignItems: 'flex-end' }}>
            <div className="kpi">
              <span className="n">{pct1(empRate)}</span>
              <span className="k">employed</span>
            </div>
            <div className="kpi" style={{ marginLeft: 14 }} title="Unemployed, or cash under $150">
              <span className="n" style={{ color: 'var(--warn)' }}>{riskCount}</span>
              <span className="k">stretched</span>
            </div>
            <div className="kpi" style={{ marginLeft: 14 }}>
              <span className="n">{compactMoney(medianCash)}</span>
              <span className="k">median cash</span>
            </div>
          </div>
        }
      />

      <div className="g12">
        {/* Left Column: Roster */}
        <Panel className="s3">
          <Search
            value={search}
            onChange={handleSearch}
            placeholder="Search name, employer, state…"
          />
          <div className="chips" style={{ marginTop: 8, marginBottom: 8 }}>
            {COHORTS.map((c) => (
              <Chip
                key={c}
                on={filter.toLowerCase() === c.toLowerCase()}
                onClick={() => handleFilter(c)}
              >
                {c === 'All' ? `All ${tracked.length}` : c}
              </Chip>
            ))}
          </div>
          <div className="roster">
            {filteredSubjects.map(({ subject: s, origIdx }) => {
              const isSelected = origIdx === subjectIndex
              const isRisk = s.state === 'UNEMPLOYED' || (s.cash || 0) < 150
              const stateTone = isRisk ? (s.state === 'UNEMPLOYED' ? 'crit' : 'warn') : 'good'
              const cashHistory = (s.history?.cash || []).map((d) => (typeof d === 'number' ? d : d.value ?? 0))
              return (
                <div
                  key={s.id ?? origIdx}
                  className={`r${isSelected ? ' on' : ''}`}
                  onClick={() => handleSelect(origIdx)}
                >
                  <i className="st" style={{ background: `var(--${stateTone})` }} />
                  <div>
                    <div className="nm">{readableName(s.name)}</div>
                    <div className="em">{s.state === 'UNEMPLOYED' ? 'Unemployed' : readableName(s.employer) || 'Unemployed'}</div>
                  </div>
                  <div className="cash">{compactMoney(s.cash || 0)}</div>
                  <Sparkline
                    data={cashHistory.length > 0 ? cashHistory : [s.cash || 0]}
                    tone={stateTone === 'crit' ? 'crit' : stateTone === 'warn' ? 'warn' : 'acc'}
                    width={56}
                    height={18}
                  />
                </div>
              )
            })}
          </div>
        </Panel>

        {/* Center Column: Hero Card */}
        {selectedSubject ? (
          <Panel hot className="s6">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>
              <div>
                <div className="lbl">
                  {`${readableName(selectedSubject.name)} · id ${String(selectedSubject.id).padStart(4, '0')} · age ${selectedSubject.age}`}
                </div>
                <div style={{ fontSize: 26, fontWeight: 700, color: 'var(--ink)', letterSpacing: '-0.02em', marginTop: 2 }}>
                  {selectedSubject.state === 'UNEMPLOYED' ? 'Looking for work' : readableName(selectedSubject.employer) || 'Employed'}
                  {selectedSubject.wage ? (
                    <span style={{ fontSize: 13, color: 'var(--ink3)', fontWeight: 500 }}>
                      {` · ${usd2(selectedSubject.wage)}/tick`}
                    </span>
                  ) : null}
                </div>
                <div className="chips" style={{ marginTop: 8 }}>
                  <Pill tone={selectedSubject.state === 'WORKING' ? 'good' : selectedSubject.state === 'UNEMPLOYED' ? 'crit' : 'warn'}>
                    {selectedSubject.state ? selectedSubject.state.charAt(0) + selectedSubject.state.slice(1).toLowerCase() : 'Unknown'}
                  </Pill>
                  <Pill tone={housingSecurityTone}>
                    {housingSecurityLabel}
                  </Pill>
                  {(selectedSubject.needs?.food ?? 1) < 0.3 && (
                    <Pill tone="warn">Food inventory low</Pill>
                  )}
                </div>
              </div>
              <div style={{ textAlign: 'right' }}>
                <HeroMetric
                  label="Net worth"
                  value={netWorthVal}
                  format={compactMoney}
                  history={selectedSubject.history?.netWorth || selectedSubject.history?.cash || []}
                  tick={tick}
                />
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '150px 1fr', gap: 14, marginTop: 14 }}>
              <div className="canvas-slot" style={{ minHeight: 200 }}>
                <NeuralAvatar
                  active={true}
                  mood={(selectedSubject.health || 1) < 0.3 ? 'distressed' : (selectedSubject.happiness || 0) > 0.7 ? 'happy' : 'neutral'}
                />
              </div>
              <div>
                <div className="profhead">
                  <span className="lbl">Profile · {readableName(selectedSubject.name)} against the population median</span>
                  <span className="chips">
                    <Chip on={profileMode !== 'bars'} onClick={() => setProfileMode('radar')}>Radar</Chip>
                    <Chip on={profileMode === 'bars'} onClick={() => setProfileMode('bars')}>Bars</Chip>
                  </span>
                </div>
                {profileMode === 'bars' ? (
                  <ProfileBars dims={dims} median={medians} />
                ) : (
                  <Radar dims={dims} median={medians} />
                )}
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10, marginTop: 14 }}>
              <KeyValue
                label="Expected wage"
                value={usd2(selectedSubject.expectedWage ?? selectedSubject.wage ?? 0)}
              />
              <KeyValue
                label="Reservation wage"
                value={usd2(selectedSubject.reservationWage ?? ((selectedSubject.wage || 39) - 0.05))}
              />
              <KeyValue
                label="Monthly rent"
                value={usd2(selectedSubject.monthlyRent ?? selectedSubject.rent ?? 0)}
              />
              <KeyValue
                label="Medical debt"
                value={usd2(selectedSubject.medicalDebt || 0)}
                tone={Number(selectedSubject.medicalDebt || 0) > 0 ? 'crit' : undefined}
              />
            </div>

            <div className="g2" style={{ marginTop: 14 }}>
              <div>
                <SectionTitle title="Wealth" meta="40 ticks" />
                <TimeSeries
                  series={[{
                    data: netWorthHistory,
                    tone: 'acc',
                    name: 'Wealth',
                  }]}
                  format={compactMoney}
                  axes
                  height={118}
                />
              </div>
              <div>
                <SectionTitle title="Wage" meta="40 ticks" />
                <TimeSeries
                  series={[{
                    data: wageHistory,
                    tone: 's1',
                    name: 'Wage',
                  }]}
                  format={usd2}
                  axes
                  height={118}
                />
              </div>
            </div>
          </Panel>
        ) : (
          <Panel hot className="s6">
            <div className="muted" style={{ padding: 20, textAlign: 'center' }}>
              No subject selected
            </div>
          </Panel>
        )}

        {/* Right Column */}
        {selectedSubject ? (
          <div className="s3 col">
            {/* Wage drivers */}
            <Panel>
              <SectionTitle
                title="Wage drivers"
                meta={`why they ask ${usd2(selectedSubject.expectedWage || selectedSubject.wage || 0)}`}
              />
              {wageDriverEntries.map(([k, v]) => (
                <KeyValue
                  key={k}
                  label={humaniseKey(k)}
                  value={formatWageDriverValue(k, v)}
                  tone={wageDriverTone(k, v)}
                />
              ))}
            </Panel>

            {/* Housing */}
            <Panel>
              <SectionTitle title="Housing" />
              <KeyValue
                label="Status"
                value={housingSecurityLabel}
                tone={housingSecurityTone}
              />
              <KeyValue
                label="Monthly rent"
                value={usd2(selectedSubject.monthlyRent ?? selectedSubject.rent ?? 0)}
              />
              <KeyValue
                label="Need met"
                value={selectedSubject.metHousingNeed ? 'Yes' : (selectedSubject.needs?.housing ?? 0) > 0.6 ? 'Yes' : 'Partly'}
                tone={selectedSubject.metHousingNeed || (selectedSubject.needs?.housing ?? 0) > 0.6 ? 'good' : 'warn'}
              />
              <KeyValue
                label="Security"
                value={hasHousingSecurity(selectedSubject) && (selectedSubject.cash || 0) >= 150 ? 'Secure' : 'Fragile'}
                tone={hasHousingSecurity(selectedSubject) && (selectedSubject.cash || 0) >= 150 ? 'good' : 'crit'}
              />
            </Panel>

          </div>
        ) : null}
      </div>
    </div>
  )
}
