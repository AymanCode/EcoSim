// One town's card on the Run screen: its name, the rules in force, how it is
// doing (the mood chip), the diorama for the week on the clock, four facts,
// and a summary list for screen readers (the drawing is aria-hidden). Every
// part keeps its size as the week changes (spec section 6): the header stays
// on one line, the mood chip and the button have fixed widths, the drawing a
// fixed aspect ratio, each value one line and each label a two-line area.
// While the run plays, the drawing moves between weeks (useSceneMotion);
// `scrubs` counts the viewer's moves on the timeline, so a week reached by
// scrubbing is never taken for a step forward.
import { useId, useMemo, useState } from 'react'
import { COPY, NOT_MEASURED, describePolicy, formatMetric, formatMoneyShort } from '../catalog.js'
import { rulesAt, rulesDiff, snapshotAt } from '../data/derive.js'
import Diorama from './Diorama.jsx'
import { townAt } from './model.js'
import './town.css'

const D = COPY.diorama

// The chip's little weather picture for each mood (mockup 08's MOOD_ICON).
function MoodIcon({ band }) {
  return (
    <svg viewBox="0 0 18 18" aria-hidden="true" focusable="false">
      {band === 'thriving' && (
        <>
          <circle cx={9} cy={9} r={3.6} fill="#F2A93B" />
          <path d="M9 1.8v1.8M9 14.4v1.8M1.8 9h1.8M14.4 9h1.8M3.9 3.9l1.3 1.3M12.8 12.8l1.3 1.3M3.9 14.1l1.3-1.3M12.8 5.2l1.3-1.3" stroke="#F2A93B" strokeWidth={1.4} strokeLinecap="round" />
        </>
      )}
      {band === 'okay' && (
        <>
          <circle cx={7} cy={7} r={3.2} fill="#F2A93B" />
          <path d="M6 14.5h7.5a3 3 0 0 0 .2-6 4 4 0 0 0-7.6 1A2.6 2.6 0 0 0 6 14.5z" fill="#fff" stroke="#9AA58A" strokeWidth={1.1} />
        </>
      )}
      {band === 'struggling' && (
        <path d="M4.5 13.5h9a3.3 3.3 0 0 0 .2-6.6 4.4 4.4 0 0 0-8.4 1.1A2.8 2.8 0 0 0 4.5 13.5z" fill="#C9CED6" stroke="#7D8796" strokeWidth={1.1} />
      )}
      {band === 'hard' && (
        <>
          <path d="M4.5 10.5h9a3.3 3.3 0 0 0 .2-6.6 4.4 4.4 0 0 0-8.4 1.1A2.8 2.8 0 0 0 4.5 10.5z" fill="#8F9BAD" stroke="#55627A" strokeWidth={1.1} />
          <path d="M6 12.5l-1 3M9.5 12.5l-1 3M13 12.5l-1 3" stroke="#55627A" strokeWidth={1.2} strokeLinecap="round" />
        </>
      )}
    </svg>
  )
}

// Out of work, typical weekly pay, shops open (and how many struggle), and
// the town hall's money (red when it owes). An unmeasured figure reads "not
// measured".
function factsOf({ out, pay, open, struggling, hallCash }) {
  const known = Number.isFinite(hallCash)
  const owes = known && hallCash < 0
  return [
    { key: 'out', value: formatMetric('peopleOutOfWorkPer100', out), label: COPY.town.outOfWork },
    { key: 'pay', value: formatMetric('typicalWeeklyPay', pay), label: COPY.town.typicalPay },
    { key: 'shops', value: String(open), label: D.facts.shops(struggling) },
    { key: 'hall', value: known ? formatMoneyShort(Math.abs(hallCash)) : NOT_MEASURED, label: D.facts.hall(owes), owes },
  ]
}

export default function TownCard({
  arm: armNow, tick: tickNow, focused = false, canFocus = false, onFocus, towns = 1, hidden = false, playing = false, speed = 1, scrubs = 0, children,
}) {
  // A card hidden by Enlarge keeps the week it showed when it was hidden and
  // does no work (no model, no weather, no motion) until it is shown again.
  const [frozen, setFrozen] = useState(null)
  if (hidden !== (frozen !== null)) setFrozen(hidden ? { arm: armNow, tick: tickNow, weeks: armNow.ticks.length } : null)
  const { arm, tick, weeks } = frozen ?? { arm: armNow, tick: tickNow, weeks: armNow.ticks.length }
  // An arm's weeks grow in place (data/session.js), so the model is memoised
  // on the week count too, as RunScreen memoises its weeks; never on the
  // identity of the arm's inner arrays or the lots map.
  const model = useMemo(() => townAt(arm, tick), [arm, tick, weeks]) // eslint-disable-line react-hooks/exhaustive-deps
  const titleId = useId()
  const rules = describePolicy(rulesDiff(rulesAt(arm, tick)))
  const closed = snapshotAt(arm, tick)?.firmsClosed?.length ?? 0
  const { counts, facts } = model

  return (
    <article className="nx-card lt-card" data-stable={`town-${arm.label}`} hidden={hidden}>
      <header className="lt-head">
        <i className="lt-dot" style={{ background: arm.color }} aria-hidden="true" />
        <h2 id={titleId}>{arm.label}</h2>
        <span className="lt-rules" title={rules}>{rules}</span>
        <span className={`lt-mood is-${model.band}`}>
          <MoodIcon band={model.band} />
          <span>{D.moods[model.band]}</span>
        </span>
        {canFocus && (
          <button type="button" className="lt-focus" onClick={onFocus} aria-describedby={titleId}>
            {focused ? D.showAll(towns) : D.enlarge}
          </button>
        )}
      </header>
      <div className="lt-canvas">
        <Diorama model={model} color={arm.color} playing={playing} speed={speed} towns={towns} scrubs={scrubs} hidden={hidden} />
        {children}
      </div>
      <dl className="lt-facts">
        {factsOf(facts).map(fact => (
          <div key={fact.key}>
            <dt data-fits="town-fact">{fact.label}</dt>
            <dd className={fact.owes ? 'is-owed' : undefined} title={fact.value}>{fact.value}</dd>
          </div>
        ))}
      </dl>
      <ul className="nx-sr">
        <li>{COPY.town.altHouses(counts.work, counts.look, counts.home)}</li>
        <li>{COPY.town.altFirms(facts.open, facts.struggling, closed)}</li>
        <li>{D.summary.mood(model.band)}</li>
        <li>{D.summary.weather(model.season, model.band)}</li>
        {model.overflow > 0 && <li>{D.summary.overflow(model.overflow)}</li>}
        {model.hall.changedTick != null && <li>{COPY.town.hallChanged}</li>}
      </ul>
    </article>
  )
}
