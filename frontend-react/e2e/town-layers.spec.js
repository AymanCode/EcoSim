import { expect, test } from '@playwright/test'

// Each town, and Main Street, is drawn as three stacked layers
// (town/Diorama.jsx, town/MainStreet.jsx): the sky at the back, the world,
// and what moves on top. Smooth frames depend on the world layer never
// running a CSS animation or transition (the browser would give each animated
// shape, and every shape painted over it, a compositor layer of its own); the
// place cards (Task 7) depend on the back and motion layers letting the
// pointer through to the world. The demo has two towns, so three scenes.

async function openDemo(page, height = 900) {
  await page.setViewportSize({ width: 1440, height })
  await page.goto('/?view=next&demo')
  await page.locator('input[type=range]').first().waitFor()
  await page.locator('.lt-towns').scrollIntoViewIfNeeded()
}

async function play(page) {
  await page.getByRole('button', { name: 'Play at 1× speed' }).click()
  const button = page.locator('button.nx-play')
  if (!/pause/i.test(await button.textContent())) await button.click()
}

test('while the demo plays at 1×, no world layer runs an animation: not the towns\', not Main Street\'s', async ({ page }) => {
  await openDemo(page)
  for (const name of ['back', 'world', 'motion']) await expect(page.locator(`.lt-stage > [data-layer="${name}"]`)).toHaveCount(3)
  await expect(page.locator(`.lt-street .lt-stage > [data-layer="world"]`)).toHaveCount(1)
  await play(page)
  const counts = []
  for (let i = 0; i < 6; i += 1) {
    await page.waitForTimeout(350)
    counts.push(await page.evaluate(() => [...document.querySelectorAll('[data-layer="world"]')].map(world => world.getAnimations({ subtree: true }).length)))
  }
  expect(counts).toEqual(Array.from({ length: 6 }, () => [0, 0, 0]))
  // The scenes are moving all the while: coins fly in each motion layer, and
  // people stroll Main Street's pavement.
  expect(await page.locator('.lt-card [data-layer="motion"] [data-layer="coins"] circle').count()).toBeGreaterThan(0)
  expect(await page.locator('.lt-street [data-layer="motion"] [data-layer="coins"] circle').count()).toBeGreaterThan(0)
  const strollers = page.locator('.lt-street [data-layer="walk"] > .lt-walker')
  expect(await strollers.count()).toBeGreaterThan(1)
  const where = await strollers.first().getAttribute('transform')
  await page.waitForTimeout(300)
  expect(await strollers.first().getAttribute('transform')).not.toBe(where)
})

// A tall window shows both towns and Main Street at once.
test('the pointer passes through the sky and the moving layer to the world', async ({ page }) => {
  await openDemo(page, 1600)
  await play(page)
  await page.waitForTimeout(800)
  const found = await page.evaluate(() => {
    const out = { back: 0, motion: 0, world: 0, kinds: new Set(), streetKinds: new Set(), pointerEvents: [] }
    for (const stage of document.querySelectorAll('.lt-stage')) {
      for (const layer of stage.querySelectorAll(':scope > [data-layer="back"], :scope > [data-layer="motion"]')) out.pointerEvents.push(getComputedStyle(layer).pointerEvents)
      const box = stage.getBoundingClientRect()
      for (let x = box.left + 4; x < box.right; x += 9) {
        for (let y = Math.max(0, box.top) + 4; y < Math.min(box.bottom, innerHeight); y += 9) {
          const hit = document.elementFromPoint(x, y)
          const layer = hit?.closest('[data-layer="back"], [data-layer="world"], [data-layer="motion"]')?.dataset.layer
          if (layer) out[layer] += 1
          const kind = hit?.closest('[data-kind]')?.dataset.kind
          if (kind) out.kinds.add(kind)
          if (kind && stage.closest('.lt-street')) out.streetKinds.add(kind)
        }
      }
    }
    return { ...out, kinds: [...out.kinds].sort(), streetKinds: [...out.streetKinds].sort() }
  })
  expect(found.pointerEvents).toEqual(['none', 'none', 'none', 'none', 'none', 'none'])
  expect(found.back).toBe(0)
  expect(found.motion).toBe(0)
  expect(found.world).toBeGreaterThan(1000)
  expect(found.kinds).toEqual(['bank', 'hall', 'house', 'person', 'shop'])
  expect(found.streetKinds).toEqual(['bank', 'hall', 'house', 'person', 'shop'])
})
