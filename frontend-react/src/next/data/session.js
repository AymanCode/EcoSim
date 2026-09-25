// Turns a recorded frame-2 session (JSON Lines from scripts/record_session.py)
// into one "arm": the per-tick series, snapshots and events a town needs.
// Raw frames are projected and dropped; nothing here keeps a whole frame.

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

// session = parseSession(...); meta = { label, color }.
export function buildArm(session, { label, color } = {}) {
  const header = session?.header ?? null
  const messages = session?.messages ?? []
  const setup = { ...(header?.setup ?? {}) }

  const profiles = {}
  let completeHorizon = null
  const byTick = new Map()
  for (const message of messages) {
    if (message?.type === 'SETUP_COMPLETE') {
      Object.assign(profiles, message.trackedProfiles ?? {})
      completeHorizon = numberOrNull(message.config?.horizon_ticks)
    } else if (message?.type === 'TRACKED') {
      Object.assign(profiles, message.profiles ?? {})
    } else if (isFrame(message)) {
      // A repeated tick (a legacy RESET replay) keeps its latest frame.
      byTick.set(message.tick, message)
    }
  }

  const ticks = [...byTick.keys()].sort((a, b) => a - b)
  const frames = ticks.map(tick => byTick.get(tick))

  const keys = new Set()
  for (const frame of frames) for (const key of Object.keys(frame.curated ?? {})) keys.add(key)
  const series = {}
  for (const key of keys) series[key] = frames.map(frame => numberOrNull(frame.curated?.[key]))

  const snapshots = {}
  const events = []
  const policyChanges = []
  const firmDirectory = { byId: {}, byName: {} }
  for (const frame of frames) {
    const firms = Array.isArray(frame.firms) ? frame.firms : []
    const firmsClosed = Array.isArray(frame.firmsClosed) ? frame.firmsClosed : []
    snapshots[frame.tick] = {
      firms,
      subjects: Array.isArray(frame.metrics?.trackedSubjects) ? frame.metrics.trackedSubjects : [],
      firmsClosed,
      eventCounts: frame.eventCounts ?? null,
    }
    for (const firm of firms) registerFirm(firmDirectory, firm)
    for (const firm of firmsClosed) registerFirm(firmDirectory, firm)
    for (const event of Array.isArray(frame.events) ? frame.events : []) {
      events.push(event)
      if (event.firmId != null && event.firmName) registerFirm(firmDirectory, { id: event.firmId, name: event.firmName, sector: event.sector ?? undefined })
      if (event.type === 'policy_changed') {
        const parsed = parsePolicyText(event.text)
        if (parsed) policyChanges.push({ tick: event.tick, ...parsed })
      }
    }
  }

  const headerHorizon = numberOrNull(header?.setup?.horizon_ticks)
  const horizon = completeHorizon ?? headerHorizon ?? (ticks.length ? ticks[ticks.length - 1] : 0)

  return { label, color, setup, horizon, profiles, ticks, series, snapshots, events, policyChanges, firmDirectory }
}
