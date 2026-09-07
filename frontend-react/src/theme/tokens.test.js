import { readFileSync } from 'node:fs'
import { describe, expect, test } from 'vitest'

// Note: `new URL('./tokens.css', import.meta.url)` (as written in the task
// brief) resolves against a virtual http: URL under this project's jsdom
// test environment rather than a real file: URL, so `fs.readFileSync`
// rejects it. A bare relative path is resolved by Node against the cwd
// (the frontend-react package root, where vitest always runs), which
// sidesteps that and keeps the file lint-clean (no `process` global).
const css = readFileSync('src/theme/tokens.css', 'utf8')

// Builds a selector -> last-declared-value map for a given CSS property,
// approximating cascade resolution for this flat, non-nested stylesheet:
// comments are stripped, each `selector[, selector...]{ ... }` block is
// split on commas, and a later rule that names the same exact selector
// string overwrites an earlier one (same-specificity, source-order wins —
// the only override pattern this file actually uses). A selector whose
// declared value is never revisited under its own exact string (e.g. a
// compound modifier like `.btn.big`) keeps its own value, which is exactly
// the specificity bug this suite guards against.
function lastDeclaredValueBySelector(propertyName) {
  const withoutComments = css.replace(/\/\*[\s\S]*?\*\//g, '')
  const ruleRe = /([^{}]+)\{([^{}]*)\}/g
  const lastBySelector = new Map()
  let match
  while ((match = ruleRe.exec(withoutComments))) {
    const [, selectorList, body] = match
    const propRe = new RegExp(`${propertyName}:\\s*([^;]+)`)
    const propMatch = body.match(propRe)
    if (!propMatch) continue
    const value = propMatch[1].trim()
    for (const rawSelector of selectorList.split(',')) {
      const selector = rawSelector.replace(/\s+/g, ' ').trim()
      if (selector) lastBySelector.set(selector, value)
    }
  }
  return lastBySelector
}

describe('tokens.css', () => {
  test('defines both themes with the approved accents', () => {
    expect(css).toMatch(/\[data-theme="ember"\][^}]*--acc:\s*#FF6B1A/i)
    expect(css).toMatch(/\[data-theme="paper"\][^}]*--acc:\s*#D2491E/i)
  })
  test('uses Barlow and never Inter', () => {
    expect(css).toMatch(/--font:\s*'Barlow'/)
    expect(css).not.toMatch(/Inter/)
  })
  test('has no glow, dashed grid, or large radius', () => {
    expect(css).not.toMatch(/drop-shadow|text-shadow/)
    // Flags a real blur/glow: a box-shadow whose blur-radius token (the
    // 3rd space-separated value, right after the box-shadow's own start or
    // a comma separating another shadow layer) is non-zero. Offsets may be
    // unitless zero ("0 0 8px ...", not just "0px 0px 8px ..." — the gap
    // the previous regex missed). Anchoring each candidate to immediately
    // follow "box-shadow:" or "," (rather than scanning from any token)
    // keeps this from misreading a zero-blur ring's own spread radius as a
    // blur: "box-shadow:0 0 0 3px var(--panel)" has blur token "0", so it
    // is correctly left alone (verified below).
    expect(css).not.toMatch(/(?:box-shadow:|,)\s*(?:inset\s+)?\d+(?:px)?\s+\d+(?:px)?\s+[1-9]\d*px/)
    expect(css).toMatch(/box-shadow:0 0 0 3px/) // zero-blur ring stays allowed
    expect(css).not.toMatch(/stroke-dasharray/)
    expect(css).not.toMatch(/border-radius:\s*(1[2-9]|[2-9]\d)px/)
  })
  test('never sets a font-size below the 10.5px floor', () => {
    const sizes = [...css.matchAll(/font-size:\s*([\d.]+)px/g)].map((m) => Number(m[1]))
    expect(sizes.length).toBeGreaterThan(0)
    for (const size of sizes) {
      expect(size).toBeGreaterThanOrEqual(10.5)
    }
  })
  test('keeps every border-radius on the approved scale (3, 4, 5, 6, 999px; 2px for chart tracks)', () => {
    const allowed = new Set(['2', '3', '4', '5', '6', '999'])
    const bySelector = lastDeclaredValueBySelector('border-radius')
    expect(bySelector.size).toBeGreaterThan(0)
    for (const [selector, value] of bySelector) {
      const pxMatch = value.match(/^([\d.]+)px$/)
      if (!pxMatch) continue // 50%, 0, etc. are not on this scale and are fine
      expect(allowed.has(pxMatch[1]), `${selector} has border-radius:${value}`).toBe(true)
    }
  })
})
