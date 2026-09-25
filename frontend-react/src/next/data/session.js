// Turns frame-2 server messages, recorded (JSON Lines from
// scripts/record_session.py) or live, into one "arm" per town. A raw frame is
// never kept: `ingest` copies out what the Run screen reads and drops the rest.
//
// Kept per tick, because scrubbing goes back to any week:
//   - every `curated` figure, as one array per key (`series`, aligned to `ticks`);
//   - the open firms: id, name, sector, cash, staff, state, isBaseline;
//   - the tracked households: id, age, isEmployed, canWork, housingSecurity,
//     employer, employerCategory, wage, cash, rentArrears, unemploymentDuration;
//   - firms closed in the last year: id, name, sector, closedTick, lastStaff;
//   - the town-wide `eventCounts` (`eventCounts[tick]`).
// Kept across ticks: every event in tick order, the policy changes, a directory
// of every firm seen, the tracked households' profiles, the setup and the horizon.
// Kept as the latest value only: `policy`, the lever vector in force (the
// highest tick's `metrics.governmentPolicy`, null before any frame).
// Also kept: `receipts`, one per CONFIG in send order. A live client adds a
// 'sending' receipt as it sends (`addPendingConfig`); CONFIG_QUEUED and
// CONFIG_APPLIED fill it in, and a `CONFIG failed` error fails it
// (`failPendingConfig`). A recording's CONFIG replies make their own receipts.
// A receipt that changes is replaced, never edited, and so is the `receipts`
// array, so a reader memoised on either sees the change.

// A tick frame is the only server message with both `tick` and `metrics`.
export function isFrame(message) {
  return Boolean(message) && typeof message.tick === 'number' && Boolean(message.metrics) && !message.type
}

// JSON Lines -> { header, messages }. `messages` are the payloads of the
// `message` lines in wire order; `sent` lines and the footer are left out.
export function parseSession(text) {
  let header = null
  const messages = []
  const lines = String(text ?? '').split(/\r?\n/)
  lines.forEach((line, index) => {
    if (!line.trim()) return
    let record
    try {
      record = JSON.parse(line)
    } catch (error) {
      throw new Error(`Recorded session line ${index + 1} is not valid JSON: ${error.message}`, { cause: error })
    }
    if (record?.kind === 'header') header = record
    else if (record?.kind === 'message' && record.message) messages.push(record.message)
  })
  return { header, messages }
}

const isNumber = value => typeof value === 'number' && Number.isFinite(value)
const numberOrNull = value => (isNumber(value) ? value : null)

// The setup keys SETUP_COMPLETE confirms; the recording's header is the fallback.
const WIRE_SETUP = ['initial_policy', 'seed', 'num_households', 'horizon_ticks']

const pick = (source, keys) => {
  const out = {}
  for (const key of keys) out[key] = source?.[key] ?? null
  return out
}
const FIRM_FIELDS = ['id', 'name', 'sector', 'cash', 'staff', 'state', 'isBaseline']
const SUBJECT_FIELDS = [
  'id', 'age', 'isEmployed', 'canWork', 'housingSecurity', 'employer', 'employerCategory', 'wage', 'cash', 'rentArrears',
  'unemploymentDuration',
]
const CLOSED_FIELDS = ['id', 'name', 'sector', 'closedTick', 'lastStaff']
const list = value => (Array.isArray(value) ? value : [])

function registerFirm(directory, firm) {
  if (!firm || firm.id == null) return
  const known = directory.byId[firm.id] ?? {}
  const entry = {
    id: firm.id,
    name: firm.name ?? known.name ?? null,
    sector: firm.sector ?? known.sector ?? null,
    isBaseline: firm.isBaseline ?? known.isBaseline ?? (typeof firm.name === 'string' && firm.name.startsWith('Baseline')),
  }
  directory.byId[firm.id] = entry
  if (entry.name) directory.byName[entry.name] = entry
}

function parsePolicyText(text) {
  const raw = String(text ?? '')
  const at = raw.indexOf('=')
  if (at < 1) return null
  return { policy: raw.slice(0, at), value: raw.slice(at + 1) }
}

// First index in the ascending `values` (read through `get`) whose value is > limit.
function upperBound(values, limit, get = value => value) {
  let lo = 0
  let hi = values.length
  while (lo < hi) {
    const mid = (lo + hi) >> 1
    if (get(values[mid]) <= limit) lo = mid + 1
    else hi = mid
  }
  return lo
}

function refreshHorizon(arm) {
  const last = arm.ticks.length ? arm.ticks[arm.ticks.length - 1] : 0
  arm.horizon = arm.horizonTick ?? numberOrNull(arm.setup.horizon_ticks) ?? last
}

// An empty town. `setup` is the recording's header setup, used until the
// server confirms its own.
export function createArm({ label, color, setup } = {}) {
  const arm = {
    label,
    color,
    setup: { ...(setup ?? {}) },
    horizon: 0,
    horizonTick: null,
    profiles: {},
    ticks: [],
    series: {},
    snapshots: {},
    eventCounts: {},
    events: [],
    policyChanges: [],
    firmDirectory: { byId: {}, byName: {} },
    policy: null,
    receipts: [],
  }
  refreshHorizon(arm)
  return arm
}

// Receipt = { actionId, status: 'sending'|'queued'|'applied'|'failed', requested,
//             applied, rejected: { [lever]: reason }, effectiveTick, message }
function newReceipt(fields) {
  return {
    actionId: null, status: 'sending', requested: {}, applied: {}, rejected: {}, effectiveTick: null, message: null, ...fields,
  }
}

function replaceReceipt(arm, index, fields) {
  const receipt = { ...arm.receipts[index], ...fields }
  arm.receipts = arm.receipts.map((old, i) => (i === index ? receipt : old))
  return receipt
}

const oldestSending = arm => arm.receipts.findIndex(receipt => receipt.status === 'sending')
const plainObject = value => (value && typeof value === 'object' && !Array.isArray(value) ? { ...value } : {})

// A CONFIG the client is about to send: a 'sending' receipt at the end.
export function addPendingConfig(arm, levers) {
  const receipt = newReceipt({ requested: plainObject(levers) })
  arm.receipts = [...arm.receipts, receipt]
  return receipt
}

// A `CONFIG failed: <reason>` error answers the oldest CONFIG still waiting.
export function failPendingConfig(arm, message) {
  const index = oldestSending(arm)
  if (index < 0) return null
  return replaceReceipt(arm, index, { status: 'failed', message: String(message ?? '') })
}

// Match by actionId; else the oldest 'sending' receipt adopts it (the server
// answers in send order); else it is a receipt nobody here was waiting for.
function receiptIndex(arm, actionId) {
  const matched = actionId == null ? -1 : arm.receipts.findIndex(receipt => receipt.actionId === actionId)
  if (matched >= 0) return matched
  const adopted = oldestSending(arm)
  if (adopted >= 0) return adopted
  arm.receipts = [...arm.receipts, newReceipt({ actionId })]
  return arm.receipts.length - 1
}

function ingestReceipt(arm, message) {
  const actionId = message.actionId ?? null
  const index = receiptIndex(arm, actionId)
  const receipt = arm.receipts[index]
  if (message.type === 'CONFIG_QUEUED') {
    // Never step back from a final answer.
    if (receipt.status === 'sending' || receipt.status === 'queued') replaceReceipt(arm, index, { actionId, status: 'queued' })
    return
  }
  replaceReceipt(arm, index, {
    actionId,
    status: 'applied',
    requested: Object.keys(receipt.requested).length ? receipt.requested : plainObject(message.requested),
    applied: plainObject(message.applied),
    rejected: plainObject(message.rejected),
    effectiveTick: numberOrNull(message.effectiveTick),
    message: null,
  })
}

function ingestFrame(arm, frame) {
  const tick = frame.tick
  const curated = frame.curated ?? {}
  const at = upperBound(arm.ticks, tick) - 1
  const repeated = at >= 0 && arm.ticks[at] === tick

  for (const key of Object.keys(curated)) {
    if (!arm.series[key]) arm.series[key] = arm.ticks.map(() => null)
  }
  if (repeated) {
    for (const key of Object.keys(arm.series)) arm.series[key][at] = numberOrNull(curated[key])
    // A repeated tick (a legacy RESET replay) keeps its latest frame only.
    arm.events = arm.events.filter(event => event.tick !== tick)
    arm.policyChanges = arm.policyChanges.filter(change => change.tick !== tick)
  } else {
    const index = at + 1
    arm.ticks.splice(index, 0, tick)
    for (const key of Object.keys(arm.series)) arm.series[key].splice(index, 0, numberOrNull(curated[key]))
  }
  // The rules in force are the highest tick's; a late older week leaves them be.
  const policy = frame.metrics?.governmentPolicy
  if (policy && typeof policy === 'object' && tick === arm.ticks[arm.ticks.length - 1]) arm.policy = { ...policy }

  const firms = list(frame.firms)
  const firmsClosed = list(frame.firmsClosed)
  arm.snapshots[tick] = {
    firms: firms.map(firm => pick(firm, FIRM_FIELDS)),
    subjects: list(frame.metrics?.trackedSubjects).map(subject => pick(subject, SUBJECT_FIELDS)),
    firmsClosed: firmsClosed.map(firm => pick(firm, CLOSED_FIELDS)),
  }
  arm.eventCounts[tick] = frame.eventCounts ? { ...frame.eventCounts } : null
  for (const firm of firms) registerFirm(arm.firmDirectory, firm)
  for (const firm of firmsClosed) registerFirm(arm.firmDirectory, firm)

  const events = list(frame.events)
  const changes = []
  for (const event of events) {
    if (event.firmId != null && event.firmName) registerFirm(arm.firmDirectory, { id: event.firmId, name: event.firmName, sector: event.sector ?? undefined })
    if (event.type === 'policy_changed') {
      const parsed = parsePolicyText(event.text)
      if (parsed) changes.push({ id: event.id, tick: event.tick ?? tick, ...parsed })
    }
  }
  arm.events.splice(upperBound(arm.events, tick, event => event.tick), 0, ...events)
  arm.policyChanges.splice(upperBound(arm.policyChanges, tick, change => change.tick), 0, ...changes)

  if (isNumber(frame.horizonTick)) arm.horizonTick = frame.horizonTick
}

// Folds one server message into the arm, in place, and returns the arm.
export function ingest(arm, message) {
  if (message?.type === 'SETUP_COMPLETE') {
    const config = message.config ?? {}
    for (const key of WIRE_SETUP) if (config[key] !== undefined) arm.setup[key] = config[key]
    Object.assign(arm.profiles, message.trackedProfiles ?? {})
  } else if (message?.type === 'TRACKED') {
    Object.assign(arm.profiles, message.profiles ?? {})
  } else if (message?.type === 'EXTENDED') {
    if (isNumber(message.horizonTick)) arm.horizonTick = message.horizonTick
  } else if (message?.type === 'CONFIG_QUEUED' || message?.type === 'CONFIG_APPLIED') {
    ingestReceipt(arm, message)
  } else if (isFrame(message)) {
    ingestFrame(arm, message)
  } else {
    return arm
  }
  refreshHorizon(arm)
  return arm
}

// session = parseSession(...); meta = { label, color }.
export function buildArm(session, { label, color } = {}) {
  const arm = createArm({ label, color, setup: session?.header?.setup })
  for (const message of session?.messages ?? []) ingest(arm, message)
  return arm
}
