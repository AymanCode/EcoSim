import { COPY, METRICS, formatMetric } from '../catalog.js'
import { everMeasured, valueAt } from '../data/derive.js'
import Card, { TownName } from './Card.jsx'
import { isNumber } from './chartKit.js'
import '../next.css'

const KEY = 'happiness'
const clampPercent = value => Math.min(100, Math.max(0, value))

// How people feel (mockup 06): a meter from 0 to 100 per town, filled to
// this week's average happiness, with a mark where the town started (its
// first recorded week) and the meaning above. It opens big on the whole run.
export default function FeelMeter({ arms, tick, onSeeBig, className = '' }) {
  const metric = METRICS[KEY]
  const measured = everMeasured(arms, KEY)
  const values = arms.map(arm => valueAt(arm, KEY, tick))
  const starts = arms.map(arm => (arm.series?.[KEY] ?? []).find(isNumber) ?? null)
  const startWords = starts.every(isNumber) ? COPY.numbers.feel.started(arms.map(arm => arm.label), starts.map(Math.round)) : null

  let body
  if (!measured) body = <p className="nx-quiet">{COPY.numbers.notMeasured}</p>
  else if (!values.some(isNumber)) body = <p className="nx-quiet">{COPY.numbers.noWeeks}</p>
  else {
    body = (
      <>
        <p className="def is-top">{metric.meaning}</p>
        <ul className="nx-meters">
          {arms.map((arm, i) => (
            <li key={arm.label} className="nx-meter-row">
              <TownName arm={arm} />
              <span className="nx-meter" aria-hidden="true">
                {[25, 50, 75].map(at => <i key={at} className="nx-meter-tick" style={{ left: `${at}%` }} />)}
                {isNumber(values[i]) && <span className="nx-meter-fill" style={{ width: `${clampPercent(values[i])}%`, background: arm.color }} />}
                {isNumber(starts[i]) && <span className="nx-meter-start" style={{ left: `${clampPercent(starts[i])}%` }} />}
              </span>
              <b className="nx-meter-v">{isNumber(values[i]) ? formatMetric(KEY, values[i]) : COPY.numbers.notMeasured}</b>
            </li>
          ))}
          <li className="nx-meter-row is-scale" aria-hidden="true">
            <span />
            <span className="nx-meter-scale"><span>0</span><span>50</span><span>100</span></span>
            <span />
          </li>
        </ul>
        {startWords && <p className="nx-foot">{startWords}</p>}
      </>
    )
  }
  return <Card title={metric.name} metricKey={KEY} measured={measured} onSeeBig={onSeeBig} className={className}>{body}</Card>
}
