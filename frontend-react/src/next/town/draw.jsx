// A line between two points, for the diorama's parts (homes.jsx, shops.jsx,
// civic.jsx).
import { r1 } from './geometry.js'

export function Line({ a, b, ...rest }) {
  return <line x1={r1(a[0])} y1={r1(a[1])} x2={r1(b[0])} y2={r1(b[1])} {...rest} />
}
