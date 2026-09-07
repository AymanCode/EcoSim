// Centralized tone-to-CSS-variable mapping for chart components.
// Eliminates duplication of TONE objects and colorFor helpers across
// Meter, CompositionBar, Ledger, ProfileBars, Radar, Sparkline, and TimeSeries.

export const TONES = {
  acc: 'var(--acc)',
  good: 'var(--good)',
  warn: 'var(--warn)',
  crit: 'var(--crit)',
  ai: 'var(--ai)',
  s1: 'var(--s1)',
  s2: 'var(--s2)',
  s3: 'var(--s3)',
  s4: 'var(--s4)',
  ink: 'var(--ink)',
  ink2: 'var(--ink2)',
  ink3: 'var(--ink3)',
  ink4: 'var(--ink4)',
  flat: 'var(--ink3)',
  panel: 'var(--panel)',
  panel3: 'var(--panel3)',
  grid: 'var(--grid)',
}

/**
 * Map a tone name to its CSS variable string.
 * Returns the tone's var(--...) if present, otherwise var(--${tone}).
 * @param {string} tone - The tone name
 * @returns {string} The CSS variable string
 */
export function toneVar(tone) {
  return TONES[tone] ?? `var(--${tone})`
}

/**
 * Map a numeric value to a threshold-based tone name.
 * Used for indicators where colours represent status levels.
 * @param {number} value - A value typically in [0, 1]
 * @returns {string} One of 'crit', 'warn', or 'acc'
 */
export function thresholdTone(value) {
  if (value < 0.3) return 'crit'
  if (value < 0.5) return 'warn'
  return 'acc'
}
