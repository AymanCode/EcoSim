import fs from 'node:fs'
import { describe, expect, test, vi } from 'vitest'
import { fireEvent, render, screen, within } from '@testing-library/react'
import HorizonBar from '../components/HorizonBar.jsx'

// See fixture.js: keep import.meta.url in a variable so Vite leaves it a file: URL.
const here = import.meta.url
const CSS = fs.readFileSync(new URL('../next.css', here), 'utf8')

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

  test('the bar wraps at every width, and ends before the Town hall drawer', () => {
    // jsdom does no layout, so the guard is the stylesheet.
    const style = document.createElement('style')
    style.textContent = CSS
    document.head.appendChild(style)
    try {
      const rules = [...style.sheet.cssRules]
      const top = rules.filter(rule => rule.selectorText)
      const inMedia = text => rules.filter(rule => rule.media?.mediaText.replace(/\s+/g, ' ').includes(text)).flatMap(rule => [...rule.cssRules])
      const bar = top.find(rule => rule.selectorText === '.nx .nx-hbar-in')
      expect(bar.style.getPropertyValue('flex-wrap')).toBe('wrap')
      expect(bar.style.getPropertyValue('gap')).toBe('10px 20px')
      // The scrubber keeps a usable width when the controls wrap round it.
      const scrubber = top.find(rule => rule.selectorText === '.nx .nx-scrubber')
      expect(scrubber.style.getPropertyValue('min-width')).toBe('160px')
      // At 1100px and up the app makes room for the drawer; narrower, the bar does.
      expect(inMedia('(min-width: 1100px)').find(rule => rule.selectorText === '.nx.nx-app.has-hall').style.getPropertyValue('padding-right')).toBe('380px')
      const narrow = inMedia('(min-width: 721px) and (max-width: 1099px)').find(rule => rule.selectorText === '.nx.nx-app.has-hall .nx-hbar')
      expect(narrow.style.getPropertyValue('padding-right')).toBe('380px')
      expect(top.find(rule => rule.selectorText === '.nx .nx-hall').style.getPropertyValue('width')).toBe('380px')
    } finally {
      style.remove()
    }
  })
})
