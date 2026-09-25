import { describe, expect, test, vi } from 'vitest'
import { fireEvent, render, screen, within } from '@testing-library/react'
import HorizonBar from '../components/HorizonBar.jsx'

function bar(props = {}) {
  const handlers = { onToggle: vi.fn(), onScrub: vi.fn(), onSpeed: vi.fn() }
  const view = render(<HorizonBar tick={20} horizon={104} maxTick={104} playing={false} speed={1} {...handlers} {...props} />)
  return { ...view, ...handlers }
}

describe('HorizonBar', () => {
  test('a labelled slider over the recorded weeks', () => {
    const { onScrub } = bar()
    const slider = screen.getByRole('slider', { name: 'Week of the run' })
    expect(slider).toHaveAttribute('min', '1')
    expect(slider).toHaveAttribute('max', '104')
    expect(slider).toHaveValue('20')
    expect(slider).toHaveAttribute('aria-valuetext', 'Year 1, week 20')
    fireEvent.change(slider, { target: { value: '60' } })
    expect(onScrub).toHaveBeenCalledWith(60)
  })

  test('shows the week, the length of the run and the year marks', () => {
    const { container } = bar({ tick: 60 })
    expect(container.querySelector('.nx-week')).toHaveTextContent('Year 2, week 8')
    expect(screen.getByText('of 2 years')).toBeInTheDocument()
    expect([...container.querySelectorAll('.nx-marks span')].map(mark => mark.textContent)).toEqual(['Year 1', 'Year 2'])
  })

  test('play and pause', () => {
    const { onToggle, rerender } = bar()
    fireEvent.click(screen.getByRole('button', { name: 'Play' }))
    expect(onToggle).toHaveBeenCalledTimes(1)
    rerender(<HorizonBar tick={20} horizon={104} maxTick={104} playing speed={1} onToggle={onToggle} onScrub={() => {}} onSpeed={() => {}} />)
    expect(screen.getByRole('button', { name: 'Pause' })).toBeInTheDocument()
    rerender(<HorizonBar tick={104} horizon={104} maxTick={104} playing={false} speed={1} onToggle={onToggle} onScrub={() => {}} onSpeed={() => {}} />)
    expect(screen.getByRole('button', { name: 'Play again' })).toBeInTheDocument()
  })

  test('speed buttons', () => {
    const { onSpeed } = bar()
    const group = screen.getByRole('group', { name: 'Speed' })
    const buttons = within(group).getAllByRole('button')
    expect(buttons.map(button => button.textContent)).toEqual(['0.5×', '1×', '2×', '4×'])
    expect(within(group).getByRole('button', { name: 'Play at 1× speed' })).toHaveAttribute('aria-pressed', 'true')
    fireEvent.click(within(group).getByRole('button', { name: 'Play at 4× speed' }))
    expect(onSpeed).toHaveBeenCalledWith(4)
  })
})
