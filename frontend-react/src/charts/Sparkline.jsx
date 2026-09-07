import { toneVar } from './tones.js'

// Ported from `drawSpark` in docs/superpowers/specs/2026-09-06-prototype.html:
// a tiny inline SVG trend line with a coloured end dot. Nominal data draws a
// muted line with an accent dot; warn/crit tones colour the whole thing.
export default function Sparkline({ data, tone = 'acc', width = 64, height = 22 }) {
  if (!data || data.length === 0) return null

  const lo = Math.min(...data)
  const hi = Math.max(...data)
  const span = (hi - lo) || 1
  const last = data.length - 1
  const sx = i => (data.length > 1 ? 2 + (i * (width - 4)) / (data.length - 1) : width / 2)
  const sy = v => height - 3 - ((v - lo) / span) * (height - 6)

  const path = data.map((v, i) => `${i ? 'L' : 'M'}${sx(i).toFixed(1)} ${sy(v).toFixed(1)}`).join(' ')
  const alert = tone === 'warn' || tone === 'crit'
  const lineColor = alert ? toneVar(tone) : toneVar('ink4')
  const dotColor = alert ? toneVar(tone) : (tone === 'flat' ? toneVar('flat') : toneVar('acc'))

  return (
    <svg data-spark="" viewBox={`0 0 ${width} ${height}`} width={width} height={height}>
      <path d={path} fill="none" style={{ stroke: lineColor, strokeWidth: 1.25, strokeLinecap: 'round', strokeLinejoin: 'round' }} />
      <circle cx={sx(last)} cy={sy(data[last])} r={2.4} style={{ fill: dotColor }} />
    </svg>
  )
}
