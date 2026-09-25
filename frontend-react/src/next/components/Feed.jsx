import { COPY } from '../catalog.js'
import { eventsUpTo } from '../data/derive.js'
import { firmDisplayName } from '../names.js'
import { eventGroupSentence, weekLabel } from '../narration.js'
import '../next.css'

// A town's events through `tick`, newest first, with events that share a type
// and text within one week folded into one line. Stops after `limit` lines,
// finishing the week it is in so no line undercounts.
function linesFor(arm, tick, limit) {
  const lines = []
  let week = null
  let byKind = new Map()
  for (const event of eventsUpTo(arm, tick)) {
    if (event.tick !== week) {
      if (lines.length >= limit) break
      week = event.tick
      byKind = new Map()
    }
    const kind = `${event.type}|${event.text ?? ''}`
    const line = byKind.get(kind)
    if (line) line.events.push(event)
    else {
      const next = { tick: event.tick, events: [event] }
      byKind.set(kind, next)
      lines.push(next)
    }
  }
  return lines.slice(0, limit)
}

// Newest first across towns. Within a week the towns take turns, so one busy
// town cannot crowd the others out.
export default function Feed({ arms, tick, limit = 8 }) {
  const rows = arms
    .flatMap((arm, order) => linesFor(arm, tick, limit).map((line, rank) => ({ arm, line, order, rank })))
    .sort((a, b) => (b.line.tick - a.line.tick) || (a.rank - b.rank) || (a.order - b.order))
    .slice(0, limit)

  return (
    <section className="nx-sect">
      <h3>{COPY.feed.title} <span>{COPY.feed.subtitle}</span></h3>
      {rows.length === 0 ? (
        <p className="nx-empty">{COPY.feed.empty}</p>
      ) : (
        <ul className="nx-feed">
          {rows.map(({ arm, line }) => (
            <li key={`${arm.label}:${line.events[0].id}`} data-tick={line.tick} data-count={line.events.length}>
              <i style={{ background: arm.color }} aria-hidden="true" />
              <div>
                <span className="w">{COPY.feed.when(weekLabel(line.tick), arm.label)}</span>
                {eventGroupSentence(line.events, { firmName: firm => firmDisplayName(arm.firmDirectory?.byId?.[firm.id] ?? firm) })}
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
