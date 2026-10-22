import { COPY } from '../catalog.js'
import { moments } from '../narration.js'
import '../next.css'

function Chips({ list }) {
  return list.map(moment => (
    <li key={moment.id} className="nx-moment" title={moment.text}>
      <i style={{ background: moment.color }} aria-hidden="true" />
      {moment.text}
    </li>
  ))
}

// What just happened, under the lead: up to three chips, newest first, each
// with its town's colour. A chip keeps its key while its moment lasts, so it
// fades in once. It is a polite log, so a screen reader reads each new chip,
// not the whole strip. The strip is as tall as the tallest row of chips the
// towns can show (`rows`, every week's chips), so the page below does not jump
// as moments come and go: hidden copies of those rows share the strip's one
// grid cell with this week's chips (spec section 6). With no rows it is one
// chip row tall. Live runs instead hold three fixed slots before any events
// arrive. Their room is bounded, independent of the history received.
export default function Moments({ arms, tick, rows = [], live = false }) {
  const list = moments(arms, tick)
  return (
    <div
      className={`nx-moments${live ? ' is-live' : ''}`}
      role="log"
      aria-live="polite"
      aria-atomic="false"
      aria-relevant="additions"
      aria-label={COPY.moments.label}
      data-stable="moments"
    >
      <ul><Chips list={list} /></ul>
      {!live && <div className="nx-moments-room" aria-hidden="true">
        {rows.map(row => <ul key={row.map(moment => moment.text).join('\n')}><Chips list={row} /></ul>)}
      </div>}
    </div>
  )
}
