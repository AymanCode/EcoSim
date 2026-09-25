import { Fragment } from 'react'
import {
  COPY, DEFAULT_POLICY, LEVER_GROUPS, LEVER_OPTIONS, LEVERS, capitalise, leverName, leverValuePhrase,
} from '../catalog.js'
import { PROBLEM_LEVERS, policyProblems } from '../policyRules.js'
import '../next.css'

// Levers with this many options or fewer are a row of buttons, more a select.
const MAX_BUTTONS = 5
const THUMB = 16

// Where the slider's fill ends, measured the way a range input places its thumb.
const along = fraction => `calc(${THUMB / 2}px + (100% - ${THUMB}px) * ${fraction})`

// A lever's value as the schema holds it: rates and the integer levers as
// numbers, the rest as their option.
function asOption(lever, value) {
  const options = LEVER_OPTIONS[lever]
  if (!Array.isArray(options)) {
    const number = Number(value)
    return Number.isFinite(number) ? number : value
  }
  return options.find(option => String(option) === String(value)) ?? value
}

// All 17 levers: DEFAULT_POLICY under whatever the vector sets.
function complete(vector) {
  const full = { ...DEFAULT_POLICY }
  for (const lever of Object.keys(DEFAULT_POLICY)) {
    if (vector?.[lever] !== undefined) full[lever] = asOption(lever, vector[lever])
  }
  return full
}

const same = (a, b) => (typeof a === 'number' && typeof b === 'number' ? Math.abs(a - b) < 1e-9 : String(a) === String(b))
const toCents = value => Math.round(value * 100) / 100

// The lever's name and, when it differs from the base, a dot. Controls take
// their name from the name plus the hidden "(changed)" through
// aria-labelledby, which joins the two with a space.
function LeverName({ lever, changed, as: Tag = 'span', labelId, changedId, htmlFor }) {
  return (
    <>
      <Tag className="nx-lname" id={labelId} htmlFor={htmlFor}>
        {capitalise(leverName(lever))}
        {changed && <i className="nx-ldot" aria-hidden="true" />}
      </Tag>
      {changed && <span className="nx-sr" id={changedId}>{COPY.levers.changed}</span>}
    </>
  )
}

function Lever({ lever, value, changed, id, onPick }) {
  const spec = LEVERS[lever]
  const options = LEVER_OPTIONS[lever]
  const labelId = `${id}-label`
  const changedId = `${id}-changed`
  const helpId = `${id}-help`
  const labelledBy = changed ? `${labelId} ${changedId}` : labelId
  const nameProps = { lever, changed, labelId, changedId }
  const help = <p className="nx-lhelp" id={helpId}>{spec.help}</p>

  if (!Array.isArray(options)) {
    const { min, max } = options
    const shown = leverValuePhrase(lever, value)
    const fraction = max > min ? Math.min(1, Math.max(0, (value - min) / (max - min))) : 0
    return (
      <div className="nx-lever" data-lever={lever}>
        <div className="nx-lhead">
          <LeverName {...nameProps} as="label" htmlFor={id} />
          <output className="nx-lval" htmlFor={id}>{shown}</output>
        </div>
        {help}
        <input
          type="range"
          className="nx-range"
          id={id}
          min={min}
          max={max}
          step={0.01}
          value={value}
          aria-labelledby={labelledBy}
          aria-valuetext={shown}
          aria-describedby={helpId}
          style={{ '--nx-fill': along(fraction) }}
          onChange={event => onPick(toCents(Number(event.target.value)))}
        />
      </div>
    )
  }

  const optionLabel = option => spec.values?.[String(option)] ?? String(option)

  if (options.length > MAX_BUTTONS) {
    return (
      <div className="nx-lever" data-lever={lever}>
        <div className="nx-lhead">
          <LeverName {...nameProps} as="label" htmlFor={id} />
        </div>
        {help}
        <select
          className="nx-select"
          id={id}
          value={String(value)}
          aria-labelledby={labelledBy}
          aria-describedby={helpId}
          onChange={event => onPick(options.find(option => String(option) === event.target.value))}
        >
          {options.map(option => <option key={String(option)} value={String(option)}>{optionLabel(option)}</option>)}
        </select>
      </div>
    )
  }

  return (
    <div className="nx-lever" data-lever={lever}>
      <div className="nx-lhead">
        <LeverName {...nameProps} />
      </div>
      {help}
      <div className="nx-seg" role="group" aria-labelledby={labelledBy} aria-describedby={helpId}>
        {options.map(option => (
          <button key={String(option)} type="button" aria-pressed={same(option, value)} onClick={() => onPick(option)}>
            {optionLabel(option)}
          </button>
        ))}
      </div>
    </div>
  )
}

// Every lever of the town hall in five sections. `value` is the rules being
// edited, `base` the rules to mark changes against; onChange always gets all
// 17 levers, numbers as numbers. A group rule the rules break shows under its
// section.
export default function LeverEditor({ value, base = DEFAULT_POLICY, onChange, idPrefix = 'levers' }) {
  const current = complete(value)
  const baseline = complete(base)
  const problems = Object.entries(policyProblems(current))
  const pick = lever => next => onChange({ ...current, [lever]: asOption(lever, next) })

  return (
    <div className="nx-levers">
      {LEVER_GROUPS.map(group => {
        const copy = COPY.levers.groups[group.id]
        const blurbId = `${idPrefix}-${group.id}-blurb`
        // A broken rule shows right after the last of its levers in this section.
        const after = lever => problems.filter(([key]) => {
          const tied = (PROBLEM_LEVERS[key] ?? []).filter(l => group.levers.includes(l))
          return tied[tied.length - 1] === lever
        })
        return (
          <fieldset key={group.id} className="nx-lgroup" aria-describedby={blurbId}>
            <legend>{copy.title}</legend>
            <p className="nx-lblurb" id={blurbId}>{copy.blurb}</p>
            {group.levers.map(lever => (
              <Fragment key={lever}>
                <Lever
                  lever={lever}
                  value={current[lever]}
                  changed={!same(current[lever], baseline[lever])}
                  id={`${idPrefix}-${lever}`}
                  onPick={pick(lever)}
                />
                {after(lever).map(([key, text]) => <p key={key} className="nx-lproblem" role="alert">{text}</p>)}
              </Fragment>
            ))}
          </fieldset>
        )
      })}
    </div>
  )
}
