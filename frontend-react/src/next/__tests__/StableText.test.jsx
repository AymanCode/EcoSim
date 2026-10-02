import { afterEach, describe, expect, test, vi } from 'vitest'
import { act, render } from '@testing-library/react'
import StableText from '../components/StableText.jsx'

// jsdom has no layout: fake each element's height from its text length (one
// line per 20 characters, 30 px a line) and its width from a variable.
let width = 400
function fakeLayout() {
  vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockImplementation(function rect() {
    const lines = Math.max(1, Math.ceil((this.textContent ?? '').length / (width / 20)))
    return { width, height: lines * 30, top: 0, left: 0, right: width, bottom: lines * 30, x: 0, y: 0, toJSON() {} }
  })
}
// Measurements of hidden copies (probes), told apart from the box by its data-stable.
const probeCalls = () => HTMLElement.prototype.getBoundingClientRect.mock.contexts
  .filter(element => !element.hasAttribute('data-stable')).length

// A stand-in for document.fonts: ready at once, and fires 'loadingdone' on demand.
function fakeFonts() {
  const fonts = new EventTarget()
  fonts.ready = Promise.resolve(fonts)
  Object.defineProperty(document, 'fonts', { value: fonts, configurable: true })
  return fonts
}
afterEach(() => {
  vi.restoreAllMocks()
  delete document.fonts
})

describe('StableText', () => {
  test('reserves the height of the longest candidate, not the current text', () => {
    width = 400
    fakeLayout()
    const texts = ['short', 'x'.repeat(70)] // 1 line and 4 lines at 20 chars a line
    const { container } = render(<StableText texts={texts} stable="lead">short</StableText>)
    const box = container.querySelector('[data-stable="lead"]')
    expect(box.style.minHeight).toBe('120px')
    expect(box).toHaveTextContent('short')
  })

  test('measures again when the candidates change', () => {
    width = 400
    fakeLayout()
    const { container, rerender } = render(<StableText texts={['a']} stable="v">a</StableText>)
    rerender(<StableText texts={['a', 'y'.repeat(50)]} stable="v">a</StableText>)
    expect(container.querySelector('[data-stable="v"]').style.minHeight).toBe('90px')
  })

  test('new candidates are measured alone; fonts loading measures them all again', async () => {
    width = 400
    fakeLayout()
    const fonts = fakeFonts()
    const { container, rerender } = render(<StableText texts={['a', 'b']} stable="v">a</StableText>)
    await act(async () => {})
    const settled = probeCalls()
    rerender(<StableText texts={['a', 'b', 'z'.repeat(50)]} stable="v">a</StableText>)
    await act(async () => {})
    expect(probeCalls() - settled).toBe(1)
    expect(container.querySelector('[data-stable="v"]').style.minHeight).toBe('90px')
    await act(async () => { fonts.dispatchEvent(new Event('loadingdone')) })
    expect(probeCalls() - settled).toBe(4)
  })
})
