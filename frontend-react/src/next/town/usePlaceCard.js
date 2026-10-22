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
// house) or data-id (a shop or person); its back and motion layers let the pointer
// through, so the element under the pointer is in the world layer. Only
// marks inside that box count. The state lives in the component that calls
// this hook, never in the memoised drawing, so pointing renders the card
// again and leaves the scene alone. While `hidden` (a town card hidden by
// Enlarge) a card that was only pointed at goes, so it does not come back
// stale when the town shows again; a kept card stays kept.
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
  if (kind === 'shop' || kind === 'person') return { kind, id: /^-?\d+$/.test(id) ? Number(id) : id }
  if (kind === 'house') return { kind, index: Number(index) }
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

// The marked place under the pointer, if it is part of this drawing.
function placeAt(event) {
  const place = event.target.closest?.('[data-kind]')
  return place && event.currentTarget.contains(place) ? place : null
}
const now = () => performance.now()

export default function usePlaceCard(model, total, hidden = false) {
  // { target, pinned, x, y } while a card is shown, else null.
  const [shown, setShown] = useState(null)
  if (hidden && shown && !shown.pinned) setShown(null)
  const touched = useRef(-Infinity)
  const card = shown ? placeCard(model, shown.target, total) : null
  // Drop the retained identity when it leaves the sample; returning later
  // must not resurrect a card the viewer can no longer point at.
  if (shown && !card) setShown(null)
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
