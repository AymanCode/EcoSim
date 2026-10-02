import { expect, test } from '@playwright/test'

// Changing the week must not move or resize anything on the Run screen (spec
// section 6). For each width, open the recorded demo, step the timeline
// through every week, and compare every watched box with week 1.
const WIDTHS = [390, 489, 768, 1024, 1280, 1440]
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

// Steps from week 1 to `max` and lists every week whose boxes differ from week 1's.
async function shifts(page, max) {
  await goToWeek(page, 1)
  const base = await boxes(page)
  const problems = []
  for (let week = 2; week <= max; week += 1) {
    await goToWeek(page, week)
    const diff = firstDifference(base, await boxes(page))
    if (diff) problems.push(`week ${week}: ${diff}`)
  }
  return problems
}

for (const width of WIDTHS) {
  test(`nothing moves when the week changes at ${width}px`, async ({ page }) => {
    const max = await openDemo(page, width)
    const problems = await shifts(page, max)
    expect(problems, problems.slice(0, 12).join('\n')).toEqual([])
  })
}

// "See all" is a viewer's choice that stays open while the weeks change.
test('nothing moves when the week changes with the first town\'s businesses all shown, at 1440px', async ({ page }) => {
  const max = await openDemo(page, 1440)
  await goToWeek(page, max)
  await page.getByRole('button', { name: /^See all/ }).first().click()
  await expect(page.getByRole('region', { name: /^Every business in / })).toHaveCount(1)
  const problems = await shifts(page, max)
  expect(problems, problems.slice(0, 12).join('\n')).toEqual([])
})
