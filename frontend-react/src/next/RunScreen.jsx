import { Activity, useCallback, useEffect, useId, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { COPY, STAT_METRICS, STORY_METRICS, describePolicy, townTextColor } from './catalog.js'
import { commonTicks, rulesAt, rulesDiff } from './data/derive.js'
import { leadSentence, moments, verdict } from './narration.js'
import BusinessList from './components/BusinessList.jsx'
import EndPanel from './components/EndPanel.jsx'
import Feed from './components/Feed.jsx'
import HorizonBar from './components/HorizonBar.jsx'
import HouseholdCards from './components/HouseholdCards.jsx'
import HowToRead from './components/HowToRead.jsx'
import LostPanel from './components/LostPanel.jsx'
import Moments from './components/Moments.jsx'
import NumbersSheet from './numbers/NumbersSheet.jsx'
import StableText from './components/StableText.jsx'
import StatCard from './components/StatCard.jsx'
import StoryChart from './components/StoryChart.jsx'
import TownHall from './components/TownHall.jsx'
import Legend from './town/Legend.jsx'
import MainStreetCard from './town/MainStreetCard.jsx'
import TownCard from './town/TownCard.jsx'
import './next.css'

const escapeRegExp = text => text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
const HTML_ESCAPES = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }
const escapeHtml = text => String(text).replace(/[&<>"']/g, char => HTML_ESCAPES[char])

// Why the Town hall cannot change rules in this phase of a live run, or null.
const HALL_LOCKS = {
  connecting: COPY.hall.locked.connecting,
  horizon: COPY.hall.locked.over,
  finished: COPY.hall.locked.over,
  lost: COPY.hall.locked.lost,
}

// The lead sentence in parts: plain text, and each town's name with its
// colour. <Lead> renders them and leadMarkup writes the same as HTML for the
// lead's measuring copy, so the two cannot drift apart.
function leadParts(text, arms) {
  const labels = arms.map(arm => arm.label).filter(Boolean)
  if (!labels.length) return [{ text }]
  const colors = Object.fromEntries(arms.map(arm => [arm.label, townTextColor(arm.color)]))
  return text.split(new RegExp(`(${labels.map(escapeRegExp).join('|')})`))
    .map((part, i) => (colors[part] && i % 2 === 1 ? { text: part, color: colors[part] } : { text: part }))
}

// The lead sentence with each town's name in its colour.
function Lead({ text, arms }) {
  return leadParts(text, arms).map((part, i) => (part.color
    ? <span key={i} className="nx-tname" style={{ color: part.color }}>{part.text}</span>
    : part.text))
}

// The HTML <Lead> renders for `text`. A town's name is its own inline box, and
// the browser measures each box's text separately and rounds each width, so a
// line with names can come out a fraction of a pixel wider than the same
// words as plain text and wrap one word sooner: the lead's room is measured
// with this markup, not the plain sentence.
function leadMarkup(text, arms) {
  return leadParts(text, arms).map(part => (part.color
    ? `<span class="nx-tname" style="color: ${escapeHtml(part.color)}">${escapeHtml(part.text)}</span>`
    : escapeHtml(part.text))).join('')
}

// A column head names the rules the town has in force at the week shown, on
// one line (the full wording in its title). A live town keeps an (empty)
// status line for the server's notices, so a notice is announced when it
// arrives. The town itself is drawn in its card above the columns; a single
// town's column puts its businesses beside its households.
function TownColumn({ arm, tick, single, live, notice, onTrack, canReshuffle }) {
  const businesses = <BusinessList arm={arm} tick={tick} />
  const households = <HouseholdCards arm={arm} tick={tick} onTrack={onTrack} canReshuffle={canReshuffle} />
  const rules = describePolicy(rulesDiff(rulesAt(arm, tick)))
  return (
    <section className="nx-col" aria-label={arm.label}>
      <div className="nx-colhead" data-stable={`town-rules:${arm.label}`}>
        <i style={{ background: arm.color }} aria-hidden="true" />
        <h2>{arm.label}</h2>
        <span title={rules}>{rules}</span>
      </div>
      {live && (
        <p className="nx-notice" role="status" data-stable={`notice:${arm.label}`}
          title={notice ? `${COPY.live.notice} ${COPY.app.detail(notice)}` : undefined}>
          {notice ? `${COPY.live.notice} ${COPY.app.detail(notice)}` : null}
        </p>
      )}
      {single ? <div className="nx-solo">{businesses}{households}</div> : <>{businesses}{households}</>}
    </section>
  )
}

// Whether the town hall applied any change during the run.
const changedRules = arms => arms.some(arm => (arm.receipts ?? []).some(receipt => (
  receipt.status === 'applied' && Object.keys(receipt.applied ?? {}).length > 0
)))

// The live phases in which a run has stopped for good, not paused.
const END_PHASES = new Set(['horizon', 'finished', 'lost'])

// A live run's end or lost panel, or nothing while it runs.
function LivePanel({ live, arms, maxTick, horizon, onFollow }) {
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
        onFollow={onFollow}
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
// "Show all the numbers" (the line under the stat cards, or the timeline's
// button) opens the numbers sheet in the towns' place, under the timeline that
// still drives it; `numbersOpen` opens the screen on it. The sheet and the Town
// hall drawer are never open together.
export default function RunScreen({
  arms, tick, maxTick, playing, onToggle, onScrub, live, numbersOpen: numbersAtStart = false,
}) {
  const horizon = Math.max(maxTick, ...arms.map(arm => arm.horizon || 0))
  const [metricKey, setMetricKey] = useState(STORY_METRICS[0])
  // The Town hall toggle, so focus can return to it when the drawer closes,
  // and whether the drawer was opened from it (then focus moves into it).
  const hallToggleRef = useRef(null)
  const [hallFocus, setHallFocus] = useState(false)
  const hallId = `${useId()}-hall`
  const single = arms.length === 1
  // Enlarge shows one town on its own (by label) until the viewer shows them all again.
  const [focused, setFocused] = useState(null)
  const focus = arms.some(arm => arm.label === focused) ? focused : null
  // Which town Main Street shows (by index): the picker's choice, or the town
  // last enlarged. Showing all the towns again leaves it there.
  const [streetTown, setStreetTown] = useState(0)
  // A live run shows its towns from the first week every town has reached.
  const building = Boolean(live) && maxTick < 1
  // The towns move while the clock plays forward: a live run held on a past
  // week does not, though its towns run on. Every move on the timeline is
  // counted, so the drawings never take a scrubbed week for a step forward.
  const moving = playing && (!live || live.following !== false)
  // A run that has stopped at its end (the replay's last week, or a live run
  // at its horizon, finished or lost) rather than paused by the viewer: what
  // is in flight in the drawings lands instead of freezing.
  const ended = !moving && (live ? live.following !== false && END_PHASES.has(live.phase) : tick >= maxTick)
  const [scrubs, setScrubs] = useState(0)
  const scrub = week => {
    setScrubs(count => count + 1)
    onScrub(week)
  }
  const follow = () => {
    setScrubs(count => count + 1)
    live.onFollow()
  }
  const panel = live ? <LivePanel live={live} arms={arms} maxTick={maxTick} horizon={horizon} onFollow={follow} /> : null
  // New families appear in the live week only, so meeting them waits for a
  // running town and the viewer on the newest week.
  const canReshuffle = live?.phase === 'running' && live.following !== false

  // Every lead, verdict and row of moments the towns can show, so their boxes
  // keep one height as the week changes (spec section 6). A live run's arms
  // can grow in place, so the weeks also follow each town's week count.
  const ticksKey = arms.map(arm => arm.ticks.length).join(',')
  const isLive = Boolean(live)
  const weeks = useMemo(() => commonTicks(arms), [arms, ticksKey]) // eslint-disable-line react-hooks/exhaustive-deps
  const leadTexts = useMemo(() => [...new Set(weeks.map(week => leadSentence(arms, week)))], [arms, weeks])
  const leadHtml = useCallback(text => leadMarkup(text, arms), [arms])
  const verdictTexts = useMemo(() => [...new Set(weeks.map(week => verdict(arms, week)))], [arms, weeks])
  const momentRows = useMemo(() => {
    if (isLive) return []
    const rows = new Map()
    for (const week of weeks) {
      const row = moments(arms, week)
      const key = row.map(moment => moment.text).join('\n')
      if (row.length && !rows.has(key)) rows.set(key, row)
    }
    return [...rows.values()]
  }, [arms, weeks, isLive])

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
        onScrub={scrub}
        live={live}
        following={live?.following}
        onFollow={live ? follow : undefined}
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
              <StableText className="nx-lead" texts={leadTexts} stable="lead" markup={leadHtml}>
                <Lead text={leadSentence(arms, tick)} arms={arms} />
              </StableText>
              <Moments arms={arms} tick={tick} rows={momentRows} live={isLive} />
              {panel}

              {arms.length > 2 && <Legend arms={arms} tick={tick} />}
              <section className={`lt-towns is-${arms.length}${focus ? ' is-focus' : ''}`} data-stable="towns">
                {arms.map((arm, i) => (
                  <TownCard
                    key={arm.label}
                    arm={arm}
                    tick={tick}
                    towns={arms.length}
                    playing={moving}
                    scrubs={scrubs}
                    ended={ended}
                    lostTick={live?.towns?.find(town => town.label === arm.label && town.status === 'lost')?.lastTick ?? null}
                    lostRow={Boolean(live?.towns?.some(town => town.status === 'lost'))}
                    canFocus={!single}
                    focused={focus === arm.label}
                    hidden={Boolean(focus) && focus !== arm.label}
                    onFocus={() => {
                      if (focus !== arm.label) setStreetTown(i)
                      setFocused(focus === arm.label ? null : arm.label)
                    }}
                  />
                ))}
              </section>
              {arms.length <= 2 && <Legend arms={arms} tick={tick} />}
              <MainStreetCard
                arms={arms}
                tick={tick}
                playing={moving}
                scrubs={scrubs}
                ended={ended}
                selected={Math.min(streetTown, arms.length - 1)}
                onSelect={setStreetTown}
              />

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
                  <StableText className="nx-verdict" texts={verdictTexts} stable="verdict">{verdict(arms, tick)}</StableText>
                  <div className="nx-stats">
                    {STAT_METRICS.map(key => <StatCard key={key} metricKey={key} arms={arms} tick={tick} />)}
                  </div>
                  <p className="nx-morestats" data-stable="morestats">
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
