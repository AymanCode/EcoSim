import { render } from '@testing-library/react'
import { describe, expect, test } from 'vitest'
import Meter from './Meter.jsx'; import CompositionBar from './CompositionBar.jsx'; import Radar from './Radar.jsx'; import Ledger from './Ledger.jsx'

describe('small charts', () => {
  test('Meter fills to the value in the zone tone', () => {
    const { container } = render(<Meter value={52} zones={[45, 70]} />)
    const fill = container.querySelector('.meter .fill'); expect(fill.style.width).toBe('52%'); expect(fill.style.background).toContain('--warn'); expect(container.querySelectorAll('.meter .z').length).toBe(2)
  })
  test('CompositionBar widths sum to 100', () => {
    const { container } = render(<CompositionBar segments={[{ label: 'Bottom 50%', value: 6.7, tone: 'ink4' }, { label: 'Middle 40%', value: 46.5, tone: 's1' }, { label: 'Top 10%', value: 46.8, tone: 'acc' }]} />)
    const w = [...container.querySelectorAll('.stack > div')].map(d => parseFloat(d.style.width)); expect(w.reduce((a, b) => a + b)).toBeCloseTo(100, 0)
  })
  test('Radar draws one vertex per dimension', () => {
    const dims = ['Health', 'Happiness', 'Morale', 'Skills', 'Food', 'Housing', 'Healthcare'].map(label => ({ label, value: 0.6 }))
    const { container } = render(<Radar dims={dims} median={dims.map(() => 0.5)} />)
    expect(container.querySelectorAll('circle').length).toBe(dims.length * 2); expect(container.textContent).toContain('Happiness')
  })
  test('Ledger scales rows to the largest and colours the net', () => {
    const { container } = render(<Ledger rows={[{ label: 'Revenue', value: 48200, tone: 'acc', sign: '+' }, { label: 'Transfers', value: 12100, tone: 's1', sign: '−' }]} net={{ label: 'Net flow', value: 28700 }} format={v => `$${Math.round(v / 1000)}K`} />)
    const fills = container.querySelectorAll('.lr .fl'); expect(fills[0].style.width).toBe('100%'); expect(container.querySelector('.lr.net .nv').style.color).toContain('--good')
  })
})
