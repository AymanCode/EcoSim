import { COPY } from '../catalog.js'
import { moments } from '../narration.js'
import '../next.css'

// What just happened, under the lead: up to three chips, newest first, each
// with its town's colour. A chip keeps its key while its moment lasts, so it
// fades in once. Nothing at all when nothing happened.
export default function Moments({ arms, tick }) {
  const list = moments(arms, tick)
  if (!list.length) return null
  return (
    <div className="nx-moments" role="status" aria-label={COPY.moments.label}>
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
