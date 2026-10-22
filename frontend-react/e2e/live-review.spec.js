import fs from 'node:fs'
import { expect, test } from '@playwright/test'
import { STAT_METRICS, formatMetric } from '../src/next/catalog.js'
import { isFrame, parseSession } from '../src/next/data/session.js'
import { runScreenFonts } from './fonts.js'

// Feed real recorded frames over mocked /ws connections. NextApp still uses
// its production experiment controller, ingest, throttling, and live clock.
// Recording lines wrap the wire payload in record.message; header/sent/footer
// records must never reach the client. parseSession preserves message order.
const { messages } = parseSession(fs.readFileSync(new URL('../public/demo/town-a.jsonl', import.meta.url), 'utf8'))
const [session, setupComplete, started] = messages
const frames = messages.filter(message => isFrame(message) && message.tick > 0 && message.curated)
test.setTimeout(30_000)

async function liveRun(page, width = 390, towns = 2) {
  const sockets = []
  const commands = []
  const errors = []
  expect([session.type, setupComplete.type, started.type]).toEqual(['SESSION', 'SETUP_COMPLETE', 'STARTED'])
  expect(frames.map(frame => frame.tick)).toEqual(Array.from({ length: 104 }, (_, i) => i + 1))
  page.on('pageerror', error => errors.push(error.message))
  await page.routeWebSocket('**/ws', socket => {
    const index = sockets.length
    sockets.push(socket)
    commands[index] = []
    socket.onMessage(raw => {
      const message = JSON.parse(raw)
      commands[index].push(message.command)
      if (message.command === 'SETUP') {
        socket.send(JSON.stringify({ ...setupComplete, config: { ...setupComplete.config, ...message.config } }))
      } else if (message.command === 'START') {
        socket.send(JSON.stringify(started))
      } else if (message.command === 'STOP') {
        socket.send(JSON.stringify({ type: 'STOPPED' }))
      }
    })
    socket.send(JSON.stringify({ ...session, sessionId: `review-${index + 1}` }))
  })
  await page.setViewportSize({ width, height: 900 })
  await page.goto('/?view=next')
  if (towns > 2) {
    await page.getByRole('button', { name: 'Build my own', exact: true }).click()
    for (let i = 2; i < towns; i += 1) await page.getByRole('button', { name: 'Add a town', exact: true }).click()
  }
  await page.getByRole('button', { name: 'Start the experiment', exact: true }).click()
  await expect.poll(() => sockets.length).toBe(towns)
  // createExperiment sends SETUP after SESSION, then START only once every
  // town is ready. Do not feed frames merely because the sockets exist.
  await expect.poll(() => commands.map(town => town.slice(0, 2)))
    .toEqual(Array.from({ length: towns }, () => ['SETUP', 'START']))
  await expect(page.getByRole('button', { name: 'Pause', exact: true })).toBeEnabled()
  await runScreenFonts(page)
  const send = message => {
    expect(message).not.toHaveProperty('kind')
    sockets.forEach(socket => socket.send(JSON.stringify(message)))
  }
  const week = async messages => {
    expect(isFrame(messages.at(-1)), 'week() needs a nonempty batch ending in a tick payload').toBe(true)
    for (const message of messages) send(message)
    const tick = messages.at(-1).tick
    await expect(page.locator('.nx-clock .nx-week')).toHaveText(`Year 1, week ${tick}`)
    await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))))
  }
  return { send, week, errors }
}

async function scrub(page, tick) {
  await page.getByRole('slider', { name: 'Week of the run' }).evaluate((input, value) => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(input, String(value))
    input.dispatchEvent(new Event('input', { bubbles: true }))
    input.dispatchEvent(new Event('change', { bubbles: true }))
  }, tick)
  await expect(page.locator('.nx-clock .nx-week')).toHaveText(`Year 1, week ${tick}`)
  await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))))
}

async function layout(page) {
  return page.evaluate(() => {
    const lead = document.querySelector('.nx-lead').getBoundingClientRect()
    const leadHeight = lead.height
    // Spec accepts live lead growth; deduct that height from positions and
    // page height so it cannot hide a shift in any other box.
    const boxes = [...new Set([
      ...document.querySelectorAll('[data-stable]:not(.nx-lead)'),
      ...document.querySelectorAll('main.nx-wrap > *:not(.nx-lead)'),
      ...document.querySelectorAll('main.nx-wrap .nx-card'),
    ])].map(el => {
      const r = el.getBoundingClientRect()
      return { name: el.dataset.stable || el.className, box: [r.x, r.y + scrollY - (r.y >= lead.bottom ? leadHeight : 0), r.width, r.height] }
    })
    return { boxes, height: document.scrollingElement.scrollHeight - leadHeight }
  })
}

function sameLayout(before, after) {
  expect(after.boxes.map(item => item.name)).toEqual(before.boxes.map(item => item.name))
  before.boxes.forEach((item, i) => item.box.forEach((value, j) => {
    expect(Math.abs(after.boxes[i].box[j] - value), `${item.name} ${['x', 'y', 'width', 'height'][j]}`).toBeLessThanOrEqual(0.5)
  }))
  expect(Math.abs(after.height - before.height), 'page height').toBeLessThanOrEqual(0.5)
}

test('incremental live frames reserve moments before arrival and notices before errors', async ({ page }) => {
  const live = await liveRun(page)
  await live.week(frames.filter(frame => frame.tick <= 12))
  const before = await layout(page)
  await expect(page.locator('.nx-moments > ul .nx-moment')).toHaveCount(0)
  await live.week(frames.filter(frame => frame.tick === 13))
  await expect(page.locator('.nx-moments > ul .nx-moment')).toHaveCount(2)
  sameLayout(before, await layout(page))
  live.send({ error: 'Unknown command: REVIEW_TEST' })
  await expect(page.locator('.nx-notice').first()).not.toBeEmpty()
  sameLayout(before, await layout(page))
  await live.week(frames.filter(frame => frame.tick === 14))
  await expect(page.locator('.nx-notice').first()).toBeEmpty()
  sameLayout(before, await layout(page))
  // A late event-rich part of the run cannot grow the fixed live strip.
  await live.week(frames.filter(frame => frame.tick > 14 && frame.tick <= 40))
  expect((await layout(page)).boxes.find(item => item.name === 'moments').box[3]).toBe(before.boxes.find(item => item.name === 'moments').box[3])
  expect(live.errors).toEqual([])
})

test('scrubbing across historical policy changes keeps the policy note and page fixed', async ({ page }) => {
  const live = await liveRun(page)
  await live.week(frames.filter(frame => frame.tick <= 12))
  live.send({ type: 'CONFIG_APPLIED', actionId: 'review-policy', effectiveTick: 13,
    requested: {}, rejected: {}, applied: { minimum_wage_policy: 'high', benefit_level: 'high', wage_tax_rate: 0.3, profit_tax_rate: 0.3 } })
  await live.week(frames.filter(frame => frame.tick === 13).map(frame => ({ ...frame, events: [
    ...(frame.events ?? []),
    ...Object.entries({ minimum_wage_policy: 'high', benefit_level: 'high', wage_tax_rate: 0.3, profit_tax_rate: 0.3 })
      .map(([policy, value], i) => ({ id: `review-policy-${i}`, tick: 13, type: 'policy_changed', text: `${policy}=${value}` })),
  ] })))
  const after = await page.locator('.nx-howto li').nth(1).textContent()
  // Hold both sides of the policy boundary in history. The live toolbar's
  // Follow control then stays in the same state throughout the comparison.
  await live.week(frames.filter(frame => frame.tick === 14))
  await scrub(page, 13)
  const base = await layout(page)
  for (const tick of [12, 13, 11, 13]) {
    await scrub(page, tick)
    sameLayout(base, await layout(page))
  }
  await scrub(page, 12)
  expect(await page.locator('.nx-howto li').nth(1).textContent()).not.toBe(after)
  expect(live.errors).toEqual([])
})

for (const towns of [3, 4]) {
  test(`${towns} town stat cards keep their height as values widen, with the Town hall open`, async ({ page }) => {
    const live = await liveRun(page, 1680, towns)
    // One-digit values fit together more often than two/three-digit values.
    const base = frames.find(frame => frame.tick === 11)
    await live.week([{ ...base, tick: 11, curated: { ...base.curated, peopleOutOfWorkPer100: 1 } }])
    await page.getByRole('button', { name: 'Town hall', exact: true }).click()
    await expect(page.locator('.nx-stat .pair')).toHaveCount(STAT_METRICS.length)
    const values = page.locator('[data-stable="stat:peopleOutOfWorkPer100"] .nx-pv b')
    await expect(values).toHaveText(Array(towns).fill(formatMetric('peopleOutOfWorkPer100', 1)))
    const stats = async () => page.locator('.nx-stat .pair').evaluateAll(elements => elements.map(el => el.getBoundingClientRect().height))
    const before = await stats()
    await live.week([{ ...base, tick: 12, curated: { ...base.curated, peopleOutOfWorkPer100: 100 } }])
    await expect(values).toHaveText(Array(towns).fill(formatMetric('peopleOutOfWorkPer100', 100)))
    expect(await stats()).toEqual(before)
    await scrub(page, 11)
    await expect(values).toHaveText(Array(towns).fill(formatMetric('peopleOutOfWorkPer100', 1)))
    expect(await stats()).toEqual(before)
    expect(live.errors).toEqual([])
  })
}
