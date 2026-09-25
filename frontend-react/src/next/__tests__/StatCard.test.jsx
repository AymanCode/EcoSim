import { describe, expect, test } from 'vitest'
import { render, screen } from '@testing-library/react'
import StatCard from '../components/StatCard.jsx'
import { METRICS } from '../catalog.js'
import { fixtureArm, TOWN_A, TOWN_B } from './fixture.js'

describe('StatCard', () => {
  test('shows the catalog name, one value per town, sparklines and the meaning', () => {
    const b = fixtureArm(TOWN_B)
    b.series.peopleOutOfWorkPer100 = b.series.peopleOutOfWorkPer100.map(v => v + 3)
    const { container } = render(<StatCard metricKey="peopleOutOfWorkPer100" arms={[fixtureArm(TOWN_A), b]} tick={11} />)
    expect(screen.getByRole('heading', { name: 'People out of work' })).toBeInTheDocument()
    const values = container.querySelectorAll('.nx-pv')
    expect(values).toHaveLength(2)
    expect(values[0]).toHaveTextContent('42 in 100')
    expect(values[0]).toHaveTextContent('Town A')
    expect(values[1]).toHaveTextContent('45 in 100')
    expect(values[1]).toHaveTextContent('Town B')
    expect(container.querySelectorAll('.nx-mini path')).toHaveLength(2)
    expect(screen.getByText(METRICS.peopleOutOfWorkPer100.meaning)).toBeInTheDocument()
  })

  test('says "not measured" when a town has no value yet', () => {
    const { container } = render(<StatCard metricKey="bankDefaultsTotal" arms={[fixtureArm()]} tick={5} />)
    expect(container.querySelector('.nx-pv')).toHaveTextContent('not measured')
    expect(container.querySelectorAll('.nx-mini path')).toHaveLength(0)
  })
})
