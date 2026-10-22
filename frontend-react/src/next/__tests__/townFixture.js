import { createArm, ingest } from '../data/session.js'

// Small hand-made towns for the town model and card tests: one frame per week
// through `ingest`, so a late or repeated week behaves exactly as it does live.
export const firm = (id, extra = {}) => ({
  id, name: `Shop ${id}`, sector: 'Food', cash: 1000, staff: 10, state: 'steady', isBaseline: false, ...extra,
})

export const subject = (id, extra = {}) => ({
  id, age: 40, isEmployed: false, canWork: true, housingSecurity: true, employer: null, employerCategory: null, wage: 0,
  cash: 100, rentArrears: 0, unemploymentDuration: 0, health: 0.8, happiness: 0.5, ...extra,
})

export const frame = (tick, { firms = [], closed = [], subjects = [], curated = {} } = {}) => ({
  tick, metrics: { trackedSubjects: subjects }, curated, firms, firmsClosed: closed, events: [],
})

// weeks: [[tick, { firms, closed, subjects, curated }], ...] in arrival order.
export function liveArm(weeks) {
  const arm = createArm({ label: 'Town', color: '#000' })
  for (const [tick, week] of weeks) ingest(arm, frame(tick, week))
  return arm
}

// The same arm with nothing cached against it: the answer to compare a live one with.
export const freshCopy = arm => ({ ...arm, ticks: [...arm.ticks] })
