// The Set up screen's state and the Plan it builds (live/plan.js). NextApp owns
// this hook so the plan survives a trip to the Run screen and back.
//
// state: { mode: 'compare'|'play', questionId: 'minimum-wage'|'benefits'|'custom'|null,
//          towns: [{ label, color, policy /* all 17 levers */ }], households, years, seed,
//          editing: index of the town whose rules are open, or null }
import { useMemo, useReducer } from 'react'
import { DEFAULT_POLICY, QUESTIONS, TOWN_COLORS } from '../catalog.js'
import { HOUSEHOLD_STEP, TOWN_LABELS, YEARS, householdCap, rollSeed } from '../live/plan.js'

const MAX_SEED = 2147483647
const DEFAULT_QUESTION = 'minimum-wage'
const MIN_COMPARE_TOWNS = 2

// Labels and colours follow the towns' order.
const inOrder = policies => policies.map((policy, i) => ({ label: TOWN_LABELS[i], color: TOWN_COLORS[i], policy }))

function questionTowns(id) {
  const question = QUESTIONS.find(q => q.id === id)
  return question ? inOrder(question.towns.map(levers => ({ ...DEFAULT_POLICY, ...levers }))) : null
}

// Households per town: a multiple of the step, from one step to the cap for this many towns.
function fitHouseholds(value, townCount) {
  const stepped = Math.round(value / HOUSEHOLD_STEP) * HOUSEHOLD_STEP
  return Math.min(householdCap(townCount), Math.max(HOUSEHOLD_STEP, stepped))
}

// A new set of towns: households clamp to the new cap, and the editor closes
// if its town is gone.
function withTowns(state, towns, editing = state.editing) {
  return {
    ...state,
    towns,
    households: fitHouseholds(state.households, towns.length),
    editing: editing != null && editing < towns.length ? editing : null,
  }
}

function init(random) {
  return {
    mode: 'compare',
    questionId: DEFAULT_QUESTION,
    towns: questionTowns(DEFAULT_QUESTION),
    households: 1000,
    years: 5,
    seed: rollSeed(random),
    editing: null,
  }
}

function reducer(state, action) {
  switch (action.type) {
    case 'mode': {
      if (action.mode === state.mode) return state
      if (action.mode === 'play') {
        return { ...withTowns(state, inOrder([DEFAULT_POLICY]), null), mode: 'play', questionId: null }
      }
      if (action.mode === 'compare') {
        return { ...withTowns(state, questionTowns(DEFAULT_QUESTION), null), mode: 'compare', questionId: DEFAULT_QUESTION }
      }
      return state
    }
    case 'question': {
      if (state.mode !== 'compare') return state
      if (action.id === 'custom') return { ...state, questionId: 'custom' }
      const towns = questionTowns(action.id)
      return towns ? { ...withTowns(state, towns, null), questionId: action.id } : state
    }
    case 'add': {
      if (state.mode !== 'compare' || state.towns.length >= TOWN_LABELS.length) return state
      return withTowns(state, inOrder([...state.towns.map(town => town.policy), { ...state.towns[0].policy }]))
    }
    case 'remove': {
      const min = state.mode === 'compare' ? MIN_COMPARE_TOWNS : 1
      const { index } = action
      if (state.towns.length <= min || !(index >= 0 && index < state.towns.length)) return state
      const left = state.towns.filter((_, i) => i !== index).map(town => town.policy)
      const editing = state.editing == null || state.editing === index ? null : state.editing - (state.editing > index ? 1 : 0)
      return withTowns(state, inOrder(left), editing)
    }
    case 'edit':
      return action.index >= 0 && action.index < state.towns.length ? { ...state, editing: action.index } : state
    case 'close':
      return { ...state, editing: null }
    case 'policy': {
      const { index, policy } = action
      if (!(index >= 0 && index < state.towns.length)) return state
      const towns = state.towns.map((town, i) => (i === index ? { ...town, policy: { ...DEFAULT_POLICY, ...policy } } : town))
      return { ...state, towns, questionId: state.mode === 'compare' ? 'custom' : state.questionId }
    }
    case 'households': {
      const value = Number(action.value)
      return Number.isFinite(value) ? { ...state, households: fitHouseholds(value, state.towns.length) } : state
    }
    case 'years':
      return YEARS.includes(action.years) ? { ...state, years: action.years } : state
    case 'seed': {
      const value = Math.floor(Number(action.seed))
      if (!Number.isFinite(value)) return state
      const seed = Math.min(MAX_SEED, Math.max(0, value))
      // A reroll that lands on the same town moves one along, so the button always changes it.
      if (action.different && seed === state.seed) return { ...state, seed: (seed % MAX_SEED) + 1 }
      return { ...state, seed }
    }
    default:
      return state
  }
}

export default function useSetup({ random = Math.random } = {}) {
  const [state, dispatch] = useReducer(reducer, random, init)

  const actions = useMemo(() => ({
    setMode: mode => dispatch({ type: 'mode', mode }),
    pickQuestion: id => dispatch({ type: 'question', id }),
    addTown: () => dispatch({ type: 'add' }),
    removeTown: index => dispatch({ type: 'remove', index }),
    editTown: index => dispatch({ type: 'edit', index }),
    closeEditor: () => dispatch({ type: 'close' }),
    setTownPolicy: (index, policy) => dispatch({ type: 'policy', index, policy }),
    setHouseholds: value => dispatch({ type: 'households', value }),
    setYears: years => dispatch({ type: 'years', years }),
    rerollSeed: () => dispatch({ type: 'seed', seed: rollSeed(random), different: true }),
    setSeed: seed => dispatch({ type: 'seed', seed }),
  }), [random])

  const plan = useMemo(() => ({
    mode: state.mode,
    questionId: state.questionId,
    towns: state.towns.map(({ label, color, policy }) => ({ label, color, policy })),
    households: state.households,
    years: state.years,
    seed: state.seed,
  }), [state.mode, state.questionId, state.towns, state.households, state.years, state.seed])

  return { state, actions, plan }
}
