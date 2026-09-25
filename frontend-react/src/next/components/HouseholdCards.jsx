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
    ? eventSentence(event, {
      firmName: firm => firmDisplayName(directory?.byId?.[firm.id] ?? firm),
      lostHome: subject.housingSecurity === false,
    })
    : householdStateSentence(subject, { employerName: employer })

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
            aria-label={COPY.households.followLabel(name)}
            onClick={() => onTogglePin(subject.id)}
          >
            {COPY.households.follow}
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
// In a live town (`onTrack(action, householdId)`) Follow also pins or unpins
// the household on the server: it asks the server to follow it first, since
// the week shown may be older than the server's sample. "Meet other families"
// asks for a new sample, which shows from the next live week, so it is on
// only while `canReshuffle` (the town runs and the viewer is on the live week).
export default function HouseholdCards({ arm, tick, onTrack, canReshuffle = true }) {
  const [offset, setOffset] = useState(0)
  const [pinnedId, setPinnedId] = useState(null)
  const sample = snapshotAt(arm, tick)?.subjects ?? []

  const pinned = pinnedId == null ? null : sample.find(subject => subject.id === pinnedId) ?? null
  const rest = pinned ? sample.filter(subject => subject !== pinned) : sample
  const slots = Math.min(PAGE - (pinned ? 1 : 0), rest.length)
  const start = rest.length ? offset % rest.length : 0
  const shown = Array.from({ length: slots }, (_, i) => rest[(start + i) % rest.length])
  const cards = pinned ? [pinned, ...shown] : shown

  const togglePin = id => {
    if (onTrack) {
      if (pinnedId === id) {
        onTrack('unpin', id)
      } else {
        if (pinnedId != null) onTrack('unpin', pinnedId)
        onTrack('follow', id)
        onTrack('pin', id)
      }
    }
    setPinnedId(current => (current === id ? null : id))
  }
  const meetOthers = () => {
    onTrack('reshuffle')
    setOffset(0)
  }

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
      {onTrack && (
        <button type="button" className="nx-more" disabled={!canReshuffle} onClick={meetOthers}>{COPY.live.meetOthers}</button>
      )}
    </div>
  )
}
