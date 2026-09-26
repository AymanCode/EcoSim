import { COPY } from '../catalog.js'
import { countedAt, everMeasured } from '../data/derive.js'
import { countedNote } from '../narration.js'
import Card, { Bolded, TownName } from './Card.jsx'
import { isNumber } from './chartKit.js'
import '../next.css'

const TOP = 'topTenthShare'
const BOTTOM = 'bottomHalfShare'
// Float noise in the server's percentages, not a real share.
const NOISE = 1e-6

// Whole dollars out of $100 that add up to exactly 100: each share rounded
// down, then the dollars left over go to the largest remainders.
function wholeDollars(raw) {
  const dollars = raw.map(Math.floor)
  let left = 100 - dollars.reduce((sum, value) => sum + value, 0)
  const order = raw.map((value, i) => ({ i, rest: value - dollars[i] })).sort((a, b) => b.rest - a.rest || a.i - b.i)
  for (const { i } of order) {
    if (left <= 0) break
    dollars[i] += 1
    left -= 1
  }
  return dollars
}

// How a town's savings split at the last count, out of every $100: the
// poorest half and the richest tenth as counted, the next 40% the rest.
// Null when either share is missing. { none } when households' cash adds up
// to nothing or less (the server sends both shares as 0); { owing } when a
// group's share is below zero, which means some households owe more than
// they have and the split cannot be drawn as parts of $100.
function split(arm, tick) {
  const top = countedAt(arm, TOP, tick)?.value
  const bottom = countedAt(arm, BOTTOM, tick)?.value
  if (!isNumber(top) || !isNumber(bottom)) return null
  if (Math.abs(top) <= NOISE && Math.abs(bottom) <= NOISE) return { none: true }
  const middle = 100 - top - bottom
  if (top < -NOISE || bottom < -NOISE || middle < -NOISE) return { owing: true }
  const [bottomDollars, middleDollars, topDollars] = wholeDollars([bottom, middle, top].map(value => Math.max(0, value)))
  return { bottom: bottomDollars, middle: middleDollars, top: topDollars }
}

// "Who holds the savings" (mockup 06): per town, one bar split into the
// poorest half, the next 40% and the richest tenth of households, out of every
// $100 saved, as last counted. A town missing either share says "Not measured
// in this run", and one whose savings cannot be split into parts of $100
// says why instead. Drawn for topTenthShare and bottomHalfShare together; it
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
                {!parts && <p className="nx-quiet">{COPY.numbers.notMeasured}</p>}
                {parts?.none && <p className="nx-quiet">{copy.none}</p>}
                {parts?.owing && <p className="nx-quiet">{copy.owing}</p>}
                {parts && !parts.none && !parts.owing && (
                  <>
                    <div className="nx-sbar" aria-hidden="true">
                      {[parts.bottom, parts.middle, parts.top].map((dollars, k) => (dollars > 0
                        ? <b key={k} className={`is-part${k}`} style={{ width: `${dollars}%`, background: arm.color }} />
                        : null))}
                    </div>
                    <p className="nx-vline"><Bolded parts={copy.line(parts.bottom, parts.middle, parts.top)} /></p>
                  </>
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
