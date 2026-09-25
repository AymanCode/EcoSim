import { useMemo, useState } from 'react'
import { STAT_METRICS, STORY_METRICS, describePolicy } from './catalog.js'
import { commonTicks } from './data/derive.js'
import { leadSentence, verdict } from './narration.js'
import useReplay from './useReplay.js'
import BusinessList from './components/BusinessList.jsx'
import Feed from './components/Feed.jsx'
import HorizonBar from './components/HorizonBar.jsx'
import HouseholdCards from './components/HouseholdCards.jsx'
import HowToRead from './components/HowToRead.jsx'
import StatCard from './components/StatCard.jsx'
import StoryChart from './components/StoryChart.jsx'
import Town from './components/Town.jsx'
import './next.css'

const escapeRegExp = text => text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

// The lead sentence with each town's name in its colour.
function Lead({ text, arms }) {
  const labels = arms.map(arm => arm.label).filter(Boolean)
  if (!labels.length) return text
  const colors = Object.fromEntries(arms.map(arm => [arm.label, arm.color]))
  const parts = text.split(new RegExp(`(${labels.map(escapeRegExp).join('|')})`))
  return parts.map((part, i) => (colors[part] && i % 2 === 1
    ? <span key={i} className="nx-tname" style={{ color: colors[part] }}>{part}</span>
    : part))
}

function TownColumn({ arm, tick, single }) {
  const town = <Town arm={arm} tick={tick} />
  const businesses = <BusinessList arm={arm} tick={tick} />
  return (
    <section className="nx-col" aria-label={arm.label}>
      <div className="nx-colhead">
        <i style={{ background: arm.color }} aria-hidden="true" />
        <h2>{arm.label}</h2>
        <span>{describePolicy(arm.setup?.initial_policy)}</span>
      </div>
      {single ? <div className="nx-solo">{town}{businesses}</div> : <>{town}{businesses}</>}
      <HouseholdCards arm={arm} tick={tick} />
    </section>
  )
}

// The Run screen for recorded towns: every panel reads the same week.
export default function RunScreen({ arms }) {
  const ticks = useMemo(() => commonTicks(arms), [arms])
  const maxTick = ticks.length ? ticks[ticks.length - 1] : 1
  const horizon = Math.max(maxTick, ...arms.map(arm => arm.horizon || 0))
  const { tick, playing, toggle, scrub, speed, setSpeed } = useReplay({ maxTick })
  const [metricKey, setMetricKey] = useState(STORY_METRICS[0])
  const single = arms.length === 1

  return (
    <div className="nx-run">
      <HorizonBar
        tick={tick}
        horizon={horizon}
        maxTick={maxTick}
        playing={playing}
        onToggle={toggle}
        onScrub={scrub}
        speed={speed}
        onSpeed={setSpeed}
      />
      <main className="nx-wrap">
        <p className="nx-lead"><Lead text={leadSentence(arms, tick)} arms={arms} /></p>

        <div className={`nx-cols${single ? ' is-single' : ''}`}>
          {arms.map(arm => <TownColumn key={arm.label} arm={arm} tick={tick} single={single} />)}
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
          <HowToRead armCount={arms.length} />
        </div>
      </main>
    </div>
  )
}
