import { useEffect, useId, useMemo, useState } from 'react'
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceArea,
  ReferenceDot,
  ReferenceLine,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import useMeasured from './useMeasured.js'
import { toneVar } from './tones.js'

// Ported from `drawChart` in docs/superpowers/specs/2026-09-06-prototype.html,
// rebuilt on Recharts primitives instead of hand-rolled SVG.

const MARKERS_MIN_WIDTH = 470

// Pure alignment: the x domain is the union of every series' ticks, and a
// series missing a given tick is `null` there — never a fabricated 0 — so
// Recharts' `connectNulls` (not zero-fill) is what bridges the gap visually.
// Exported (rather than split into its own module) so TimeSeries.test.jsx
// can assert its contract directly; that mixes a non-component export into
// a component file, which react-refresh's fast-refresh rule flags — the
// helper is pure and stateless, so refresh correctness isn't actually at risk.
// eslint-disable-next-line react-refresh/only-export-components
export function alignByTick(series, n = 250) {
  const sliced = (series || []).map(s => (s.data || []).slice(-n))
  const tickSet = new Set()
  sliced.forEach(data => data.forEach(d => tickSet.add(d.tick)))
  const ticks = Array.from(tickSet).sort((a, b) => a - b)
  const valueMaps = sliced.map(data => new Map(data.map(d => [d.tick, d.value])))
  return ticks.map(t => {
    const row = { tick: t }
    valueMaps.forEach((m, idx) => {
      row[`s${idx}`] = m.has(t) ? m.get(t) : null
    })
    return row
  })
}

function ChartTooltip({ active, payload, label, format, series }) {
  if (!active || !payload || !payload.length) return null
  return (
    <div className="tip">
      <span className="muted">{`t${label}`}</span>
      {series.map((s, idx) => {
        // In split mode the visible Area/Line only ever carry the
        // `pre{idx}`/`post{idx}` segment currently on screen, not the
        // full-domain `s{idx}` key, so check every dataKey this series
        // could be rendered under and take whichever one has a value here.
        const entry = payload.find(
          p => (p.dataKey === `s${idx}` || p.dataKey === `pre${idx}` || p.dataKey === `post${idx}`) && p.value != null
        )
        if (!entry) return null
        return (
          <div key={idx}>
            {s.name ? `${s.name} ` : ''}<b>{format(entry.value)}</b>
          </div>
        )
      })}
    </div>
  )
}

export default function TimeSeries({
  series,
  format,
  axes = true,
  endLabel = false,
  band,
  markers,
  split,
  n = 250,
  height = 150,
}) {
  const [ref, measured] = useMeasured()
  const { width, height: measuredHeight } = measured
  const fmt = format || (v => v)
  const uid = useId()

  // Draw-in animation plays once, on first mount. `animate` starts `true` so
  // Recharts' JavascriptAnimate sees `isAnimationActive` true on the very
  // first committed render. It flips to `false` when the Area's own animation
  // completes (`onAnimationEnd`), or when a 1500 ms hard-stop timer fires
  // (preventing continuous animation restarts if data frames arrive every ~100 ms).
  // After that, every render passes `isAnimationActive={false}`.
  const [animate, setAnimate] = useState(true)

  useEffect(() => {
    const timer = setTimeout(() => {
      setAnimate(false)
    }, 1500)
    return () => clearTimeout(timer)
  }, [])

  const slicedSeries = useMemo(
    () => (series || []).map(s => ({ ...s, data: (s.data || []).slice(-n) })),
    [series, n]
  )

  const splitTick = split ? split.tick : null

  const baseRows = useMemo(() => alignByTick(series, n), [series, n])

  const rows = useMemo(() => {
    if (!split) return baseRows
    // Split mode: the grey pre-split segment and the coloured post-split
    // segment share the split tick itself (both carry its value) so the two
    // segments meet with no visual gap at the boundary.
    return baseRows.map(row => {
      const next = { ...row }
      slicedSeries.forEach((_, idx) => {
        const v = row[`s${idx}`]
        next[`pre${idx}`] = row.tick <= splitTick ? v : null
        next[`post${idx}`] = row.tick >= splitTick ? v : null
      })
      return next
    })
  }, [baseRows, split, splitTick, slicedSeries])

  const lastTick = baseRows.length ? baseRows[baseRows.length - 1].tick : 0
  const firstTick = baseRows.length ? baseRows[0].tick : 0

  const xTicks = useMemo(() => {
    if (!baseRows.length) return [0]
    if (firstTick === lastTick) return [firstTick]
    const span = lastTick - firstTick
    const raw = [0, 0.25, 0.5, 0.75, 1].map(f => Math.round(firstTick + f * span))
    return [...new Set(raw)]
  }, [baseRows.length, firstTick, lastTick])

  const allValues = useMemo(
    () => baseRows.flatMap(r => slicedSeries.map((_, idx) => r[`s${idx}`]).filter(v => v != null)),
    [baseRows, slicedSeries]
  )
  const rawLo = allValues.length ? Math.min(...allValues) : 0
  const rawHi = allValues.length ? Math.max(...allValues) : 1
  // Headroom matches the prototype's `drawChart`: -4% / +6% of the value
  // span, so extreme points don't sit flush on the plot's own gridlines.
  const valueSpan = (rawHi - rawLo) || Math.abs(rawHi) || 1
  const valueLo = rawLo - valueSpan * 0.04
  const valueHi = rawHi + valueSpan * 0.06
  const yTicks = valueLo === valueHi ? [valueLo] : [valueLo, (valueLo + valueHi) / 2, valueHi]

  const showMarkers = Boolean(markers && markers.length && width >= MARKERS_MIN_WIDTH)

  const margin = {
    top: markers && markers.length ? 14 : 8,
    right: endLabel ? 78 : 12,
    left: 8,
    bottom: 8,
  }

  return (
    <div
      ref={ref}
      className="chart"
      data-animating={animate ? 'true' : 'false'}
      style={{ minHeight: height ?? 150 }}
    >
      {width > 0 && measuredHeight > 0 && (
        <ComposedChart width={width} height={measuredHeight} data={rows} margin={margin}>
          <defs>
            {slicedSeries.map((s, idx) => (
              <linearGradient key={idx} id={`ts-grad-${uid}-${idx}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={toneVar(s.tone)} stopOpacity={0.14} />
                <stop offset="100%" stopColor={toneVar(s.tone)} stopOpacity={0} />
              </linearGradient>
            ))}
          </defs>

          {axes ? (
            <>
              <CartesianGrid horizontal vertical={false} stroke={toneVar('grid')} />
              <XAxis
                dataKey="tick"
                type="number"
                domain={[firstTick, lastTick]}
                ticks={xTicks}
                tickFormatter={t => `t${t}`}
                className="axis"
                tickLine={false}
                axisLine={false}
              />
              <YAxis
                domain={[valueLo, valueHi]}
                ticks={yTicks}
                tickFormatter={fmt}
                className="axis"
                tickLine={false}
                axisLine={false}
                width={44}
              />
            </>
          ) : (
            <>
              <XAxis dataKey="tick" type="number" domain={[firstTick, lastTick]} hide />
              <YAxis domain={[valueLo, valueHi]} hide />
            </>
          )}

          <Tooltip
            content={<ChartTooltip format={fmt} series={slicedSeries} />}
            cursor={{ stroke: toneVar('ink3'), strokeDasharray: '3 3' }}
            isAnimationActive={false}
          />

          {band && (
            <ReferenceArea y1={band[0]} y2={band[1]} fill={toneVar('crit')} fillOpacity={0.07} stroke="none" ifOverflow="hidden" />
          )}

          {split && (
            <ReferenceArea x1={splitTick} x2={lastTick} fill={split.color} fillOpacity={0.07} stroke="none" ifOverflow="hidden" />
          )}

          {slicedSeries.map((s, idx) => (
            <Area
              key={`area-${idx}`}
              type="monotone"
              dataKey={split ? `post${idx}` : `s${idx}`}
              stroke={toneVar(s.tone)}
              strokeWidth={2}
              fill={`url(#ts-grad-${uid}-${idx})`}
              fillOpacity={1}
              connectNulls={!split}
              isAnimationActive={animate}
              onAnimationEnd={() => setAnimate(false)}
              dot={false}
            />
          ))}

          {split && slicedSeries.map((s, idx) => (
            <Line
              key={`pre-${idx}`}
              type="monotone"
              dataKey={`pre${idx}`}
              stroke={toneVar('ink4')}
              strokeWidth={1.5}
              dot={false}
              connectNulls={false}
              isAnimationActive={animate}
            />
          ))}

          {split && (
            <ReferenceLine x={splitTick} stroke={split.color} strokeWidth={1.5} ifOverflow="visible" />
          )}

          {showMarkers && markers.map((m, idx) => {
            const color = toneVar(m.ai ? 'ai' : 'acc')
            return (
              <ReferenceLine
                key={`mk-${idx}`}
                x={m.tick}
                stroke={color}
                strokeWidth={1.5}
                strokeDasharray={m.ok === false ? '3 3' : undefined}
                ifOverflow="visible"
                label={labelProps => {
                  const x = labelProps.x ?? labelProps.viewBox?.x ?? 0
                  const topY = labelProps.viewBox?.y ?? 0
                  const nearRight = x > width * 0.7
                  const y = topY + 11 + (idx % 2) * 13
                  return (
                    <g className="mk">
                      <circle cx={x} cy={topY} r={3} style={{ fill: color }} />
                      <text
                        x={nearRight ? x - 6 : x + 6}
                        y={y}
                        textAnchor={nearRight ? 'end' : 'start'}
                        style={{ fill: color }}
                      >
                        {(m.ai ? 'AI · ' : '') + m.label}
                      </text>
                    </g>
                  )
                }}
              />
            )
          })}

          {slicedSeries.map((s, idx) => {
            const last = s.data[s.data.length - 1]
            if (!last) return null
            const color = toneVar(s.tone)
            return (
              <ReferenceDot
                key={`end-${idx}`}
                x={last.tick}
                y={last.value}
                r={4.5}
                ifOverflow="visible"
                shape={dotProps => (
                  <g>
                    <circle cx={dotProps.cx} cy={dotProps.cy} r={7} style={{ fill: toneVar('panel') }} />
                    <circle cx={dotProps.cx} cy={dotProps.cy} r={4.5} style={{ fill: color }} />
                    {endLabel && (
                      <>
                        <text x={dotProps.cx + 11} y={dotProps.cy + 4} className="endlab">{fmt(last.value)}</text>
                        <text x={dotProps.cx + 11} y={dotProps.cy + 16} className="endsub">{s.name}</text>
                      </>
                    )}
                  </g>
                )}
              />
            )
          })}
        </ComposedChart>
      )}
    </div>
  )
}
