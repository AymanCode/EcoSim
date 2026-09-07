import React, { useEffect, useRef } from 'react'

// Point-cloud figure of one household. It reads its colours from the theme
// tokens, fits itself to whatever box it is given, and keeps the old props:
// `active` pauses the rotation, `mood` picks the node colour.

const MOOD_TOKEN = { happy: '--good', distressed: '--crit', neutral: '--acc' }
const FOV = 4
const CAMERA = 3
const S_MAX = FOV / (FOV + CAMERA - 1) // nearest possible perspective scale

function readToken(name, fallback) {
  if (typeof getComputedStyle !== 'function') return fallback
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim()
  return v || fallback
}

function withAlpha(color, alpha) {
  const m = /^#([0-9a-f]{3}|[0-9a-f]{6})$/i.exec(color)
  if (!m) return color
  let h = m[1]
  if (h.length === 3) h = h.split('').map((c) => c + c).join('')
  const r = parseInt(h.slice(0, 2), 16)
  const g = parseInt(h.slice(2, 4), 16)
  const b = parseInt(h.slice(4, 6), 16)
  return `rgba(${r},${g},${b},${alpha})`
}

// Small deterministic generator so the figure is identical on every mount.
function mulberry32(seed) {
  let a = seed >>> 0
  return () => {
    a = (a + 0x6d2b79f5) >>> 0
    let t = a
    t = Math.imul(t ^ (t >>> 15), t | 1)
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

function buildFigure(seed = 7) {
  const rnd = mulberry32(seed)
  const pts = []
  const add = (x, y, z, tag) => pts.push({ x, y, z, tag })
  for (let i = 0; i < 26; i++) {
    const th = rnd() * Math.PI * 2
    const ph = Math.acos(2 * rnd() - 1)
    add(14 * Math.sin(ph) * Math.cos(th), 14 * Math.sin(ph) * Math.sin(th) - 65, 14 * Math.cos(ph), 'head')
  }
  for (let i = 0; i < 48; i++) {
    const th = rnd() * Math.PI * 2
    const y = rnd() * 65 - 45
    const rr = (12 + y / 10) * Math.sqrt(rnd())
    add(rr * Math.cos(th), y, rr * Math.sin(th), 'body')
  }
  ;[-22, 22].forEach((x) => {
    for (let y = -45; y < 15; y += 6) add(x + (rnd() * 4 - 2), y, rnd() * 6 - 3, 'limb')
  })
  ;[-10, 10].forEach((x) => {
    for (let y = 20; y < 90; y += 7) add(x + (rnd() * 4 - 2), y, rnd() * 6 - 3, 'limb')
  })
  // Normalise: centre vertically and scale so y spans [-1, 1].
  let yMin = Infinity
  let yMax = -Infinity
  pts.forEach((p) => {
    yMin = Math.min(yMin, p.y)
    yMax = Math.max(yMax, p.y)
  })
  const cy = (yMin + yMax) / 2
  const half = (yMax - yMin) / 2
  let rMax = 0
  pts.forEach((p) => {
    p.x /= half
    p.y = (p.y - cy) / half
    p.z /= half
    rMax = Math.max(rMax, Math.hypot(p.x, p.z))
  })
  const linkRadius = 16 / half
  const links = []
  for (let i = 0; i < pts.length; i++) {
    for (let j = i + 1; j < pts.length; j++) {
      const a = pts[i]
      const b = pts[j]
      if (Math.hypot(a.x - b.x, a.y - b.y, a.z - b.z) < linkRadius) links.push([i, j])
    }
  }
  return { pts, links, rMax }
}

export default function NeuralAvatar({ active = true, mood = 'neutral' }) {
  const hostRef = useRef(null)
  const canvasRef = useRef(null)

  useEffect(() => {
    const host = hostRef.current
    const canvas = canvasRef.current
    if (!host || !canvas) return undefined
    const ctx = canvas.getContext('2d')
    if (!ctx) return undefined

    const { pts, links, rMax } = buildFigure()
    const reduceMotion = typeof window.matchMedia === 'function' && window.matchMedia('(prefers-reduced-motion: reduce)').matches
    const spin = active && !reduceMotion
    let w = 0
    let h = 0
    let angle = 0.6
    let raf = 0

    const paint = () => {
      const node = readToken(MOOD_TOKEN[mood] || '--acc', '#FF6B1A')
      return {
        node,
        head: readToken('--ink', '#F5F6F7'),
        link: withAlpha(readToken('--ink4', '#5B626C'), 0.38),
      }
    }
    let colors = paint()

    const size = () => {
      const r = host.getBoundingClientRect()
      w = r.width
      h = r.height
      if (!w || !h) return
      const dpr = window.devicePixelRatio || 1
      canvas.width = Math.round(w * dpr)
      canvas.height = Math.round(h * dpr)
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    }

    const draw = (t) => {
      if (!w || !h) return
      ctx.clearRect(0, 0, w, h)
      const pad = 10
      // Fit: the nearest point projects at S_MAX, so this scale keeps the whole
      // figure inside the box at every rotation angle.
      const k = Math.min((w / 2 - pad) / (rMax * S_MAX), (h / 2 - pad) / S_MAX)
      const cos = Math.cos(angle)
      const sin = Math.sin(angle)
      const proj = pts.map((p) => {
        const x = p.x * cos - p.z * sin
        const z = p.x * sin + p.z * cos
        const s = FOV / (FOV + CAMERA + z)
        return { x: w / 2 + x * s * k, y: h / 2 + p.y * s * k, near: (s - 0.5) / (S_MAX - 0.5), tag: p.tag }
      })
      ctx.lineWidth = 1
      ctx.strokeStyle = colors.link
      ctx.beginPath()
      links.forEach(([i, j]) => {
        ctx.moveTo(proj[i].x, proj[i].y)
        ctx.lineTo(proj[j].x, proj[j].y)
      })
      ctx.stroke()
      proj.forEach((p, i) => {
        const near = Math.max(0, Math.min(1, p.near))
        const shimmer = spin ? 0.1 * Math.sin(t / 900 + i) : 0
        ctx.globalAlpha = Math.max(0.25, Math.min(1, 0.45 + 0.5 * near + shimmer))
        ctx.fillStyle = p.tag === 'head' ? colors.head : colors.node
        ctx.beginPath()
        ctx.arc(p.x, p.y, 1 + 1.4 * near, 0, Math.PI * 2)
        ctx.fill()
      })
      ctx.globalAlpha = 1
    }

    const loop = (t) => {
      angle += 0.006
      draw(t)
      raf = requestAnimationFrame(loop)
    }

    const ro = new ResizeObserver(() => {
      size()
      draw(performance.now())
    })
    ro.observe(host)
    size()
    const mo = new MutationObserver(() => {
      colors = paint()
      draw(performance.now())
    })
    mo.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] })

    if (spin) raf = requestAnimationFrame(loop)
    else draw(performance.now())

    return () => {
      cancelAnimationFrame(raf)
      ro.disconnect()
      mo.disconnect()
    }
  }, [active, mood])

  return (
    <div ref={hostRef} className="w-full h-full absolute inset-0">
      <canvas ref={canvasRef} className="block w-full h-full" />
    </div>
  )
}
