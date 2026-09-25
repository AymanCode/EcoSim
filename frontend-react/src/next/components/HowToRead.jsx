import { COPY, describePolicy, householdsPerHouse } from '../catalog.js'
import { rulesAt, rulesDiff, valueAt } from '../data/derive.js'
import '../next.css'

// "**word**" in a catalog note becomes the bold lead-in.
function withBold(note) {
  return note.split(/\*\*(.+?)\*\*/).map((part, i) => (i % 2 ? <b key={i}>{part}</b> : part))
}

export default function HowToRead({ arms = [], tick = 1 }) {
  const [first] = arms
  const total = valueAt(first, 'householdsTotal', tick) ?? first?.setup?.num_households ?? null
  const notes = COPY.howTo.notes({
    armCount: arms.length,
    perHouse: householdsPerHouse(total),
    // The first town's rules in force at the week shown, as its title names them.
    firstPolicy: describePolicy(first ? rulesDiff(rulesAt(first, tick)) : null),
  })
  return (
    <section className="nx-sect">
      <h3>{COPY.howTo.title} <span>{COPY.howTo.subtitle}</span></h3>
      <ul className="nx-feed nx-howto">
        {notes.map(note => (
          <li key={note}>
            <i aria-hidden="true" />
            <div>{withBold(note)}</div>
          </li>
        ))}
      </ul>
    </section>
  )
}
