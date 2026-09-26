import { useId } from 'react'
import {
  COPY, COUNTED_EVERY_5, GLANCE_KEYS, METRICS, NO_CHANGES, describePolicy, formatEndLabel, formatMetric,
} from '../catalog.js'
import { countedAt, everMeasured, rangeSoFar, rulesAt, rulesDiff, valueAt } from '../data/derive.js'
import { countedNote, differencePhrase, weekLabel } from '../narration.js'
import '../next.css'

const position = (value, range) => {
  if (!(range.max > range.min)) return 50
  return Math.min(100, Math.max(0, ((value - range.min) / (range.max - range.min)) * 100))
}

// Where each town's value sits between the lowest and highest any town has
// shown since setting up (rangeSoFar), one dot per town.
function DotTrack({ metricKey, arms, tick }) {
  const range = rangeSoFar(arms, metricKey, tick)
  const readings = arms.map(arm => ({ arm, value: valueAt(arm, metricKey, tick) })).filter(item => item.value !== null)
  if (!range || !readings.length) return <span className="nx-dbw">{COPY.numbers.glance.trackWait}</span>
  const at = readings.map(item => position(item.value, range))
  const low = formatEndLabel(metricKey, range.min)
  const high = formatEndLabel(metricKey, range.max)
  const flat = !(range.max > range.min)
  const towns = readings.map((item, i) => ({
    label: item.arm.label,
    value: formatMetric(metricKey, item.value),
    where: COPY.numbers.glance.where(at[i], flat),
  }))
  return (
    <>
      <div aria-hidden="true">
        <div className="nx-dbt">
          <span className="nx-dbseg" style={{ left: `${Math.min(...at)}%`, width: `${Math.max(...at) - Math.min(...at)}%` }} />
          {readings.map((item, i) => <span key={item.arm.label} className="nx-dot" style={{ left: `${at[i]}%`, background: item.arm.color }} />)}
        </div>
        <div className="nx-dbe"><span>{low}</span><span>{high}</span></div>
      </div>
      <span className="nx-sr">{COPY.numbers.glance.trackAlt(low, high, towns)}</span>
    </>
  )
}

function GlanceRow({ metricKey, arms, tick }) {
  const metric = METRICS[metricKey] ?? { name: metricKey, meaning: '' }
  const measured = everMeasured(arms, metricKey)
  const values = arms.map(arm => valueAt(arm, metricKey, tick))
  const counted = COUNTED_EVERY_5.includes(metricKey)
  const asOf = counted ? arms.map(arm => countedAt(arm, metricKey, tick)?.asOfTick).find(Number.isFinite) ?? null : null
  const baseLabel = arms[0]?.label

  return (
    <div className="nx-srow" role="row">
      <div className="nx-sname" role="rowheader">
        <b>{metric.name}</b>
        <small>{metric.meaning}</small>
        {measured && counted && <small className="nx-foot">{countedNote(asOf)}</small>}
      </div>
      {measured ? arms.map((arm, i) => {
        const phrase = i > 0 ? differencePhrase(metricKey, values[i], values[0], { tick, baseLabel }) : null
        return (
          <div className="nx-sval" role="cell" key={arm.label}>
            <span className="nx-mlab" aria-hidden="true">{arm.label}</span>
            <span className="nx-sv"><i style={{ background: arm.color }} aria-hidden="true" />{formatMetric(metricKey, values[i])}</span>
            {phrase && <span className="nx-diff">{phrase}</span>}
          </div>
        )
      }) : (
        <div className="nx-sval is-none" role="cell" aria-colspan={arms.length} style={{ gridColumn: `span ${arms.length}` }}>
          {COPY.numbers.notMeasured}
        </div>
      )}
      <div className="nx-db" role="cell">
        {measured && <DotTrack metricKey={metricKey} arms={arms} tick={tick} />}
      </div>
    </div>
  )
}

// This week's headline numbers (GLANCE_KEYS), one row each: the name and
// meaning, every town's value, how each town after the first differs from it
// (in neutral words), and where this week sits in the range seen so far.
// `notes[i]` goes under town i's column head (a live town's lost connection).
export default function AtAGlance({ arms, tick, id, notes = [] }) {
  const uid = useId().replace(/:/g, '')
  const titleId = `nx-glance-${uid}`
  const labels = arms.map(arm => arm.label)
  const firstUnchanged = arms.length > 0 && describePolicy(rulesDiff(rulesAt(arms[0], tick))) === NO_CHANGES

  return (
    <section id={id} className="nx-nsec" aria-labelledby={titleId}>
      <div className="nx-sh">
        <h3 id={titleId} tabIndex={-1}>{COPY.numbers.glance.title}</h3>
        <p>{COPY.numbers.glance.lead(weekLabel(tick), labels, firstUnchanged)}</p>
      </div>
      <div className="nx-scroll">
        <div className="nx-glance" role="table" aria-labelledby={titleId} style={{ '--nx-towns': arms.length }}>
          <div className="nx-srow is-head" role="row">
            <span className="nx-sname" role="columnheader"><span className="nx-sr">{COPY.numbers.glance.number}</span></span>
            {arms.map((arm, i) => (
              <span className="nx-sval" role="columnheader" key={arm.label}>
                <span className="nx-shead"><i style={{ background: arm.color }} aria-hidden="true" />{arm.label}</span>
                {notes[i] && <small>{notes[i]}</small>}
              </span>
            ))}
            <span className="nx-db" role="columnheader">{COPY.numbers.glance.track(arms.length)}</span>
          </div>
          {GLANCE_KEYS.map(key => <GlanceRow key={key} metricKey={key} arms={arms} tick={tick} />)}
        </div>
      </div>
    </section>
  )
}
