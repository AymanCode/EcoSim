import { render, screen, fireEvent } from '@testing-library/react'
import { describe, expect, test, vi } from 'vitest'
import Rail from './Rail.jsx'; import TopBar from './TopBar.jsx'; import StatusStrip from './StatusStrip.jsx'

describe('shell', () => {
  test('rail disables non-config views until initialised', () => {
    const onSelect = vi.fn(); render(<Rail view="CONFIG" enabled={false} connected onSelect={onSelect} />)
    fireEvent.click(screen.getByText('Population')); expect(onSelect).not.toHaveBeenCalled()
    fireEvent.click(screen.getByText('Config')); expect(onSelect).toHaveBeenCalledWith('CONFIG')
  })
  test('top bar shows the tick and the run state', () => {
    render(<TopBar view="DASHBOARD" tick={262} running initialized connected onToggleRun={() => {}} onReset={() => {}} onToggleTheme={() => {}} />)
    expect(screen.getByText('00262')).toBeInTheDocument(); expect(screen.getByText('Running')).toBeInTheDocument(); expect(screen.getByText(/Suspend/)).toBeInTheDocument()
  })
  test('status strip stamps the last change with its own tick', () => {
    const { container } = render(
      <StatusStrip
        sessionId="d9b78c2e1234"
        metrics={{ tickComputeMs: 25, unemployment: 28.8 }}
        firmStats={{ total_firms: 30 }}
        population={1000}
        config={{ enableLlmGovernment: false }}
        tick={262}
        policyChanges={[{ tick: 96, policy: 'wageTax', value: 0.18, reason: 'User updated wageTax' }]}
      />
    )
    const lastChangeSpan = screen.getByText(/last change/).closest('span')
    expect(container.textContent).toContain('t96')
    expect(lastChangeSpan.textContent).toContain('t96')
    expect(lastChangeSpan.textContent).not.toContain('t262')
  })
})

