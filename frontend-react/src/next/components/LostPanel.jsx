import { COPY } from '../catalog.js'
import { weekLabel } from '../narration.js'
import '../next.css'

// A town's socket dropped, or (`crashed`) the server stopped its run with an
// error, whose text shows behind "Details:" (`detail`): the others are paused.
// A lost session cannot be resumed, so the choice is a fresh start from the
// same plan or a new set up. The fresh start uses the rules as set up, which
// it says once the town hall has changed any (`rulesChanged`).
export default function LostPanel({
  town, tick, townCount, crashed = false, detail = null, rulesChanged = false, onRestart, onNewExperiment,
}) {
  const week = Number(tick) >= 1 ? weekLabel(tick) : null
  const say = crashed ? COPY.live.crashed : COPY.live.lost
  return (
    <section className="nx-lostp">
      <p className="nx-lostp-t" role="alert">{say(town, week, townCount > 1)}</p>
      {detail && <p className="nx-detail">{COPY.app.detail(detail)}</p>}
      {rulesChanged && <p className="nx-lostp-n">{COPY.live.notRepeated}</p>}
      <div className="nx-endp-act">
        <button type="button" className="nx-abtn is-dark" onClick={onRestart}>{COPY.live.restart(townCount)}</button>
        <button type="button" className="nx-abtn" onClick={onNewExperiment}>{COPY.live.newSetup}</button>
      </div>
    </section>
  )
}
