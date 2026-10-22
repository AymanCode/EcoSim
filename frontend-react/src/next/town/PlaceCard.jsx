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
// While a card shows, it measures itself after each render and sits beside
// the pointer, inside the drawing (cardSpot), so a kept card whose rows
// change with the week never pushes past an edge; and it is placed again
// when the drawing changes size with no render (a window resized, a phone
// turned). With no card nothing is measured, so a week change costs no
// layout read.
import { useLayoutEffect, useRef } from 'react'
import { cardSpot } from './cards.js'

// Measures the card where it starts (at the drawing's top left: by the right
// edge it would have less room, and wrap narrower and taller) and puts it by
// the point (x, y), as fractions of the drawing.
function place(element, x, y) {
  const room = element?.offsetParent
  if (!room) return
  element.style.left = '0px'
  element.style.top = '0px'
  const width = element.offsetWidth
  const height = element.offsetHeight
  element.style.left = `${cardSpot(x * room.clientWidth, width, room.clientWidth)}px`
  element.style.top = `${cardSpot(y * room.clientHeight, height, room.clientHeight)}px`
}

export default function PlaceCard({ card, x = 0, y = 0, pinned = false }) {
  const ref = useRef(null)
  const at = useRef({ x, y })
  const on = Boolean(card)
  useLayoutEffect(() => {
    at.current = { x, y }
    if (on) place(ref.current, x, y)
  })
  useLayoutEffect(() => {
    const element = ref.current
    const room = on ? element?.offsetParent : null
    if (!room || typeof ResizeObserver === 'undefined') return undefined
    const observer = new ResizeObserver(() => place(element, at.current.x, at.current.y))
    observer.observe(room)
    return () => observer.disconnect()
  }, [on])
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
