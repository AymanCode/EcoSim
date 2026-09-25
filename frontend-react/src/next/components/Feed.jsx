import { COPY } from '../catalog.js'
import { eventsUpTo } from '../data/derive.js'
import { firmDisplayName } from '../names.js'
import { eventSentence, weekLabel } from '../narration.js'
import '../next.css'

// Newest first across towns. Within a week the towns take turns, so one busy
// town cannot crowd the others out.
export default function Feed({ arms, tick, limit = 8 }) {
  const rows = arms
    .flatMap((arm, order) => eventsUpTo(arm, tick, limit).map((event, rank) => ({ arm, event, order, rank })))
    .sort((a, b) => (b.event.tick - a.event.tick) || (a.rank - b.rank) || (a.order - b.order))
    .slice(0, limit)

  return (
    <section className="nx-sect">
      <h3>{COPY.feed.title} <span>{COPY.feed.subtitle}</span></h3>
      {rows.length === 0 ? (
        <p className="nx-empty">{COPY.feed.empty}</p>
      ) : (
        <ul className="nx-feed">
          {rows.map(({ arm, event }) => (
            <li key={`${arm.label}:${event.id}`} data-tick={event.tick}>
              <i style={{ background: arm.color }} aria-hidden="true" />
              <div>
                <span className="w">{COPY.feed.when(weekLabel(event.tick), arm.label)}</span>
                {eventSentence(event, { firmName: firm => firmDisplayName(arm.firmDirectory?.byId?.[firm.id] ?? firm) })}
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
