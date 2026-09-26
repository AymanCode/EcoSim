import { useEffect, useRef, useState } from 'react'
import { COPY, COUNTED_EVERY_5, METRICS, NUMBER_GROUPS } from '../catalog.js'
import { countedAt, everMeasured } from '../data/derive.js'
import { countedNote } from '../narration.js'
import StoryChart from '../components/StoryChart.jsx'
import '../next.css'

// Numbers that are not tiles but open big from a special visual, each with
// its neighbours as chips: the savings ladder, the businesses by how they are
// doing, and money in and out.
const BIG_SETS = [
  ['wealthP10', 'wealthP50', 'wealthP90'],
  ['firmsGrowing', 'firmsSteady', 'firmsStruggling'],
  ['townHallIncome', 'familySupportPaid'],
]

function BackIcon() {
  return <svg viewBox="0 0 12 12" aria-hidden="true" focusable="false"><path d="M7.5 2 L3.5 6 L7.5 10" /></svg>
}

// One number drawn big: the Run screen's story chart for any METRICS key, on
// the same clock. Its chips are the other measured numbers of the same group
// in the sheet (NUMBER_GROUPS, or BIG_SETS for a special visual's numbers),
// and a counted-every-5-weeks number is drawn only at its counts, with the
// week of the last one. Focus moves to the way back when it opens; the sheet
// brings focus back to the card that opened it.
// `playing` stops the cursor easing while the clock runs, as on the Run screen.
export default function SeeItBig({ metricKey, arms, tick, onClose, playing = false }) {
  const [shown, setShown] = useState(metricKey)
  const backRef = useRef(null)
  useEffect(() => { backRef.current?.focus() }, [])

  const group = NUMBER_GROUPS.find(entry => entry.keys.includes(metricKey))?.keys ?? BIG_SETS.find(set => set.includes(metricKey))
  const keys = (group ?? [metricKey]).filter(key => key === metricKey || everMeasured(arms, key))
  const metric = METRICS[shown] ?? { name: shown, meaning: '' }
  const horizon = Math.max(1, tick, ...arms.map(arm => arm.horizon || 0))
  const measured = everMeasured(arms, shown)
  const counted = COUNTED_EVERY_5.includes(shown)
  const asOf = counted ? arms.map(arm => countedAt(arm, shown, tick)?.asOfTick).find(Number.isFinite) ?? null : null

  return (
    <div className="nx-seebig">
      <button ref={backRef} type="button" className="nx-abtn" onClick={onClose}><BackIcon />{COPY.numbers.backToNumbers}</button>
      {measured ? (
        <StoryChart
          arms={arms}
          metricKey={shown}
          tick={tick}
          horizon={horizon}
          onMetricChange={setShown}
          metricKeys={keys}
          countedWeeks
          playing={playing}
        />
      ) : (
        <div className="nx-card">
          <h3>{metric.name}</h3>
          <p className="cs">{metric.meaning}</p>
          <p className="nx-quiet">{COPY.numbers.notMeasured}</p>
        </div>
      )}
      {measured && counted && <p className="nx-foot">{countedNote(asOf)}</p>}
    </div>
  )
}
