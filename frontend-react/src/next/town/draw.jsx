// Small parts both drawings share: a line between two points (the
// diorama's homes.jsx, shops.jsx and civic.jsx), and a standing person (the
// queues outside the town halls, civic.jsx and streetParts.jsx).
import { r1 } from './geometry.js'
import { FIGURE } from './nodes.js'

export function Line({ a, b, ...rest }) {
  return <line x1={r1(a[0])} y1={r1(a[1])} x2={r1(b[0])} y2={r1(b[1])} {...rest} />
}

// A person standing at (x, y), as the motion loop's figureNode draws one.
export function Figure({ x, y, shirt, carry = false, scale = 1 }) {
  const { body, head, box } = FIGURE
  return (
    <g className="lt-walker" transform={`translate(${r1(x)} ${r1(y)})${scale === 1 ? '' : ` scale(${scale})`}`}>
      <path d={FIGURE.legs} strokeWidth={0.9} fill="none" />
      <line x1={body.x1} y1={body.y1} x2={body.x2} y2={body.y2} stroke={shirt} strokeWidth={body.width} />
      <circle cx={head.cx} cy={head.cy} r={head.r} fill={head.fill} stroke="none" />
      {carry && <rect x={box.x} y={box.y} width={box.width} height={box.height} fill={box.fill} stroke={box.stroke} strokeWidth={box.strokeWidth} />}
    </g>
  )
}
