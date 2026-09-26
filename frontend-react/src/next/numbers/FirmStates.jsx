import { COPY } from '../catalog.js'
import { everMeasured, firmStatesAt } from '../data/derive.js'
import Card, { Bolded, SwatchKey, TownName } from './Card.jsx'
import '../next.css'

const STATES = ['growing', 'steady', 'struggling']

// "How they are doing" (mockup 06): per town, the open businesses as one
// stacked bar, growing, steady and struggling, its length set by how many are
// open against the town with the most; the counts are written underneath. It
// opens big on the growing businesses, with the three counts as chips.
export default function FirmStates({ arms, tick, onSeeBig, className = '' }) {
  const copy = COPY.numbers.states
  const measured = ['firmsGrowing', 'firmsSteady', 'firmsStruggling'].every(key => everMeasured(arms, key))
  const counts = arms.map(arm => firmStatesAt(arm, tick))
  const open = counts.map(states => (states ? STATES.reduce((sum, state) => sum + states[state], 0) : null))
  const most = Math.max(1, ...open.filter(count => count !== null))

  let body
  if (!measured) body = <p className="nx-quiet">{COPY.numbers.notMeasured}</p>
  else if (!counts.some(Boolean)) body = <p className="nx-quiet">{COPY.numbers.noWeeks}</p>
  else {
    body = (
      <>
        <p className="def is-top">{copy.lead}</p>
        <SwatchKey items={STATES.map(state => ({ label: copy[state], className: `is-${state}` }))} />
        <div className="nx-vbars">
          {arms.map((arm, i) => {
            const states = counts[i]
            return (
              <div className="nx-vpanel" key={arm.label}>
                <TownName arm={arm}>{states && <span> {copy.open(open[i])}</span>}</TownName>
                {states ? (
                  <>
                    <div className="nx-sbar" style={{ width: `${(open[i] / most) * 100}%` }} aria-hidden="true">
                      {STATES.filter(state => states[state] > 0).map(state => (
                        <b key={state} className={`is-${state}`} style={{ width: `${(states[state] / open[i]) * 100}%` }} />
                      ))}
                    </div>
                    <p className="nx-vline"><Bolded parts={copy.line(states.growing, states.steady, states.struggling)} /></p>
                  </>
                ) : (
                  <p className="nx-quiet">{COPY.numbers.notMeasured}</p>
                )}
              </div>
            )
          })}
        </div>
      </>
    )
  }
  return <Card title={copy.title} metricKey="firmsGrowing" measured={measured} onSeeBig={onSeeBig} className={className}>{body}</Card>
}
