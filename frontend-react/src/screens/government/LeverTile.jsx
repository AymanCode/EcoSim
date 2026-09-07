import { formatLeverValue, isLeverActive } from '../../governmentInsights.js'
import { formatInteger } from '../../format.js'

const tickText = (value) =>
  value === undefined || value === null || value === '' || Number.isNaN(Number(value))
    ? '—'
    : formatInteger(value)

export function LeverControl({ lever, config, onConfigChange, enumOptions }) {
  const value = config?.[lever.configKey]
  if (lever.kind === 'readonly-percent') {
    return (
      <div style={{ fontSize: '11px', color: 'var(--ink4)', padding: '4px 0' }}>
        Fixed by the simulator
      </div>
    )
  }
  if (lever.kind === 'percent') {
    const progress =
      ((Number(value) - lever.min) / ((lever.max - lever.min) || 1)) * 100
    return (
      <input
        type="range"
        aria-label={lever.label}
        min={lever.min}
        max={lever.max}
        step={lever.step}
        value={value ?? lever.min}
        onChange={(e) => onConfigChange(lever.configKey, parseFloat(e.target.value))}
        style={{
          '--p': `${Math.max(0, Math.min(100, progress))}%`,
          width: '100%',
        }}
      />
    )
  }
  if (lever.kind === 'toggle') {
    const checked = Boolean(value)
    return (
      <button
        type="button"
        onClick={() => onConfigChange(lever.configKey, !checked)}
        aria-pressed={checked}
        aria-label={lever.label}
        className={`toggle${checked ? ' on' : ''}`}
        style={{ padding: '3px 8px', fontSize: 11 }}
      >
        <span className="tl" style={{ fontSize: 11 }}>
          {checked ? 'Hiring programme running' : 'Hiring programme off'}
        </span>
        <span className="sw" />
      </button>
    )
  }
  const numeric = lever.kind === 'enum-number'
  const options = enumOptions?.[lever.options] || []
  return (
    <select
      aria-label={lever.label}
      value={String(value ?? '')}
      onChange={(e) =>
        onConfigChange(
          lever.configKey,
          numeric ? Number(e.target.value) : e.target.value
        )
      }
      className="select"
      style={{ padding: '4px 8px', fontSize: 11.5, width: '100%' }}
    >
      {options.map((option) => (
        <option key={option.value} value={option.value}>
          {option.label}
        </option>
      ))}
    </select>
  )
}

export default function LeverTile({
  lever,
  live,
  isDefault,
  lastChange,
  refusal,
  hit,
  hitColor,
  isOpen,
  onEdit,
  config,
  onConfigChange,
  enumOptions,
}) {
  const active = !isDefault && isLeverActive(lever.key, live)
  const isAiMover = lastChange?.actor === 'ai'

  const valueStyle = isAiMover
    ? { color: 'var(--ai)' }
    : active
      ? { color: 'var(--acc)' }
      : undefined

  const whoLabel = (actor) =>
    actor === 'ai' ? 'AI' : actor === 'you' ? 'You' : 'Auto'

  let foot
  if (refusal) {
    foot = (
      <span style={{ color: 'var(--crit)' }}>
        {formatLeverValue(lever.key, refusal.value)} refused · tick {tickText(refusal.tick)}
      </span>
    )
  } else if (lastChange) {
    const label = whoLabel(lastChange.actor)
    foot = (
      <span>
        {label} · tick {tickText(lastChange.tick)}
        {lastChange.previous != null && ` · was ${formatLeverValue(lever.key, lastChange.previous)}`}
      </span>
    )
  } else {
    foot = <span>{isDefault ? 'Default' : 'Set at launch'}</span>
  }

  return (
    <div
      className={`lv${active ? ' active' : ''}${hit ? ' hit' : ''}`}
      style={hit ? { '--hit': hitColor || 'var(--acc)', cursor: 'pointer' } : { cursor: 'pointer' }}
      onClick={() => onEdit?.(lever.key)}
    >
      <div className="lvt">
        <span>{lever.label}</span>
        <b className="mono" style={valueStyle}>
          {formatLeverValue(lever.key, live)}
        </b>
      </div>
      <div className="lvc" style={hit && hitColor ? { color: hitColor } : undefined}>
        {foot}
      </div>
      <div
        style={{ display: isOpen ? 'block' : 'none', marginTop: 6 }}
        onClick={(e) => e.stopPropagation()}
      >
        <LeverControl
          lever={lever}
          config={config}
          onConfigChange={onConfigChange}
          enumOptions={enumOptions}
        />
      </div>
    </div>
  )
}
