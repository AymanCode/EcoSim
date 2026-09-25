import { COPY } from '../catalog.js'
import { weekLabel } from '../narration.js'
import '../next.css'

// A town's socket dropped: the others are paused. A lost session cannot be
// resumed, so the choice is a fresh start from the same plan or a new set up.
export default function LostPanel({ town, tick, townCount, onRestart, onNewExperiment }) {
  const week = Number(tick) >= 1 ? weekLabel(tick) : null
  return (
    <section className="nx-lostp">
      <p className="nx-lostp-t" role="alert">{COPY.live.lost(town, week, townCount > 1)}</p>
      <div className="nx-endp-act">
        <button type="button" className="nx-abtn is-dark" onClick={onRestart}>{COPY.live.restart(townCount)}</button>
        <button type="button" className="nx-abtn" onClick={onNewExperiment}>{COPY.live.newSetup}</button>
      </div>
    </section>
  )
}
