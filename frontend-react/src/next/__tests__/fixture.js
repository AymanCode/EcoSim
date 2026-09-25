import fs from 'node:fs'
import { parseSession, buildArm } from '../data/session.js'

// Vite rewrites the literal pattern `new URL('<path>', import.meta.url)` into a
// served http URL (its asset-URL transform), which fs cannot read. Holding
// import.meta.url in a variable keeps it a file: URL.
const here = import.meta.url

export const FIXTURE_TEXT = fs.readFileSync(new URL('../../test/fixtures/session-compare-small.jsonl', here), 'utf8')

export const TOWN_A = { label: 'Town A', color: '#2E6FE0' }
export const TOWN_B = { label: 'Town B', color: '#E0762C' }

// A fresh arm per call, so a test can doctor one without touching another.
export function fixtureArm(meta = TOWN_A) {
  return buildArm(parseSession(FIXTURE_TEXT), meta)
}
