// The card for one place in a living-town drawing (mockup 08's .pop): its
// name, a line under it, a few rows of figures, a note and a tag in the
// place's tone. `card` is placeCard's answer (town/cards.js), or null for no
// card; `x` and `y` are where the pointer was, as fractions of the drawing's
// width and height; `pinned` says the viewer clicked to keep it.
//
// The card lies over the drawing (absolutely placed in .lt-canvas), so it
// never takes room or moves anything, and it is decoration for pointer
// users: aria-hidden, with nothing to focus. Keyboard and screen-reader users
// have the town card's summary list and the Businesses and Households panels.
// After each render the card measures itself and sits beside the pointer,
// inside the drawing (cardSpot), so a kept card whose rows change with the
// week, or a drawing that changes size, never pushes it past an edge.
import { useLayoutEffect, useRef } from 'react'
import { cardSpot } from './cards.js'

export default function PlaceCard({ card, x = 0, y = 0, pinned = false }) {
  const ref = useRef(null)
  useLayoutEffect(() => {
    const element = ref.current
    const room = element?.offsetParent
    if (!card || !room) return
    element.style.left = `${cardSpot(x * room.clientWidth, element.offsetWidth, room.clientWidth)}px`
    element.style.top = `${cardSpot(y * room.clientHeight, element.offsetHeight, room.clientHeight)}px`
  })
  const on = Boolean(card)
  return (
    <div ref={ref} className={`lt-place${on ? ' is-on' : ''}${on && pinned ? ' is-pinned' : ''}`} aria-hidden="true">
      {card && (
        <>
          <div className="lt-place-title">{card.title}</div>
          {card.sub && <div className="lt-place-sub">{card.sub}</div>}
          {card.rows.map(([label, value]) => (
            <div key={label} className="lt-place-row">
              <span>{label}</span>
              <span>{value}</span>
            </div>
          ))}
          {card.note && <div className="lt-place-note">{card.note}</div>}
          {card.tag && <span className={`lt-place-tag is-${card.tag.tone}`}>{card.tag.text}</span>}
        </>
      )}
    </div>
  )
}
