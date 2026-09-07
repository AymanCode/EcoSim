import { toneVar } from './tones.js'

// Ported from `ledgerHTML` in docs/superpowers/specs/2026-09-06-prototype.html:
// each `.lr` row's fill scales to the largest absolute value across every row
// and the net row; the net row carries the `.lr.net` class and colours its
// `.nv` good/crit by sign.
export default function Ledger({ rows, net, format }) {
  const fmt = format || (v => v)
  const magnitudes = [...rows.map(r => Math.abs(r.value)), Math.abs(net.value)]
  const mx = Math.max(...magnitudes, 1)
  const netTone = toneVar(net.value >= 0 ? 'good' : 'crit')
  const netSign = net.value >= 0 ? '+' : '−'

  const row = (label, value, sign, background, key, extraNvStyle) => {
    const width = Math.round((Math.abs(value) / mx) * 100)
    return (
      <div className={`lr${extraNvStyle ? ' net' : ''}`} key={key}>
        <span>{label}</span>
        <div className="tr">
          <div className="fl" style={{ width: `${width}%`, background }} />
        </div>
        <span className="nv" style={extraNvStyle}>
          {sign}{fmt(Math.abs(value))}
        </span>
      </div>
    )
  }

  return (
    <div className="ledger">
      {rows.map((r, i) => row(r.label, r.value, r.sign, toneVar(r.tone), i))}
      {row(net.label, net.value, netSign, netTone, 'net', { color: netTone })}
    </div>
  )
}
