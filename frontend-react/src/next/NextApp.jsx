import { useEffect, useState } from 'react'
import { COPY, TOWN_COLORS } from './catalog.js'
import { buildArm, parseSession } from './data/session.js'
import { experimentQuestion } from './narration.js'
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

// The new Run screen, opened at ?view=next, playing the recorded demo.
export default function NextApp() {
  const [state, setState] = useState({ status: 'loading', arms: null, reason: null })

  useEffect(() => {
    let live = true
    Promise.all(DEMO_FILES.map(loadTown))
      .then(arms => { if (live) setState({ status: 'ready', arms, reason: null }) })
      .catch(error => { if (live) setState({ status: 'error', arms: null, reason: error?.message ?? String(error) }) })
    return () => { live = false }
  }, [])

  const question = state.arms ? experimentQuestion(state.arms) : null

  return (
    <div className="nx nx-app">
      <header className="nx-appbar">
        <div className="nx-brand">{COPY.app.brand}</div>
        {question && <p className="nx-question">{question}</p>}
        <div className="nx-sp" />
        <a className="nx-abtn is-link" href="?view=classic">{COPY.app.classic}</a>
      </header>
      {state.status === 'ready' && <RunScreen arms={state.arms} />}
      {state.status === 'loading' && (
        <main className="nx-wrap nx-status"><p>{COPY.app.loading}</p></main>
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
