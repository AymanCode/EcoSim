import { COPY, formatMoney } from '../catalog.js'
import { cumulativeUpTo, everMeasured, seriesUpTo, valueAt } from '../data/derive.js'
import { weekLabel } from '../narration.js'
import Card, { TownName, Values } from './Card.jsx'
import { isNumber } from './chartKit.js'
import '../next.css'

const KEY = 'bankDefaultAmountThisTick'
const COUNT = 'bankDefaultsTotal'

// "Loans written off so far" (mockup 06): per town, the money the bank wrote
// off, added up since week 1 (cumulativeUpTo), drawn as a pile of blocks, one
// per week it wrote money off, on a length shared by every town. The runs
// recorded so far keep no count of unpaid loans: when that count is missing it
// says so, and when a run has it, it gives it.
export default function LoansWrittenOff({ arms, tick, className = '' }) {
  const copy = COPY.numbers.writtenOff
  const measured = everMeasured(arms, KEY)
  const totals = arms.map(arm => cumulativeUpTo(arm, KEY, tick))
  const weeks = arms.map(arm => seriesUpTo(arm, KEY, tick).filter(point => isNumber(point.value) && point.value > 0))
  const most = Math.max(0, ...totals.filter(isNumber))
  const counted = everMeasured(arms, COUNT)
  const counts = arms.map(arm => valueAt(arm, COUNT, tick))

  let body
  if (!measured) body = <p className="nx-quiet">{COPY.numbers.notMeasured}</p>
  else if (!totals.some(isNumber)) body = <p className="nx-quiet">{COPY.numbers.noWeeks}</p>
  else {
    body = (
      <>
        <Values arms={arms} texts={totals.map(value => (isNumber(value) ? formatMoney(value) : COPY.numbers.notMeasured))} />
        {most > 0 ? (
          <div className="nx-piles" aria-hidden="true">
            {arms.map((arm, i) => (
              <div className="nx-pile-row" key={arm.label}>
                <TownName arm={arm} />
                <span className="nx-pile-track">
                  <span className="nx-pile" style={{ width: `${((totals[i] ?? 0) / most) * 100}%` }}>
                    {weeks[i].map(point => (
                      <b key={point.tick} style={{ width: `${(point.value / totals[i]) * 100}%`, background: arm.color }} />
                    ))}
                  </span>
                </span>
              </div>
            ))}
          </div>
        ) : (
          <p className="nx-quiet">{copy.none(arms.length)}</p>
        )}
        <p className="nx-sr">
          {arms.map((arm, i) => (isNumber(totals[i])
            ? copy.alt(arm.label, formatMoney(totals[i]), weeks[i].map(point => copy.weekAmount(weekLabel(point.tick), formatMoney(point.value))))
            : `${arm.label}: ${COPY.numbers.notMeasured}.`)).join(' ')}
        </p>
        <p className="def">{copy.lead}</p>
        <p className="nx-foot">
          {counted
            ? copy.counts(arms.map((arm, i) => copy.countIn(isNumber(counts[i]) ? counts[i] : COPY.numbers.notRecorded, arm.label)))
            : copy.noCount}
        </p>
      </>
    )
  }
  return <Card title={copy.title} className={className}>{body}</Card>
}
