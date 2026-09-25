import { useState } from 'react'
import { COPY, STAT_METRICS, STORY_METRICS, describePolicy, townTextColor } from './catalog.js'
import { leadSentence, verdict } from './narration.js'
import BusinessList from './components/BusinessList.jsx'
import EndPanel from './components/EndPanel.jsx'
import Feed from './components/Feed.jsx'
import HorizonBar from './components/HorizonBar.jsx'
import HouseholdCards from './components/HouseholdCards.jsx'
import HowToRead from './components/HowToRead.jsx'
import LostPanel from './components/LostPanel.jsx'
import Moments from './components/Moments.jsx'
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

function TownColumn({ arm, tick, single, notice, onTrack }) {
  const town = <Town arm={arm} tick={tick} />
  const businesses = <BusinessList arm={arm} tick={tick} />
  return (
    <section className="nx-col" aria-label={arm.label}>
      <div className="nx-colhead">
        <i style={{ background: arm.color }} aria-hidden="true" />
        <h2>{arm.label}</h2>
        <span>{describePolicy(arm.setup?.initial_policy)}</span>
      </div>
      {notice && <p className="nx-notice">{notice}</p>}
      {single ? <div className="nx-solo">{town}{businesses}</div> : <>{town}{businesses}</>}
      <HouseholdCards arm={arm} tick={tick} onTrack={onTrack} />
    </section>
  )
}

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
        onExtend={live.onExtend}
        onNewExperiment={live.onNewExperiment}
      />
    )
  }
  return null
}

// The Run screen: every panel reads the week its parent's clock is on. With
// `live` (NextApp's live experiment) it also steers the towns: pause and
// resume, the end and lost panels, the Town hall drawer and the household
// sample. Without it, it replays recorded towns.
export default function RunScreen({ arms, tick, maxTick, playing, onToggle, onScrub, speed, onSpeed, live }) {
  const horizon = Math.max(maxTick, ...arms.map(arm => arm.horizon || 0))
  const [metricKey, setMetricKey] = useState(STORY_METRICS[0])
  const single = arms.length === 1
  // A live run shows its towns from the first week every town has reached.
  const building = Boolean(live) && maxTick < 1
  const panel = live ? <LivePanel live={live} arms={arms} maxTick={maxTick} horizon={horizon} /> : null

  return (
    <div className="nx-run">
      <HorizonBar
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
      />
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
                  notice={live?.towns?.[i]?.notice}
                  onTrack={live ? (action, householdId) => live.onTrack(i, action, householdId) : undefined}
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
              </div>
            </div>

            <div className="nx-feedwrap">
              <Feed arms={arms} tick={tick} />
              <HowToRead arms={arms} tick={tick} />
            </div>
          </>
        )}
      </main>
      {live?.hallOpen && (
        <TownHall
          arms={arms}
          tick={tick}
          onConfigure={live.onConfigure}
          onClose={() => live.onHall(false)}
          locked={HALL_LOCKS[live.phase] ?? null}
        />
      )}
    </div>
  )
}
