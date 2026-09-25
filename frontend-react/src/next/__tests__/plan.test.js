import { describe, expect, test } from 'vitest'
import {
  HOUSEHOLD_STEP, TOWN_LABELS, YEARS, estimatePhrase, estimateSeconds, householdCap, policyChanges, rollSeed, setupConfigs,
} from '../live/plan.js'
import { newExperimentId, ownerId, resolveSocketUrl } from '../live/endpoint.js'
import { DEFAULT_POLICY, LEVER_OPTIONS, LEVERS } from '../catalog.js'
import { isFrame, parseSession } from '../data/session.js'
import { FIXTURE_TEXT } from './fixture.js'

describe('the default policy and the lever options', () => {
  test('DEFAULT_POLICY is the tick-1 governmentPolicy of a town with no changes', () => {
    const { header, messages } = parseSession(FIXTURE_TEXT)
    expect(header.setup.initial_policy).toEqual({})
    const first = messages.find(isFrame)
    expect(first.tick).toBe(1)
    expect(DEFAULT_POLICY).toEqual(first.metrics.governmentPolicy)
  })

  test('both cover exactly the 17 levers, and every default is an allowed value', () => {
    const levers = Object.keys(LEVERS).sort()
    expect(levers).toHaveLength(17)
    expect(Object.keys(DEFAULT_POLICY).sort()).toEqual(levers)
    expect(Object.keys(LEVER_OPTIONS).sort()).toEqual(levers)
    for (const [lever, value] of Object.entries(DEFAULT_POLICY)) {
      const options = LEVER_OPTIONS[lever]
      if (Array.isArray(options)) expect(options).toContain(value)
      else expect(value >= options.min && value <= options.max).toBe(true)
    }
  })

  test('numbers stay numbers and the display order is kept', () => {
    expect(LEVER_OPTIONS.sector_subsidy_level).toEqual([0, 10, 25, 50])
    expect(LEVER_OPTIONS.bailout_budget).toEqual([0, 5000, 10000, 25000, 50000])
    expect(LEVER_OPTIONS.wage_tax_rate).toEqual({ min: 0, max: 0.5 })
    expect(LEVER_OPTIONS.investment_tax_rate).toEqual({ min: 0, max: 0.3 })
    expect(LEVER_OPTIONS.public_works).toEqual(['off', 'on'])
    expect(LEVER_OPTIONS.sector_subsidy_target).toEqual(['none', 'food', 'housing', 'services', 'healthcare'])
    expect(LEVER_OPTIONS.price_stabilization_target).toEqual(['none', 'food', 'services', 'healthcare'])
  })
})

describe('plan', () => {
  test('constants', () => {
    expect(TOWN_LABELS).toEqual(['Town A', 'Town B', 'Town C', 'Town D'])
    expect(YEARS).toEqual([1, 2, 5, 10])
    expect(HOUSEHOLD_STEP).toBe(100)
  })

  test('householdCap splits 10,000 households in steps of 100', () => {
    expect([1, 2, 3, 4].map(householdCap)).toEqual([10000, 5000, 3300, 2500])
  })

  test('estimates the wall-clock time from the frame benchmark', () => {
    expect(estimateSeconds({ households: 1000, towns: 2, years: 5 })).toBeCloseTo(51.6, 6)
    expect(estimatePhrase(estimateSeconds({ households: 1000, towns: 2, years: 5 }))).toBe('About a minute.')
    expect(estimatePhrase(estimateSeconds({ households: 500, towns: 1, years: 1 }))).toBe('Under a minute.')
    expect(estimateSeconds({ households: 2500, towns: 4, years: 10 })).toBeCloseTo(516, 6)
    expect(estimatePhrase(estimateSeconds({ households: 2500, towns: 4, years: 10 }))).toBe('About 9 minutes.')
    expect(estimatePhrase(39.9)).toBe('Under a minute.')
    expect(estimatePhrase(40)).toBe('About a minute.')
    expect(estimatePhrase(90)).toBe('About 2 minutes.')
  })

  test('rollSeed gives an integer from 1 to 99999', () => {
    expect(rollSeed(() => 0)).toBe(1)
    expect(rollSeed(() => 0.9999999)).toBe(99999)
    const seed = rollSeed()
    expect(Number.isInteger(seed) && seed >= 1 && seed <= 99999).toBe(true)
  })

  test('policyChanges keeps only the levers that differ from the default', () => {
    expect(policyChanges({ ...DEFAULT_POLICY, minimum_wage_policy: 'high' })).toEqual({ minimum_wage_policy: 'high' })
    expect(policyChanges(DEFAULT_POLICY)).toEqual({})
    expect(policyChanges({ ...DEFAULT_POLICY, wage_tax_rate: 0.1 + 0.05, sector_subsidy_level: 25, sector_subsidy_target: 'food' }))
      .toEqual({ sector_subsidy_target: 'food', sector_subsidy_level: 25 })
    expect(policyChanges({ ...DEFAULT_POLICY, profit_tax_rate: 0.25 })).toEqual({ profit_tax_rate: 0.25 })
  })

  test('setupConfigs gives one lean SETUP config per town, in order', () => {
    const plan = {
      mode: 'compare', questionId: 'minimum-wage', households: 1000, years: 5, seed: 48213,
      towns: [
        { label: 'Town A', color: '#2E6FE0', policy: { ...DEFAULT_POLICY } },
        { label: 'Town B', color: '#E0762C', policy: { ...DEFAULT_POLICY, minimum_wage_policy: 'high' } },
      ],
    }
    const shared = {
      num_households: 1000, seed: 48213, horizon_ticks: 260, frame_profile: 'lean', enable_llm_government: false,
      experiment_id: 'exp-1', arm_count: 2, experiment_owner: 'owner-1',
    }
    expect(setupConfigs(plan, { experimentId: 'exp-1', owner: 'owner-1' })).toEqual([
      { ...shared, initial_policy: {}, arm_label: 'Town A' },
      { ...shared, initial_policy: { minimum_wage_policy: 'high' }, arm_label: 'Town B' },
    ])
  })
})

describe('endpoint', () => {
  test('newExperimentId joins the time and six random base-36 digits', () => {
    expect(newExperimentId(0, () => 0.5)).toBe('exp-0-i00000')
    expect(newExperimentId(36, () => 0)).toBe('exp-10-000000')
    expect(newExperimentId()).toMatch(/^exp-[0-9a-z]+-[0-9a-z]{6}$/)
  })

  test('resolveSocketUrl prefers VITE_WS_URL, then the page host, then localhost', () => {
    expect(resolveSocketUrl({ VITE_WS_URL: '  ws://example.test:9000/ws  ' }, { protocol: 'https:', host: 'x' })).toBe('ws://example.test:9000/ws')
    expect(resolveSocketUrl({ VITE_WS_URL: '   ' }, { protocol: 'https:', host: 'eco.test' })).toBe('wss://eco.test/ws')
    expect(resolveSocketUrl({}, { protocol: 'http:', host: 'localhost:5173' })).toBe('ws://localhost:5173/ws')
    expect(resolveSocketUrl({}, null)).toBe('ws://localhost:8002/ws')
    expect(resolveSocketUrl({}, { protocol: 'file:', host: '' })).toBe('ws://localhost:8002/ws')
    // The defaults read Vite's env and the page's location.
    expect(resolveSocketUrl()).toBe(resolveSocketUrl(import.meta.env, window.location))
  })

  test('ownerId is stable for the tab and short enough for the server', () => {
    const owner = ownerId()
    expect(owner).toBe(ownerId())
    expect(owner.length).toBeGreaterThan(0)
    expect(owner.length).toBeLessThanOrEqual(64)
    expect(sessionStorage.getItem('ecosim-owner')).toBe(owner)
  })
})
