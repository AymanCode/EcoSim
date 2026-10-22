import { useMemo } from 'react'
import { COPY, describePolicy, householdsPerHouse } from '../catalog.js'
import { commonTicks, rulesAt, rulesDiff, valueAt } from '../data/derive.js'
import StableText from './StableText.jsx'
import '../next.css'

// "**word**" in a catalog note becomes the bold lead-in.
function withBold(note) {
  return note.split(/\*\*(.+?)\*\*/).map((part, i) => (i % 2 ? <b key={i}>{part}</b> : part))
}

const escapes = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }
const boldMarkup = note => note.replace(/[&<>"']/g, char => escapes[char]).replace(/\*\*(.+?)\*\*/g, '<b>$1</b>')

function notesAt(arms, tick) {
  const [first] = arms
  const total = valueAt(first, 'householdsTotal', tick) ?? first?.setup?.num_households ?? null
  return COPY.howTo.notes({
    armCount: arms.length,
    perHouse: householdsPerHouse(total),
    // The first town's rules in force at the week shown, as its title names them.
    firstPolicy: describePolicy(first ? rulesDiff(rulesAt(first, tick)) : null),
  })
}

export default function HowToRead({ arms = [], tick = 1 }) {
  const notes = notesAt(arms, tick)
  // Include every historical policy description before a scrub can show it.
  // Live arms grow in place; their week count invalidates the reservation.
  const ticksKey = arms.map(arm => arm.ticks.length).join(',')
  const candidates = useMemo(() => {
    const weeks = commonTicks(arms)
    const all = (weeks.length ? weeks : [1]).map(week => notesAt(arms, week))
    return Array.from({ length: 4 }, (_, i) => [...new Set(all.map(row => row[i]))])
  }, [arms, ticksKey]) // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <section className="nx-sect">
      <h3>{COPY.howTo.title} <span>{COPY.howTo.subtitle}</span></h3>
      <ul className="nx-feed nx-howto">
        {notes.map((note, i) => (
          <li key={i}>
            <i aria-hidden="true" />
            <StableText as="div" texts={candidates[i]} markup={boldMarkup} stable={`howto:${i}`}>
              {withBold(note)}
            </StableText>
          </li>
        ))}
      </ul>
    </section>
  )
}
