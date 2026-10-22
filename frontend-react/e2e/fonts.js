// The Run screen's two web fonts (--nx-disp and --nx-body), which next.css
// imports from Google Fonts.
export const RUN_SCREEN_FONTS = ['Bricolage Grotesque', 'Instrument Sans']

const DECLARED_MS = 30_000

// Waits until the Run screen draws with its own fonts. document.fonts.ready
// is not enough: it settles as soon as nothing is loading, which can be before
// next.css has declared these faces, and a font that arrives later reflows
// text in the middle of a layout check.
export async function runScreenFonts(page) {
  // Polled synchronously: waitForFunction takes a returned promise as success.
  await page.waitForFunction(families => families.every(family => [...document.fonts]
    .some(face => face.family.replace(/["']/g, '') === family)), RUN_SCREEN_FONTS, { timeout: DECLARED_MS })
    .catch(error => {
      throw new Error(`${RUN_SCREEN_FONTS.join(' and ')} were not declared within ${DECLARED_MS / 1000} s; the Run screen loads them from Google Fonts. ${error.message}`)
    })
  // Every face of both families, each weight and subset, not only those the
  // first paint asked for.
  await page.evaluate(families => Promise.all([...document.fonts]
    .filter(face => families.includes(face.family.replace(/["']/g, '')))
    .map(face => face.load())).then(() => true), RUN_SCREEN_FONTS)
  await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))))
}
