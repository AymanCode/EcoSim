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
    expect(container.querySelectorAll('.nx-mini path:not(.is-warm)')).toHaveLength(2)
    expect(screen.getByText(METRICS.peopleOutOfWorkPer100.meaning)).toBeInTheDocument()
  })

  test('the warm-up weeks sit in a band labelled "setting up", with the line dashed there', () => {
    const { container } = render(<StatCard metricKey="peopleOutOfWorkPer100" arms={[fixtureArm(TOWN_A), fixtureArm(TOWN_B)]} tick={24} />)
    const band = container.querySelector('.nx-mini-warm')
    expect(band).toHaveTextContent('setting up')
    const width = parseFloat(band.style.width)
    expect(width).toBeGreaterThan(30)
    expect(width).toBeLessThan(50)
    expect(container.querySelectorAll('.nx-mini path.is-warm')).toHaveLength(2)
    expect(container.querySelectorAll('.nx-mini path:not(.is-warm)')).toHaveLength(2)
  })

  test('the sparkline scale leaves out the warm-up weeks', () => {
    const arm = fixtureArm(TOWN_A)
    arm.series.peopleOutOfWorkPer100 = arm.series.peopleOutOfWorkPer100.map((v, i) => (arm.ticks[i] <= 10 ? 1000 : v))
    const { container } = render(<StatCard metricKey="peopleOutOfWorkPer100" arms={[arm]} tick={24} />)
    const live = container.querySelector('.nx-mini path:not(.is-warm)').getAttribute('d')
    const ys = live.split(/[ML]/).filter(Boolean).map(pair => Number(pair.trim().split(' ')[1]))
    // Without the warm-up spike the real weeks use the full height.
    expect(Math.max(...ys) - Math.min(...ys)).toBeGreaterThan(20)
  })

  test('says "not measured" when a town has no value yet', () => {
    const { container } = render(<StatCard metricKey="bankDefaultsTotal" arms={[fixtureArm()]} tick={5} />)
    expect(container.querySelector('.nx-pv')).toHaveTextContent('not measured')
    expect(container.querySelectorAll('.nx-mini path')).toHaveLength(0)
  })
})
