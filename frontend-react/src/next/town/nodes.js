// What the town drawings share with the motion loop (Task 6), which adds and
// moves walkers, cars and floating signs without React: the scene colours that
// are not mood-driven, the shape of a walking figure and of a sign pill, and
// plain-DOM builders for them. Ported from mockup 08 (figure, carShape, tagPill).
import { iso, pts } from './geometry.js'
import { mix } from './mood.js'

const NS = 'http://www.w3.org/2000/svg'
const r1 = value => Math.round(value * 10) / 10

// Shop walls (left face, right face) and awning, by sector; closed shops are grey.
export const SHOP_COLOURS = {
  Food: { l: '#F2BC8D', r: '#D99567', a: '#D07A45' },
  Housing: { l: '#ADC6DA', r: '#86A3BC', a: '#5F86AA' },
  Services: { l: '#A3D2B6', r: '#79B193', a: '#4E9671' },
  Healthcare: { l: '#F1B6C3', r: '#D48EA1', a: '#C0627B' },
  PublicWorks: { l: '#E4D199', r: '#C6B173', a: '#A88F45' },
  Other: { l: '#D8D0C2', r: '#BAB1A2', a: '#8E8576' },
}
export const CLOSED_COLOURS = { l: '#D3CCC0', r: '#B9B1A4', a: '#8F877A' }
export const shopColours = (sector, closed) => (closed ? CLOSED_COLOURS : SHOP_COLOURS[sector] ?? SHOP_COLOURS.Other)

// Coins by the money they carry.
export const FLOW_COLOURS = { spend: '#E3A92B', pay: '#3B9B68', tax: '#7B61C6', help: '#2696AB' }
export const CAR_COLOURS = ['#D9534F', '#4F7CC9', '#F2C14E', '#5BA37A', '#EDE7DC', '#8A6FC4', '#E58A4B']
export const SHIRTS = ['#4F7CC9', '#D07A45', '#5BA37A', '#8A6FC4', '#C0627B', '#3F8FA0']

// Sign pills: text colour and fill per kind of sign.
export const PILL_TONES = {
  hiring: { fg: '#2F7D52', bg: '#E7F4EC' },
  closed: { fg: '#C8483B', bg: '#FBEDEA' },
  fresh: { fg: '#1F7F94', bg: '#E3F3F6' },
  more: { fg: '#6F675B', bg: '#FBF8F1' },
}

// A pill's box around its centre for a label at a font size.
export function pillBox(label, size = 5.6) {
  const w = String(label).length * size * 0.68 + 8
  return { x: r1(-w / 2), y: r1(-size * 0.95), width: r1(w), height: r1(size * 1.9), rx: r1(size * 0.95) }
}

// A person standing at (0, 0): legs, body in the shirt colour, head, and a box
// when carrying their things home.
export const FIGURE = {
  legs: 'M0 -2.6 l-1 2.6 M0 -2.6 l1 2.6',
  body: { x1: 0, y1: -2.6, x2: 0, y2: -6.4, width: 2.2 },
  head: { cx: 0, cy: -8, r: 1.45, fill: '#5A4636' },
  box: { x: 0.6, y: -5.6, width: 2.8, height: 2.3, fill: '#C49A66', stroke: '#8A6440', strokeWidth: 0.4 },
}

function el(doc, tag, attrs, parent) {
  const node = doc.createElementNS(NS, tag)
  for (const [name, value] of Object.entries(attrs)) node.setAttribute(name, String(value))
  if (parent) parent.appendChild(node)
  return node
}

// A walking figure for the motion loop. Returns the group and its legs, whose
// `d` the loop swings as it walks.
export function figureNode(doc, shirt, carry = false) {
  const g = el(doc, 'g', { class: 'lt-walker' })
  const legs = el(doc, 'path', { d: FIGURE.legs, 'stroke-width': 0.9, fill: 'none' }, g)
  const { body, head, box } = FIGURE
  el(doc, 'line', { x1: body.x1, y1: body.y1, x2: body.x2, y2: body.y2, stroke: shirt, 'stroke-width': body.width }, g)
  el(doc, 'circle', { cx: head.cx, cy: head.cy, r: head.r, fill: head.fill, stroke: 'none' }, g)
  if (carry) el(doc, 'rect', { x: box.x, y: box.y, width: box.width, height: box.height, fill: box.fill, stroke: box.stroke, 'stroke-width': box.strokeWidth }, g)
  return { g, legs }
}

// A small car drawn around (0, 0), facing along the x or y road; the loop
// moves it with a translate.
export function carNode(doc, axis, colour) {
  const g = el(doc, 'g', { class: 'lt-car' })
  const [hx, hy] = axis === 'x' ? [0.24, 0.12] : [0.12, 0.24]
  const [cx, cy] = axis === 'x' ? [0.12, 0.1] : [0.1, 0.12]
  const face = (list, fill) => el(doc, 'polygon', { points: pts(list), fill }, g)
  const box = (ax, ay, z0, z1, top, left, right) => {
    face([iso(-ax, ay, z0), iso(ax, ay, z0), iso(ax, ay, z1), iso(-ax, ay, z1)], left)
    face([iso(ax, -ay, z0), iso(ax, ay, z0), iso(ax, ay, z1), iso(ax, -ay, z1)], right)
    face([iso(-ax, -ay, z1), iso(ax, -ay, z1), iso(ax, ay, z1), iso(-ax, ay, z1)], top)
  }
  el(doc, 'ellipse', { cx: 0, cy: 1.5, rx: 8, ry: 3.2, fill: 'rgba(40,40,30,.18)' }, g)
  box(hx, hy, 0.6, 4.2, mix(colour, '#ffffff', 0.25), colour, mix(colour, '#000000', 0.22))
  box(cx, cy, 4.2, 7, '#EAF2F8', '#A9C3D6', '#8FAABF')
  return g
}

// A floating sign pill centred at (x, y), for this week's moments.
export function pillNode(doc, x, y, label, tone, size = 7) {
  const { fg, bg } = PILL_TONES[tone] ?? tone
  const g = el(doc, 'g', { class: 'lt-pill', transform: `translate(${r1(x)} ${r1(y)})` })
  el(doc, 'rect', { ...pillBox(label, size), fill: bg, stroke: fg, 'stroke-width': 0.6 }, g)
  const text = el(doc, 'text', { x: 0, y: 0.4, 'font-size': size, fill: fg }, g)
  text.textContent = label
  return g
}
