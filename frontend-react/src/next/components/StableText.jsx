import { useCallback, useEffect, useLayoutEffect, useRef } from 'react'

// Text that changes with the week, in a box as tall as the tallest text it can
// show at its current width, so nothing below it moves when the text changes
// (spec section 6). `texts` are every string the box may show; each is
// measured once per width with a hidden copy of the box, and again after web
// fonts load. The height is written to the box's style, not React state, so a
// measurement never re-renders the page. Pass a memoised `texts` array.
export default function StableText({ as: Tag = 'p', className, texts, stable, children }) {
  const boxRef = useRef(null)
  const heights = useRef(new Map())

  const measure = useCallback(() => {
    const box = boxRef.current
    if (!box || !box.parentNode) return
    const width = Math.round(box.getBoundingClientRect().width)
    const probe = box.cloneNode(false)
    probe.removeAttribute('data-stable')
    Object.assign(probe.style, { position: 'absolute', visibility: 'hidden', left: '-10000px', top: '0', width: `${width}px`, minHeight: '0', height: 'auto' })
    box.parentNode.appendChild(probe)
    let tallest = 0
    for (const text of texts ?? []) {
      const key = `${width}|${text}`
      let height = heights.current.get(key)
      if (height == null) {
        probe.textContent = text
        height = probe.getBoundingClientRect().height
        heights.current.set(key, height)
      }
      if (height > tallest) tallest = height
    }
    probe.remove()
    box.style.minHeight = tallest ? `${Math.ceil(tallest)}px` : ''
  }, [texts])

  useLayoutEffect(() => { measure() }, [measure])

  useEffect(() => {
    const box = boxRef.current
    if (!box || typeof ResizeObserver === 'undefined') return undefined
    let lastWidth = -1
    const observer = new ResizeObserver(() => {
      const width = Math.round(box.getBoundingClientRect().width)
      if (width !== lastWidth) { lastWidth = width; measure() }
    })
    observer.observe(box)
    return () => observer.disconnect()
  }, [measure])

  useEffect(() => {
    let live = true
    document.fonts?.ready?.then(() => { if (live) { heights.current.clear(); measure() } })
    return () => { live = false }
  }, [measure])

  return <Tag ref={boxRef} className={className} data-stable={stable}>{children}</Tag>
}
