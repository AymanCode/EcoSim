import { expect, test } from '@playwright/test'
import { RUN_SCREEN_FONTS, runScreenFonts } from './fonts.js'

// The layout checks measure the Run screen with its own fonts, so a slow
// Google Fonts download must not let them start early: with every font
// request held back, every face of both families is loaded on return.
test('runScreenFonts waits for slow Google Fonts', async ({ page }) => {
  await page.route(/fonts\.(googleapis|gstatic)\.com/, async route => {
    await new Promise(resolve => setTimeout(resolve, 1500))
    await route.continue()
  })
  await page.goto('/?view=next&demo')
  await page.locator('input[type=range]').first().waitFor()
  await runScreenFonts(page)
  const faces = await page.evaluate(families => [...document.fonts]
    .filter(face => families.includes(face.family.replace(/["']/g, '')))
    .map(face => `${face.family.replace(/["']/g, '')} ${face.weight} ${face.style} ${face.status}`), RUN_SCREEN_FONTS)
  for (const family of RUN_SCREEN_FONTS) expect(faces.some(face => face.startsWith(`${family} `)), family).toBe(true)
  expect(faces.filter(face => !face.endsWith(' loaded'))).toEqual([])
})
