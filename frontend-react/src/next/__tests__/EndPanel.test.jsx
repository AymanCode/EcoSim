import { describe, expect, test, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import EndPanel from '../components/EndPanel.jsx'
import LostPanel from '../components/LostPanel.jsx'
import { verdict } from '../narration.js'
import { fixtureArm, TOWN_A, TOWN_B } from './fixture.js'

function end(props = {}) {
  const onExtend = vi.fn()
  const onNewExperiment = vi.fn()
  const arms = [fixtureArm(TOWN_A), fixtureArm(TOWN_B)]
  const view = render(
    <EndPanel phase="horizon" horizon={260} arms={arms} tick={24} onExtend={onExtend} onNewExperiment={onNewExperiment} {...props} />,
  )
  return { ...view, arms, onExtend, onNewExperiment }
}

describe('EndPanel', () => {
  test('says the years are up and gives the verdict for the latest week', () => {
    const { arms, container } = end()
    expect(screen.getByRole('heading', { name: '5 years are up.' })).toBeInTheDocument()
    expect(container).toHaveTextContent(verdict(arms, 24))
  })

  test('"Add a year" waits for the run to finish, then asks for 52 more weeks', () => {
    const { onExtend, onNewExperiment, rerender, arms } = end()
    expect(screen.getByRole('button', { name: 'Add a year' })).toBeDisabled()
    expect(screen.getByRole('status')).toHaveTextContent('Wrapping up the run…')
    rerender(<EndPanel phase="finished" horizon={260} arms={arms} tick={24} onExtend={onExtend} onNewExperiment={onNewExperiment} />)
    expect(screen.queryByRole('status')).toBeNull()
    const add = screen.getByRole('button', { name: 'Add a year' })
    expect(add).toBeEnabled()
    fireEvent.click(add)
    expect(onExtend).toHaveBeenCalledWith(52)
    fireEvent.click(screen.getByRole('button', { name: 'Try another question' }))
    expect(onNewExperiment).toHaveBeenCalledTimes(1)
  })

  test('one year reads in the singular', () => {
    end({ horizon: 52 })
    expect(screen.getByRole('heading', { name: '1 year is up.' })).toBeInTheDocument()
  })

  test('while the viewer looks back at an earlier week it folds to a bar: no verdict, a way back, a year more', () => {
    const onFollow = vi.fn()
    const { arms, container, onExtend } = end({ phase: 'finished', following: false, onFollow })
    expect(screen.getByRole('heading', { name: '5 years are up.' })).toBeInTheDocument()
    expect(container).not.toHaveTextContent(verdict(arms, 24))
    expect(screen.queryByRole('button', { name: 'Try another question' })).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Back to the end' }))
    expect(onFollow).toHaveBeenCalledTimes(1)
    fireEvent.click(screen.getByRole('button', { name: 'Add a year' }))
    expect(onExtend).toHaveBeenCalledWith(52)
  })
})

describe('LostPanel', () => {
  test('names the town and the week, and offers a restart or a new set up', () => {
    const onRestart = vi.fn()
    const onNewExperiment = vi.fn()
    render(<LostPanel town="Town B" tick={60} townCount={2} onRestart={onRestart} onNewExperiment={onNewExperiment} />)
    expect(screen.getByRole('alert')).toHaveTextContent(
      'Town B lost its connection to the simulation in Year 2, week 8. The other towns are paused.',
    )
    fireEvent.click(screen.getByRole('button', { name: 'Start these towns again' }))
    expect(onRestart).toHaveBeenCalledTimes(1)
    fireEvent.click(screen.getByRole('button', { name: 'Set up something new' }))
    expect(onNewExperiment).toHaveBeenCalledTimes(1)
  })

  test('a town the server stopped with an error says so, with the server\'s words behind "Details:"', () => {
    render(<LostPanel town="Town B" tick={60} townCount={2} crashed detail="float division by zero" onRestart={() => {}} onNewExperiment={() => {}} />)
    expect(screen.getByRole('alert')).toHaveTextContent(
      'Town B stopped because the simulation hit an error in Year 2, week 8. The other towns are paused.',
    )
    expect(screen.getByRole('alert')).not.toHaveTextContent('float division')
    expect(screen.getByText('Details: float division by zero')).toBeInTheDocument()
  })

  test('after the town hall changed rules, the restart says those changes are not repeated', () => {
    const { rerender } = render(<LostPanel town="Town B" tick={60} townCount={2} onRestart={() => {}} onNewExperiment={() => {}} />)
    expect(screen.queryByText(/will not be repeated/)).toBeNull()
    rerender(<LostPanel town="Town B" tick={60} townCount={2} rulesChanged onRestart={() => {}} onNewExperiment={() => {}} />)
    expect(screen.getByText('Starting again uses the rules you set up. Your rule changes will not be repeated.')).toBeInTheDocument()
  })

  test('a single town, lost before its first week', () => {
    render(<LostPanel town="Town A" tick={0} townCount={1} onRestart={() => {}} onNewExperiment={() => {}} />)
    expect(screen.getByRole('alert')).toHaveTextContent('Town A lost its connection to the simulation before its first week.')
    expect(screen.getByRole('alert')).not.toHaveTextContent('other towns')
    expect(screen.getByRole('button', { name: 'Start this town again' })).toBeInTheDocument()
  })
})
