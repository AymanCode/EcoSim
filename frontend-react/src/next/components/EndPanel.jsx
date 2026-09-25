import { useId } from 'react'
import { COPY } from '../catalog.js'
import { verdict } from '../narration.js'
import '../next.css'

const YEAR = 52

// The end of a live run: the years are up, the verdict for the latest week,
// and a year more once every town has finished. While the viewer looks back
// at an earlier week (`following` false) it folds to a slim bar, so the
// latest verdict does not sit beside that week.
export default function EndPanel({
  phase, horizon, arms, tick, following = true, onFollow, onExtend, onNewExperiment,
}) {
  const titleId = useId()
  const finished = phase === 'finished'
  const addYear = (
    <button type="button" className="nx-abtn is-dark" disabled={!finished} onClick={() => onExtend(YEAR)}>{COPY.end.addYear}</button>
  )
  if (!following) {
    return (
      <section className="nx-endp is-slim" aria-labelledby={titleId}>
        <h2 id={titleId}>{COPY.end.up(horizon)}</h2>
        <div className="nx-endp-act">
          <button type="button" className="nx-abtn" onClick={onFollow}>{COPY.end.backToEnd}</button>
          {addYear}
        </div>
      </section>
    )
  }
  return (
    <section className="nx-endp" aria-labelledby={titleId}>
      <h2 id={titleId}>{COPY.end.up(horizon)}</h2>
      <p className="nx-endp-v">{verdict(arms, tick)}</p>
      {!finished && <p className="nx-endp-wait" role="status">{COPY.end.finishing}</p>}
      <div className="nx-endp-act">
        {addYear}
        <button type="button" className="nx-abtn" onClick={onNewExperiment}>{COPY.end.another}</button>
      </div>
    </section>
  )
}
