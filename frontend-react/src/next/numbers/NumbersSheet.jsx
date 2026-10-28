import { useEffect, useEffectEvent, useId, useLayoutEffect, useRef, useState } from 'react'
import { COPY, NUMBER_DERIVED_ROWS, NUMBER_GROUPS, WARMUP_TICKS, capitalise, describePolicy } from '../catalog.js'
import { rulesAt, rulesDiff } from '../data/derive.js'
import { weekLabel } from '../narration.js'
import StoryChart from '../components/StoryChart.jsx'
import AnswerCard from './AnswerCard.jsx'
import NumberRow from './NumberRow.jsx'
import { RulesLine } from './RulesInForce.jsx'
import WealthLadder from './WealthLadder.jsx'
import HiresAndLayoffs from './HiresAndLayoffs.jsx'
import FirmStates from './FirmStates.jsx'
import OpenedClosed from './OpenedClosed.jsx'
import LoansWrittenOff from './LoansWrittenOff.jsx'
import { foldLines, nextFoldKeys, rowDefinition, rowSeries, rowValues, visibleRows } from './compare.js'
import useFoldLayout from './useFoldLayout.js'
import '../next.css'
import './numbersSheet.css'

const ALL_ROWS = NUMBER_GROUPS.flatMap(group => group.rows)
const DEFAULT_OPEN = Object.fromEntries(ALL_ROWS.filter(row => row.defaultOpen).map(row => [row.key, true]))

function BackIcon() {
  return <svg viewBox="0 0 12 12" aria-hidden="true" focusable="false"><path d="M7.5 2 L3.5 6 L7.5 10" /></svg>
}

function lostNote(live, index) {
  const town = live?.towns?.[index]
  return town?.status === 'lost' ? COPY.numbers.lost(town.lastTick ? weekLabel(town.lastTick) : null) : null
}

function liveStatus(live, arms) {
  if (live?.phase === 'lost') {
    const label = live.error?.town ?? live.towns?.find(town => town.status === 'lost')?.label
    const town = live.towns?.find(town => town.label === label)
    const describe = live.error?.kind === 'crashed' ? COPY.numbers.live.crashed : COPY.numbers.live.lost
    return `${describe(label, town?.lastTick ? weekLabel(town.lastTick) : null, arms.length > 1)} ${COPY.numbers.continue}`
  }
  if (live?.phase === 'horizon' || live?.phase === 'finished') {
    const horizon = Math.max(0, ...arms.map(arm => arm.horizon || arm.ticks.at(-1) || 0))
    return `${COPY.numbers.live.end(horizon)} ${COPY.numbers.continue}`
  }
  return null
}

function RowVisual({ row, arms, tick, playing }) {
  if (row.visual === 'ladder') return <WealthLadder arms={arms} tick={tick} inline />
  if (row.visual === 'hires') return <HiresAndLayoffs arms={arms} tick={tick} inline />
  if (row.visual === 'firms') return <><FirmStates arms={arms} tick={tick} inline /><OpenedClosed arms={arms} tick={tick} inline /></>
  if (row.visual === 'loans') return <LoansWrittenOff arms={arms} tick={tick} inline playing={playing} />
  if (!rowValues(arms, row, tick).some(value => value.measured)) return null
  // StoryChart reads series. Derived measures get read-only synthetic series
  // from the same pure helper that supplies their row values and sparklines.
  const chartArms = NUMBER_DERIVED_ROWS[row.key] ? arms.map(arm => {
    const points = new Map(rowSeries(arm, row, arm.ticks.at(-1) ?? tick).map(point => [point.tick, point.value]))
    return { ...arm, series: { ...arm.series, [row.key]: arm.ticks.map(week => points.get(week) ?? null) } }
  }) : arms
  const horizon = Math.max(tick, ...arms.map(arm => arm.horizon || arm.ticks.at(-1) || tick))
  return <>
    <StoryChart arms={chartArms} metricKey={row.key} metricKeys={[row.key]} tick={tick} horizon={horizon} playing={playing} countedWeeks hideEndLabels inline interactive />
  </>
}

function FoldLines({ arms, rows, tick, onJump, layout, focusedKey }) {
  // Retain the focused source through the commit that makes its row usable.
  // The sheet transfers focus in a layout effect before removing this entry.
  const entries = rows.filter(row => row.key === focusedKey || ['folded', 'entering-entry', 'leaving-entry'].includes(layout[row.key]?.phase))
  const items = entries.map(row => {
    const phase = ['row', 'entering-row'].includes(layout[row.key].phase) ? 'leaving-entry' : layout[row.key].phase
    const item = foldLines(arms, [row], tick)[0]?.items[0]
    // A promoted entry fades its name only: never leave a stale numeric value
    // in the equality line while its current values differ.
    return item ? { ...item, phase } : { key: row.key, name: rowDefinition(row).name, values: [], phase }
  })
  return <div className={`nx-fold-motion${items.length ? ' is-visible' : ''}`} data-state={items.length ? 'open' : 'closed'} aria-hidden={!items.length}>
    <div className="nx-fold-motion-inner"><p className="nx-number-fold">
      <span className="nx-number-fold-label">{COPY.numbers.fold.equal(arms.length)}</span>{' '}
      {items.map((item, i) => <span className="nx-fold-entry" data-metric={item.key} data-state={item.phase} key={item.key} aria-hidden={item.phase === 'leaving-entry' && item.key !== focusedKey} inert={item.phase === 'leaving-entry' && item.key !== focusedKey}>
        <span>{i > 0 && COPY.numbers.fold.join}
        <button type="button" onClick={() => onJump(item.key)} aria-label={COPY.numbers.fold.show(item.name)}>{item.name}</button>{' '}
        {item.values.map((value, index) => <span key={index}>{index > 0 && COPY.numbers.fold.and}<b>{value}</b></span>)}
        </span>
      </span>)}
    </p></div>
  </div>
}

// The timeline above is the only clock. Each measure appears in one hero or
// one row/fold, with its expanded chart in place. Fold membership is frozen
// while playing; values and comparisons continue to follow tick.
export default function NumbersSheet({ id, arms, tick, onClose, live, playing = false, top = 0 }) {
  const uid = useId().replace(/:/g, '')
  const titleId = `nx-sheet-${uid}`
  const headingRef = useRef(null)
  const headBackRef = useRef(null)
  const sheetRef = useRef(null)
  const columnScrollRef = useRef(null)
  const [stuck, setStuck] = useState(false)
  const [expanded, setExpanded] = useState(DEFAULT_OPEN)
  const [focusOwner, setFocusOwner] = useState(null)
  const jumpKey = useRef(null)
  const warming = tick <= WARMUP_TICKS
  const rows = visibleRows(arms, ALL_ROWS, tick)
  const stamp = `${tick}:${arms.map(arm => `${arm.label}:${arm.ticks.length}`).join('|')}:${rows.map(row => row.key).join('|')}`
  const openKeys = Object.keys(expanded).filter(key => expanded[key])
  const chooseFolds = previous => nextFoldKeys(arms, rows, tick, previous, playing, openKeys)
  const [foldSnapshot, setFoldSnapshot] = useState(() => ({ stamp, playing, keys: nextFoldKeys(arms, rows, tick, [], false, openKeys), open: openKeys.join('|') }))
  // Adjust during render so a paused scrub never paints stale fold membership.
  if (foldSnapshot.stamp !== stamp || foldSnapshot.playing !== playing || foldSnapshot.open !== openKeys.join('|')) {
    setFoldSnapshot({ stamp, playing, keys: chooseFolds(foldSnapshot.keys), open: openKeys.join('|') })
  }
  const foldedKeys = arms.length < 2 || warming ? [] : foldSnapshot.keys.filter(key => !expanded[key] && rows.some(row => row.key === key))
  const layout = useFoldLayout(rows, foldedKeys, openKeys)
  const notes = arms.map((_, index) => lostNote(live, index))
  const rowId = key => `nx-number-${uid}-${key}`

  useEffect(() => {
    const opener = document.activeElement
    headingRef.current?.focus()
    return () => {
      if (opener && opener !== document.body && opener.isConnected && typeof opener.focus === 'function') opener.focus()
    }
  }, [])

  const onKey = useEffectEvent(event => {
    if (event.key !== 'Escape' || event.defaultPrevented) return
    event.preventDefault()
    onClose?.()
  })
  useEffect(() => {
    const listener = event => onKey(event)
    document.addEventListener('keydown', listener)
    return () => document.removeEventListener('keydown', listener)
  }, [])

  useEffect(() => {
    const target = headBackRef.current
    if (!target || typeof IntersectionObserver === 'undefined') return undefined
    const rootMargin = `${top > 0 ? `-${top}px` : '0px'} 0px 0px 0px`
    const observer = new IntersectionObserver(([entry]) => setStuck(!entry.isIntersecting), { rootMargin })
    observer.observe(target)
    return () => observer.disconnect()
  }, [top])

  const jump = key => {
    jumpKey.current = key
    setExpanded(all => ({ ...all, [key]: true }))
  }

  // Focus only after the new layout has committed without inert/aria-hidden.
  // Until then the disappearing source stays accessible, including on a snap
  // for reduced motion. NumberRow owns its button; locate it by its existing id.
  useLayoutEffect(() => {
    const key = jumpKey.current ?? focusOwner?.key
    if (!key) return
    const entry = layout[key]
    const toRow = jumpKey.current !== null || (focusOwner?.kind === 'entry' && !entry?.folded)
    const toFold = focusOwner?.kind === 'row' && entry?.folded
    let target
    if (toRow && ['row', 'entering-row'].includes(entry?.phase)) {
      target = document.getElementById(`nx-number-${uid}-${key}-button`)
    } else if (toFold && ['folded', 'entering-entry'].includes(entry?.phase)) {
      target = sheetRef.current?.querySelector(`.nx-fold-entry[data-metric="${key}"] button`)
    }
    if (!target || target.closest('[inert], [aria-hidden="true"]')) return
    if (jumpKey.current !== null) {
      document.getElementById(`nx-number-${uid}-${key}`)?.scrollIntoView?.({ block: 'start' })
    }
    jumpKey.current = null
    target.focus({ preventScroll: true })
  })

  const trackFocus = event => {
    const source = event.target.closest('.nx-row-motion, .nx-fold-entry')
    setFocusOwner(source ? { key: source.dataset.metric, kind: source.classList.contains('nx-fold-entry') ? 'entry' : 'row' } : null)
  }

  return (
    <section ref={sheetRef} id={id} className={`nx-sheet${playing ? ' is-playing' : ''}${arms.length === 1 ? ' is-one-town' : ''}`} style={{ '--nx-sheet-top': `${top}px`, '--nx-towns': arms.length }} role="dialog" aria-labelledby={titleId} onFocusCapture={trackFocus} onBlurCapture={event => { if (!event.currentTarget.contains(event.relatedTarget)) setFocusOwner(null) }}>
      <header className="nx-sheet-head">
        <div>
          <h2 id={titleId} ref={headingRef} tabIndex={-1}>{COPY.numbers.title}</h2>
          {live && <p className="nx-notice" role="status" aria-live="polite">{liveStatus(live, arms)}</p>}
          <ul className="nx-sheet-towns" aria-label={COPY.numbers.towns}>
            {arms.map(arm => <li key={arm.label} className="nx-tchip">
              <i style={{ background: arm.color }} aria-hidden="true" /><b>{arm.label}</b>
              {capitalise(describePolicy(rulesDiff(rulesAt(arm, tick))))}
            </li>)}
          </ul>
        </div>
        <button ref={headBackRef} type="button" className="nx-abtn is-dark" onClick={onClose}><BackIcon />{COPY.numbers.back}</button>
      </header>
      <div className="nx-number-answer-wrap"><AnswerCard arms={arms} rows={rows} tick={tick} foldedKeys={foldedKeys} onJump={jump} /></div>
      <div className={`nx-number-columns${stuck ? ' has-back' : ''}`} role="group" aria-label={COPY.numbers.columns.label}>
        <div ref={columnScrollRef} className="nx-number-column-scroll">
        <div className={`nx-number-grid${arms.length === 1 ? ' is-one-town' : ''}`}>
          <span><span className="nx-sr">{COPY.numbers.columns.measure}</span></span>
          {arms.map((arm, index) => <span className="nx-number-column-town" key={arm.label}>
            <span><i style={{ background: arm.color }} aria-hidden="true" />{arm.label}</span>
            {notes[index] && <small>{notes[index]}</small>}
          </span>)}
          {arms.length > 1 && <span className="nx-number-column-difference">{!warming && (arms.length === 2 ? COPY.numbers.columns.difference(arms[1].label, arms[0].label) : COPY.numbers.columns.differences(arms[0].label))}</span>}
          <span className="nx-number-column-run">{COPY.numbers.columns.run}</span><span />
        </div>
        </div>
        <button type="button" className="nx-abtn nx-number-back" style={{ visibility: stuck ? 'visible' : 'hidden' }} onClick={onClose}><BackIcon />{COPY.numbers.back}</button>
      </div>
      <div className="nx-sheet-body" onScroll={event => { if (columnScrollRef.current) columnScrollRef.current.scrollLeft = event.currentTarget.scrollLeft }}>
        {NUMBER_GROUPS.map(group => {
          const copy = COPY.numbers.groups[group.id]
          const ownRows = visibleRows(arms, group.rows, tick)
          const headingId = `nx-number-group-${uid}-${group.id}`
          return <section key={group.id} className="nx-number-group" aria-labelledby={headingId}>
            <div className="nx-number-group-heading"><h3 id={headingId}>{copy.title}</h3><p>{copy.blurb}</p></div>
            {ownRows.map(row => <div key={row.key} className={`nx-row-motion${layout[row.key]?.promoted ? ' is-promoted' : ''}${focusOwner?.kind === 'row' && focusOwner.key === row.key ? ' has-focus' : ''}`} data-metric={row.key} data-state={layout[row.key]?.phase} aria-hidden={!(focusOwner?.kind === 'row' && focusOwner.key === row.key) && ['folded', 'leaving-entry', 'entering-entry', 'leaving-row'].includes(layout[row.key]?.phase)} inert={!(focusOwner?.kind === 'row' && focusOwner.key === row.key) && ['folded', 'leaving-entry', 'entering-entry', 'leaving-row'].includes(layout[row.key]?.phase)}>
              <div className="nx-row-motion-inner"><NumberRow id={rowId(row.key)} row={row} arms={arms} tick={tick} open={Boolean(expanded[row.key])} onToggle={() => setExpanded(all => ({ ...all, [row.key]: !all[row.key] }))}>
              <RowVisual row={row} arms={arms} tick={tick} playing={playing} />
            </NumberRow></div></div>)}
            {arms.length > 1 && !warming && <FoldLines arms={arms} rows={ownRows} tick={tick} onJump={jump} layout={layout} focusedKey={focusOwner?.kind === 'entry' ? focusOwner.key : null} />}
            {group.rules && <RulesLine arms={arms} tick={tick} />}
          </section>
        })}
      </div>
    </section>
  )
}
