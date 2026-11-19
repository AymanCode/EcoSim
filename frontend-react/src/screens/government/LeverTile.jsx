import { formatLeverValue, isLeverActive } from '../../governmentInsights.js'
import { formatInteger } from '../../format.js'
import CurrencyInput from '../../ui/CurrencyInput.jsx'
import { FOOD_CREDIT_BUDGET_HELP } from '../../foodCredit.js'

const tickText = (value) =>
  value === undefined || value === null || value === '' || Number.isNaN(Number(value))
    ? '—'
    : formatInteger(value)

export function LeverControl({ lever, live, config, onConfigChange, enumOptions, foodCreditAvailable = true }) {
  const value = lever.key === 'food_credit_policy' ? live : config?.[lever.configKey]
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
  const options = lever.key === 'food_credit_policy'
    ? [{ value: 'off', label: 'Off' }, { value: 'on', label: 'On' }]
    : enumOptions?.[lever.options] || []
  return (
    <>
    <select
      aria-label={lever.label}
      value={String(value ?? '')}
      onChange={(e) =>
        (lever.key !== 'food_credit_policy' || e.target.value !== 'on' || foodCreditAvailable) && onConfigChange(
          lever.configKey,
          numeric ? Number(e.target.value) : e.target.value
        )
      }
      className="select"
      style={{ padding: '4px 8px', fontSize: 11.5, width: '100%' }}
    >
      {options.map((option) => (
        <option key={option.value} value={option.value} disabled={lever.key === 'food_credit_policy' && option.value === 'on' && !foodCreditAvailable}>
          {option.label}
        </option>
      ))}
    </select>
    {lever.key === 'food_credit_policy' && (
      <p className="muted" style={{ fontSize: 11, margin: '6px 0 0' }}>
        Closing the program stops new awards. Households can still spend the credit on their cards.
        {!foodCreditAvailable && ' Opening is available only when income arrives before bills.'}
      </p>
    )}
    </>
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
  foodCreditAvailable,
  foodCreditBudget,
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
      {lever.key === 'food_credit_policy' && (
        <div style={{ marginTop: 6 }} onClick={(e) => e.stopPropagation()}>
          <label htmlFor="food-credit-weekly-budget" style={{ display: 'block', fontSize: 11 }}>
            Weekly cap ($)
          </label>
          <CurrencyInput
            id="food-credit-weekly-budget"
            aria-label="Grocery benefit weekly cap"
            aria-describedby="food-credit-budget-help"
            className="select"
            style={{ padding: '4px 8px', fontSize: 11.5, width: '100%' }}
            value={foodCreditBudget}
            placeholder="Awaiting policy"
            disabled={!foodCreditAvailable}
            commitOnBlur
            onChange={(amount) => onConfigChange('food_credit_weekly_budget', amount)}
          />
          <p id="food-credit-budget-help" className="muted" style={{ fontSize: 11, margin: '6px 0 0' }}>
            {FOOD_CREDIT_BUDGET_HELP}
          </p>
        </div>
      )}
      <div
        style={{ display: isOpen || lever.key === 'food_credit_policy' ? 'block' : 'none', marginTop: 6 }}
        onClick={(e) => e.stopPropagation()}
      >
        <LeverControl
          lever={lever}
          live={live}
          config={config}
          onConfigChange={onConfigChange}
          enumOptions={enumOptions}
          foodCreditAvailable={foodCreditAvailable}
        />
      </div>
    </div>
  )
}
