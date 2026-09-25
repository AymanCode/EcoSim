import { useId, useState } from 'react'
import { COPY, DEFAULT_POLICY, NO_CHANGES, QUESTIONS, TOWN_COLORS, capitalise, describePolicy } from '../catalog.js'
import { HOUSEHOLD_STEP, TOWN_LABELS, YEARS, estimatePhrase, estimateSeconds, householdCap, policyChanges } from '../live/plan.js'
import { policyProblems } from '../policyRules.js'
import LeverEditor from '../components/LeverEditor.jsx'
import '../next.css'

const THUMB = 16
const along = fraction => `calc(${THUMB / 2}px + (100% - ${THUMB}px) * ${fraction})`
const MAX_SEED = 2147483647

const MODES = ['compare', 'ai', 'play']
const MODE_ICONS = {
  compare: <path d="M4 18h16M6 18V9M12 18V5M18 18v-7" />,
  ai: (
    <>
      <rect x="4" y="7" width="16" height="12" rx="3" />
      <path d="M12 3v4M9 13h.01M15 13h.01" />
    </>
  ),
  play: <path d="M5 12h14M12 5v14" />,
}

// A card's town as a chip: the rules it changes, or "No changes".
function chipText(levers) {
  const phrase = describePolicy(levers)
  return phrase === NO_CHANGES ? COPY.setup.noChanges : capitalise(phrase)
}

// A town tile's sentence about its rules.
function rulesSentence(policy, mode) {
  const phrase = describePolicy(policyChanges(policy))
  if (phrase === NO_CHANGES) return mode === 'play' ? COPY.setup.usual : COPY.setup.control
  return COPY.setup.townRules(phrase)
}

function StepHead({ id, number, title, note }) {
  return (
    <div className="nx-stephead">
      <h2 id={id}><b aria-hidden="true">{number}</b>{title}</h2>
      {note && <p>{note}</p>}
    </div>
  )
}

function ModeCard({ uid, mode, pressed, onPick }) {
  const copy = COPY.setup.modes[mode]
  const soon = mode === 'ai'
  const ids = { title: `${uid}-mode-${mode}`, blurb: `${uid}-mode-${mode}-d`, soon: `${uid}-mode-${mode}-soon` }
  return (
    <button
      type="button"
      className="nx-mode"
      aria-pressed={soon ? undefined : pressed}
      disabled={soon}
      aria-labelledby={ids.title}
      aria-describedby={soon ? `${ids.blurb} ${ids.soon}` : ids.blurb}
      onClick={soon ? undefined : onPick}
    >
      <span className="nx-pick" aria-hidden="true" />
      <span className={`nx-mode-ic is-${mode}`} aria-hidden="true">
        <svg viewBox="0 0 24 24" focusable="false">{MODE_ICONS[mode]}</svg>
      </span>
      <span className="nx-mode-t" id={ids.title}>{copy.title}</span>
      <span className="nx-mode-d" id={ids.blurb}>{copy.blurb}</span>
      {soon && <span className="nx-soon" id={ids.soon}>{COPY.setup.comingSoon}</span>}
    </button>
  )
}

function QuestionCard({ uid, question, pressed, onPick }) {
  const ids = { title: `${uid}-q-${question.id}`, towns: `${uid}-q-${question.id}-towns`, blurb: `${uid}-q-${question.id}-d` }
  const towns = question.towns.map((levers, i) => ({ label: TOWN_LABELS[i], color: TOWN_COLORS[i], text: chipText(levers) }))
  return (
    <button
      type="button"
      className="nx-q"
      aria-pressed={pressed}
      aria-labelledby={ids.title}
      aria-describedby={`${ids.towns} ${ids.blurb}`}
      onClick={onPick}
    >
      <span className="nx-q-t" id={ids.title}>{question.title}</span>
      <span className="nx-arms" aria-hidden="true">
        {towns.map(town => (
          <span key={town.label}><i style={{ background: town.color }} />{town.text}</span>
        ))}
      </span>
      <span className="nx-sr" id={ids.towns}>{COPY.setup.cardTowns(towns)}</span>
      <span className="nx-q-d" id={ids.blurb}>{question.blurb}</span>
    </button>
  )
}

// The seed field of "Build my own". It keeps what is being typed until it
// leaves the field, so clearing it to type a new number works.
function SeedField({ id, seed, onSeed }) {
  const [draft, setDraft] = useState(null)
  return (
    <div className="nx-seed">
      <label htmlFor={id}>{COPY.setup.seedLabel}</label>
      <input
        id={id}
        type="number"
        inputMode="numeric"
        min={0}
        max={MAX_SEED}
        step={1}
        value={draft ?? String(seed)}
        onChange={event => {
          const text = event.target.value
          setDraft(text)
          if (text.trim() !== '' && Number.isFinite(Number(text))) onSeed(Number(text))
        }}
        onBlur={() => setDraft(null)}
      />
    </div>
  )
}

function Problem({ problem, onWatchExample }) {
  const kind = COPY.setup.problems[problem.kind] ? problem.kind : 'setup'
  return (
    <div className="nx-problem" role="alert">
      <p className="nx-problem-t">{COPY.setup.problems[kind]}</p>
      {kind === 'unreachable' ? (
        <>
          <p>{COPY.setup.startWith}</p>
          <code>{COPY.setup.command}</code>
          <button type="button" className="nx-abtn" onClick={onWatchExample}>{COPY.setup.watchInstead}</button>
        </>
      ) : (
        problem.message && <p className="nx-detail">{COPY.app.detail(problem.message)}</p>
      )}
    </div>
  )
}

// The Set up screen: the kind of experiment, a question, the towns and their
// rules, and the world they share. NextApp owns `setup` (useSetup) so the plan
// survives a trip to the Run screen and back.
export default function SetupScreen({ setup, onStart, onWatchExample, problem = null }) {
  const uid = useId()
  const { state, actions, plan } = setup
  const { mode, questionId, towns, households, years, seed, editing } = state
  const compare = mode === 'compare'
  const cap = householdCap(towns.length)
  const broken = towns.filter(town => Object.keys(policyProblems(town.policy)).length).map(town => town.label)
  const estimate = estimatePhrase(estimateSeconds({ households, towns: towns.length, years }))
  const open = editing != null ? towns[editing] : null

  const ids = {
    mode: `${uid}-step-mode`,
    question: `${uid}-step-question`,
    towns: `${uid}-step-towns`,
    world: `${uid}-step-world`,
    editor: `${uid}-editor`,
    editorTitle: `${uid}-editor-title`,
    add: `${uid}-add`,
    addNote: `${uid}-add-note`,
    households: `${uid}-households`,
    householdsCap: `${uid}-households-cap`,
    householdsNote: `${uid}-households-note`,
    years: `${uid}-years`,
    seed: `${uid}-seed`,
  }
  // Step numbers: the question step is there only when comparing.
  const steps = { mode: 1, question: 2, towns: compare ? 3 : 2, world: compare ? 4 : 3 }

  return (
    <main className="nx-wrap nx-setup">
      <h1 className="nx-setup-lead">{COPY.setup.title}</h1>
      <p className="nx-setup-sub">{COPY.setup.subhead}</p>
      <button type="button" className="nx-more nx-watch" onClick={onWatchExample}>{COPY.setup.watchFirst}</button>

      <section className="nx-step" aria-labelledby={ids.mode}>
        <StepHead id={ids.mode} number={steps.mode} title={COPY.setup.steps.mode} />
        <div className="nx-modes">
          {MODES.map(value => (
            <ModeCard key={value} uid={uid} mode={value} pressed={mode === value} onPick={() => actions.setMode(value)} />
          ))}
        </div>
      </section>

      {compare && (
        <section className="nx-step" aria-labelledby={ids.question}>
          <StepHead id={ids.question} number={steps.question} title={COPY.setup.steps.question} />
          <div className="nx-qs">
            {QUESTIONS.map(question => (
              <QuestionCard
                key={question.id}
                uid={uid}
                question={question}
                pressed={questionId === question.id}
                onPick={() => actions.pickQuestion(question.id)}
              />
            ))}
            <button
              type="button"
              className="nx-q is-custom"
              aria-pressed={questionId === 'custom'}
              aria-labelledby={`${uid}-q-custom`}
              aria-describedby={`${uid}-q-custom-d`}
              onClick={() => actions.pickQuestion('custom')}
            >
              <span className="nx-q-t" id={`${uid}-q-custom`}>{COPY.setup.custom.title}</span>
              <span className="nx-q-d" id={`${uid}-q-custom-d`}>{COPY.setup.custom.blurb}</span>
            </button>
          </div>
        </section>
      )}

      <section className="nx-step" aria-labelledby={ids.towns}>
        <StepHead id={ids.towns} number={steps.towns} title={compare ? COPY.setup.steps.towns : COPY.setup.steps.town} />
        <ul className="nx-towns">
          {towns.map((town, i) => {
            const editingThis = editing === i
            const needsFix = broken.includes(town.label)
            return (
              <li key={town.label} className={`nx-tw${editingThis ? ' is-editing' : ''}`} aria-label={town.label}>
                <i className="nx-tw-dot" style={{ background: town.color }} aria-hidden="true" />
                <div className="nx-tw-text">
                  <div className="nx-tw-n">
                    {town.label}
                    {needsFix && <span className="nx-fixtag">{COPY.setup.needsFix}</span>}
                  </div>
                  <div className="nx-tw-r">{rulesSentence(town.policy, mode)}</div>
                </div>
                <div className="nx-tw-act">
                  <button
                    type="button"
                    className="nx-more"
                    aria-label={COPY.setup.changeRulesFor(town.label)}
                    aria-expanded={editingThis}
                    aria-controls={editingThis ? ids.editor : undefined}
                    onClick={() => (editingThis ? actions.closeEditor() : actions.editTown(i))}
                  >
                    {COPY.setup.changeRules}
                  </button>
                  {compare && i >= 2 && (
                    <button
                      type="button"
                      className="nx-more"
                      aria-label={COPY.setup.removeTown(town.label)}
                      onClick={() => actions.removeTown(i)}
                    >
                      {COPY.setup.remove}
                    </button>
                  )}
                </div>
              </li>
            )
          })}
          {compare && towns.length < TOWN_LABELS.length && (
            <li className="nx-tw is-add">
              <button type="button" aria-labelledby={ids.add} aria-describedby={ids.addNote} onClick={actions.addTown}>
                <b id={ids.add}>{COPY.setup.addTown}</b>
                <small id={ids.addNote}>{COPY.setup.addTownNote}</small>
              </button>
            </li>
          )}
        </ul>

        {open && (
          <section className="nx-editor" id={ids.editor} aria-labelledby={ids.editorTitle}>
            <div className="nx-editor-head">
              <i style={{ background: open.color }} aria-hidden="true" />
              <h3 id={ids.editorTitle}>{COPY.setup.editorTitle(open.label)}</h3>
              <div className="nx-sp" />
              <button type="button" className="nx-abtn is-dark" onClick={actions.closeEditor}>{COPY.setup.done}</button>
            </div>
            <LeverEditor
              value={open.policy}
              base={DEFAULT_POLICY}
              onChange={policy => actions.setTownPolicy(editing, policy)}
              idPrefix={`${uid}-town-${editing}`}
            />
          </section>
        )}
      </section>

      <section className="nx-step" aria-labelledby={ids.world}>
        <StepHead id={ids.world} number={steps.world} title={COPY.setup.steps.world} note={compare ? COPY.setup.worldNote : null} />
        <div className="nx-world">
          <div className="nx-f">
            <div className="nx-f-k">
              <label htmlFor={ids.households}>{COPY.setup.households}</label>
              <output className="nx-f-v" htmlFor={ids.households}>{COPY.setup.householdsValue(households)}</output>
            </div>
            <div className="nx-f-range">
              <span className="nx-f-cap" id={ids.householdsCap}>{COPY.setup.householdsCap(cap, towns.length)}</span>
              <input
                type="range"
                className="nx-range"
                id={ids.households}
                min={HOUSEHOLD_STEP}
                max={cap}
                step={HOUSEHOLD_STEP}
                value={households}
                aria-describedby={`${ids.householdsCap} ${ids.householdsNote}`}
                style={{ '--nx-fill': along(cap > HOUSEHOLD_STEP ? (households - HOUSEHOLD_STEP) / (cap - HOUSEHOLD_STEP) : 1) }}
                onChange={event => actions.setHouseholds(Number(event.target.value))}
              />
            </div>
            <p className="nx-f-d" id={ids.householdsNote}>{COPY.setup.householdsNote}</p>
          </div>

          <div className="nx-f">
            <div className="nx-f-k">
              <span id={ids.years}>{COPY.setup.years}</span>
              <span className="nx-f-v">{COPY.setup.yearsValue(years)}</span>
            </div>
            <div className="nx-seg" role="group" aria-labelledby={ids.years}>
              {YEARS.map(value => (
                <button
                  key={value}
                  type="button"
                  aria-pressed={value === years}
                  aria-label={COPY.setup.yearsValue(value)}
                  onClick={() => actions.setYears(value)}
                >
                  {value}
                </button>
              ))}
            </div>
            <p className="nx-f-d">{COPY.setup.yearsNote}</p>
          </div>

          <div className="nx-f">
            <div className="nx-f-k">
              <span>{COPY.setup.town}</span>
              <span className="nx-f-v">{COPY.setup.townNumber(seed)}</span>
            </div>
            <button type="button" className="nx-abtn nx-reroll" onClick={actions.rerollSeed}>{COPY.setup.reroll}</button>
            {questionId === 'custom' && <SeedField id={ids.seed} seed={seed} onSeed={actions.setSeed} />}
            <p className="nx-f-d">{COPY.setup.townNote}</p>
          </div>
        </div>
      </section>

      <div className="nx-go">
        {problem && <Problem problem={problem} onWatchExample={onWatchExample} />}
        <div className="nx-go-row">
          <button type="button" className="nx-start" disabled={broken.length > 0} onClick={() => onStart(plan)}>
            {compare ? COPY.setup.start : COPY.setup.startPlay}
          </button>
          <p className="nx-est">
            <span>{COPY.setup.estimate({ towns: towns.length, households, years })}</span>{' '}
            <b>{estimate}</b>
            <br />
            {COPY.setup.anyTime}
          </p>
        </div>
        {broken.length > 0 && <p className="nx-fix" role="status">{COPY.setup.fixFirst(broken)}</p>}
      </div>
    </main>
  )
}
