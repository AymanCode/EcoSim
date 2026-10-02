// The place card for a living-town drawing (spec section 4.4): pointing at a
// house, a shop, the town hall, the bank or a pin shows its card beside the
// pointer; clicking keeps it open; clicking empty ground (or the kept card)
// closes it. The card is placeCard(model, target, total) for the model of
// each render, so a kept card follows the week, and goes when its place does
// (a shop that has left the town), which also frees the pointer to show
// other cards again.
//
// The caller spreads `handlers` on the box that holds the drawing and renders
// `overlay` inside it (TownCard's .lt-canvas; Main Street's too). The drawing
// marks what can be pointed at with data-kind, plus data-index (a house or a
// person) or data-id (a shop); its back and motion layers let the pointer
// through, so the element under the pointer is in the world layer. The state
// lives in the component that calls this hook, never in the memoised
// drawing, so pointing renders the card again and leaves the scene alone.
//
// A touch screen has no pointing: a tap opens and keeps a card, and a tap on
// empty ground or on the card closes it. The browser follows each touch with
// a copy of a mouse move and then the click; the move is skipped, so the
// click does the work (and iOS Safari, which drops a tap's click when its
// mouse move shows something new, still sends it).
import { createElement, useRef, useState } from 'react'
import { placeCard } from './cards.js'
import PlaceCard from './PlaceCard.jsx'

// How long after a touch the mouse events are the browser's copies of it.
const TOUCH_COPIES_MS = 800

// The place an element of the drawing stands for, from its data attributes.
function targetOf(element) {
  const { kind, index, id } = element.dataset
  if (kind === 'shop') return { kind, id: /^-?\d+$/.test(id) ? Number(id) : id }
  if (kind === 'house' || kind === 'person') return { kind, index: Number(index) }
  return { kind }
}

// Where the pointer is, as fractions of the drawing's box (so a kept card
// stays by its place when the drawing changes size, as on Enlarge).
function pointerIn(event) {
  const box = event.currentTarget.getBoundingClientRect()
  return {
    x: box.width > 0 ? (event.clientX - box.left) / box.width : 0,
    y: box.height > 0 ? (event.clientY - box.top) / box.height : 0,
  }
}

const placeAt = event => event.target.closest?.('[data-kind]') ?? null
const now = () => performance.now()

export default function usePlaceCard(model, total) {
  // { target, pinned, x, y } while a card is shown, else null.
  const [shown, setShown] = useState(null)
  const touched = useRef(-Infinity)
  const card = shown ? placeCard(model, shown.target, total) : null
  const kept = Boolean(shown?.pinned && card)

  const noteTouch = () => { touched.current = now() }
  const onMouseMove = event => {
    if (kept || now() - touched.current < TOUCH_COPIES_MS) return
    const place = placeAt(event)
    if (place) setShown({ target: targetOf(place), pinned: false, ...pointerIn(event) })
    else if (shown) setShown(null)
  }
  const onMouseLeave = () => {
    if (shown && !kept) setShown(null)
  }
  // A click on a place keeps its card; on empty ground, or on the kept card
  // itself (on a phone it covers much of the drawing), closes it.
  const onClick = event => {
    const place = event.target.closest?.('.lt-place') ? null : placeAt(event)
    setShown(place ? { target: targetOf(place), pinned: true, ...pointerIn(event) } : null)
  }

  return {
    overlay: createElement(PlaceCard, { card, x: shown?.x, y: shown?.y, pinned: kept }),
    handlers: { onMouseMove, onMouseLeave, onClick, onTouchStart: noteTouch, onTouchEnd: noteTouch },
  }
}
