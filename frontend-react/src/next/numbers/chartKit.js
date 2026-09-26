// Small pure helpers shared by the numbers sheet's special visuals.

export const r1 = value => Math.round(value * 10) / 10

export const isNumber = value => typeof value === 'number' && Number.isFinite(value)

// The first week of a window of `weeks` weeks that ends at `tick`.
export const windowStart = (tick, weeks) => Math.max(1, Math.floor(tick) - weeks + 1)

// Rough width of a label in px (no DOM measuring), with a little slack.
export const textWidth = (text, size = 12, bold = false) => String(text).length * size * (bold ? 0.58 : 0.54)

// An axis on round numbers from lo to hi, with at most `count` steps.
// Ported from mockup 06's `nice`.
export function niceScale(lo, hi, count = 5) {
  let top = hi
  if (top - lo < 1e-9) top = lo + 1
  const magnitude = 10 ** Math.floor(Math.log10((top - lo) / count))
  let step = magnitude
  for (const m of [1, 2, 2.5, 5, 10, 20, 25, 50]) {
    step = m * magnitude
    if (Math.ceil(top / step - 1e-9) - Math.floor(lo / step + 1e-9) <= count) break
  }
  const start = Math.floor(lo / step + 1e-9) * step
  const end = Math.ceil(top / step - 1e-9) * step
  const ticks = []
  for (let value = start; value <= end + step / 2; value += step) ticks.push(Math.round(value * 1e6) / 1e6)
  return { lo: start, hi: end, ticks }
}

// Push labels ({ y }) apart to at least `gap` px, keeping them between top
// and bottom; returns them sorted by y.
export function spreadLabels(items, gap, top, bottom) {
  const sorted = [...items].sort((a, b) => a.y - b.y)
  for (let i = 1; i < sorted.length; i += 1) {
    if (sorted[i].y - sorted[i - 1].y < gap) sorted[i].y = sorted[i - 1].y + gap
  }
  const overflow = sorted.length ? sorted[sorted.length - 1].y - bottom : 0
  if (overflow > 0) {
    sorted[sorted.length - 1].y = bottom
    for (let i = sorted.length - 2; i >= 0; i -= 1) {
      if (sorted[i + 1].y - sorted[i].y < gap) sorted[i].y = sorted[i + 1].y - gap
    }
  }
  const underflow = sorted.length ? top - sorted[0].y : 0
  if (underflow > 0) sorted.forEach(item => { item.y += underflow })
  return sorted
}

// Whether any town recorded an `eventCounts` figure for `key` in any week.
export function everCounted(arms, key) {
  return (arms ?? []).some(arm => Object.values(arm?.eventCounts ?? {}).some(counts => isNumber(counts?.[key])))
}

export const total = (rows, key) => rows.reduce((sum, row) => sum + (isNumber(row[key]) ? row[key] : 0), 0)
