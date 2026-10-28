// "Main Street, up close" on the Run screen (spec sections 3 and 4.3.17): the
// side view of one town's street (MainStreet), a header naming the town and
// its rules, and, with two or more towns, a segmented picker for which town
// it shows (`selected`, reported through `onSelect`). Enlarge on a town card
// moves it to that town (RunScreen).
//
// Nothing here changes size as the week changes (spec section 6): the header
// is one line on a wide card (two on a narrow one), its rules text is cut
// short with the full wording in its title, the picker's buttons have fixed
// widths, and the drawing keeps the street's aspect ratio. The drawing is
// aria-hidden; a short summary says what it shows for screen readers.
// Pointing at a place shows its card (usePlaceCard), as on the town cards;
// showing another town starts afresh, with no card.
import { useId, useMemo } from 'react'
import { COPY, describePolicy } from '../catalog.js'
import { rulesAt, rulesDiff, valueAt } from '../data/derive.js'
import MainStreet from './MainStreet.jsx'
import { townAt } from './model.js'
import { onStreet } from './streetShape.js'
import usePlaceCard from './usePlaceCard.js'
import './town.css'

const D = COPY.diorama

// One town's street for the week on the clock, with its place cards and its
// summary. Keyed by the town, so picking another town starts a new scene.
function Street({ arm, tick, playing, towns, scrubs, ended }) {
  // An arm's weeks grow in place (data/session.js): memoised on the count too.
  const weeks = arm.ticks.length
  const model = useMemo(() => townAt(arm, tick), [arm, tick, weeks]) // eslint-disable-line react-hooks/exhaustive-deps
  const { overlay, handlers } = usePlaceCard(model, valueAt(arm, 'householdsTotal', tick))
  const shops = model.shops.filter(onStreet)
  return (
    <>
      <div className="lt-canvas" {...handlers}>
        <MainStreet model={model} color={arm.color} playing={playing} towns={towns} scrubs={scrubs} ended={ended} />
        {overlay}
      </div>
      <p className="nx-sr">
        {D.streetSummary(shops.length, shops.filter(shop => shop.state === 'growing').length, shops.filter(shop => shop.state === 'closed').length)}
      </p>
    </>
  )
}

export default function MainStreetCard({ arms, tick, playing = false, selected = 0, onSelect, scrubs = 0, ended = false }) {
  const titleId = useId()
  const index = Math.min(Math.max(0, selected), arms.length - 1)
  const arm = arms[index]
  const sub = D.mainStreetFor(arm.label, describePolicy(rulesDiff(rulesAt(arm, tick))))
  return (
    <article className="nx-card lt-street" data-stable="main-street" aria-labelledby={titleId}>
      <header className="lt-street-head">
        <h2 id={titleId}>{D.mainStreet}</h2>
        <span className="lt-street-sub" title={sub}>{sub}</span>
        {arms.length > 1 && (
          <div className="lt-pick" role="group" aria-label={D.streetPicker}>
            {arms.map((town, n) => (
              <button key={town.label} type="button" aria-pressed={n === index} onClick={() => onSelect?.(n)}>
                <i style={{ background: town.color }} aria-hidden="true" />
                {town.label}
              </button>
            ))}
          </div>
        )}
      </header>
      <Street key={arm.label} arm={arm} tick={tick} playing={playing} towns={arms.length} scrubs={scrubs} ended={ended} />
    </article>
  )
}
