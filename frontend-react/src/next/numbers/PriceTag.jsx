import { COPY, WARMUP_TICKS } from '../catalog.js'
import { valueAt } from '../data/derive.js'
import { weekLabel } from '../narration.js'
import { isNumber } from './chartKit.js'
import Tile from './Tile.jsx'
import '../next.css'

// Two prices count as the same only when they are equal but for float noise
// (well under a cent): $10.801 and $10.799 both show as $10.80 but differ.
const same = (a, b) => Math.abs(a - b) <= Math.min(0.005, 1e-6 * Math.max(1, Math.abs(a), Math.abs(b)))

// How long a price must have stood still before a sentence replaces its
// line, as in mockup 06: until then the line shows how it got there.
const STEADY_WEEKS = 13

// The first week of the stretch, ending at `tick`, in which a price has
// stood at the same value in every town; null while the towns are being set
// up, when a town has no price, when the stretch starts after the end of
// warm-up, or when it has lasted less than STEADY_WEEKS weeks.
function steadySince(arms, key, tick) {
  const last = Math.floor(tick)
  if (!arms.length || last <= WARMUP_TICKS) return null
  const values = week => arms.map(arm => valueAt(arm, key, week))
  const now = values(last)
  if (now.some(value => !isNumber(value) || !same(value, now[0]))) return null
  let since = last
  while (since > 1 && values(since - 1).every(value => isNumber(value) && same(value, now[0]))) since -= 1
  return since <= WARMUP_TICKS + 1 && last - since >= STEADY_WEEKS ? since : null
}

// A sector price as a price tag (mockup 06): the tile's values and
// sparkline in a tag shape. When the price is the same in every town and has
// not moved since the end of warm-up, for 13 weeks or more, a sentence says
// so instead of drawing a flat line. It opens big for its own price.
export default function PriceTag({ metricKey, arms, tick, onSeeBig, className = '' }) {
  const since = steadySince(arms, metricKey, tick)
  const note = since === null ? null : COPY.numbers.price.steady(arms.length, weekLabel(since))
  return (
    <div className={`nx-ptag${className ? ` ${className}` : ''}`}>
      <Tile metricKey={metricKey} arms={arms} tick={tick} onSeeBig={onSeeBig} height={40} chartNote={note} />
    </div>
  )
}
