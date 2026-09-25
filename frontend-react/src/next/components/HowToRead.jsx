import { COPY } from '../catalog.js'
import '../next.css'

// "**word**" in a catalog note becomes the bold lead-in.
function withBold(note) {
  return note.split(/\*\*(.+?)\*\*/).map((part, i) => (i % 2 ? <b key={i}>{part}</b> : part))
}

export default function HowToRead({ armCount = 2 }) {
  return (
    <section className="nx-sect">
      <h3>{COPY.howTo.title} <span>{COPY.howTo.subtitle}</span></h3>
      <ul className="nx-feed nx-howto">
        {COPY.howTo.notes(armCount).map(note => (
          <li key={note}>
            <i aria-hidden="true" />
            <div>{withBold(note)}</div>
          </li>
        ))}
      </ul>
    </section>
  )
}
