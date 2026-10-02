// Puts a mood and season on a scene: CSS variables the scene's styles read,
// the cloud count, and rain or snow. The motion loop (useSceneMotion) paints
// it every frame while the mood eases; with no rain at all the rain layer is
// taken out (is-dry), so its drops do not keep animating unseen.
//
// The variables go on the few parts of the scene marked data-weather, not on
// the svg itself: a custom property set on the svg makes the browser restyle
// every one of the scene's thousands of shapes (measured: about 13 ms of a
// week change's 18 ms of style work at 1440 px). Each part names what it
// reads (data-weather="sky", "grass" ...), so a sky that changes does not
// restyle the 256 ground tiles; a part marked data-weather="" gets them all.
import { scenePalette } from './mood.js'

// The variables each kind of part reads.
const READS = {
  sky: ['--lt-sky-top', '--lt-sky-bottom'],
  sun: ['--lt-sun'],
  clouds: ['--lt-cloud-fill'],
  rain: ['--lt-rain'],
  shade: ['--lt-shade'],
  grass: ['--lt-grass-a', '--lt-grass-b'],
  glow: ['--lt-glow'],
  hills: ['--lt-hill-a', '--lt-hill-b', '--lt-meadow'],
}
const ALL = Object.values(READS).flat()

function variables(p) {
  return {
    '--lt-sky-top': p.skyTop, '--lt-sky-bottom': p.skyBottom, '--lt-sun': p.sun.toFixed(2), '--lt-cloud-fill': p.cloudFill,
    '--lt-rain': p.rain.toFixed(2), '--lt-shade': p.shade.toFixed(3), '--lt-grass-a': p.grassA, '--lt-grass-b': p.grassB,
    '--lt-glow': p.glow.toFixed(2), '--lt-hill-a': p.hillA, '--lt-hill-b': p.hillB, '--lt-meadow': p.meadow,
  }
}

// A scene's weather parts, found once, and what was last written to each, so
// painting again writes only what changed.
export function weatherOf(svg) {
  const parts = [...svg.querySelectorAll('[data-weather]')].map(el => {
    const kinds = el.dataset.weather.split(/\s+/).filter(Boolean)
    return { el, names: kinds.length ? kinds.flatMap(kind => READS[kind] ?? []) : ALL, written: {} }
  })
  return {
    parts,
    clouds: [...svg.querySelectorAll('[data-cloud]')].map(el => ({ el, k: Number(el.dataset.cloud), opacity: null })),
    rain: svg.querySelector('[data-layer="rain"]'),
  }
}

export function paintWeather(scene, mood, season) {
  const p = scenePalette(mood, season)
  const vars = variables(p)
  for (const part of scene.parts) {
    for (const name of part.names) {
      if (part.written[name] === vars[name]) continue
      part.written[name] = vars[name]
      part.el.style.setProperty(name, vars[name])
    }
  }
  const shown = p.cloudOpacity.toFixed(2)
  for (const cloud of scene.clouds) {
    const opacity = cloud.k < p.cloudCount ? shown : '0'
    if (cloud.opacity !== opacity) { cloud.opacity = opacity; cloud.el.style.opacity = opacity }
  }
  scene.rain?.classList.toggle('is-snow', p.snow)
  scene.rain?.classList.toggle('is-dry', p.rain <= 0)
}

// Paints a scene once, finding its parts as it goes.
export function applyWeather(svg, mood, season) {
  if (!svg) return
  paintWeather(weatherOf(svg), mood, season)
}
