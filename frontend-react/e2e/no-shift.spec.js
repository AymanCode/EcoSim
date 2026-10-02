import { expect, test } from '@playwright/test'

// Changing the week must not move or resize anything on the Run screen (spec
// section 6). For each width, open the recorded demo, step the timeline
// through every week, and compare every watched box with week 1.
const WIDTHS = [390, 489, 560, 592, 600, 700, 768, 1024, 1280, 1440]
const TOLERANCE = 0.5

// Every element marked data-stable, every direct child of the Run screen's
// <main>, and every card, keyed so the same element is compared each week.
async function boxes(page) {
  return page.evaluate(() => {
    const out = {}
    const seen = new Set()
    const watched = [
      ...document.querySelectorAll('[data-stable]'),
      ...document.querySelectorAll('main.nx-wrap > *'),
      ...document.querySelectorAll('main.nx-wrap .nx-card'),
    ]
    watched.forEach((el, i) => {
      if (seen.has(el)) return
      seen.add(el)
      const key = el.dataset.stable ? `stable:${el.dataset.stable}` : `${el.tagName.toLowerCase()}.${String(el.className).split(' ')[0]}#${i}`
      const r = el.getBoundingClientRect()
      out[key] = [r.left, r.top + window.scrollY, r.width, r.height]
    })
    out.__scrollHeight = [0, 0, 0, document.scrollingElement.scrollHeight]
    return out
  })
}

async function goToWeek(page, week) {
  await page.locator('input[type=range]').first().evaluate((input, value) => {
    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set
    setter.call(input, String(value))
    input.dispatchEvent(new Event('input', { bubbles: true }))
    input.dispatchEvent(new Event('change', { bubbles: true }))
  }, week)
  await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))))
}

function firstDifference(base, now) {
  for (const key of new Set([...Object.keys(base), ...Object.keys(now)])) {
    const a = base[key], b = now[key]
    if (!a || !b) return `${key} ${a ? 'disappeared' : 'appeared'}`
    for (let k = 0; k < 4; k += 1) {
      if (Math.abs(a[k] - b[k]) > TOLERANCE) return `${key} ${['left', 'top', 'width', 'height'][k]} ${a[k].toFixed(1)} → ${b[k].toFixed(1)}`
    }
  }
  return null
}

// Opens the recorded demo at `width` and returns its last week.
async function openDemo(page, width) {
  await page.setViewportSize({ width, height: 900 })
  await page.goto('/?view=next&demo')
  await page.locator('input[type=range]').first().waitFor()
  await page.evaluate(() => document.fonts.ready)
  return Number(await page.locator('input[type=range]').first().getAttribute('max'))
}

// The first clamped or fixed-height text box (marked data-fits) whose text
// does not fit in it, or null: cutting text would hide what a viewer needs.
async function firstCut(page) {
  return page.evaluate(() => {
    for (const el of document.querySelectorAll('[data-fits]')) {
      if (el.scrollHeight > el.clientHeight + 1) {
        return `${el.dataset.fits} ${el.scrollHeight} > ${el.clientHeight}: "${el.textContent.trim().slice(0, 140)}"`
      }
    }
    return null
  })
}

// The first box with reserved room (StableText, marked data-reserve) that is
// taller than its reservation, or null: its text is longer than the room it
// was measured for, so the page below it would move.
async function firstOutgrown(page) {
  return page.evaluate(() => {
    for (const el of document.querySelectorAll('[data-reserve]')) {
      const height = el.getBoundingClientRect().height
      const room = parseFloat(el.style.minHeight)
      if (!(height <= room + 0.5)) return `${el.dataset.stable} ${height.toFixed(1)} > ${el.style.minHeight || 'no room'}: "${el.textContent.trim().slice(0, 140)}"`
    }
    return null
  })
}

// Steps from week 1 to `max`. `moved` lists every week whose boxes differ from
// week 1's, `cut` every week with text that does not fit its box, `outgrown`
// every week with a reserved box taller than its room.
async function walk(page, max) {
  await goToWeek(page, 1)
  const base = await boxes(page)
  const moved = []
  const cut = []
  const outgrown = []
  for (let week = 1; week <= max; week += 1) {
    if (week > 1) {
      await goToWeek(page, week)
      const diff = firstDifference(base, await boxes(page))
      if (diff) moved.push(`week ${week}: ${diff}`)
    }
    const text = await firstCut(page)
    if (text) cut.push(`week ${week}: ${text}`)
    const grown = await firstOutgrown(page)
    if (grown) outgrown.push(`week ${week}: ${grown}`)
  }
  return { moved, cut, outgrown }
}

for (const width of WIDTHS) {
  test(`nothing moves, no text is cut and no reserved box outgrows its room as the week changes at ${width}px`, async ({ page }) => {
    const max = await openDemo(page, width)
    const { moved, cut, outgrown } = await walk(page, max)
    expect(moved, moved.slice(0, 12).join('\n')).toEqual([])
    expect(cut, cut.slice(0, 12).join('\n')).toEqual([])
    expect(outgrown, outgrown.slice(0, 12).join('\n')).toEqual([])
  })
}

// "See all" is a viewer's choice that stays open while the weeks change.
test('nothing moves when the week changes with the first town\'s businesses all shown, at 1440px', async ({ page }) => {
  const max = await openDemo(page, 1440)
  await goToWeek(page, max)
  await page.getByRole('button', { name: /^See all/ }).first().click()
  await expect(page.getByRole('region', { name: /^Every business in / })).toHaveCount(1)
  const { moved, cut, outgrown } = await walk(page, max)
  expect(moved, moved.slice(0, 12).join('\n')).toEqual([])
  expect(cut, cut.slice(0, 12).join('\n')).toEqual([])
  expect(outgrown, outgrown.slice(0, 12).join('\n')).toEqual([])
})

// Enlarge is a viewer's choice too: one town at full width while the weeks change.
test('nothing moves when the week changes with the second town enlarged, at 1440px', async ({ page }) => {
  const max = await openDemo(page, 1440)
  await page.getByRole('button', { name: 'Enlarge' }).nth(1).click()
  await expect(page.locator('.lt-card:not([hidden])')).toHaveCount(1)
  await expect(page.getByRole('button', { name: 'Show both' })).toHaveCount(1)
  const { moved, cut, outgrown } = await walk(page, max)
  expect(moved, moved.slice(0, 12).join('\n')).toEqual([])
  expect(cut, cut.slice(0, 12).join('\n')).toEqual([])
  expect(outgrown, outgrown.slice(0, 12).join('\n')).toEqual([])
})
