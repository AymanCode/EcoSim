// The experiment plan the Set up screen builds, and the SETUP configs it becomes.
// Pure functions only: no sockets, no React.
//
// Plan = { mode: 'compare'|'play', questionId: string|null,
//          towns: [{ label, color, policy /* all 17 levers */ }], households, years, seed }
import { COPY, DEFAULT_POLICY } from '../catalog.js'

export const TOWN_LABELS = ['Town A', 'Town B', 'Town C', 'Town D']
export const YEARS = [1, 2, 5, 10]
export const HOUSEHOLD_STEP = 100

const TOTAL_HOUSEHOLDS = 10000
const WEEKS_PER_YEAR = 52

// Households per town: the server splits 10,000 evenly (10000 // arm_count),
// rounded down to the slider's step. 1 -> 10000, 2 -> 5000, 3 -> 3300, 4 -> 2500.
export function householdCap(townCount) {
  const towns = Math.min(TOWN_LABELS.length, Math.max(1, Math.floor(Number(townCount)) || 1))
  return Math.floor(TOTAL_HOUSEHOLDS / towns / HOUSEHOLD_STEP) * HOUSEHOLD_STEP
}

// Wall-clock seconds, scaled from the frame benchmark: two towns of 1,000
// households over 260 weeks took 51.6 s. Towns share one server thread, so the
// cost grows with every household in every town and with every week.
const BENCH_SECONDS = 51.6
const BENCH_HOUSEHOLDS = 2 * 1000
const BENCH_WEEKS = 260

export function estimateSeconds({ households, towns, years }) {
  return BENCH_SECONDS * ((households * towns) / BENCH_HOUSEHOLDS) * ((years * WEEKS_PER_YEAR) / BENCH_WEEKS)
}

export function estimatePhrase(seconds) {
  if (seconds < 40) return COPY.estimate.underMinute
  if (seconds < 90) return COPY.estimate.aboutMinute
  return COPY.estimate.minutes(Math.round(seconds / 60))
}

// A town number from 1 to 99999.
export function rollSeed(random = Math.random) {
  return 1 + Math.floor(random() * 99999)
}

// Rates that differ only by float noise (0.1 + 0.05) count as unchanged.
const same = (a, b) => (typeof a === 'number' && typeof b === 'number' ? Math.abs(a - b) < 1e-9 : a === b)

// The levers whose value differs from DEFAULT_POLICY: the SETUP `initial_policy`.
export function policyChanges(vector) {
  const changes = {}
  for (const [lever, value] of Object.entries(vector ?? {})) {
    if (value !== undefined && !same(value, DEFAULT_POLICY[lever])) changes[lever] = value
  }
  return changes
}

// One SETUP config per town, in town order. Every town shares the world
// (households, seed, horizon); only its rules differ.
export function setupConfigs(plan, { experimentId, owner }) {
  return plan.towns.map(town => ({
    num_households: plan.households,
    seed: plan.seed,
    horizon_ticks: plan.years * WEEKS_PER_YEAR,
    initial_policy: policyChanges(town.policy),
    frame_profile: 'lean',
    enable_llm_government: false,
    experiment_id: experimentId,
    arm_label: town.label,
    arm_count: plan.towns.length,
    experiment_owner: owner,
  }))
}
