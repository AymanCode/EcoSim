// Puts a mood and season on a scene: CSS variables the scene's styles read,
// the cloud count, and rain or snow. Task 6 calls it every frame while the
// mood eases; here it runs once per week change. With no rain at all the rain
// layer is taken out (is-dry), so its drops do not keep animating unseen.
//
// The variables go on the few parts of the scene marked data-weather (the
// sky, sun, clouds, ground, shade, glows and rain), not on the svg itself: a
// custom property set on the svg makes the browser restyle every one of the
// scene's thousands of shapes (measured: about 13 ms of a week change's 18 ms
// of style work at 1440 px), while these parts hold a few hundred.
import { scenePalette } from './mood.js'

export function applyWeather(svg, mood, season) {
  if (!svg) return
  const p = scenePalette(mood, season)
  const vars = {
    '--lt-sky-top': p.skyTop, '--lt-sky-bottom': p.skyBottom, '--lt-sun': p.sun.toFixed(2), '--lt-cloud-fill': p.cloudFill,
    '--lt-rain': p.rain.toFixed(2), '--lt-shade': p.shade.toFixed(3), '--lt-grass-a': p.grassA, '--lt-grass-b': p.grassB,
    '--lt-glow': p.glow.toFixed(2), '--lt-hill-a': p.hillA, '--lt-hill-b': p.hillB, '--lt-meadow': p.meadow,
  }
  const parts = svg.querySelectorAll('[data-weather]')
  for (const [name, value] of Object.entries(vars)) parts.forEach(part => part.style.setProperty(name, value))
  svg.querySelectorAll('[data-cloud]').forEach(cloud => {
    cloud.style.opacity = Number(cloud.dataset.cloud) < p.cloudCount ? p.cloudOpacity.toFixed(2) : '0'
  })
  const rain = svg.querySelector('[data-layer="rain"]')
  rain?.classList.toggle('is-snow', p.snow)
  rain?.classList.toggle('is-dry', p.rain <= 0)
}
