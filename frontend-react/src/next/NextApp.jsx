import { useEffect, useMemo, useState } from 'react'
import { COPY, TOWN_COLORS } from './catalog.js'
import { commonTicks } from './data/derive.js'
import { buildArm, parseSession } from './data/session.js'
import { useExperiment } from './live/useExperiment.js'
import { useLiveClock } from './live/useLiveClock.js'
import { experimentQuestion } from './narration.js'
import { pickScreen } from './pickScreen.js'
import useSetup from './setup/useSetup.js'
import SetupScreen from './setup/SetupScreen.jsx'
import useReplay from './useReplay.js'
import RunScreen from './RunScreen.jsx'
import './next.css'

// The two recorded demo towns, served from public/demo/.
const DEMO_FILES = ['town-a.jsonl', 'town-b.jsonl']
const DEMO_IDLE = { status: 'idle', arms: null, reason: null }

async function loadTown(file, index) {
  const url = `${import.meta.env.BASE_URL}demo/${file}`
  const response = await fetch(url)
  if (!response.ok) throw new Error(`${url} answered ${response.status}`)
  const arm = buildArm(parseSession(await response.text()), { label: COPY.app.townLabel(index), color: TOWN_COLORS[index] })
  if (!arm.ticks.length) throw new Error(`${url} has no recorded weeks`)
  return arm
}

// The recorded demo on the Run screen, with its own replay clock;
// `numbersOpen` opens it on all the numbers.
function DemoRun({ arms, numbersOpen = false }) {
  const ticks = useMemo(() => commonTicks(arms), [arms])
  const maxTick = ticks.length ? ticks[ticks.length - 1] : 1
  const clock = useReplay({ maxTick })
  return (
    <RunScreen
      arms={arms}
      tick={clock.tick}
      maxTick={maxTick}
      playing={clock.playing}
      onToggle={clock.toggle}
      onScrub={clock.scrub}
      speed={clock.speed}
      onSpeed={clock.setSpeed}
      numbersOpen={numbersOpen}
    />
  )
}

// Live towns on the Run screen. The live clock follows the newest week every
// town has reached, unless the viewer scrubs back.
function LiveRun({ state, experiment, hallOpen, onHall, onRestart, onNewExperiment }) {
  const clock = useLiveClock(state.liveTick)
  const playing = state.phase === 'running'
  return (
    <RunScreen
      arms={state.arms}
      tick={clock.tick}
      maxTick={state.liveTick}
      playing={playing}
      onToggle={playing ? experiment.pause : experiment.resume}
      onScrub={clock.scrub}
      live={{
        phase: state.phase,
        towns: state.towns,
        error: state.error,
        following: clock.following,
        onFollow: clock.follow,
        hallOpen,
        onHall,
        onConfigure: experiment.configure,
        onTrack: experiment.track,
        onExtend: experiment.extend,
        onRestart,
        onNewExperiment,
      }}
    />
  )
}

// The new app at ?view=next: Set up, live towns on the Run screen, or the
// recorded demo (?view=next&demo), opened on all the numbers with
// ?view=next&demo&numbers. Sockets open only when Start is pressed.
export default function NextApp({ search = window.location.search, WebSocketImpl = globalThis.WebSocket }) {
  const [screen, setScreen] = useState(() => pickScreen(search))
  // The link's `numbers` applies to the demo it opens, not to a later one.
  const [demoOnNumbers, setDemoOnNumbers] = useState(() => new URLSearchParams(search ?? '').has('numbers'))
  const [problem, setProblem] = useState(null)
  const [plan, setPlan] = useState(null)
  const [hallOpen, setHallOpen] = useState(false)
  const [demo, setDemo] = useState(DEMO_IDLE)
  const setup = useSetup()
  const experiment = useExperiment({ WebSocketImpl })
  const { state } = experiment

  // A start that fails while connecting goes back to Set up with the reason;
  // the plan stays as it was. (Adjusting state during render, not in an effect.)
  if (screen === 'live' && state?.phase === 'failed') {
    setScreen('setup')
    setProblem(state.error)
  }

  // The demo files load only once the demo opens.
  useEffect(() => {
    if (screen !== 'demo' || demo.status !== 'idle') return undefined
    let current = true
    Promise.all(DEMO_FILES.map(loadTown))
      .then(arms => { if (current) setDemo({ status: 'ready', arms, reason: null }) })
      .catch(error => { if (current) setDemo({ status: 'error', arms: null, reason: error?.message ?? String(error) }) })
    return () => { current = false }
  }, [screen, demo.status])

  // The page behind the app takes the new screen's colour while it is open.
  useEffect(() => {
    const page = document.documentElement
    page.classList.add('nx-page')
    return () => page.classList.remove('nx-page')
  }, [])

  const start = next => {
    setProblem(null)
    setPlan(next)
    setHallOpen(next.mode === 'play')
    experiment.start(next)
    setScreen('live')
  }
  const restart = () => {
    if (plan) experiment.start(plan)
  }
  const newExperiment = () => {
    experiment.leave()
    setProblem(null)
    setScreen('setup')
  }
  const watchExample = () => {
    experiment.leave()
    setProblem(null)
    setDemoOnNumbers(false)
    setScreen('demo')
  }

  const live = screen === 'live' ? state : null
  const demoStatus = demo.status === 'idle' ? 'loading' : demo.status
  const question = live ? experimentQuestion(live.arms) : screen === 'demo' && demo.arms ? experimentQuestion(demo.arms) : null

  return (
    <div className={`nx nx-app${live && hallOpen ? ' has-hall' : ''}`}>
      <header className="nx-appbar">
        <div className="nx-brand">{COPY.app.brand}</div>
        {question && <h1 className="nx-question">{question}</h1>}
        <div className="nx-sp" />
        {screen === 'live' && <button type="button" className="nx-abtn" onClick={newExperiment}>{COPY.live.newExperiment}</button>}
        {screen === 'demo' && <button type="button" className="nx-abtn" onClick={() => setScreen('setup')}>{COPY.live.setUp}</button>}
        {screen !== 'demo' && <button type="button" className="nx-abtn is-link" onClick={watchExample}>{COPY.live.watchExample}</button>}
        <a className="nx-abtn is-link" href="?view=classic">{COPY.app.classic}</a>
      </header>

      {screen === 'setup' && <SetupScreen setup={setup} onStart={start} onWatchExample={watchExample} problem={problem} />}

      {live && (
        <LiveRun
          key={live.experimentId}
          state={live}
          experiment={experiment}
          hallOpen={hallOpen}
          onHall={setHallOpen}
          onRestart={restart}
          onNewExperiment={newExperiment}
        />
      )}

      {screen === 'demo' && demoStatus === 'ready' && <DemoRun arms={demo.arms} numbersOpen={demoOnNumbers} />}
      {screen === 'demo' && demoStatus === 'loading' && (
        <main className="nx-wrap nx-status"><p role="status">{COPY.app.loading}</p></main>
      )}
      {screen === 'demo' && demoStatus === 'error' && (
        <main className="nx-wrap nx-status">
          <p className="nx-error" role="alert">{COPY.app.missing}</p>
          <p className="nx-detail">{COPY.app.detail(demo.reason)}</p>
        </main>
      )}
    </div>
  )
}
