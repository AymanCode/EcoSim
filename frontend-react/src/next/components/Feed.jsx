import { COPY } from '../catalog.js'
import { eventsUpTo } from '../data/derive.js'
import { firmDisplayName } from '../names.js'
import { eventGroupSentence, townWideSentence, weekLabel } from '../narration.js'
import '../next.css'

// A town's lines through `tick`, newest week first. Each week opens with a
// town-wide line when many people were hired or laid off, then its events,
// with events that share a type and text folded into one counted line. Stops
// after `limit` lines, finishing the week it is in so no line undercounts.
function linesFor(arm, tick, limit) {
  const events = eventsUpTo(arm, tick)
  const weeks = (arm.ticks ?? []).filter(week => week <= tick).reverse()
  const lines = []
  let next = 0
  for (const week of weeks) {
    if (lines.length >= limit) break
    const town = townWideSentence(arm.eventCounts?.[week])
    if (town) lines.push({ key: `town:${week}`, tick: week, town })
    const byKind = new Map()
    while (next < events.length && events[next].tick >= week) {
      const event = events[next]
      next += 1
      if (event.tick !== week) continue
      const kind = `${event.type}|${event.text ?? ''}`
      const line = byKind.get(kind)
      if (line) line.events.push(event)
      else {
        const fresh = { key: event.id, tick: week, events: [event] }
        byKind.set(kind, fresh)
        lines.push(fresh)
      }
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
            <li
              key={`${arm.label}:${line.key}`}
              className={line.town ? 'is-town' : undefined}
              data-tick={line.tick}
              data-count={line.events?.length ?? 0}
            >
              <i style={{ background: arm.color }} aria-hidden="true" />
              <div>
                <span className="w">{COPY.feed.when(weekLabel(line.tick), arm.label)}</span>
                {line.town ?? eventGroupSentence(line.events, { firmName: firm => firmDisplayName(arm.firmDirectory?.byId?.[firm.id] ?? firm) })}
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
