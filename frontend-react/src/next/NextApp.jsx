import { useEffect, useMemo, useState } from 'react'
import { COPY, TOWN_COLORS } from './catalog.js'
import { commonTicks } from './data/derive.js'
import { buildArm, parseSession } from './data/session.js'
import { experimentQuestion } from './narration.js'
import useReplay from './useReplay.js'
import RunScreen from './RunScreen.jsx'
import './next.css'

// The two recorded demo towns, served from public/demo/.
const DEMO_FILES = ['town-a.jsonl', 'town-b.jsonl']

async function loadTown(file, index) {
  const url = `${import.meta.env.BASE_URL}demo/${file}`
  const response = await fetch(url)
  if (!response.ok) throw new Error(`${url} answered ${response.status}`)
  const arm = buildArm(parseSession(await response.text()), { label: COPY.app.townLabel(index), color: TOWN_COLORS[index] })
  if (!arm.ticks.length) throw new Error(`${url} has no recorded weeks`)
  return arm
}

// The new Run screen, opened at ?view=next, playing the recorded demo. It owns
// the replay clock and hands it down.
export default function NextApp() {
  const [state, setState] = useState({ status: 'loading', arms: null, reason: null })

  useEffect(() => {
    let live = true
    Promise.all(DEMO_FILES.map(loadTown))
      .then(arms => { if (live) setState({ status: 'ready', arms, reason: null }) })
      .catch(error => { if (live) setState({ status: 'error', arms: null, reason: error?.message ?? String(error) }) })
    return () => { live = false }
  }, [])

  // The page behind the app takes the new screen's colour while it is open.
  useEffect(() => {
    const page = document.documentElement
    page.classList.add('nx-page')
    return () => page.classList.remove('nx-page')
  }, [])

  const ticks = useMemo(() => commonTicks(state.arms ?? []), [state.arms])
  const maxTick = ticks.length ? ticks[ticks.length - 1] : 1
  const clock = useReplay({ maxTick })
  const question = state.arms ? experimentQuestion(state.arms) : null

  return (
    <div className="nx nx-app">
      <header className="nx-appbar">
        <div className="nx-brand">{COPY.app.brand}</div>
        {question && <h1 className="nx-question">{question}</h1>}
        <div className="nx-sp" />
        <a className="nx-abtn is-link" href="?view=classic">{COPY.app.classic}</a>
      </header>
      {state.status === 'ready' && (
        <RunScreen
          arms={state.arms}
          tick={clock.tick}
          maxTick={maxTick}
          playing={clock.playing}
          onToggle={clock.toggle}
          onScrub={clock.scrub}
          speed={clock.speed}
          onSpeed={clock.setSpeed}
        />
      )}
      {state.status === 'loading' && (
        <main className="nx-wrap nx-status"><p role="status">{COPY.app.loading}</p></main>
      )}
      {state.status === 'error' && (
        <main className="nx-wrap nx-status">
          <p className="nx-error" role="alert">{COPY.app.missing}</p>
          <p className="nx-detail">{COPY.app.detail(state.reason)}</p>
        </main>
      )}
    </div>
  )
}
