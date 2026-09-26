import { Activity, useEffect, useEffectEvent, useId, useRef, useState } from 'react'
import { COPY, NUMBER_GROUPS, capitalise, describePolicy } from '../catalog.js'
import { rulesAt, rulesDiff } from '../data/derive.js'
import { hardshipNote, weekLabel } from '../narration.js'
import AtAGlance from './AtAGlance.jsx'
import CashChart from './CashChart.jsx'
import FeelMeter from './FeelMeter.jsx'
import FirmStates from './FirmStates.jsx'
import HiresAndLayoffs from './HiresAndLayoffs.jsx'
import LoansWrittenOff from './LoansWrittenOff.jsx'
import MoneyInOut from './MoneyInOut.jsx'
import OpenedClosed from './OpenedClosed.jsx'
import PriceTag from './PriceTag.jsx'
import RulesInForce from './RulesInForce.jsx'
import SeeItBig from './SeeItBig.jsx'
import ShareBars from './ShareBars.jsx'
import Tile from './Tile.jsx'
import WealthLadder from './WealthLadder.jsx'
import '../next.css'

// The special visuals of each group (NUMBER_GROUPS `extras`), by id, each
// drawn as <Extra arms tick onSeeBig className />.
const EXTRAS = {
  hiresAndLayoffs: HiresAndLayoffs,
  wealthLadder: WealthLadder,
  firmStates: FirmStates,
  openedClosed: OpenedClosed,
  moneyInOut: MoneyInOut,
  loansWrittenOff: LoansWrittenOff,
}

// Numbers drawn by a special visual instead of a Tile, each as <Visual
// metricKey arms tick onSeeBig className />; null when the visual of another
// number already draws it (the share bars hold both shares).
const KEY_VISUALS = {
  priceFood: PriceTag,
  priceHousing: PriceTag,
  priceServices: PriceTag,
  priceHealthcare: PriceTag,
  townHallCash: CashChart,
  happiness: FeelMeter,
  topTenthShare: ShareBars,
  bottomHalfShare: null,
}

// An extra that sits right after a number of its group, as in mockup 06; the
// others follow the group's numbers.
const AFTER = { wealthLadder: 'gini', moneyInOut: 'townHallCash' }

// How many of the 12 grid columns a card spans, from mockup 06; 4 otherwise.
const SPAN = {
  peopleOutOfWorkPer100: 3,
  typicalWeeklyPay: 3,
  publicWorksJobs: 6,
  hiresAndLayoffs: 12,
  priceFood: 3,
  priceHousing: 3,
  priceServices: 3,
  priceHealthcare: 3,
  foodSpendPerHousehold: 12,
  wealthLadder: 8,
  topTenthShare: 12,
  townHallCash: 8,
  homelessHouseholds: 3,
  careDenials: 3,
  happiness: 6,
}
const TILE_HEIGHT = { peopleOutOfWorkPer100: 90, typicalWeeklyPay: 90, gini: 90, firmsOpen: 80, foodSpendPerHousehold: 90 }

// A group's cards in order: each number (or the visual that draws it), with
// the extras placed after their number, then the other extras.
function cardsOf(group) {
  const extras = group.extras ?? []
  const cards = []
  for (const key of group.keys) {
    if (KEY_VISUALS[key] !== null) cards.push({ id: key, extra: false })
    extras.filter(extra => AFTER[extra] === key).forEach(extra => cards.push({ id: extra, extra: true }))
  }
  extras.filter(extra => !group.keys.includes(AFTER[extra])).forEach(extra => cards.push({ id: extra, extra: true }))
  return cards
}

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

function liveStatus(live, arms) {
  if (live?.phase === 'lost') {
    const label = live.error?.town ?? live.towns?.find(town => town.status === 'lost')?.label
    const town = live.towns?.find(town => town.label === label)
    const describe = live.error?.kind === 'crashed' ? COPY.live.crashed : COPY.live.lost
    return `${describe(label, town?.lastTick ? weekLabel(town.lastTick) : null, arms.length > 1)} ${COPY.numbers.continue}`
  }
  if (live?.phase === 'horizon' || live?.phase === 'finished') {
    const horizon = Math.max(0, ...arms.map(arm => arm.horizon || arm.ticks.at(-1) || 0))
    return `${COPY.end.up(horizon)} ${COPY.numbers.continue}`
  }
  return null
}

// "Show me all the numbers": a sheet over the Run screen, on the same clock
// (`tick`). A header with the week and each town's rules, jump chips and a
// chart key, then the rules in force, this week at a glance, and one card per
// NUMBER_GROUPS entry: a Tile per number, or the special visual that draws it,
// and the group's extras. Focus moves to the heading when
// it opens and back to whatever had it when it closes; Escape closes it (or
// the big chart first, when one is open), as do both "Back to the towns"
// buttons. The jump bar's button shows once the header's has scrolled away.
// `live` (RunScreen's live prop) marks a lost town's columns; `playing` stops
// the big chart's cursor easing while the clock runs. `top` is the height in
// px of the sticky bar above the sheet (RunScreen's timeline, measured): the
// jump bar sticks right under it, and the header's way back counts as gone
// once it has slid under it. `id` names the sheet for the button that opens it.
export default function NumbersSheet({ id, arms, tick, onClose, live, playing = false, top = 0 }) {
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

  // One way back at a time: the jump bar's button once the header's is gone,
  // that is, once it has slid under the bar above the sheet.
  useEffect(() => {
    const target = headBackRef.current
    if (!target || typeof IntersectionObserver === 'undefined') return undefined
    const rootMargin = `${top > 0 ? `-${top}px` : '0px'} 0px 0px 0px`
    const observer = new IntersectionObserver(([entry]) => setStuck(!entry.isIntersecting), { rootMargin })
    observer.observe(target)
    return () => observer.disconnect()
  }, [top])

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
    <section
      ref={sheetRef}
      id={id}
      className={`nx-sheet${playing ? ' is-playing' : ''}`}
      style={{ '--nx-sheet-top': `${top}px` }}
      role="dialog"
      aria-labelledby={titleId}
    >
      <header className="nx-sheet-head">
        <div>
          <h2 id={titleId} ref={headingRef} tabIndex={-1}>{COPY.numbers.title}</h2>
          <p className="nx-sheet-lead">{COPY.numbers.lead(arms.length, weekLabel(tick))}</p>
          <p className="nx-sheet-hint">{COPY.numbers.hint}</p>
          {live && <p className="nx-notice" role="status" aria-live="polite">{liveStatus(live, arms)}</p>}
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
        <div className="nx-jump-links">
          {sections.map(section => (
            <a key={section.id} href={`#${section.id}`} onClick={jump(section.id)}>{section.label}</a>
          ))}
        </div>
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
                    {cardsOf(group).map(({ id, extra }) => {
                      const span = `nx-s${SPAN[id] ?? 4}`
                      if (extra) {
                        const Extra = EXTRAS[id]
                        return Extra ? <Extra key={id} arms={arms} tick={tick} onSeeBig={setBig} className={span} /> : null
                      }
                      const Visual = KEY_VISUALS[id]
                      if (Visual) return <Visual key={id} metricKey={id} arms={arms} tick={tick} onSeeBig={setBig} className={span} />
                      const note = hardshipNote(id, arms, tick)
                      return (
                        <Tile key={id} metricKey={id} arms={arms} tick={tick} onSeeBig={setBig} className={span} height={TILE_HEIGHT[id]}>
                          {note && <p className="nx-quiet">{note}</p>}
                        </Tile>
                      )
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
