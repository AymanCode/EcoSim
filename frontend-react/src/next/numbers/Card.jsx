import { useId } from 'react'
import { COPY } from '../catalog.js'
import '../next.css'

function BigIcon() {
  return (
    <svg viewBox="0 0 10 10" aria-hidden="true" focusable="false">
      <path d="M6 1.5h2.5V4M8.5 1.5 5 5M4 8.5H1.5V6M1.5 8.5 5 5" />
    </svg>
  )
}

// A card of the numbers sheet, in the tile's look: a title and whatever it
// draws. When it has a measured number to show big (`metricKey`, `measured`
// and `onSeeBig`), it carries the "See it big" badge and a click, Enter or
// Space calls onSeeBig(metricKey); `data-metric` lets the sheet bring focus
// back to it when the big chart closes.
export default function Card({ title, metricKey = null, measured = true, onSeeBig, className = '', children }) {
  const uid = useId().replace(/:/g, '')
  const titleId = `nx-card-${uid}`
  const bigId = `nx-card-big-${uid}`
  const opens = Boolean(metricKey) && measured && typeof onSeeBig === 'function'

  const open = () => onSeeBig(metricKey)
  const onKeyDown = event => {
    if (event.target !== event.currentTarget || (event.key !== 'Enter' && event.key !== ' ')) return
    event.preventDefault()
    open()
  }
  const interactive = opens
    ? { tabIndex: 0, 'aria-describedby': bigId, onClick: open, onKeyDown, 'data-metric': metricKey }
    : {}

  return (
    <article className={`nx-tile${opens ? ' is-open' : ''}${className ? ` ${className}` : ''}`} aria-labelledby={titleId} {...interactive}>
      {opens && <span className="nx-big" id={bigId} aria-hidden="true"><BigIcon />{COPY.numbers.seeBig}</span>}
      <div className="nx-th"><h4 id={titleId}>{title}</h4></div>
      {children}
    </article>
  )
}

// Each town's value with its colour dot, large, as on a tile. `texts[i]` is
// town i's value, already worded.
export function Values({ arms, texts }) {
  return (
    <div className="pair">
      {arms.map((arm, i) => (
        <div className="nx-pv" key={arm.label}>
          <b><i style={{ background: arm.color }} aria-hidden="true" />{texts[i]}</b>
          <small>{arm.label}</small>
        </div>
      ))}
    </div>
  )
}

// A town's colour swatch and name.
export function TownName({ arm, children }) {
  return (
    <span className="nx-vtown">
      <i style={{ background: arm.color }} aria-hidden="true" />{arm.label}{children}
    </span>
  )
}

// Copy given as parts, the odd ones bold: ['this week ', 6, ' hired'].
export function Bolded({ parts }) {
  return <>{parts.map((part, i) => (i % 2 ? <b key={i}>{part}</b> : part))}</>
}

// The hatched "setting up" fill of weeks 1 to 10, as an SVG pattern.
export function Hatch({ id }) {
  return (
    <pattern id={id} width={6} height={6} patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
      <rect className="nx-hatch-bg" width={6} height={6} />
      <line className="nx-hatch" x1={0} y1={0} x2={0} y2={6} />
    </pattern>
  )
}

// A colour key: [{ label, className, style }] as small swatches.
export function SwatchKey({ items }) {
  return (
    <ul className="nx-skey">
      {items.map(item => (
        <li key={item.label}><i className={item.className} style={item.style} aria-hidden="true" />{item.label}</li>
      ))}
    </ul>
  )
}
