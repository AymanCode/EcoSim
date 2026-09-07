import { toneVar, thresholdTone } from './tones.js'

// Ported from `drawRadar` in docs/superpowers/specs/2026-09-06-prototype.html:
// rings at .25/.5/.75/1, spoke axes, a median polygon (ink4, 12% fill), a
// subject polygon (accent, 14% fill, 1.5px stroke), vertex dots (crit below
// .3, warn below .5, else accent) ringed in the panel colour, per-vertex
// labels with the rounded percentage, and a footer note. Built as JSX SVG
// elements (never innerHTML), sized to the final viewBox (320x248, cx 160,
// cy 118, R 84) rather than the prototype's original numbers.
const W = 320
const H = 248
const CX = 160
const CY = 118
const R = 84

export default function Radar({ dims, median }) {
  const n = dims.length
  const pt = (i, r) => {
    const a = -Math.PI / 2 + (i * 2 * Math.PI) / n
    return [CX + r * Math.cos(a), CY + r * Math.sin(a)]
  }
  const polygon = getR => dims
    .map((_, i) => {
      const [x, y] = pt(i, getR(i))
      return `${i ? 'L' : 'M'}${x.toFixed(1)} ${y.toFixed(1)}`
    })
    .join(' ') + 'Z'

  const hasMedian = Array.isArray(median) && median.length === n
  const medianPath = hasMedian ? polygon(i => R * median[i]) : null
  const subjectPath = polygon(i => R * Math.max(0.04, dims[i].value))

  return (
    <svg className="radar" viewBox={`0 0 ${W} ${H}`}>
      {[0.25, 0.5, 0.75, 1].map(k => (
        <path key={k} d={polygon(() => R * k)} fill="none" style={{ stroke: toneVar('grid'), strokeWidth: 1 }} />
      ))}
      {dims.map((_, i) => {
        const [x, y] = pt(i, R)
        return <line key={i} x1={CX} y1={CY} x2={x} y2={y} style={{ stroke: toneVar('grid'), strokeWidth: 1 }} />
      })}
      {medianPath && (
        <path d={medianPath} style={{ fill: toneVar('ink4'), fillOpacity: 0.12, stroke: toneVar('ink4'), strokeWidth: 1 }} />
      )}
      <path
        d={subjectPath}
        style={{ fill: toneVar('acc'), fillOpacity: 0.14, stroke: toneVar('acc'), strokeWidth: 1.5, strokeLinejoin: 'round' }}
      />
      {dims.map((d, i) => {
        const [x, y] = pt(i, R * Math.max(0.04, d.value))
        return (
          <g key={i}>
            <circle cx={x} cy={y} r={5} style={{ fill: toneVar('panel') }} />
            <circle cx={x} cy={y} r={3} style={{ fill: toneVar(thresholdTone(d.value)) }} />
          </g>
        )
      })}
      {dims.map((d, i) => {
        const [lx, ly] = pt(i, R + 22)
        const anchor = Math.abs(lx - CX) < 8 ? 'middle' : lx > CX ? 'start' : 'end'
        return (
          <text
            key={i}
            x={lx}
            y={ly + 3}
            textAnchor={anchor}
            style={{ fontFamily: 'var(--font), sans-serif', fontSize: '10.5px', fontWeight: 600, fill: toneVar('ink3') }}
          >
            {d.label}
            <tspan
              x={lx}
              dy={12}
              style={{
                fontFamily: 'var(--mono), monospace',
                fontSize: '10.5px',
                fontWeight: 500,
                fill: thresholdTone(d.value) === 'crit' ? toneVar('crit') : toneVar('ink'),
              }}
            >
              {Math.round(d.value * 100)}
            </tspan>
          </text>
        )
      })}
      <text x={W - 4} y={H - 4} textAnchor="end" style={{ fontFamily: 'var(--font), sans-serif', fontSize: '10.5px', fill: toneVar('ink4') }}>
        grey = population median
      </text>
    </svg>
  )
}
