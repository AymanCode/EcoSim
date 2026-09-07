import TimeSeries from '../../charts/TimeSeries.jsx'
import { toneVar } from '../../charts/tones.js'
import { formatMillionsAdaptive, signedMillions } from '../../format.js'
import {
  changeNarrative,
  classifyActor,
  describeEvidenceAudit,
  formatLeverValue,
  leverLabel,
  parsePreviousValue,
} from '../../governmentInsights.js'

const lastSampleAtOrBefore = (series, tick) => {
  if (!Array.isArray(series)) return null
  let found = null
  for (const point of series) {
    if (Number(point?.tick) <= tick) found = point
    else break
  }
  return found
}

const lastSample = (series) =>
  Array.isArray(series) && series.length ? series[series.length - 1] : null

export default function EffectsPanel({
  change,
  histories,
  decision,
  latestDecision = decision,
  llmGov,
  tick = 0,
}) {
  if (!change) {
    return (
      <div
        className="effpane"
        style={{
          borderLeft: '1px solid var(--line)',
          paddingLeft: 14,
          minWidth: 0,
        }}
      >
        <div className="ttl">
          <h4 style={{ fontSize: 14 }}>Policy effects</h4>
          <small>no change selected</small>
        </div>
        <div
          className="muted"
          style={{ fontSize: 12, padding: '16px 0', color: 'var(--ink4)' }}
        >
          Select a policy change from the timeline to inspect its economic effects.
        </div>
      </div>
    )
  }

  const key = change.policy || change.key || 'policy'
  const prev = change.previous ?? parsePreviousValue(change.reason)
  const actor = change.actor || classifyActor(change.reason)
  const actorColor = !change.ok
    ? toneVar('crit')
    : actor === 'ai'
      ? toneVar('ai')
      : actor === 'you'
        ? toneVar('acc')
        : toneVar('ink4')
  const whoLabel = !change.ok
    ? 'Refused'
    : actor === 'ai'
      ? 'AI'
      : actor === 'you'
        ? 'You'
        : 'Auto'

  const effSeries = [
    {
      id: 'gdp',
      label: 'GDP output',
      tone: 'acc',
      data: histories?.gdp || [],
      fmt: formatMillionsAdaptive,
      formatDelta: (d) => `${d > 0 ? '+' : '-'}${formatMillionsAdaptive(Math.abs(d))}`,
      isGood: (d) => d > 0,
    },
    {
      id: 'unemp',
      label: 'Unemployment',
      tone: 's1',
      data: histories?.unemployment || [],
      fmt: (v) => `${Number(v).toFixed(1)}%`,
      formatDelta: (d) => `${d > 0 ? '+' : '-'}${Math.abs(d).toFixed(1)} pp`,
      isGood: (d) => d < 0,
    },
    {
      id: 'happy',
      label: 'Happiness',
      tone: 's2',
      data: histories?.happiness || [],
      fmt: (v) => Number(v).toFixed(1),
      formatDelta: (d) => `${d > 0 ? '+' : '-'}${Math.abs(d).toFixed(1)} pts`,
      isGood: (d) => d > 0,
    },
    {
      id: 'profit',
      label: 'Net fiscal flow',
      tone: 'good',
      data: histories?.fiscal || [],
      fmt: signedMillions,
      formatDelta: (d) => `${d > 0 ? '+' : '-'}${formatMillionsAdaptive(Math.abs(d))}`,
      isGood: (d) => d > 0,
    },
  ]

  const activeDecision = latestDecision ?? decision
  const appliedTick = activeDecision?.appliedTick ?? llmGov?.appliedTick
  const snapshotTick = activeDecision?.snapshotTick ?? llmGov?.snapshotTick
  const targetTick = appliedTick != null ? appliedTick : snapshotTick

  const isLatestDecision =
    actor === 'ai' &&
    targetTick != null &&
    change.tick != null &&
    Number(change.tick) === Number(targetTick)

  const evidence = Array.isArray(activeDecision?.evidence) ? activeDecision.evidence : []
  const audit = Array.isArray(activeDecision?.evidence_audit) ? activeDecision.evidence_audit : []
  const rationale =
    changeNarrative(change.reason) ||
    activeDecision?.rationale ||
    activeDecision?.reasoning ||
    activeDecision?.decision_summary ||
    ''


  return (
    <div
      className="effpane"
      style={{
        borderLeft: '1px solid var(--line)',
        paddingLeft: 14,
        minWidth: 0,
      }}
    >
      <div className="ttl">
        <h4 style={{ fontSize: 14 }}>
          {change.ok ? (
            <>
              Effects since t{change.tick} · <b>{leverLabel(key)}</b>
            </>
          ) : (
            <>
              Refused at t{change.tick} · <b>{leverLabel(key)}</b>
            </>
          )}
        </h4>
        <small>
          {change.ok
            ? `${whoLabel} · ${Math.max(0, tick - change.tick)} ticks of movement · not attribution`
            : 'no effect'}
        </small>
      </div>

      {change.ok ? (
        <div className="effgrid">
          {effSeries.map((s) => {
            const bPoint = lastSampleAtOrBefore(s.data, change.tick)
            const nPoint = lastSample(s.data)
            const b = bPoint?.value != null ? Number(bPoint.value) : null
            const n = nPoint?.value != null ? Number(nPoint.value) : null
            const d = b != null && n != null ? n - b : null
            const good = d != null ? s.isGood(d) : null

            return (
              <div key={s.id}>
                <div className="effh">
                  <span className="lbl">{s.label}</span>
                  <span className="mono" style={{ color: 'var(--ink)' }}>
                    {b == null ? '—' : s.fmt(b)}{' '}
                    <span className="muted">→</span> {n == null ? '—' : s.fmt(n)}
                    {d != null && (
                      <b
                        style={{
                          color: good ? 'var(--good)' : 'var(--crit)',
                          marginLeft: 6,
                        }}
                      >
                        {s.formatDelta(d)}
                      </b>
                    )}
                  </span>
                </div>
                <TimeSeries
                  series={[{ data: s.data, tone: s.tone }]}
                  format={s.fmt}
                  axes={false}
                  n={170}
                  split={{ tick: change.tick, color: actorColor }}
                  height={110}
                />
              </div>
            )
          })}
        </div>
      ) : (
        <div
          className="muted"
          style={{ fontSize: 12, padding: '10px 0', color: 'var(--ink3)' }}
        >
          The fiscal guard blocked this change, so the economy never saw it.
          The charts on the left show the accepted changes instead.
        </div>
      )}

      {isLatestDecision && (
        <div style={{ marginTop: 10 }}>
          <div className="lbl">What the model argued</div>
          {rationale && (
            <p className="quote" style={{ margin: '6px 0' }}>
              {rationale}
            </p>
          )}
          {evidence.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              {evidence.map((item, index) => {
                const entry =
                  audit[index] && audit[index].evidence === item
                    ? audit[index]
                    : audit.find((a) => a.evidence === item) || {}
                const verdict = describeEvidenceAudit(entry)
                return (
                  <div
                    key={`${item}-${index}`}
                    style={{
                      display: 'flex',
                      gap: 8,
                      alignItems: 'center',
                      fontSize: 11.5,
                      padding: '2px 0',
                    }}
                  >
                    <span
                      className={`audit ${verdict.mark === 'matched' ? 'ok' : verdict.mark === 'mismatch' ? 'bad' : ''}`}
                    >
                      {verdict.mark}
                    </span>
                    <span className="mono" style={{ color: 'var(--ink2)' }}>
                      {item}
                    </span>
                    <span
                      className="muted"
                      style={{ marginLeft: 'auto', fontSize: 10.5 }}
                    >
                      {verdict.note}
                    </span>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      )}



      <div
        style={{
          marginTop: 10,
          display: 'flex',
          gap: 6,
          flexWrap: 'wrap',
          alignItems: 'center',
        }}
      >
        <span className="lbl">Lever moved</span>
        <span className="pill" style={{ color: actorColor }}>
          <i style={{ background: actorColor }} />
          {leverLabel(key)} ·{' '}
          {prev != null ? `${formatLeverValue(key, prev)} → ` : ''}
          {formatLeverValue(key, change.value)}
        </span>
      </div>
    </div>
  )
}
