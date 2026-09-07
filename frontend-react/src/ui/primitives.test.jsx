import { render, screen, fireEvent } from '@testing-library/react'
import { describe, expect, test, vi } from 'vitest'
import Pill from './Pill.jsx'; import Delta from './Delta.jsx'; import KeyValue from './KeyValue.jsx'; import { Slider, Toggle } from './Inputs.jsx'

describe('primitives', () => {
  test('Pill carries a tone class and a dot', () => { const { container } = render(<Pill tone="crit">Critical</Pill>); expect(container.querySelector('.pill.crit i')).toBeTruthy(); expect(screen.getByText('Critical')).toBeInTheDocument() })
  test('Delta direction follows upBad', () => {
    const { container, rerender } = render(<Delta diff={2} pct={3.2} unit="pct" />); expect(container.firstChild).toHaveClass('up'); expect(container.textContent).toBe('▲ 3.2%')
    rerender(<Delta diff={2} pct={3.2} unit="pct" upBad />); expect(container.firstChild).toHaveClass('down')
    rerender(<Delta diff={0} pct={0} unit="pts" />); expect(container.textContent).toBe('— 0.0 pts')
  })
  test('KeyValue renders label and value', () => { render(<KeyValue label="Bonds held" value="$750" />); expect(screen.getByText('Bonds held')).toBeInTheDocument(); expect(screen.getByText('$750')).toBeInTheDocument() })
  test('Slider reports numbers and Toggle flips', () => {
    const onChange = vi.fn(); render(<Slider label="Wage tax" value={0.15} min={0} max={0.5} step={0.01} format={v => `${(v*100).toFixed(0)}%`} onChange={onChange} />)
    fireEvent.change(screen.getByRole('slider'), { target: { value: '0.2' } }); expect(onChange).toHaveBeenCalledWith(0.2)
    const flip = vi.fn(); render(<Toggle label="AI government" checked={false} onChange={flip} />); fireEvent.click(screen.getByText('AI government')); expect(flip).toHaveBeenCalledWith(true)
  })
})
