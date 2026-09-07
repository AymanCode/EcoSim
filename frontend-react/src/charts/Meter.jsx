import { toneVar } from './tones.js'

// Ported from the `.meter`/`.fill`/`.z` markup used for population stress in
// docs/superpowers/specs/2026-09-06-prototype.html (see the "stressmeter"
// block): a track with a coloured fill and tick marks at each zone boundary.
export default function Meter({ value, zones = [45, 70], tones = ['good', 'warn', 'crit'] }) {
  let tone = tones[tones.length - 1]
  for (let i = 0; i < zones.length; i++) {
    if (value < zones[i]) {
      tone = tones[i]
      break
    }
  }
  const width = Math.min(100, value)

  return (
    <div className="meter">
      <div className="fill" style={{ width: `${width}%`, background: toneVar(tone) }} />
      {zones.map((z, i) => (
        <i key={i} className="z" style={{ left: `${z}%` }} />
      ))}
    </div>
  )
}
