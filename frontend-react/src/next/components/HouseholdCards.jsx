import { useState } from 'react'
import { COPY, HOUSEHOLD_STATES, formatMoney } from '../catalog.js'
import { householdState, latestEventFor, snapshotAt } from '../data/derive.js'
import { firmDisplayName, householdName } from '../names.js'
import { eventSentence, householdStateSentence, weekLabel } from '../narration.js'
import '../next.css'

const PAGE = 4

function jobLine(subject, employerName) {
  if (subject.isEmployed && employerName) return COPY.households.worksAt(employerName)
  if (subject.canWork) return COPY.households.looking
  return COPY.households.notWorking
}

function HouseholdCard({ subject, arm, tick, pinned, onTogglePin }) {
  const name = householdName(subject.id)
  const state = householdState(subject)
  const directory = arm?.firmDirectory
  const employer = subject.employer
    ? firmDisplayName(directory?.byName?.[subject.employer] ?? { name: subject.employer, sector: subject.employerCategory })
    : null
  const event = latestEventFor(arm, subject.id, tick)
  const sentence = event
    ? eventSentence(event, { firmName: firm => firmDisplayName(directory?.byId?.[firm.id] ?? firm) })
    : householdStateSentence(subject, { employerName: employer })
  const visible = pinned ? COPY.households.following : COPY.households.follow

  return (
    <li className={`nx-hc${pinned ? ' is-pinned' : ''}`}>
      <div className={`av is-${state}-bg`} aria-hidden="true">{name.charAt(0)}</div>
      <div>
        <div className="n">
          <span className="nx-hname">{COPY.households.nameAge(name, subject.age)}</span>
          <button
            type="button"
            className="pin"
            aria-pressed={pinned}
            aria-label={COPY.households.followLabel(visible, name)}
            onClick={() => onTogglePin(subject.id)}
          >
            {visible}
          </button>
        </div>
        <div className="j">{jobLine(subject, employer)}</div>
        <div className="m">
          <span className={`nx-chip is-${state}`}><i aria-hidden="true" />{HOUSEHOLD_STATES[state].chip}</span>
          <span className="cash"><b>{formatMoney(subject.cash)}</b> {COPY.households.saved}</span>
        </div>
        <div className="ev">
          {sentence}
          {event && <span className="when"> · {weekLabel(event.tick)}</span>}
        </div>
      </div>
    </li>
  )
}

// Four households from the tracked sample; "Follow" keeps one in the first slot.
export default function HouseholdCards({ arm, tick }) {
  const [offset, setOffset] = useState(0)
  const [pinnedId, setPinnedId] = useState(null)
  const sample = snapshotAt(arm, tick)?.subjects ?? []

  const pinned = pinnedId == null ? null : sample.find(subject => subject.id === pinnedId) ?? null
  const rest = pinned ? sample.filter(subject => subject !== pinned) : sample
  const slots = Math.min(PAGE - (pinned ? 1 : 0), rest.length)
  const start = rest.length ? offset % rest.length : 0
  const shown = Array.from({ length: slots }, (_, i) => rest[(start + i) % rest.length])
  const cards = pinned ? [pinned, ...shown] : shown

  const togglePin = id => setPinnedId(current => (current === id ? null : id))

  return (
    <div className="nx-card nx-hh">
      <div className="nx-bh"><h3>{COPY.households.title}</h3><span>{COPY.households.subtitle}</span></div>
      {cards.length === 0 ? (
        <p className="nx-empty">{COPY.households.empty}</p>
      ) : (
        <ul className="nx-hgrid">
          {cards.map(subject => (
            <HouseholdCard
              key={subject.id}
              subject={subject}
              arm={arm}
              tick={tick}
              pinned={subject.id === pinned?.id}
              onTogglePin={togglePin}
            />
          ))}
        </ul>
      )}
      {rest.length > slots && (
        <button type="button" className="nx-more" onClick={() => setOffset(value => value + slots)}>
          {COPY.households.showOthers}
        </button>
      )}
    </div>
  )
}
