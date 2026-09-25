import { describe, expect, test } from 'vitest'
import { render, screen } from '@testing-library/react'
import HowToRead from '../components/HowToRead.jsx'

describe('HowToRead', () => {
  test('four first-timer notes for two towns', () => {
    const { container } = render(<HowToRead armCount={2} />)
    expect(screen.getByRole('heading', { name: /How to read this/ })).toBeInTheDocument()
    expect(container.querySelectorAll('li')).toHaveLength(4)
    expect(container).toHaveTextContent('Both towns')
    expect(container.querySelector('li b')).toHaveTextContent('tick')
  })

  test('adapted for one town', () => {
    const { container } = render(<HowToRead armCount={1} />)
    expect(container.querySelectorAll('li')).toHaveLength(4)
    expect(container).not.toHaveTextContent('Both towns')
  })
})
