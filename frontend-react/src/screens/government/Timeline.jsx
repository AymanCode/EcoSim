import KeyValue from '../../ui/KeyValue.jsx'
import { toneVar } from '../../charts/tones.js'
import { signedMillions } from '../../format.js'
import {
  DECISION_INTERVAL,
  changeNarrative,
  classifyActor,
  formatLeverValue,
  impactSince,
  leverLabel,
  parsePreviousValue,
} from '../../governmentInsights.js'

export function ImpactChips({ impact }) {
  if (!impact || impact.status !== 'ready') {
    return <span className="ic muted">measuring…</span>
  }
  const chip = (label, text, favourable) => {
    const tone =
      favourable === null
        ? 'var(--ink)'
        : favourable
          ? 'var(--good)'
          : 'var(--crit)'
    return (
      <span key={label} className="ic">
        {label} <b style={{ color: tone }}>{text}</b>
      </span>
    )
  }
  const signed = (num, digits, suffix = '') =>
    `${num > 0 ? '+' : num < 0 ? '-' : ''}${Math.abs(num).toFixed(digits)}${suffix}`
  const direction = (num, upIsGood) =>
    num === 0 ? null : upIsGood ? num > 0 : num < 0

  const chips = []
  if (impact.gdpPct !== null && impact.gdpPct !== undefined) {
    chips.push(
      chip('GDP', signed(impact.gdpPct, 1, '%'), direction(impact.gdpPct, true))
    )
  }
  chips.push(
    chip(
      'Unemployment',
      signed(impact.unemploymentPp, 1, ' pp'),
      direction(impact.unemploymentPp, false)
    )
  )
  chips.push(
    chip('Happiness', signed(impact.happinessPts, 1), direction(impact.happinessPts, true))
  )
  chips.push(
    chip(
      'Net flow',
      signedMillions(impact.fiscalDeltaMillions),
      direction(impact.fiscalDeltaMillions, true)
    )
  )
  return <>{chips}</>
}

export default function Timeline({
  changes = [],
  selected = 0,
  onSelect,
  histories,
  latestDecision,
  tick = 0,
}) {
  const whoColor = (c) => {
    if (!c.ok) return toneVar('crit')
    if (c.actor === 'ai') return toneVar('ai')
    if (c.actor === 'you') return toneVar('acc')
    return toneVar('ink4')
  }

  const whoLabel = (c) => {
    if (!c.ok) return 'Refused'
    if (c.actor === 'ai') return 'AI'
    if (c.actor === 'you') return 'You'
    return 'Auto'
  }

  const aiAcceptedCount = changes.filter(
    (c) => c.actor === 'ai' && c.ok
  ).length
  const aiRefusedCount = changes.filter((c) => !c.ok).length
  const manualCount = changes.filter((c) => c.actor === 'you').length
  const autoCount = changes.filter((c) => c.actor === 'auto').length

  const nextReviewTick = latestDecision?.appliedTick
    ? latestDecision.appliedTick + DECISION_INTERVAL
    : tick > 0
      ? Math.ceil(tick / DECISION_INTERVAL) * DECISION_INTERVAL
      : DECISION_INTERVAL

  return (
    <div style={{ display: 'flex', flexDirection: 'column', minHeight: 0 }}>
      <div className="ttl">
        <h4 style={{ fontSize: 14 }}>Policy timeline</h4>
        <span className="legend">
          <span>
            <i
              style={{
                background: 'var(--ai)',
                width: 8,
                height: 8,
                borderRadius: '50%',
              }}
            />
            AI
          </span>
          <span>
            <i
              style={{
                background: 'var(--acc)',
                width: 8,
                height: 8,
                borderRadius: '50%',
              }}
            />
            You
          </span>
          <span>
            <i
              style={{
                background: 'var(--ink4)',
                width: 8,
                height: 8,
                borderRadius: '50%',
              }}
            />
            Auto
          </span>
        </span>
      </div>

      <div className="tlwrap" style={{ flex: 1, overflowY: 'auto' }}>
        {changes.length === 0 ? (
          <div
            className="muted"
            style={{ fontSize: 12, padding: '16px 0', color: 'var(--ink4)' }}
          >
            No policy changes this run. Every lever below is yours to move.
          </div>
        ) : (
          changes.map((change, index) => {
            const actor = change.actor || classifyActor(change.reason)
            const cWithActor = { ...change, actor }
            const col = whoColor(cWithActor)
            const label = whoLabel(cWithActor)
            const key = change.policy || change.key || 'policy'
            const id = `${change.tick}:${key}`
            const prev = change.previous ?? parsePreviousValue(change.reason)
            const isSelected = selected != null && (selected === id || selected === index)

            const headline = change.ok
              ? `${leverLabel(key)} ${prev != null ? `${formatLeverValue(key, prev)} → ` : ''}${formatLeverValue(key, change.value)}`
              : `${leverLabel(key)} ${change.value !== undefined ? formatLeverValue(key, change.value) : ''}`

            const narrative = change.ok
              ? changeNarrative(change.reason) ||
                (actor === 'you'
                  ? 'Manual change from the console.'
                  : 'Automatic adjustment.')
              : change.reason ||
                'Blocked by the fiscal guard. The economy never saw it.'

            return (
              <div
                key={`${change.tick}-${key}-${index}`}
                className={`tlc${isSelected ? ' on' : ''}`}
                style={{ '--tlc': col, cursor: 'pointer' }}
                onClick={() => onSelect?.(id, index)}
              >
                <div>
                  <div className="tk">t{change.tick}</div>
                  <div className="ac" style={{ color: col }}>
                    {label}
                  </div>
                </div>
                <div style={{ minWidth: 0 }}>
                  <div className="tb">{headline}</div>
                  <div className="td">{narrative}</div>
                  {change.ok && (
                    <div style={{ marginTop: 6 }}>
                      <ImpactChips impact={impactSince(change.tick, histories)} />
                    </div>
                  )}
                </div>
              </div>
            )
          })
        )}
      </div>

      <div className="ttl" style={{ marginTop: 'auto', paddingTop: 8 }}>
        <h4>This run</h4>
        <small>{changes.length} {changes.length === 1 ? 'change' : 'changes'}</small>
      </div>
      <KeyValue label="AI accepted" value={aiAcceptedCount} tone="good" />
      <KeyValue label="AI refused" value={aiRefusedCount} tone="crit" />
      <KeyValue label="Manual" value={manualCount} />
      <KeyValue label="Automatic" value={autoCount} />
      <KeyValue label="Next AI review" value={`t${nextReviewTick}`} />
    </div>
  )
}
