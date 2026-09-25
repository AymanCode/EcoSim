import { useState } from 'react'
import { COPY, FIRM_STATES, formatMoneyShort, sectorName } from '../catalog.js'
import { snapshotAt } from '../data/derive.js'
import { firmDisplayName } from '../names.js'
import { weekLabel } from '../narration.js'
import '../next.css'

// Open firms richest first, then firms closed in the last year, faded.
export default function BusinessList({ arm, tick, max = 7 }) {
  const [expanded, setExpanded] = useState(false)
  const snapshot = snapshotAt(arm, tick)
  const open = [...(snapshot?.firms ?? [])].sort((a, b) => b.cash - a.cash)
  const closed = [...(snapshot?.firmsClosed ?? [])].sort((a, b) => b.closedTick - a.closedTick)
  const richest = Math.max(0, ...open.map(firm => firm.cash))
  const rows = [
    ...open.map((firm, rank) => ({
      key: `open-${firm.id}`,
      firm,
      rank: rank + 1,
      state: firm.state,
      width: richest > 0 ? clampWidth((firm.cash / richest) * 100) : 2,
      money: formatMoneyShort(firm.cash),
      staff: firm.staff,
    })),
    ...closed.map(firm => ({
      key: `closed-${firm.id}`,
      firm,
      rank: null,
      state: 'closed',
      width: 0,
      money: COPY.businesses.closedWhen(weekLabel(firm.closedTick)),
      staff: firm.lastStaff,
    })),
  ]
  const visible = expanded ? rows : rows.slice(0, max)

  return (
    <div className="nx-card nx-biz">
      <div className="nx-bh"><h3>{COPY.businesses.title}</h3><span>{COPY.businesses.subtitle}</span></div>
      {rows.length === 0 ? (
        <p className="nx-empty">{COPY.businesses.empty}</p>
      ) : (
        <ol className="nx-blist">
          {visible.map(row => (
            <li key={row.key} className={`nx-brow${row.state === 'closed' ? ' is-closed' : ''}`}>
              <div className="rk">{row.rank ?? ''}</div>
              <div className="nm">
                <span className="nx-bname">{firmDisplayName(row.firm)}</span>
                <small>{sectorName(row.firm.sector)}</small>
              </div>
              <div className="bar"><b style={{ width: `${row.width}%` }} /><span>{row.money}</span></div>
              <div className="st">{COPY.businesses.staff(row.staff ?? 0)}</div>
              <span className={`nx-tag is-${row.state}`}>{FIRM_STATES[row.state] ?? row.state}</span>
            </li>
          ))}
        </ol>
      )}
      {rows.length > max && (
        <button type="button" className="nx-more" aria-expanded={expanded} onClick={() => setExpanded(value => !value)}>
          {expanded ? COPY.businesses.showFewer : COPY.businesses.seeAll(rows.length)}
        </button>
      )}
    </div>
  )
}

function clampWidth(percent) {
  return Math.round(Math.min(100, Math.max(2, percent)) * 10) / 10
}
