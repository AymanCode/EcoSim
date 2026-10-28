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
  const job = jobLine(subject, employer)
  const cash = `${formatMoney(subject.cash)} ${COPY.households.saved}`
  const sentence = event
    ? eventSentence(event, {
      firmName: firm => firmDisplayName(directory?.byId?.[firm.id] ?? firm),
      lostHome: subject.housingSecurity === false,
    })
    : householdStateSentence(subject, { employerName: employer })
  const story = event ? `${sentence} · ${weekLabel(event.tick)}` : sentence

  // Every line keeps its height as the weeks change: the job and savings on
  // one line, the latest news in two (spec section 6). Cut-short text keeps
  // its full wording in a title.
  return (
    <li className={`nx-hc${pinned ? ' is-pinned' : ''}`}>
      <div className={`av is-${state}-bg`} aria-hidden="true">{name.charAt(0)}</div>
      <div className="nx-hctext">
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
        <div className="j" title={job}>{job}</div>
        <div className="m">
          <span className={`nx-chip is-${state}`}><i aria-hidden="true" />{HOUSEHOLD_STATES[state].chip}</span>
          <span className="cash" title={cash}><b>{formatMoney(subject.cash)}</b> {COPY.households.saved}</span>
        </div>
        <div className="ev" title={story} data-fits="household-news">
          {sentence}
          {event && <span className="when"> · {weekLabel(event.tick)}</span>}
        </div>
      </div>
    </li>
  )
}

// An empty slot, built like a card so it is exactly as tall, and hidden.
function EmptySlot() {
  return (
    <li className="nx-hc is-slot" aria-hidden="true">
      <div className="av" />
      <div className="nx-hctext">
        <div className="n">{'\u00a0'}</div>
        <div className="j">{'\u00a0'}</div>
        <div className="m"><span className="nx-chip">{'\u00a0'}</span></div>
        <div className="ev">{'\u00a0'}</div>
      </div>
    </li>
  )
}

// Four households from the tracked sample; "Follow" keeps one in the first slot.
// The panel always has four slots (empty ones when the sample is smaller) and
// a line for its buttons, so a sample that changes size never resizes it
// (spec section 6).
// In a live town (`onTrack(action, householdId)`) Follow also pins or unpins
// the household on the server: it asks the server to follow it first, since
// the week shown may be older than the server's sample. "Show other families"
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
    <div className="nx-card nx-hh" data-stable={`households:${arm?.label}`}>
      <div className="nx-bh"><h3>{COPY.households.title}</h3><span>{COPY.households.subtitle}</span></div>
      <div className="nx-hbody">
        {cards.length === 0 && <p className="nx-empty">{COPY.households.empty}</p>}
        <ul className="nx-hgrid" aria-hidden={cards.length === 0 || undefined}>
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
          {Array.from({ length: PAGE - cards.length }, (_, i) => <EmptySlot key={`slot-${i}`} />)}
        </ul>
      </div>
      <div className="nx-hfoot">
        {rest.length > slots && (
          <button type="button" className="nx-more" onClick={() => setOffset(value => value + slots)}>
            {COPY.households.showOthers}
          </button>
        )}
        {onTrack && (
          <button type="button" className="nx-more" disabled={!canReshuffle} onClick={meetOthers}>{COPY.live.meetOthers}</button>
        )}
      </div>
    </div>
  )
}
