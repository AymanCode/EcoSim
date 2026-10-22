import { useCallback, useEffect, useLayoutEffect, useRef } from 'react'

// Text that changes with the week, in a box as tall as the tallest text it can
// show at its current width, so nothing below it moves when the text changes
// (spec section 6). `texts` are every string the box may show; each is
// measured once per width with a hidden copy of the box (new candidates alone
// when `texts` grows), and all again when web fonts finish loading. The height
// is written to the box's style, not React state, so a measurement never
// re-renders the page. Pass a memoised `texts` array. When the box shows more
// than plain text, `markup(text)` gives the HTML it renders for a text (a
// memoised function), so the hidden copy wraps exactly as the box does.
export default function StableText({ as: Tag = 'p', className, texts, stable, markup, children }) {
  const boxRef = useRef(null)
  const heights = useRef(new Map())
  // The latest measure, for the resize and font listeners registered once.
  const measureRef = useRef(null)

  const measure = useCallback(() => {
    const box = boxRef.current
    if (!box || !box.parentNode) return
    const width = box.getBoundingClientRect().width
    const probe = box.cloneNode(false)
    probe.removeAttribute('data-stable')
    Object.assign(probe.style, { position: 'absolute', visibility: 'hidden', left: '-10000px', top: '0', width: `${width}px`, minHeight: '0', height: 'auto' })
    box.parentNode.appendChild(probe)
    let tallest = 0
    for (const text of texts ?? []) {
      const key = `${Math.round(width * 10) / 10}|${text}`
      let height = heights.current.get(key)
      if (height == null) {
        if (markup) probe.innerHTML = markup(text)
        else probe.textContent = text
        height = probe.getBoundingClientRect().height
        heights.current.set(key, height)
      }
      if (height > tallest) tallest = height
    }
    probe.remove()
    box.style.minHeight = tallest ? `${Math.ceil(tallest)}px` : ''
  }, [texts, markup])

  useLayoutEffect(() => {
    measureRef.current = measure
    measure()
  }, [measure])

  useEffect(() => {
    const box = boxRef.current
    if (!box || typeof ResizeObserver === 'undefined') return undefined
    let lastWidth = -1
    const observer = new ResizeObserver(() => {
      const width = box.getBoundingClientRect().width
      if (width !== lastWidth) { lastWidth = width; measureRef.current?.() }
    })
    observer.observe(box)
    return () => observer.disconnect()
  }, [])

  useEffect(() => {
    const fonts = document.fonts
    if (!fonts) return undefined
    let live = true
    const remeasure = () => {
      if (!live) return
      heights.current.clear()
      measureRef.current?.()
    }
    fonts.ready?.then(remeasure)
    fonts.addEventListener?.('loadingdone', remeasure)
    return () => {
      live = false
      fonts.removeEventListener?.('loadingdone', remeasure)
    }
  }, [])

  return <Tag ref={boxRef} className={className} data-stable={stable} data-reserve="">{children}</Tag>
}
