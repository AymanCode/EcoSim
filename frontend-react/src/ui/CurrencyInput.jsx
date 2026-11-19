import { useEffect, useId, useRef, useState } from 'react'

const textFor = value => (value === null || value === undefined ? '' : String(value))
const validAmount = text => /^\d+(?:\.\d{0,2})?$/.test(text) && Number.isFinite(Number(text))

// Keep unfinished text until it is corrected. Drafts may update a local editor
// as the user types; commitOnBlur sends a valid edit only on Enter or blur.
export default function CurrencyInput({ value, onChange, onValidityChange, commitOnBlur = false, ...props }) {
  const [text, setText] = useState(() => textFor(value))
  const [invalid, setInvalid] = useState(false)
  const dirty = useRef(false)
  const errorId = useId()

  useEffect(() => {
    if (!dirty.current && !invalid) setText(textFor(value))
  }, [value, invalid])

  return (
    <>
    <input
      {...props}
      type="text"
      pattern="[0-9]+([.][0-9]{0,2})?"
      inputMode="decimal"
      value={text}
      aria-invalid={invalid || undefined}
      aria-describedby={[props['aria-describedby'], invalid ? errorId : null].filter(Boolean).join(' ') || undefined}
      onChange={event => {
        const next = event.target.value
        dirty.current = true
        setText(next)
        const valid = validAmount(next)
        setInvalid(!valid)
        onValidityChange?.(valid)
        if (valid && !commitOnBlur) onChange(Number(next))
      }}
      onBlur={() => {
        if (!validAmount(text)) return
        if (commitOnBlur && dirty.current && Number(text) !== value) onChange(Number(text))
        dirty.current = false
        setText(textFor(value))
      }}
      onKeyDown={event => {
        if (event.key === 'Enter') {
          event.preventDefault()
          event.currentTarget.blur()
        }
      }}
    />
    {invalid && <p id={errorId} role="status">Enter a nonnegative amount with at most two decimal places.</p>}
    </>
  )
}
