import { COPY } from '../catalog.js'
import { moments } from '../narration.js'
import '../next.css'

// What just happened, under the lead: up to three chips, newest first, each
// with its town's colour. A chip keeps its key while its moment lasts, so it
// fades in once. The region is always there, one chip row tall even when
// empty, so the page below does not jump as moments come and go; it is a
// polite log, so a screen reader reads each new chip, not the whole strip.
export default function Moments({ arms, tick }) {
  const list = moments(arms, tick)
  return (
    <div className="nx-moments" role="log" aria-live="polite" aria-atomic="false" aria-relevant="additions" aria-label={COPY.moments.label}>
      <ul>
        {list.map(moment => (
          <li key={moment.id} className="nx-moment">
            <i style={{ background: moment.color }} aria-hidden="true" />
            {moment.text}
          </li>
        ))}
      </ul>
    </div>
  )
}
