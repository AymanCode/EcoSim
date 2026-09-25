import { afterEach, describe, expect, test, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import NextApp from '../NextApp.jsx'
import { FIXTURE_TEXT } from './fixture.js'

// The same recording twice, the second with a higher minimum wage in its header.
const TOWN_B_TEXT = FIXTURE_TEXT.replace('"initial_policy": {}', '"initial_policy": {"minimum_wage_policy": "high"}')

function serve(files) {
  return vi.fn(async url => {
    const name = String(url).split('/').pop()
    if (!(name in files)) return { ok: false, status: 404, text: async () => '' }
    return { ok: true, status: 200, text: async () => files[name] }
  })
}

afterEach(() => vi.unstubAllGlobals())

describe('NextApp', () => {
  test('loads the two demo towns and asks the experiment question', async () => {
    const fetch = serve({ 'town-a.jsonl': FIXTURE_TEXT, 'town-b.jsonl': TOWN_B_TEXT })
    vi.stubGlobal('fetch', fetch)
    const { container } = render(<NextApp />)
    expect(screen.getByText('Loading the demo towns…')).toBeInTheDocument()
    expect(await screen.findByText('What happens with a higher minimum wage?')).toBeInTheDocument()
    expect(container.firstChild).toHaveClass('nx')
    expect(fetch.mock.calls.map(([url]) => String(url))).toEqual(['/demo/town-a.jsonl', '/demo/town-b.jsonl'])
    expect(screen.getByText('EcoSim')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Classic dashboard' })).toHaveAttribute('href', '?view=classic')
    expect(container.querySelectorAll('.nx-col')).toHaveLength(2)
  })

  test('explains how to fix missing demo data', async () => {
    vi.stubGlobal('fetch', serve({ 'town-a.jsonl': FIXTURE_TEXT }))
    render(<NextApp />)
    expect(await screen.findByText(
      'Demo data missing: run the recorder commands in docs/superpowers/plans/2026-09-25-frontend-redesign-phase2-slice1.md',
    )).toBeInTheDocument()
  })

  test('treats a page that is not a recording as missing data', async () => {
    vi.stubGlobal('fetch', serve({ 'town-a.jsonl': '<!doctype html>', 'town-b.jsonl': '<!doctype html>' }))
    render(<NextApp />)
    expect(await screen.findByText(/^Demo data missing/)).toBeInTheDocument()
  })
})
