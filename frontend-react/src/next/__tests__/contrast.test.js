import fs from 'node:fs'
import { describe, expect, test } from 'vitest'
import { TOWN_COLORS, townTextColor } from '../catalog.js'

// See fixture.js: keep import.meta.url in a variable so Vite leaves it a file: URL.
const here = import.meta.url
const CSS = fs.readFileSync(new URL('../next.css', here), 'utf8')

const BACKGROUNDS = ['#FFFFFF', '#F3F5F7', '#EEF1F4']
// Text drawn in white sits on a dark fill set elsewhere; each of these is checked below.
const WHITE_ON_DARK = [
  '.nx-verdict', '.nx-abtn.is-dark', ".nx-mchip[aria-pressed='true']", '.nx-hc .av', '.nx-flag-mark', ".pin[aria-pressed='true']",
  '.nx-start', ".nx-seg button[aria-pressed='true']", '.nx-big',
]
const TEXT_FILL = /\btext\b|nx-label|nx-flag-mark|nx-bldg-more|nx-ann|nx-ahead|nx-endl|nx-warm-label/

function luminance(hex) {
  const [r, g, b] = [1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16) / 255)
    .map(c => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4))
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}

function contrast(a, b) {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x)
  return (hi + 0.05) / (lo + 0.05)
}

const clean = CSS.replace(/\/\*[\s\S]*?\*\//g, '').replace(/@import\s+url\([^)]*\)\s*;/g, '')
const RULES = [...clean.matchAll(/([^{}]+)\{([^{}]*)\}/g)].map(([, selector, body]) => ({
  selector: selector.trim(),
  decls: Object.fromEntries(body.split(';').map(d => d.trim()).filter(Boolean).map(d => {
    const at = d.indexOf(':')
    return [d.slice(0, at).trim(), d.slice(at + 1).trim()]
  })),
}))
const TOKENS = Object.fromEntries(Object.entries(RULES.find(rule => rule.selector === '.nx').decls)
  .filter(([name]) => name.startsWith('--nx-')))

function resolve(value) {
  const v = value.trim()
  const ref = v.match(/^var\((--nx-[\w-]+)\)$/)
  if (ref) return resolve(TOKENS[ref[1]] ?? 'unknown')
  if (/^#fff$/i.test(v)) return '#FFFFFF'
  if (/^#[0-9a-f]{6}$/i.test(v)) return v.toUpperCase()
  return null
}

const TEXT_TOKENS = Object.keys(TOKENS).filter(name => name.endsWith('-text'))

describe('text contrast in next.css', () => {
  test('every text token reads at 4.5:1 or better on the page, the panels and panel2', () => {
    expect(TEXT_TOKENS.length).toBeGreaterThanOrEqual(9)
    for (const name of TEXT_TOKENS) {
      for (const background of BACKGROUNDS) {
        expect(contrast(resolve(TOKENS[name]), background), `${name} on ${background}`).toBeGreaterThanOrEqual(4.5)
      }
    }
  })

  test('every text colour is ink, ink2, a text token, or white on a known dark fill', () => {
    const allowed = new Set(['var(--nx-ink)', 'var(--nx-ink2)', ...TEXT_TOKENS.map(name => `var(${name})`), 'inherit', 'currentColor'])
    const checked = []
    for (const { selector, decls } of RULES) {
      const text = [['color', decls.color], ['fill', TEXT_FILL.test(selector) ? decls.fill : undefined]]
      for (const [property, value] of text) {
        if (value === undefined) continue
        checked.push(selector)
        if (resolve(value) === '#FFFFFF') {
          expect(WHITE_ON_DARK.some(dark => selector.includes(dark)), `${selector} ${property}: ${value}`).toBe(true)
          continue
        }
        expect(allowed.has(value), `${selector} ${property}: ${value}`).toBe(true)
        if (value.startsWith('var(')) {
          for (const background of BACKGROUNDS.slice(0, 2)) {
            expect(contrast(resolve(value), background), `${selector} on ${background}`).toBeGreaterThanOrEqual(4.5)
          }
        }
      }
    }
    expect(checked.length).toBeGreaterThan(40)
  })

  test('tags and chips read on their own tint', () => {
    const tinted = RULES.filter(({ decls }) => decls.color && decls.background && resolve(decls.background))
    expect(tinted.length).toBeGreaterThanOrEqual(8)
    for (const { selector, decls } of tinted) {
      expect(contrast(resolve(decls.color), resolve(decls.background)), selector).toBeGreaterThanOrEqual(4.5)
    }
  })

  test('white text sits on fills dark enough for it', () => {
    const fills = RULES.filter(({ selector }) => /\.nx-hc \.av\.is-\w+-bg|\.nx-flag\b(?!-)/.test(selector))
    expect(fills.length).toBeGreaterThanOrEqual(5)
    for (const { selector, decls } of fills) {
      const colour = resolve(decls.background ?? decls.fill)
      expect(contrast(colour, '#FFFFFF'), selector).toBeGreaterThanOrEqual(4.5)
    }
  })

  test('the Set up buttons with white text sit on dark fills, disabled included', () => {
    const fills = RULES.filter(({ selector }) => /\.nx-start\b|\.nx-seg button\[aria-pressed='true'\]/.test(selector))
      .filter(({ decls }) => decls.background)
    expect(fills.map(({ selector }) => selector)).toEqual([
      '.nx .nx-start', '.nx .nx-start:disabled', ".nx .nx-seg button[aria-pressed='true']",
    ])
    for (const { selector, decls } of fills) {
      expect(contrast(resolve(decls.background), '#FFFFFF'), selector).toBeGreaterThanOrEqual(4.5)
    }
  })

  test('town names in text use each town\'s text tone', () => {
    TOWN_COLORS.forEach((color, i) => {
      const value = townTextColor(color)
      expect(value).toBe(`var(--nx-${'abcd'[i]}-text)`)
      for (const background of BACKGROUNDS) expect(contrast(resolve(value), background)).toBeGreaterThanOrEqual(4.5)
    })
    expect(townTextColor('#123456')).toBe('var(--nx-ink)')
  })

  test('a rule that differs between towns keeps every text tone readable on its tint', () => {
    const tint = RULES.find(({ selector, decls }) => selector.includes('.nx-rules') && selector.includes('is-diff') && decls.background)
    expect(tint).toBeTruthy()
    const background = resolve(tint.decls.background)
    for (const value of ['var(--nx-ink)', 'var(--nx-ink2)', 'var(--nx-ink3-text)', ...TOWN_COLORS.map(townTextColor)]) {
      expect(contrast(resolve(value), background), `${value} on ${background}`).toBeGreaterThanOrEqual(4.5)
    }
  })

  test('the "See it big" badge is white on a dark fill', () => {
    const badge = RULES.find(({ selector }) => selector === '.nx .nx-big')
    expect(resolve(badge.decls.color)).toBe('#FFFFFF')
    expect(contrast(resolve(badge.decls.background), '#FFFFFF')).toBeGreaterThanOrEqual(4.5)
  })
})
