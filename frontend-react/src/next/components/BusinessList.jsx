import { useState } from 'react'
import { COPY, FIRM_STATES, formatMoneyShort, sectorName } from '../catalog.js'
import { snapshotAt } from '../data/derive.js'
import { firmDisplayName } from '../names.js'
import { weekLabel } from '../narration.js'
import '../next.css'

// Open firms richest first, then firms closed in the last year, faded. The
// list keeps room for `max` rows and the button line under it, so the page
// does not move as firms open and close (spec section 6). "See all" shows
// every firm in a box a few rows taller that scrolls inside itself (and takes
// keyboard focus to scroll), so the page holds still with it open too; its
// button stays until the viewer closes it.
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
    <div className="nx-card nx-biz" data-stable={`businesses:${arm?.label}`}>
      <div className="nx-bh"><h3>{COPY.businesses.title}</h3><span>{COPY.businesses.subtitle}</span></div>
      <div
        className={`nx-blistbox${expanded ? ' is-open' : ''}`}
        style={{ '--nx-rows': max }}
        role={expanded ? 'region' : undefined}
        aria-label={expanded ? COPY.businesses.allLabel(arm?.label) : undefined}
        tabIndex={expanded ? 0 : undefined}
      >
        {rows.length === 0 ? (
          <p className="nx-empty">{COPY.businesses.empty}</p>
        ) : (
          <ol className="nx-blist">
            {visible.map(row => <BusinessRow key={row.key} row={row} />)}
          </ol>
        )}
      </div>
      <div className="nx-bfoot">
        {(rows.length > max || expanded) && (
          <button type="button" className="nx-more" aria-expanded={expanded} onClick={() => setExpanded(value => !value)}>
            {expanded ? COPY.businesses.showFewer : COPY.businesses.seeAll(rows.length)}
          </button>
        )}
      </div>
    </div>
  )
}

// One firm on one row: its name and trade cut short with the full wording in
// their titles.
function BusinessRow({ row }) {
  const name = firmDisplayName(row.firm)
  const sector = sectorName(row.firm.sector)
  return (
    <li className={`nx-brow${row.state === 'closed' ? ' is-closed' : ''}`} data-fits="business-row">
      <div className="rk">{row.rank ?? ''}</div>
      <div className="nm">
        <span className="nx-bname" title={name}>{name}</span>
        <small title={sector}>{sector}</small>
      </div>
      <div className="bar"><b style={{ width: `${row.width}%` }} /><span>{row.money}</span></div>
      <div className="st">{COPY.businesses.staff(row.staff ?? 0)}</div>
      <span className={`nx-tag is-${row.state}`}>{FIRM_STATES[row.state] ?? row.state}</span>
    </li>
  )
}

function clampWidth(percent) {
  return Math.round(Math.min(100, Math.max(2, percent)) * 10) / 10
}
