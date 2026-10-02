// The diorama's town hall (with its treasury and queue) and bank, one small
// memoised component each, ported from mockup 08 (IsoScene.drawHall, drawBank,
// and the treasury, queue and loan papers in apply). Nothing here animates:
// the motion loop pulses the hall's ring, waves its flag and flashes the bank
// (moments.js, ambient.js) by writing attributes on the parts marked here.
import { memo } from 'react'
import { COPY, formatMoneyShort } from '../catalog.js'
import { BANK, HALL, iso as P, onFace, pts, r1 } from './geometry.js'
import { SHIRTS } from './nodes.js'
import { Figure, Line } from './draw.jsx'

const clamp = (value, lo, hi) => Math.min(hi, Math.max(lo, value))
const SIGNS = COPY.diorama.signs

// The banner's text fits the façade: a long label is squeezed to its width.
const BANNER_ROOM = 22
const bannerFit = label => (label.length * 4.6 * 0.64 > BANNER_ROOM ? { textLength: BANNER_ROOM, lengthAdjust: 'spacingAndGlyphs' } : {})

// The town hall: columns, a flag in the town's colour, a banner naming its
// changed rule, and a ring on the ground for WEEKS.pulse weeks after the rules
// change (a newer change draws a new ring, which the loop pulses twice).
export const Hall = memo(function Hall({ color, banner, changed }) {
  const { gx: x0, gy: y0, w, d, h } = HALL
  const rA = P(x0 - 0.06, y0 + d / 2, h + 9)
  const rB = P(x0 + w + 0.06, y0 + d / 2, h + 9)
  const top = P(x0 + w / 2, y0 + d / 2, h + 9)
  const [rx, ry] = P(x0 + w / 2, y0 + d / 2)
  const bannerA = P(x0 + 0.1, y0 + d, h - 4)
  const bannerB = P(x0 + w - 0.1, y0 + d, h - 4)
  return (
    <g data-kind="hall">
      {changed != null && (
        <g transform={`translate(${r1(rx)} ${r1(ry)})`}>
          <ellipse key={changed} className="lt-hall-ring" rx={40} ry={20} stroke={color} />
        </g>
      )}
      <polygon points={pts([P(x0 - 0.08, y0 + d + 0.12), P(x0 + w + 0.08, y0 + d + 0.12), P(x0 + w + 0.08, y0 + d + 0.12, 3), P(x0 - 0.08, y0 + d + 0.12, 3)])} fill="#E2D9C9" />
      <polygon points={pts([P(x0, y0 + d), P(x0 + w, y0 + d), P(x0 + w, y0 + d, h), P(x0, y0 + d, h)])} fill="#FBF8F1" />
      <polygon points={pts([P(x0 + w, y0), P(x0 + w, y0 + d), P(x0 + w, y0 + d, h), P(x0 + w, y0, h)])} fill="#E3DCCF" />
      {[0, 1, 2, 3, 4, 5].map(k => {
        const u = x0 + 0.12 + k * 0.25
        return <Line key={k} a={P(u, y0 + d, 3)} b={P(u, y0 + d, h - 3)} stroke="#DCD3C3" strokeWidth={2.2} />
      })}
      {banner && (
        <g className="lt-banner">
          <polygon points={pts([bannerA, bannerB, [bannerB[0], bannerB[1] + 7], [bannerA[0], bannerA[1] + 7]])} fill={color} />
          <text x={0} y={0} fontSize={4.6} fontWeight={700} fill="#fff" textAnchor="middle" dominantBaseline="central" letterSpacing={0.3}
            transform={onFace(P(x0 + w / 2, y0 + d, h - 7.6))} {...bannerFit(banner)}>{banner}</text>
        </g>
      )}
      <polygon points={pts([P(x0 - 0.06, y0 - 0.06, h), P(x0 + w + 0.06, y0 - 0.06, h), rB, rA])} fill="#D8CEBD" />
      <polygon points={pts([P(x0 + w, y0), P(x0 + w, y0 + d), P(x0 + w, y0 + d / 2, h + 9)])} fill="#EFE8DC" />
      <polygon points={pts([P(x0 - 0.06, y0 + d + 0.06, h), P(x0 + w + 0.06, y0 + d + 0.06, h), rB, rA])} fill="#F2ECE1" />
      <polygon className="lt-snow" points={pts([P(x0 - 0.05, y0 + d * 0.72, h + 3), P(x0 + w + 0.05, y0 + d * 0.72, h + 3), P(x0 + w + 0.03, y0 + d / 2 + 0.05, h + 8), P(x0 - 0.03, y0 + d / 2 + 0.05, h + 8)])} />
      <Line a={top} b={[top[0], top[1] - 20]} stroke="#6B6257" strokeWidth={1.1} />
      <g transform={`translate(${r1(top[0])} ${r1(top[1] - 16.5)})`}>
        <rect className="lt-flag-wave" x={0} y={-3.5} width={11} height={7} rx={1} fill={color} />
      </g>
    </g>
  )
})

// The town hall's money in front of it: a stack of coins (one per $12,000, 1
// to 10), or a red IOU slip when it owes. Nothing when the figure is not
// measured. The amount is a separate part (TreasuryAmount) drawn in the top
// layer, so buildings in front never hide it.
const TREASURY = P(9.84, 9.84)
const coinsFor = cash => clamp(Math.ceil(cash / 12000), 1, 10)

export const Treasury = memo(function Treasury({ cash }) {
  const [x, y] = TREASURY
  if (!Number.isFinite(cash)) return <g className="lt-treasury" />
  if (cash >= 0) {
    return (
      <g className="lt-treasury">
        {Array.from({ length: coinsFor(cash) }, (_, k) => (
          <ellipse key={k} className="lt-coin" cx={x} cy={r1(y - k * 2.3)} rx={4.6} ry={2.2} fill="#E3A92B" stroke="#B9861A" strokeWidth={0.6} />
        ))}
      </g>
    )
  }
  return (
    <g className="lt-treasury is-owed">
      <path d={`M${r1(x - 6)} ${r1(y - 9)} h12 v8 l-2 -1.4 l-2 1.4 l-2 -1.4 l-2 1.4 l-2 -1.4 l-2 1.4 z`} fill="#FBEDEA" stroke="#C8483B" strokeWidth={0.8} />
    </g>
  )
})

// The amount beside the coin stack ("$78k"), or "owes $23k" beside the IOU
// slip; beside rather than above (as in the mockup), so it never runs into
// the banner on the town hall's façade.
export const TreasuryAmount = memo(function TreasuryAmount({ cash }) {
  if (!Number.isFinite(cash)) return null
  const [x, y] = TREASURY
  const owes = cash < 0
  return (
    <text className={`lt-amount${owes ? ' is-owed' : ''}`} x={r1(x + (owes ? 7.5 : 6.5))} y={r1(owes ? y - 2.5 : y - (coinsFor(cash) - 1) * 2.3 + 2.8)}>
      {owes ? `${SIGNS.owes} ${formatMoneyShort(-cash)}` : formatMoneyShort(cash)}
    </text>
  )
})

// Families queuing for help outside the town hall (the model's 0 to 9).
export const Queue = memo(function Queue({ size }) {
  return (
    <g className="lt-queue">
      {Array.from({ length: size }, (_, j) => {
        const [x, y] = P(8.22 + j * 0.16, 9.9 + (j % 2) * 0.04)
        return <Figure key={j} x={x} y={y} shirt={SHIRTS[j % SHIRTS.length]} scale={0.85} />
      })}
    </g>
  )
})

// The bank, a stack of loan papers on its roof (the model's 0 to 7), and a red
// overlay the motion loop flashes when loans go bad.
export const Bank = memo(function Bank({ papers }) {
  const { gx: x0, gy: y0, w, d, h } = BANK
  const coin = P(x0 + w + 0.001, y0 + d / 2, h / 2)
  return (
    <g data-kind="bank">
      <polygon points={pts([P(x0, y0 + d), P(x0 + w, y0 + d), P(x0 + w, y0 + d, h), P(x0, y0 + d, h)])} fill="#E6E2DA" />
      <polygon points={pts([P(x0 + w, y0), P(x0 + w, y0 + d), P(x0 + w, y0 + d, h), P(x0 + w, y0, h)])} fill="#C8C3B9" />
      <polygon points={pts([P(x0, y0, h), P(x0 + w, y0, h), P(x0 + w, y0 + d, h), P(x0, y0 + d, h)])} fill="#F1EEE8" />
      <polygon points={pts([P(x0, y0, h + 2), P(x0 + w, y0, h + 2), P(x0 + w, y0 + d, h + 2), P(x0, y0 + d, h + 2)])} fill="#D9D4CA" />
      <polygon className="lt-snow" points={pts([P(x0 + 0.1, y0 + 0.1, h + 2.2), P(x0 + w - 0.1, y0 + 0.1, h + 2.2), P(x0 + w - 0.1, y0 + d - 0.1, h + 2.2), P(x0 + 0.1, y0 + d - 0.1, h + 2.2)])} />
      {[0, 1, 2, 3, 4].map(k => {
        const u = x0 + 0.18 + k * 0.33
        return <Line key={k} a={P(u, y0 + d, 2)} b={P(u, y0 + d, h - 3)} stroke="#D2CDC3" strokeWidth={2} />
      })}
      <circle cx={r1(coin[0])} cy={r1(coin[1])} r={4} fill="#E3A92B" stroke="#fff" strokeWidth={1} />
      <polygon className="lt-flash" data-flash="bank" opacity={0} fill="#E0584A"
        points={pts([P(x0 + w, y0), P(x0 + w, y0 + d), P(x0 + w, y0 + d, h), P(x0 + w, y0, h), P(x0, y0, h), P(x0, y0 + d, h), P(x0, y0 + d)])} />
      <g className="lt-papers">
        {Array.from({ length: papers }, (_, k) => {
          const z = 19.5 + k * 1.3
          return <polygon key={k} points={pts([P(5.7, 5.7, z), P(6.3, 5.7, z), P(6.3, 6.3, z), P(5.7, 6.3, z)])} fill={k % 2 ? '#FFFFFF' : '#F3EEE3'} stroke="#C9C2B4" />
        })}
      </g>
    </g>
  )
})
