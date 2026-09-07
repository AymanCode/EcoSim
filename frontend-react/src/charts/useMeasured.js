import { useLayoutEffect, useRef, useState } from 'react'

// Measures an element's box via ResizeObserver (falling back to a window
// resize listener when ResizeObserver isn't available). Ported from
// `useMeasuredWidth` in ui/primitives.jsx, extended to report height too.
export default function useMeasured() {
  const ref = useRef(null)
  const [size, setSize] = useState({ width: 0, height: 0 })

  useLayoutEffect(() => {
    const node = ref.current
    if (!node) return undefined

    const update = (nextWidth = node.getBoundingClientRect().width, nextHeight = node.getBoundingClientRect().height) => {
      const width = Math.max(0, Math.floor(nextWidth))
      const height = Math.max(0, Math.floor(nextHeight))
      setSize(prev => (Math.abs(prev.width - width) > 1 || Math.abs(prev.height - height) > 1) ? { width, height } : prev)
    }

    update()

    if (typeof ResizeObserver === 'undefined') {
      const onResize = () => update()
      window.addEventListener('resize', onResize)
      return () => window.removeEventListener('resize', onResize)
    }

    const observer = new ResizeObserver(entries => {
      const rect = entries[0]?.contentRect
      update(rect?.width, rect?.height)
    })
    observer.observe(node)
    return () => observer.disconnect()
  }, [])

  return [ref, size]
}
