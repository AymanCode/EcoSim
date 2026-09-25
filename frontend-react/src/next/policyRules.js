// The lever group rules of backend/policy_vectors.py `policy_group_errors`,
// ported check for check and in the same order, so the Set up screen and the
// Town hall can stop a vector the server would refuse. Pure: no React.
import { COPY } from './catalog.js'

// Each problem group and the levers it ties together; the editor shows a
// problem under the section that holds these levers.
export const PROBLEM_LEVERS = {
  sector_subsidy: ['sector_subsidy_target', 'sector_subsidy_level'],
  bailout: ['bailout_policy', 'bailout_target', 'bailout_budget'],
}

// Python's dict.get(key, default).
const get = (vector, lever, fallback) => (Object.hasOwn(vector, lever) ? vector[lever] : fallback)

// The backend coerces the integer levers to numbers before these checks
// (validate_lever_value), so "0" is falsy there as 0 is.
const truthy = value => {
  if (typeof value === 'string' && value.trim() !== '' && Number.isFinite(Number(value))) return Number(value) !== 0
  return Boolean(value)
}

// { [group]: newcomer text } for every group rule the vector breaks, in checking order.
export function policyProblems(vector) {
  const levers = vector ?? {}
  const problems = {}
  if (truthy(get(levers, 'sector_subsidy_level', 0)) && get(levers, 'sector_subsidy_target', 'none') === 'none') {
    problems.sector_subsidy = COPY.levers.rules.sector_subsidy
  }
  if (get(levers, 'bailout_policy', 'off') !== 'off') {
    if (get(levers, 'bailout_target', 'none') === 'none') problems.bailout = COPY.levers.rules.bailout_target
    else if (!truthy(get(levers, 'bailout_budget', 0))) problems.bailout = COPY.levers.rules.bailout_budget
  }
  return problems
}
