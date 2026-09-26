import { Activity, useEffect, useEffectEvent, useId, useRef, useState } from 'react'
import { COPY, NUMBER_GROUPS, capitalise, describePolicy } from '../catalog.js'
import { rulesAt, rulesDiff } from '../data/derive.js'
import { weekLabel } from '../narration.js'
import AtAGlance from './AtAGlance.jsx'
import RulesInForce from './RulesInForce.jsx'
import SeeItBig from './SeeItBig.jsx'
import Tile from './Tile.jsx'
import '../next.css'

// The special visuals of each group (NUMBER_GROUPS `extras`), by id, each
// drawn as <Extra arms tick />. Task K fills this; until then an extra draws
// nothing.
const EXTRAS = {}

// How many of the 12 grid columns a tile spans, from mockup 06; 4 otherwise.
const TILE_SPAN = {
  peopleOutOfWorkPer100: 3,
  typicalWeeklyPay: 3,
  publicWorksJobs: 6,
  priceFood: 3,
  priceHousing: 3,
  priceServices: 3,
  priceHealthcare: 3,
  foodSpendPerHousehold: 12,
  townHallCash: 8,
  homelessHouseholds: 3,
  careDenials: 3,
  happiness: 6,
}
const TILE_HEIGHT = { peopleOutOfWorkPer100: 90, typicalWeeklyPay: 90, gini: 90, firmsOpen: 80, townHallCash: 120, foodSpendPerHousehold: 90 }

function BackIcon() {
  return <svg viewBox="0 0 12 12" aria-hidden="true" focusable="false"><path d="M7.5 2 L3.5 6 L7.5 10" /></svg>
}

function TapIcon() {
  return (
    <svg viewBox="0 0 16 16" aria-hidden="true" focusable="false">
      <path d="M9.5 2.5h4v4M13.5 2.5 8.5 7.5M6.5 13.5h-4v-4M2.5 13.5l5-5" />
    </svg>
  )
}

// A live town whose connection is gone keeps its last numbers; its column says when.
function lostNote(live, index) {
  const town = live?.towns?.[index]
  if (town?.status !== 'lost') return null
  return COPY.numbers.lost(town.lastTick ? weekLabel(town.lastTick) : null)
}

// "Show me all the numbers": a sheet over the Run screen, on the same clock
// (`tick`). A header with the week and each town's rules, jump chips and a
// chart key, then the rules in force, this week at a glance, and one card per
// NUMBER_GROUPS entry with a Tile per number. Focus moves to the heading when
// it opens and back to whatever had it when it closes; Escape closes it (or
// the big chart first, when one is open), as do both "Back to the towns"
// buttons. The jump bar's button shows once the header's has scrolled away.
// `live` (RunScreen's live prop) marks a lost town's columns; `playing` stops
// the big chart's cursor easing while the clock runs.
export default function NumbersSheet({ arms, tick, onClose, live, playing = false }) {
  const uid = useId().replace(/:/g, '')
  const titleId = `nx-sheet-${uid}`
  const headingRef = useRef(null)
  const headBackRef = useRef(null)
  const sheetRef = useRef(null)
  const returnTo = useRef(null)
  const [stuck, setStuck] = useState(false)
  const [big, setBig] = useState(null)

  // Focus into the sheet on open, and back to the opener when it goes.
  useEffect(() => {
    const opener = document.activeElement
    headingRef.current?.focus()
    return () => {
      if (opener && opener !== document.body && opener.isConnected && typeof opener.focus === 'function') opener.focus()
    }
  }, [])

  const closeBig = () => {
    returnTo.current = big
    setBig(null)
  }

  const onKey = useEffectEvent(event => {
    if (event.key !== 'Escape' || event.defaultPrevented) return
    event.preventDefault()
    if (big) closeBig()
    else onClose?.()
  })
  useEffect(() => {
    const listener = event => onKey(event)
    document.addEventListener('keydown', listener)
    return () => document.removeEventListener('keydown', listener)
  }, [])

  // Back to the tile that opened the big chart.
  useEffect(() => {
    if (big || !returnTo.current) return
    const key = returnTo.current
    returnTo.current = null
    const tile = [...(sheetRef.current?.querySelectorAll('[data-metric]') ?? [])].find(node => node.dataset.metric === key)
    tile?.focus()
  }, [big])

  // One way back at a time: the jump bar's button once the header's is gone.
  useEffect(() => {
    const target = headBackRef.current
    if (!target || typeof IntersectionObserver === 'undefined') return undefined
    const observer = new IntersectionObserver(([entry]) => setStuck(!entry.isIntersecting), { rootMargin: '-110px 0px 0px 0px' })
    observer.observe(target)
    return () => observer.disconnect()
  }, [])

  const sectionId = name => `nx-numbers-${uid}-${name}`
  const sections = [
    { id: sectionId('rules'), label: COPY.numbers.jumpRules },
    { id: sectionId('glance'), label: COPY.numbers.jumpGlance },
    ...NUMBER_GROUPS.map(group => ({ id: sectionId(group.id), label: COPY.numbers.groups[group.id]?.title ?? group.id })),
  ]
  const jump = id => event => {
    event.preventDefault()
    const section = document.getElementById(id)
    section?.scrollIntoView?.({ block: 'start' })
    section?.querySelector('h3')?.focus({ preventScroll: true })
  }
  const notes = arms.map((_, i) => lostNote(live, i))

  return (
    <section ref={sheetRef} className={`nx-sheet${playing ? ' is-playing' : ''}`} role="dialog" aria-labelledby={titleId}>
      <header className="nx-sheet-head">
        <div>
          <h2 id={titleId} ref={headingRef} tabIndex={-1}>{COPY.numbers.title}</h2>
          <p className="nx-sheet-lead">{COPY.numbers.lead(arms.length, weekLabel(tick))}</p>
          <p className="nx-sheet-hint">{COPY.numbers.hint}</p>
          <ul className="nx-sheet-towns" aria-label={COPY.numbers.towns}>
            {arms.map((arm, i) => (
              <li key={arm.label} className="nx-tchip">
                <i style={{ background: arm.color }} aria-hidden="true" />
                <b>{arm.label}</b>
                {capitalise(describePolicy(rulesDiff(rulesAt(arm, tick))))}
                {notes[i] && <span className="nx-tchip-note">{notes[i]}</span>}
              </li>
            ))}
          </ul>
        </div>
        <button ref={headBackRef} type="button" className="nx-abtn is-dark" onClick={onClose}><BackIcon />{COPY.numbers.back}</button>
      </header>

      <nav className="nx-jump" aria-label={COPY.numbers.jump} hidden={Boolean(big)}>
        {sections.map(section => (
          <a key={section.id} href={`#${section.id}`} onClick={jump(section.id)}>{section.label}</a>
        ))}
        <span className="nx-sp" />
        <button type="button" className="nx-abtn" style={{ visibility: stuck ? 'visible' : 'hidden' }} onClick={onClose}>
          <BackIcon />{COPY.numbers.back}
        </button>
      </nav>

      <ul className="nx-ckey" aria-label={COPY.numbers.key.label}>
        <li><i className="nx-ckey-warm" aria-hidden="true" />{COPY.numbers.key.warm}</li>
        <li><i className="nx-ckey-now" aria-hidden="true" />{COPY.numbers.key.now}</li>
        <li><i className="nx-ckey-future" aria-hidden="true" />{COPY.numbers.key.future}</li>
      </ul>

      <div className="nx-sheet-body">
        {big && <SeeItBig key={big} metricKey={big} arms={arms} tick={tick} onClose={closeBig} playing={playing} />}
        {/* While a chart is big the sections are hidden, keep their state (an
            open rules group, the tile to come back to) and update only when
            React is idle. */}
        <Activity mode={big ? 'hidden' : 'visible'}>
          <div className="nx-sheet-secs">
            <RulesInForce id={sections[0].id} arms={arms} tick={tick} notes={notes} />
            <AtAGlance id={sections[1].id} arms={arms} tick={tick} notes={notes} />
            {NUMBER_GROUPS.map(group => {
              const copy = COPY.numbers.groups[group.id] ?? { title: group.id, blurb: '' }
              const headId = `${sectionId(group.id)}-title`
              return (
                <section key={group.id} id={sectionId(group.id)} className="nx-nsec" aria-labelledby={headId}>
                  <div className="nx-sh">
                    <h3 id={headId} tabIndex={-1}>{copy.title}</h3>
                    <p>{copy.blurb}</p>
                  </div>
                  <div className="nx-ngrid">
                    {group.keys.map(key => (
                      <Tile
                        key={key}
                        metricKey={key}
                        arms={arms}
                        tick={tick}
                        onSeeBig={setBig}
                        className={`nx-s${TILE_SPAN[key] ?? 4}`}
                        height={TILE_HEIGHT[key]}
                      />
                    ))}
                    {(group.extras ?? []).map(extra => {
                      const Extra = EXTRAS[extra]
                      return Extra ? <Extra key={extra} arms={arms} tick={tick} /> : null
                    })}
                  </div>
                </section>
              )
            })}
          </div>
        </Activity>
      </div>
      <p className="nx-tap" hidden={Boolean(big)}><TapIcon />{COPY.numbers.tap}</p>
    </section>
  )
}
