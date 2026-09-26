import { Activity, useCallback, useEffect, useId, useLayoutEffect, useRef, useState } from 'react'
import { COPY, STAT_METRICS, STORY_METRICS, describePolicy, townTextColor } from './catalog.js'
import { rulesAt, rulesDiff } from './data/derive.js'
import { leadSentence, verdict } from './narration.js'
import BusinessList from './components/BusinessList.jsx'
import EndPanel from './components/EndPanel.jsx'
import Feed from './components/Feed.jsx'
import HorizonBar from './components/HorizonBar.jsx'
import HouseholdCards from './components/HouseholdCards.jsx'
import HowToRead from './components/HowToRead.jsx'
import LostPanel from './components/LostPanel.jsx'
import Moments from './components/Moments.jsx'
import NumbersSheet from './numbers/NumbersSheet.jsx'
import StatCard from './components/StatCard.jsx'
import StoryChart from './components/StoryChart.jsx'
import Town from './components/Town.jsx'
import TownHall from './components/TownHall.jsx'
import './next.css'

const escapeRegExp = text => text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

// Why the Town hall cannot change rules in this phase of a live run, or null.
const HALL_LOCKS = {
  connecting: COPY.hall.locked.connecting,
  horizon: COPY.hall.locked.over,
  finished: COPY.hall.locked.over,
  lost: COPY.hall.locked.lost,
}

// The lead sentence with each town's name in its colour.
function Lead({ text, arms }) {
  const labels = arms.map(arm => arm.label).filter(Boolean)
  if (!labels.length) return text
  const colors = Object.fromEntries(arms.map(arm => [arm.label, townTextColor(arm.color)]))
  const parts = text.split(new RegExp(`(${labels.map(escapeRegExp).join('|')})`))
  return parts.map((part, i) => (colors[part] && i % 2 === 1
    ? <span key={i} className="nx-tname" style={{ color: colors[part] }}>{part}</span>
    : part))
}

// A column head names the rules the town has in force at the week shown. A
// live town keeps an (empty) status line for the server's notices, so a
// notice is announced when it arrives.
function TownColumn({ arm, tick, single, live, notice, onTrack, canReshuffle }) {
  const town = <Town arm={arm} tick={tick} />
  const businesses = <BusinessList arm={arm} tick={tick} />
  return (
    <section className="nx-col" aria-label={arm.label}>
      <div className="nx-colhead">
        <i style={{ background: arm.color }} aria-hidden="true" />
        <h2>{arm.label}</h2>
        <span>{describePolicy(rulesDiff(rulesAt(arm, tick)))}</span>
      </div>
      {live && (
        <p className="nx-notice" role="status">
          {notice ? `${COPY.live.notice} ${COPY.app.detail(notice)}` : null}
        </p>
      )}
      {single ? <div className="nx-solo">{town}{businesses}</div> : <>{town}{businesses}</>}
      <HouseholdCards arm={arm} tick={tick} onTrack={onTrack} canReshuffle={canReshuffle} />
    </section>
  )
}

// Whether the town hall applied any change during the run.
const changedRules = arms => arms.some(arm => (arm.receipts ?? []).some(receipt => (
  receipt.status === 'applied' && Object.keys(receipt.applied ?? {}).length > 0
)))

// A live run's end or lost panel, or nothing while it runs.
function LivePanel({ live, arms, maxTick, horizon }) {
  if (live.phase === 'lost') {
    const lostLabel = live.error?.town ?? live.towns?.find(town => town.status === 'lost')?.label
    const lost = live.towns?.find(town => town.label === lostLabel)
    return (
      <LostPanel
        town={lostLabel}
        tick={lost?.lastTick ?? 0}
        townCount={arms.length}
        crashed={live.error?.kind === 'crashed'}
        detail={live.error?.kind === 'crashed' ? live.error.message : null}
        rulesChanged={changedRules(arms)}
        onRestart={live.onRestart}
        onNewExperiment={live.onNewExperiment}
      />
    )
  }
  if (live.phase === 'horizon' || live.phase === 'finished') {
    return (
      <EndPanel
        phase={live.phase}
        horizon={horizon}
        arms={arms}
        tick={maxTick}
        following={live.following !== false}
        onFollow={live.onFollow}
        onExtend={live.onExtend}
        onNewExperiment={live.onNewExperiment}
      />
    )
  }
  return null
}

// An element's height in whole px, kept up to date as it wraps and resizes;
// 0 until it has been measured. Returns the ref to put on the element.
function useHeight() {
  const [height, setHeight] = useState(0)
  const ref = useCallback(node => {
    if (!node || typeof ResizeObserver === 'undefined') return undefined
    const observer = new ResizeObserver(() => setHeight(Math.floor(node.getBoundingClientRect().height)))
    observer.observe(node)
    return () => observer.disconnect()
  }, [])
  return [ref, height]
}

const page = () => document.scrollingElement ?? document.documentElement

// The Run screen: every panel reads the week its parent's clock is on. With
// `live` (NextApp's live experiment) it also steers the towns: pause and
// resume, the end and lost panels, the Town hall drawer and the household
// sample. Without it, it replays recorded towns.
// "Show me all the numbers" (the line under the stat cards, or the timeline's
// button) opens the numbers sheet in the towns' place, under the timeline that
// still drives it; `numbersOpen` opens the screen on it. The sheet and the Town
// hall drawer are never open together.
export default function RunScreen({
  arms, tick, maxTick, playing, onToggle, onScrub, speed, onSpeed, live, numbersOpen: numbersAtStart = false,
}) {
  const horizon = Math.max(maxTick, ...arms.map(arm => arm.horizon || 0))
  const [metricKey, setMetricKey] = useState(STORY_METRICS[0])
  // The Town hall toggle, so focus can return to it when the drawer closes,
  // and whether the drawer was opened from it (then focus moves into it).
  const hallToggleRef = useRef(null)
  const [hallFocus, setHallFocus] = useState(false)
  const hallId = `${useId()}-hall`
  const single = arms.length === 1
  // A live run shows its towns from the first week every town has reached.
  const building = Boolean(live) && maxTick < 1
  const panel = live ? <LivePanel live={live} arms={arms} maxTick={maxTick} horizon={horizon} /> : null
  // New families appear in the live week only, so meeting them waits for a
  // running town and the viewer on the newest week.
  const canReshuffle = live?.phase === 'running' && live.following !== false

  // The numbers sheet: whether it is open, what opened it (focus goes back
  // there when the viewer closes it, else to the timeline's button), and the
  // page's scroll on the towns, given back when it closes.
  const [numbersOpen, setNumbersOpen] = useState(numbersAtStart)
  const numbersToggleRef = useRef(null)
  const numbersOpener = useRef(null)
  const numbersClosing = useRef(null)
  const numbersId = `${useId()}-numbers`
  const [barRef, barHeight] = useHeight()

  const openNumbers = opener => {
    numbersOpener.current = opener ?? null
    if (live?.hallOpen) live.onHall(false)
    setNumbersOpen(true)
  }
  // `refocus` false when something else takes focus (the Town hall drawer).
  const closeNumbers = ({ refocus = true } = {}) => {
    if (!numbersOpen) return
    numbersClosing.current = { refocus }
    setNumbersOpen(false)
  }

  // The sheet starts at its top; closing it goes back to where the towns were.
  // Leaving the Run screen with it open restores nothing.
  useLayoutEffect(() => {
    if (!numbersOpen) return undefined
    const scroller = page()
    const before = scroller.scrollTop
    scroller.scrollTop = 0
    return () => {
      if (numbersClosing.current) scroller.scrollTop = before
    }
  }, [numbersOpen])

  // Focus goes back to what opened the sheet, now visible again.
  useEffect(() => {
    const closing = numbersClosing.current
    if (numbersOpen || !closing) return
    numbersClosing.current = null
    if (!closing.refocus) return
    const opener = numbersOpener.current
    const target = opener?.isConnected ? opener : numbersToggleRef.current
    target?.focus()
  }, [numbersOpen])

  const toggleHall = open => {
    setHallFocus(open)
    if (open) closeNumbers({ refocus: false })
    live.onHall(open)
  }
  const closeHall = () => {
    live.onHall(false)
    hallToggleRef.current?.focus()
  }

  return (
    <div className={`nx-run${numbersOpen ? ' has-sheet' : ''}`}>
      <HorizonBar
        barRef={barRef}
        tick={tick}
        horizon={horizon}
        maxTick={maxTick}
        playing={playing}
        onToggle={onToggle}
        onScrub={onScrub}
        speed={speed}
        onSpeed={onSpeed}
        live={live}
        following={live?.following}
        onFollow={live?.onFollow}
        hallToggleRef={hallToggleRef}
        hallId={hallId}
        onHallToggle={live ? toggleHall : undefined}
        numbersOpen={numbersOpen}
        onNumbersToggle={(open, button) => (open ? openNumbers(button) : closeNumbers())}
        numbersToggleRef={numbersToggleRef}
        numbersId={numbersId}
        numbersDisabled={building}
      />
      {/* The drawer is fixed to the right; it comes right after the timeline so
          the keyboard reaches it before the columns. */}
      {live?.hallOpen && (
        <TownHall
          id={hallId}
          arms={arms}
          tick={tick}
          onConfigure={live.onConfigure}
          onClose={closeHall}
          locked={HALL_LOCKS[live.phase] ?? null}
          autoFocus={hallFocus}
        />
      )}
      {numbersOpen && (
        <NumbersSheet
          id={numbersId}
          arms={arms}
          tick={tick}
          onClose={() => closeNumbers()}
          live={live}
          playing={playing}
          top={barHeight}
        />
      )}
      {/* Under the sheet the towns are hidden but kept as they were (the chart
          picked, the families met), and catch up when React is idle. */}
      <Activity mode={numbersOpen ? 'hidden' : 'visible'}>
        <main className="nx-wrap">
          {building ? (
            <>
              {panel}
              {live.phase !== 'lost' && <p className="nx-status" role="status">{COPY.live.building}</p>}
            </>
          ) : (
            <>
              <p className="nx-lead"><Lead text={leadSentence(arms, tick)} arms={arms} /></p>
              <Moments arms={arms} tick={tick} />
              {panel}

              <div className={`nx-cols${single ? ' is-single' : ''}`}>
                {arms.map((arm, i) => (
                  <TownColumn
                    key={arm.label}
                    arm={arm}
                    tick={tick}
                    single={single}
                    live={Boolean(live)}
                    notice={live?.towns?.[i]?.notice}
                    onTrack={live ? (action, householdId) => live.onTrack(i, action, householdId) : undefined}
                    canReshuffle={canReshuffle}
                  />
                ))}
              </div>

              <div className="nx-story">
                <StoryChart
                  arms={arms}
                  metricKey={metricKey}
                  tick={tick}
                  horizon={horizon}
                  onMetricChange={setMetricKey}
                  playing={playing}
                />
                <div className="nx-side">
                  <p className="nx-verdict">{verdict(arms, tick)}</p>
                  <div className="nx-stats">
                    {STAT_METRICS.map(key => <StatCard key={key} metricKey={key} arms={arms} tick={tick} />)}
                  </div>
                  <p className="nx-morestats">
                    {COPY.numbers.more}{' '}
                    <button type="button" className="nx-more" onClick={event => openNumbers(event.currentTarget)}>
                      {COPY.numbers.open}
                    </button>{COPY.numbers.moreEnd}
                  </p>
                </div>
              </div>

              <div className="nx-feedwrap">
                <Feed arms={arms} tick={tick} />
                <HowToRead arms={arms} tick={tick} />
              </div>
            </>
          )}
        </main>
      </Activity>
    </div>
  )
}
