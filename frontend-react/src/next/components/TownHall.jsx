import { useEffect, useId, useRef, useState } from 'react'
import { COPY, DEFAULT_POLICY, describePolicy, leverName, townTextColor } from '../catalog.js'
import { weekLabel } from '../narration.js'
import { policyProblems } from '../policyRules.js'
import LeverEditor from './LeverEditor.jsx'
import '../next.css'

const MAX_RECEIPTS = 5
const same = (a, b) => (typeof a === 'number' && typeof b === 'number' ? Math.abs(a - b) < 1e-9 : String(a) === String(b))

// The rules a town's hall has in force: the latest week's lever vector (with
// any change it has applied since), or, before any week has run, the rules it
// was set up with. A change still on its way to the town hall counts as made,
// so the editor neither snaps back to the old rules nor offers to send the
// same change again; if the town hall refuses it, the rules in force show.
function currentRules(arm) {
  const rules = { ...DEFAULT_POLICY, ...(arm?.policy ?? arm?.setup?.initial_policy ?? {}) }
  for (const receipt of arm?.receipts ?? []) {
    if (receipt.status === 'sending' || receipt.status === 'queued') Object.assign(rules, receipt.requested)
  }
  return rules
}

// The levers of `draft` that differ from `current`.
function changesFrom(draft, current) {
  const changed = {}
  for (const [lever, value] of Object.entries(draft ?? {})) {
    if (!same(value, current[lever])) changed[lever] = value
  }
  return changed
}

function ReceiptLines({ receipt }) {
  if (receipt.status === 'sending' || receipt.status === 'queued') return <span>{COPY.hall.waiting}</span>
  if (receipt.status === 'failed') return <span>{COPY.hall.failed(receipt.message ?? '')}</span>
  const rejected = Object.entries(receipt.rejected ?? {})
  // A change the town hall refused outright reads as its reasons alone.
  const showApplied = Object.keys(receipt.applied ?? {}).length > 0 || rejected.length === 0
  return (
    <>
      {showApplied && <span>{COPY.hall.applied(weekLabel(receipt.effectiveTick), describePolicy(receipt.applied))}</span>}
      {rejected.map(([lever, reason]) => (
        <span key={lever} className="is-rejected">{COPY.hall.rejected(leverName(lever), reason)}</span>
      ))}
    </>
  )
}

// The Town hall drawer: pick a town, change its rules from next week, and see
// what the town hall did with each change. `locked` (a sentence) disables the
// change button and says why. With `autoFocus` (opened from its toggle) focus
// moves to the drawer's heading when it opens.
export default function TownHall({ id, arms, onConfigure, onClose, locked = null, autoFocus = false }) {
  const uid = useId()
  const headingRef = useRef(null)
  // Only on opening: the drawer keeps whatever focus it has after that.
  const focusOnOpen = useRef(autoFocus)
  useEffect(() => {
    if (focusOnOpen.current) headingRef.current?.focus()
  }, [])
  const [selected, setSelected] = useState(0)
  const [drafts, setDrafts] = useState({})
  const index = Math.min(selected, Math.max(0, arms.length - 1))
  const arm = arms[index]
  const current = currentRules(arm)
  const changed = changesFrom(drafts[index], current)
  const proposed = { ...current, ...changed }
  const ready = !locked && Object.keys(changed).length > 0 && Object.keys(policyProblems(proposed)).length === 0
  const receipts = (arm?.receipts ?? []).map((receipt, i) => ({ receipt, key: receipt.actionId ?? `r${i}` })).reverse().slice(0, MAX_RECEIPTS)
  const titleId = `${uid}-title`

  const edit = policy => setDrafts(all => ({ ...all, [index]: changesFrom(policy, current) }))
  const apply = () => {
    if (!ready) return
    onConfigure(index, changed)
    setDrafts(all => ({ ...all, [index]: {} }))
  }

  return (
    <aside
      id={id}
      className="nx-hall"
      aria-label={COPY.hall.title}
      onKeyDown={event => { if (event.key === 'Escape') onClose() }}
    >
      <div className="nx-hall-top">
        <div className="nx-hall-head">
          <h2 id={titleId} ref={headingRef} tabIndex={-1}>{COPY.hall.title}</h2>
          <button type="button" className="nx-abtn" aria-label={COPY.hall.closeLabel} onClick={onClose}>{COPY.hall.close}</button>
        </div>
        <div className="nx-hall-tabs" role="group" aria-label={COPY.hall.towns}>
          {arms.map((town, i) => (
            <button
              key={town.label}
              type="button"
              aria-pressed={i === index}
              style={{ '--nx-tab': town.color, color: townTextColor(town.color) }}
              onClick={() => setSelected(i)}
            >
              <i style={{ background: town.color }} aria-hidden="true" />
              {town.label}
            </button>
          ))}
        </div>
        <p className="nx-hall-note">{COPY.hall.note(arms.length)}</p>
      </div>

      <div className="nx-hall-body">
        {receipts.length > 0 && (
          <section className="nx-receipts" aria-labelledby={`${uid}-receipts`}>
            <h3 id={`${uid}-receipts`}>{COPY.hall.receipts}</h3>
            <ul aria-live="polite">
              {receipts.map(({ receipt, key }) => (
                <li key={key} className={`is-${receipt.status}`}><ReceiptLines receipt={receipt} /></li>
              ))}
            </ul>
          </section>
        )}
        <LeverEditor value={proposed} base={current} onChange={edit} idPrefix={`${uid}-town-${index}`} />
      </div>

      <div className="nx-hall-foot">
        {locked && <p className="nx-hall-locked" role="status">{locked}</p>}
        <button type="button" className="nx-abtn is-dark nx-hall-apply" disabled={!ready} onClick={apply}>{COPY.hall.apply}</button>
      </div>
    </aside>
  )
}
