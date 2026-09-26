import { COPY } from '../catalog.js'
import { countedAt, everMeasured } from '../data/derive.js'
import { countedNote } from '../narration.js'
import Card, { Bolded, TownName } from './Card.jsx'
import { isNumber } from './chartKit.js'
import '../next.css'

const TOP = 'topTenthShare'
const BOTTOM = 'bottomHalfShare'
const clampPercent = value => Math.min(100, Math.max(0, value))

// Out of every $100 saved in a town, as whole dollars that add up to 100:
// the poorest half and the richest tenth as counted, the next 40% the rest.
function split(arm, tick) {
  const top = countedAt(arm, TOP, tick)?.value
  const bottom = countedAt(arm, BOTTOM, tick)?.value
  if (!isNumber(top) || !isNumber(bottom)) return null
  const topDollars = Math.round(top)
  const bottomDollars = Math.round(bottom)
  return { bottom: bottomDollars, middle: 100 - topDollars - bottomDollars, top: topDollars }
}

// "Who holds the savings" (mockup 06): per town, one bar split into the
// poorest half, the next 40% and the richest tenth of households, out of every
// $100 saved, as last counted. A town missing either share says "Not measured
// in this run". Drawn for topTenthShare and bottomHalfShare together; it
// opens big on the richest tenth's share, with its group's numbers as chips.
export default function ShareBars({ arms, tick, onSeeBig, className = '' }) {
  const copy = COPY.numbers.shares
  const measured = everMeasured(arms, TOP) && everMeasured(arms, BOTTOM)
  const splits = arms.map(arm => split(arm, tick))
  const asOf = arms.map(arm => countedAt(arm, TOP, tick)?.asOfTick).find(Number.isFinite) ?? null

  let body
  if (!measured) body = <p className="nx-quiet">{COPY.numbers.notMeasured}</p>
  else if (!splits.some(Boolean)) body = <p className="nx-quiet">{COPY.numbers.noWeeks}</p>
  else {
    body = (
      <>
        <p className="def is-top">{copy.lead}</p>
        <div className="nx-vpair">
          {arms.map((arm, i) => {
            const parts = splits[i]
            return (
              <div className="nx-vpanel" key={arm.label}>
                <TownName arm={arm} />
                {parts ? (
                  <>
                    <div className="nx-sbar" aria-hidden="true">
                      {[parts.bottom, parts.middle, parts.top].map((dollars, k) => (dollars > 0
                        ? <b key={k} className={`is-part${k}`} style={{ width: `${clampPercent(dollars)}%`, background: arm.color }} />
                        : null))}
                    </div>
                    <p className="nx-vline"><Bolded parts={copy.line(parts.bottom, parts.middle, parts.top)} /></p>
                  </>
                ) : (
                  <p className="nx-quiet">{COPY.numbers.notMeasured}</p>
                )}
              </div>
            )
          })}
        </div>
        <p className="nx-foot">{countedNote(asOf)}</p>
      </>
    )
  }
  return <Card title={copy.title} metricKey={TOP} measured={measured} onSeeBig={onSeeBig} className={className}>{body}</Card>
}
