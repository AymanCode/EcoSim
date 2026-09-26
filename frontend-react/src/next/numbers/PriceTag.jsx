import { COPY, WARMUP_TICKS, shownValue } from '../catalog.js'
import { valueAt } from '../data/derive.js'
import { weekLabel } from '../narration.js'
import Tile from './Tile.jsx'
import '../next.css'

// The first week of the stretch, ending at `tick`, in which a price has
// stood still at the same value in every town (compared as shown, to the
// cent); null while the towns are being set up, when a town has no price, or
// when the stretch starts after the end of warm-up.
function steadySince(arms, key, tick) {
  const last = Math.floor(tick)
  if (!arms.length || last <= WARMUP_TICKS) return null
  const shown = week => arms.map(arm => shownValue(key, valueAt(arm, key, week)))
  const now = shown(last)
  if (now.some(value => value === null || value !== now[0])) return null
  let since = last
  while (since > 1 && shown(since - 1).every(value => value === now[0])) since -= 1
  return since <= WARMUP_TICKS + 1 ? since : null
}

// A sector price as a price tag (mockup 06): the tile's values and
// sparkline in a tag shape. When the price is the same in every town and has
// not moved since the end of warm-up, a sentence says so instead of drawing a
// flat line. It opens big for its own price.
export default function PriceTag({ metricKey, arms, tick, onSeeBig, className = '' }) {
  const since = steadySince(arms, metricKey, tick)
  const note = since === null ? null : COPY.numbers.price.steady(arms.length, weekLabel(since))
  return (
    <div className={`nx-ptag${className ? ` ${className}` : ''}`}>
      <Tile metricKey={metricKey} arms={arms} tick={tick} onSeeBig={onSeeBig} height={40} chartNote={note} />
    </div>
  )
}
