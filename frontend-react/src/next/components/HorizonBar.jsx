import { COPY } from '../catalog.js'
import { weekLabel } from '../narration.js'
import { SPEEDS } from '../useReplay.js'
import '../next.css'

const WEEKS_PER_YEAR = 52
const THUMB = 16

// Share of the track at `week`, measured the way a range input places its
// thumb (the thumb stays inside the track), so marks line up with it.
const along = fraction => `calc(${THUMB / 2}px + (100% - ${THUMB}px) * ${fraction})`

function PlayIcon({ playing }) {
  return playing ? (
    <svg viewBox="0 0 12 12" aria-hidden="true" focusable="false"><rect x="2" y="1.5" width="3" height="9" rx="1" /><rect x="7" y="1.5" width="3" height="9" rx="1" /></svg>
  ) : (
    <svg viewBox="0 0 12 12" aria-hidden="true" focusable="false"><path d="M3 1.6 L10.4 6 L3 10.4 Z" /></svg>
  )
}

// Phases in which a live run can be paused or resumed.
const STEERABLE = ['running', 'paused']

// The sticky timeline: play/pause, the week, a scrubber over the recorded
// weeks with year marks, and the playback speed (only when there is one).
// In a live run (`live`, RunScreen's live prop) the toggle pauses and
// resumes the towns, "Back to live" returns to the newest week while
// `following` is false, and a Town hall button opens the drawer.
export default function HorizonBar({
  tick, horizon, maxTick, playing, onToggle, onScrub, speed, onSpeed, live, following = true, onFollow,
}) {
  const last = Math.max(1, maxTick)
  const length = Math.max(last, horizon || 0)
  const reach = length > 1 ? (last - 1) / (length - 1) : 1
  const filled = last > 1 ? (tick - 1) / (last - 1) : 1
  const years = []
  for (let start = 1; start <= length; start += WEEKS_PER_YEAR) years.push({ n: years.length + 1, start })
  const atEnd = !playing && tick >= last && last > 1
  const replayName = playing ? COPY.horizon.pause : atEnd ? COPY.horizon.again : COPY.horizon.play
  // Live towns only ever pause and resume; before the run starts and after it
  // ends the button stays "Pause", disabled.
  const pauseShown = live ? live.phase !== 'paused' : playing
  const toggleName = live ? (pauseShown ? COPY.horizon.pause : COPY.live.resume) : replayName
  const steerable = !live || STEERABLE.includes(live.phase)
  const hasSpeed = speed !== undefined && onSpeed !== undefined

  return (
    <div className="nx-hbar" role="region" aria-label={COPY.horizon.region}>
      <div className="nx-hbar-in">
        <button type="button" className="nx-abtn is-dark nx-play" disabled={!steerable} onClick={onToggle}>
          <PlayIcon playing={pauseShown} />
          <span>{toggleName}</span>
        </button>
        <div className="nx-clock">
          <i aria-hidden="true" className={playing ? 'is-on' : ''} />
          <span className="nx-week">{weekLabel(tick)}</span>
          <span className="nx-of">{COPY.horizon.length(horizon || last)}</span>
        </div>
        {live && !following && (
          <button type="button" className="nx-abtn nx-follow" onClick={onFollow}>{COPY.live.backToLive}</button>
        )}
        <div className="nx-scrubber">
          <div className="nx-track-wrap" style={{ width: `${reach * 100}%` }}>
            <input
              type="range"
              className="nx-scrub"
              min={1}
              max={last}
              step={1}
              value={tick}
              aria-label={COPY.horizon.scrub}
              aria-valuetext={weekLabel(tick)}
              style={{ '--nx-fill': along(filled) }}
              onChange={event => onScrub(Number(event.target.value))}
            />
          </div>
          <div className="nx-marks" aria-hidden="true">
            {years.map(year => {
              const fraction = length > 1 ? (year.start - 1) / (length - 1) : 0
              return (
                <span key={year.n} style={{ left: along(fraction) }}>{COPY.horizon.year(year.n)}</span>
              )
            })}
          </div>
        </div>
        {hasSpeed && (
          <div className="nx-speed" role="group" aria-label={COPY.horizon.speed}>
            {SPEEDS.map(value => (
              <button
                key={value}
                type="button"
                aria-pressed={value === speed}
                aria-label={COPY.horizon.speedLabel(value)}
                onClick={() => onSpeed(value)}
              >
                {COPY.horizon.speedValue(value)}
              </button>
            ))}
          </div>
        )}
        {live?.hallOpen !== undefined && (
          <button
            type="button"
            className={`nx-abtn nx-hall-toggle${live.hallOpen ? ' is-dark' : ''}`}
            aria-pressed={live.hallOpen}
            onClick={() => live.onHall(!live.hallOpen)}
          >
            {COPY.hall.title}
          </button>
        )}
      </div>
    </div>
  )
}
