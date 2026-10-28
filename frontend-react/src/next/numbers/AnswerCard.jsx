import { useId } from 'react'
import { COPY, NUMBER_GROUPS, NUMBER_HERO_KEYS, WARMUP_TICKS, formatMetric } from '../catalog.js'
import { weekLabel } from '../narration.js'
import { differenceWords, heroNotes, rowSeries, rowStatus, rowValues, tally, verdictParts } from './compare.js'
import './answerCard.css'

const ALL_ROWS = NUMBER_GROUPS.flatMap(group => group.rows)
const WIDTH = 300
const HEIGHT = 34
const isNumber = value => typeof value === 'number' && Number.isFinite(value)

// One shared scale, with only weeks after set-up. The table carries the
// historical readings; this week's readings have their sole visible home above.
function HeroSparkline({ arms, metricKey, tick, name }) {
  const series = arms.map(arm => rowSeries(arm, metricKey, tick).filter(point => point.tick > WARMUP_TICKS))
  const values = series.flatMap(points => points.map(point => point.value).filter(isNumber))
  const lo = values.length ? Math.min(...values) : 0
  const hi = values.length ? Math.max(...values) : 1
  const span = hi - lo || 1
  const first = WARMUP_TICKS + 1
  const end = Math.max(first + 1, tick)
  const x = week => 2 + ((week - first) / (end - first)) * (WIDTH - 4)
  const y = value => HEIGHT - 3 - ((value - lo) / span) * (HEIGHT - 6)
  const path = points => {
    let previous = false
    return points.map(point => {
      if (!isNumber(point.value)) {
        previous = false
        return ''
      }
      const command = previous ? 'L' : 'M'
      previous = true
      return `${command}${x(point.tick).toFixed(1)} ${y(point.value).toFixed(1)}`
    }).join(' ')
  }
  const weeks = [...new Set(series.flatMap(points => points.map(point => point.tick)))].sort((a, b) => a - b)
  const byTown = series.map(points => new Map(points.map(point => [point.tick, point.value])))
  const paths = series.map(path)

  return (
    <>
      <svg className="nx-answer-spark" width={WIDTH} height={HEIGHT} viewBox={`0 0 ${WIDTH} ${HEIGHT}`} aria-hidden="true" focusable="false">
        {arms.map((arm, index) => {
          const points = series[index]
          const known = points.filter(point => isNumber(point.value))
          const same = paths.slice(0, index).includes(paths[index])
          return (
            <g key={arm.label}>
              <path d={paths[index]} fill="none" stroke={arm.color} strokeWidth={1.5} strokeLinejoin="round" strokeDasharray={same ? '3 3' : undefined} vectorEffect="non-scaling-stroke" />
              {known.length === 1 && <circle cx={x(known[0].tick)} cy={y(known[0].value)} r={1.5} fill={arm.color} />}
            </g>
          )
        })}
      </svg>
      <div className="nx-sr">
        <table>
          <caption>{COPY.numbers.chart.table(name)}</caption>
          <thead><tr><th scope="col">{COPY.numbers.chart.week}</th>{arms.map(arm => <th scope="col" key={arm.label}>{arm.label}</th>)}</tr></thead>
          <tbody>
            {weeks.map(week => (
              <tr key={week}>
                <th scope="row">{weekLabel(week)}</th>
                {arms.map((arm, index) => {
                  const value = byTown[index].get(week)
                  return <td key={arm.label}>{isNumber(value) ? formatMetric(metricKey, value) : COPY.numbers.notMeasured}</td>
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  )
}

function Hero({ arms, metricKey, tick }) {
  const uid = useId()
  const copy = COPY.numbers.heroes[metricKey]
  const readings = rowValues(arms, metricKey, tick)
  const valueGroups = []
  for (const reading of readings) {
    const existing = isNumber(reading.value) && valueGroups.find(group => group.formatted === reading.formatted)
    if (existing) existing.towns.push(reading)
    else valueGroups.push({ formatted: reading.formatted, value: reading.value, towns: [reading] })
  }
  const notes = heroNotes(arms, metricKey, tick)
  const base = readings[0]?.value
  const warming = tick <= WARMUP_TICKS
  const output = metricKey === 'salesExceptRentThisWeek'

  return (
    <article className="nx-answer-hero" aria-labelledby={uid} data-hero={metricKey}>
      <h4 id={uid} className="nx-answer-hero-title">{copy.name}</h4>
      <p className="nx-answer-hero-meaning">{copy.meaning}</p>
      <div className="nx-answer-values">
        {valueGroups.map(group => (
          <span className={`nx-answer-value${isNumber(group.value) ? '' : ' is-missing'}`} key={group.towns[0].label}>
            <span className="nx-answer-value-towns">
              {group.towns.map(town => <i className="nx-answer-swatch" key={town.label} title={town.label} style={{ background: town.color }} aria-hidden="true" />)}
            </span>
            <span className="nx-sr">{group.towns.map(town => town.label).join(COPY.numbers.fold.join)}{COPY.numbers.verdict.comma}</span>
            <span className="nx-answer-reading">{group.formatted}</span>
          </span>
        ))}
      </div>
      <HeroSparkline arms={arms} metricKey={metricKey} tick={tick} name={copy.name} />
      {arms.length > 1 && readings.slice(1).map(reading => {
        const words = differenceWords(metricKey, base, reading.value)
        if (!words) return null
        const status = warming ? 'warmup' : rowStatus(metricKey, base, reading.value, tick)
        return (
          <p className="nx-answer-hero-difference" key={reading.label}>
            {arms.length > 2 && <i className="nx-answer-swatch" style={{ background: reading.color }} aria-hidden="true" />}
            {!warming && (status === 'better' || status === 'worse') && (
              <span className={`nx-answer-tag is-${status}`}>{COPY.numbers.tags[status]}</span>
            )}
            {output ? COPY.numbers.heroes.output(reading.label, words) : COPY.numbers.heroes.wellbeing(reading.label, words)}
          </p>
        )
      })}
      {notes.map(note => <p className="nx-answer-hero-note" key={note}>{note}</p>)}
    </article>
  )
}

// The answer is always first, with one paragraph and tally per comparison
// town. Each link delegates scrolling/focus to the sheet's row owner.
export default function AnswerCard({ arms, tick, rows = ALL_ROWS, foldedKeys, onJump }) {
  const uid = useId()
  const warming = tick <= WARMUP_TICKS
  const comparing = arms.length > 1
  const verdicts = comparing && !warming ? verdictParts(arms, rows, tick) : []
  const counts = comparing && !warming ? tally(arms, rows, tick, foldedKeys) : []

  return (
    <section className="nx-answer" aria-labelledby={uid}>
      <h3 id={uid} className="nx-answer-kicker">{COPY.numbers.answer}</h3>
      {comparing && warming && <p className="nx-answer-warmup">{COPY.numbers.warmup}</p>}
      {verdicts.map(verdict => (
        <p className="nx-answer-verdict" key={verdict.label}>
          {verdict.parts.map((part, index) => (part.rowId ? (
            <a key={index} href={`#${part.rowId}`} onClick={event => {
              event.preventDefault()
              onJump?.(part.rowId)
            }}>{part.text}</a>
          ) : <span key={index}>{part.text}</span>))}
        </p>
      ))}
      <div className="nx-answer-heroes">
        {NUMBER_HERO_KEYS.map(key => <Hero key={key} arms={arms} metricKey={key} tick={tick} />)}
      </div>
      {counts.map(count => (
        <div className="nx-answer-tally" role="group" aria-label={COPY.numbers.tally.label(count.label)} key={count.label}>
          <span className="nx-answer-tag is-better">{COPY.numbers.tally.better(count.better, count.label)}</span>
          <span className="nx-answer-tag is-worse">{COPY.numbers.tally.worse(count.worse)}</span>
          <span className="nx-answer-tag is-different">{COPY.numbers.tally.different(count.different)}</span>
          <span className="nx-answer-tag is-same">{COPY.numbers.tally.same(count.same)}</span>
        </div>
      ))}
    </section>
  )
}
