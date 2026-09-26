import { useId, useState } from 'react'
import { COPY, LEVERS, WARMUP_TICKS, leverName, leverValuePhrase, townTextColor } from '../catalog.js'
import { rulesTable } from '../data/derive.js'
import { weekLabel } from '../narration.js'
import '../next.css'

const same = (a, b) => (typeof a === 'number' && typeof b === 'number' ? Math.abs(a - b) < 1e-9 : String(a) === String(b))
const ruleName = lever => COPY.numbers.rules.names[lever] ?? leverName(lever)

// A group opens by itself when a rule in it differs between towns or changed
// during the run; the viewer's Show and Hide win after that.
const opensByItself = group => group.rows.some(row => row.differs || row.changes.some(Boolean))

function GroupSummary({ group, townCount }) {
  const differ = group.rows.filter(row => row.differs).length
  if (differ) return <span className="nx-rg-s is-diff">{COPY.numbers.rules.differ(differ)}</span>
  const settings = group.rows.map(row => COPY.numbers.rules.setting(ruleName(row.lever), leverValuePhrase(row.lever, row.values[0])))
  return (
    <span className="nx-rg-s">
      {townCount > 1 && <><b>{COPY.numbers.rules.same(townCount)}</b>{' '}</>}
      {settings.join(COPY.numbers.rules.settingsJoin)}
    </span>
  )
}

function RuleRow({ row, arms }) {
  const base = arms[0]?.label
  return (
    <tr className={`nx-rrow${row.differs ? ' is-diff' : ''}`}>
      <th scope="row" className="nx-rn">
        {ruleName(row.lever)}
        {row.differs && LEVERS[row.lever]?.help && <small>{LEVERS[row.lever].help}</small>}
      </th>
      {row.values.map((value, i) => {
        const differs = i > 0 && !same(value, row.values[0])
        const change = row.changes[i]
        return (
          <td key={arms[i].label} className={`nx-rv${differs ? ' is-diff' : ''}`} style={differs ? { color: townTextColor(arms[i].color) } : undefined}>
            {leverValuePhrase(row.lever, value)}
            {differs && <small>{COPY.numbers.rules.differentFrom(base)}</small>}
            {change && (
              <small>{COPY.numbers.rules.changed(weekLabel(change.changedAt), leverValuePhrase(row.lever, change.was), change.changedAt <= WARMUP_TICKS)}</small>
            )}
          </td>
        )
      })}
    </tr>
  )
}

// The rules in force in every town at `tick`, as a table with the towns as
// columns (rulesTable). Groups where every town agrees fold to one line;
// "Show" and "Hide" open and fold any group. A town's value that differs from
// the first town's reads in that town's colour. `notes[i]` goes under town i's
// column head (a live town's lost connection).
export default function RulesInForce({ arms, tick, id, notes = [] }) {
  const uid = useId().replace(/:/g, '')
  const titleId = `nx-rules-${uid}`
  const [toggled, setToggled] = useState({})
  const groups = rulesTable(arms, tick)
  const townCount = arms.length
  const differences = groups.flatMap(group => group.rows.filter(row => row.differs).map(row => leverName(row.lever)))

  return (
    <section id={id} className="nx-nsec" aria-labelledby={titleId}>
      <div className="nx-sh">
        <h3 id={titleId} tabIndex={-1}>{COPY.numbers.rules.title}</h3>
        <p>{COPY.numbers.rules.lead(townCount, differences)}</p>
      </div>
      <div className="nx-scroll">
        <table className="nx-rules" style={{ '--nx-towns': townCount }} aria-labelledby={titleId}>
          <colgroup>
            <col />
            {arms.map(arm => <col key={arm.label} className="nx-rules-town" />)}
          </colgroup>
          <thead>
            <tr>
              <th scope="col">{COPY.numbers.rules.rule}</th>
              {arms.map((arm, i) => (
                <th scope="col" key={arm.label} className="nx-rules-town">
                  <span><i style={{ background: arm.color }} aria-hidden="true" />{arm.label}</span>
                  {notes[i] && <small>{notes[i]}</small>}
                </th>
              ))}
            </tr>
          </thead>
          {groups.map(group => {
            const title = COPY.levers.groups[group.group]?.title ?? group.group
            const open = toggled[group.group] ?? opensByItself(group)
            const bodyId = `nx-rg-${uid}-${group.group}`
            const flip = () => setToggled(all => ({ ...all, [group.group]: !open }))
            return (
              <tbody key={group.group} id={bodyId} className={`nx-rg${open ? ' is-open' : ''}`}>
                <tr>
                  <th colSpan={townCount + 1} scope="rowgroup" className="nx-rg-head">
                    {/* The whole line opens and folds the group for a mouse; the button is the keyboard's way. */}
                    <div className="nx-rg-sum" onClick={flip}>
                      <span className="nx-rg-t">{title}</span>
                      <GroupSummary group={group} townCount={townCount} />
                      <button type="button" className="nx-rg-tog" aria-expanded={open} aria-controls={bodyId}>
                        {open ? COPY.numbers.rules.hide : COPY.numbers.rules.show}
                        {' '}
                        <span className="nx-sr">{title}</span>
                      </button>
                    </div>
                  </th>
                </tr>
                {open && group.rows.map(row => <RuleRow key={row.lever} row={row} arms={arms} />)}
              </tbody>
            )
          })}
        </table>
      </div>
    </section>
  )
}
