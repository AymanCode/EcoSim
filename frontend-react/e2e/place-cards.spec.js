import { expect, test } from '@playwright/test'
import { runScreenFonts } from './fonts.js'

// Place cards (spec section 4.4, town/usePlaceCard.js): pointing at a place in
// a living town shows its card beside the pointer and inside the drawing;
// clicking keeps it; clicking the ground or the kept card closes it; on a
// touch screen a tap does what a click does. The card lies over the drawing,
// so showing it never moves or resizes anything (no-shift.spec.js also walks
// every week with a card kept open).

async function goToWeek(page, week) {
  await page.locator('input[type=range]').first().evaluate((input, value) => {
    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set
    setter.call(input, String(value))
    input.dispatchEvent(new Event('input', { bubbles: true }))
    input.dispatchEvent(new Event('change', { bubbles: true }))
  }, week)
  await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))))
}

async function openDemo(page, width) {
  await page.setViewportSize({ width, height: 900 })
  await page.goto('/?view=next&demo')
  await page.locator('input[type=range]').first().waitFor()
  await runScreenFonts(page)
  await goToWeek(page, 70)
  await page.locator('.lt-canvas').first().scrollIntoViewIfNeeded()
}

// Points on the first town's drawing (or the drawing at `selector`) where the
// pointer finds each kind of place, and the places nearest each edge of it.
async function spots(page, selector = '.lt-canvas') {
  return page.evaluate(selector => {
    const canvas = document.querySelector(selector)
    const box = canvas.getBoundingClientRect()
    const hits = []
    for (let x = box.left + 2; x < box.right - 1; x += 4) {
      for (let y = box.top + 2; y < box.bottom - 1; y += 4) {
        const place = document.elementFromPoint(x, y)?.closest('[data-kind]')
        if (place && canvas.contains(place)) hits.push({ x, y, kind: place.dataset.kind })
      }
    }
    const out = {}
    for (const kind of ['house', 'shop', 'hall', 'bank', 'person']) {
      const all = hits.filter(hit => hit.kind === kind)
      if (all.length) out[kind] = all[Math.floor(all.length / 2)]
    }
    const nearest = distance => hits.reduce((a, b) => (distance(b) < distance(a) ? b : a))
    out.left = nearest(hit => hit.x - box.left)
    out.right = nearest(hit => box.right - hit.x)
    out.top = nearest(hit => hit.y - box.top)
    out.bottom = nearest(hit => box.bottom - hit.y)
    return out
  }, selector)
}

// A point on the first town's empty ground that no kept card covers (a kept
// card takes the pointer, so the point under it is the card).
async function ground(page) {
  return page.evaluate(() => {
    const canvas = document.querySelector('.lt-canvas')
    const box = canvas.getBoundingClientRect()
    for (let y = box.top + 4; y < box.bottom - 2; y += 6) {
      for (let x = box.left + 4; x < box.right - 2; x += 6) {
        const hit = document.elementFromPoint(x, y)
        if (hit && canvas.contains(hit) && !hit.closest('[data-kind], .lt-place')) return { x, y }
      }
    }
    return null
  })
}

// The first town's card (or the card of the drawing at `selector`): its
// classes, its text, and whether it lies inside the drawing.
async function placeCard(page, selector = '.lt-canvas') {
  return page.evaluate(selector => {
    const canvas = document.querySelector(selector)
    const card = canvas.querySelector('.lt-place')
    const c = canvas.getBoundingClientRect()
    const r = card.getBoundingClientRect()
    return {
      on: card.classList.contains('is-on'),
      pinned: card.classList.contains('is-pinned'),
      visible: getComputedStyle(card).visibility === 'visible',
      text: card.textContent,
      inside: r.left >= c.left - 0.5 && r.right <= c.right + 0.5 && r.top >= c.top - 0.5 && r.bottom <= c.bottom + 0.5,
      box: [r.left, r.top, r.width, r.height].map(Math.round).join(','),
    }
  }, selector)
}

const pageSize = page => page.evaluate(() => [document.scrollingElement.scrollHeight, ...[...document.querySelectorAll('.lt-card, .lt-street')].map(card => {
  const r = card.getBoundingClientRect()
  return `${r.width.toFixed(1)}x${r.height.toFixed(1)}`
})].join(' '))

for (const width of [390, 1440]) {
  test(`pointing at each kind of place, and at places by every edge, shows a card inside the drawing that takes no room, at ${width}px`, async ({ page }) => {
    await openDemo(page, width)
    const spot = await spots(page)
    const before = await pageSize(page)
    for (const name of ['house', 'shop', 'hall', 'bank', 'person', 'left', 'right', 'top', 'bottom']) {
      expect(spot[name], name).toBeTruthy()
      await page.mouse.move(spot[name].x, spot[name].y)
      await expect(page.locator('.lt-place.is-on').first()).toBeVisible()
      const card = await placeCard(page)
      expect(card.visible, name).toBe(true)
      expect(card.pinned, name).toBe(false)
      expect(card.inside, `${name} card at ${card.box}`).toBe(true)
    }
    expect(await pageSize(page)).toBe(before)
    // Leaving the drawing takes the card away.
    await page.mouse.move(1, 1)
    await expect.poll(async () => (await placeCard(page)).on).toBe(false)
    expect((await placeCard(page)).visible).toBe(false)
  })
}

// Main Street's places have the same cards, inside the street's drawing.
test('pointing at each kind of place on Main Street shows its card inside the street, taking no room, at 1440px', async ({ page }) => {
  await openDemo(page, 1440)
  const street = '.lt-street .lt-canvas'
  await page.locator(street).scrollIntoViewIfNeeded()
  const spot = await spots(page, street)
  const before = await pageSize(page)
  for (const name of ['house', 'shop', 'hall', 'bank', 'person', 'left', 'right', 'top', 'bottom']) {
    expect(spot[name], name).toBeTruthy()
    await page.mouse.move(spot[name].x, spot[name].y)
    await expect(page.locator('.lt-street .lt-place.is-on')).toBeVisible()
    const card = await placeCard(page, street)
    expect(card.visible, name).toBe(true)
    expect(card.inside, `${name} card at ${card.box}`).toBe(true)
  }
  await page.mouse.move(spot.shop.x, spot.shop.y)
  expect((await placeCard(page, street)).text).toMatch(/Staff|Closed/)
  expect(await pageSize(page)).toBe(before)
  await page.mouse.move(1, 1)
  await expect.poll(async () => (await placeCard(page, street)).on).toBe(false)
})

test('a click keeps a card while the pointer moves on; a click on the ground or on the card closes it, at 1440px', async ({ page }) => {
  await openDemo(page, 1440)
  const spot = await spots(page)
  await page.mouse.click(spot.hall.x, spot.hall.y)
  await page.mouse.move(spot.bank.x, spot.bank.y)
  await page.mouse.move(1, 1)
  let card = await placeCard(page)
  expect(card.on && card.pinned).toBe(true)
  expect(card.text).toContain('Town hall')
  // The kept card follows the week.
  await goToWeek(page, 110)
  expect((await placeCard(page)).text).not.toBe(card.text)
  const empty = await ground(page)
  await page.mouse.click(empty.x, empty.y)
  await expect.poll(async () => (await placeCard(page)).on).toBe(false)

  await page.mouse.click(spot.bank.x, spot.bank.y)
  await expect.poll(async () => (await placeCard(page)).pinned).toBe(true)
  card = await placeCard(page)
  const [left, top] = card.box.split(',').map(Number)
  await page.mouse.click(left + 20, top + 12)
  await expect.poll(async () => (await placeCard(page)).on).toBe(false)
})

test.describe('on a touch screen', () => {
  test.use({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true })

  test('a tap on a place opens and keeps its card; a tap on the card or the ground closes it', async ({ page }) => {
    await page.goto('/?view=next&demo')
    await page.locator('input[type=range]').first().waitFor()
    await runScreenFonts(page)
    await goToWeek(page, 70)
    await page.locator('.lt-canvas').first().scrollIntoViewIfNeeded()
    const spot = await spots(page)

    await page.touchscreen.tap(spot.shop.x, spot.shop.y)
    await expect.poll(async () => (await placeCard(page)).pinned).toBe(true)
    let card = await placeCard(page)
    expect(card.on && card.visible && card.inside).toBe(true)
    const [left, top] = card.box.split(',').map(Number)
    await page.touchscreen.tap(left + 20, top + 12)
    await expect.poll(async () => (await placeCard(page)).on).toBe(false)

    await page.touchscreen.tap(spot.person.x, spot.person.y)
    await expect.poll(async () => (await placeCard(page)).pinned).toBe(true)
    card = await placeCard(page)
    expect(card.inside).toBe(true)
    expect(card.text).toContain('someone you follow')
    const empty = await ground(page)
    await page.touchscreen.tap(empty.x, empty.y)
    await expect.poll(async () => (await placeCard(page)).on).toBe(false)
  })
})
