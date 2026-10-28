import {
  COPY, COUNTED_EVERY_5, METRICS, NUMBER_DERIVED_ROWS, NUMBER_HERO_KEYS,
  WARMUP_TICKS, capitalise, formatMetric, formatMoney, shownValue,
} from '../catalog.js'
import {
  countedAt, countedSeriesUpTo, cumulativeUpTo, rulesAt,
  seriesUpTo, tickIndexAt, valueAt, weeklyCounts,
} from '../data/derive.js'

const isNumber = value => typeof value === 'number' && Number.isFinite(value)
const grouped = new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 })
const keyOf = row => (typeof row === 'string' ? row : row?.key)
const asRow = row => (typeof row === 'string' ? { key: row } : row)
const counted = new Set(COUNTED_EVERY_5)
const outputPercentage = (a, b) => {
  const base = shownValue('salesExceptRentThisWeek', a)
  const other = shownValue('salesExceptRentThisWeek', b)
  return base === 0 ? null : Math.abs(Math.round((other / base - 1) * 100))
}
const sameOutput = (a, b) => formatMetric('salesExceptRentThisWeek', a) === formatMetric('salesExceptRentThisWeek', b)
  || outputPercentage(a, b) === 0

/** Resolve shared metric metadata plus COPY.numbers.rows overrides. */
export function rowDefinition(row) {
  const key = keyOf(row)
  return { ...METRICS[key], ...COPY.numbers.rows[key], ...asRow(row), key }
}

/** Filter rows whose requiresRule is off in every town at tick. */
export function visibleRows(arms, rows, tick) {
  return (rows ?? []).filter(row => !asRow(row).requiresRule || (arms ?? []).some(arm => (
    rulesAt(arm, tick)[asRow(row).requiresRule] === 'on'
  )))
}

function netJobs(arm, tick, definition) {
  const rows = weeklyCounts(arm, definition.sources, tick, definition.weeks)
  const [hired, laidOff] = definition.sources
  if (!rows.length || rows.some(row => !isNumber(row[hired]) || !isNumber(row[laidOff]))) return null
  return rows.reduce((sum, row) => sum + row[hired] - row[laidOff], 0)
}

/** Return [{label,color,value,formatted,measured,asOfTick}] in arm order.
 * Missing readings distinguish never measured from an incomplete reading;
 * measured is per arm through tick. Derived jobs use weeklyCounts; cumulative
 * rows cumulativeUpTo.
 */
export function rowValues(arms, row, tick) {
  const key = keyOf(row)
  const derived = NUMBER_DERIVED_ROWS[key]
  return (arms ?? []).map(arm => {
    let value
    let measured
    let asOfTick = arm.ticks?.[tickIndexAt(arm, tick)] ?? null
    const measuredThroughTick = source => (arm.series?.[source] ?? []).slice(0, tickIndexAt(arm, tick) + 1).some(isNumber)
    if (derived?.kind === 'netJobs') {
      value = netJobs(arm, tick, derived)
      measured = Object.entries(arm.eventCounts ?? {}).some(([week, counts]) => Number(week) <= tick && derived.sources.some(source => isNumber(counts?.[source])))
    } else if (derived?.kind === 'cumulative') {
      value = cumulativeUpTo(arm, derived.source, tick)
      measured = measuredThroughTick(derived.source)
    } else {
      const reading = counted.has(key) ? countedAt(arm, key, tick) : null
      value = counted.has(key) ? reading?.value ?? null : valueAt(arm, key, tick)
      if (counted.has(key)) asOfTick = reading?.asOfTick ?? null
      measured = measuredThroughTick(key)
    }
    if (!isNumber(value)) value = null
    return {
      label: arm.label, color: arm.color, value,
      formatted: value === null ? (measured ? COPY.numbers.missingReading : COPY.numbers.notMeasured) : formatMetric(key, value),
      measured, asOfTick,
    }
  })
}

/** Return [{tick,value}] through tick, using counted weeks for counted metrics
 * and the same derived calculation as rowValues for derived metrics. */
export function rowSeries(arm, row, tick) {
  const key = keyOf(row)
  const derived = NUMBER_DERIVED_ROWS[key]
  if (derived?.kind === 'netJobs') {
    return (arm.ticks ?? []).filter(week => week <= tick).map(week => ({ tick: week, value: netJobs(arm, week, derived) }))
  }
  if (derived?.kind === 'cumulative') {
    let sum = 0
    let complete = true
    return seriesUpTo(arm, derived.source, tick).map(point => {
      if (!isNumber(point.value)) complete = false
      if (complete) sum += point.value
      return { tick: point.tick, value: complete ? sum : null }
    })
  }
  return counted.has(key) ? countedSeriesUpTo(arm, key, tick) : seriesUpTo(arm, key, tick)
}

/** Compare raw numeric readings a/b. Returns better|worse|different|same|
 * notMeasured|warmup. Display equality wins; no judgment at tick <= warmup. */
export function rowStatus(row, a, b, tick = Infinity) {
  if (!isNumber(a) || !isNumber(b)) return 'notMeasured'
  if (tick <= WARMUP_TICKS) return 'warmup'
  const definition = rowDefinition(row)
  if (formatMetric(definition.key, a) === formatMetric(definition.key, b)) return 'same'
  if (!definition.better) return 'different'
  return (definition.better === 'higher') === (b > a) ? 'better' : 'worse'
}

/** Difference B minus A at the displayed precision and units. Output uses a
 * whole percentage of the displayed dollars (unless A shows zero). */
export function differenceWords(row, a, b) {
  if (!isNumber(a) || !isNumber(b)) return ''
  const definition = rowDefinition(row)
  const copy = COPY.numbers.difference
  if (definition.key === 'salesExceptRentThisWeek' && sameOutput(a, b)) return copy.aboutSame
  if (formatMetric(definition.key, a) === formatMetric(definition.key, b)) return copy.same
  const base = shownValue(definition.key, a)
  const delta = shownValue(definition.key, b) - base
  const amount = Math.abs(delta)
  const more = delta > 0
  if (definition.key === 'salesExceptRentThisWeek' && base !== 0) {
    return copy.percentage(outputPercentage(a, b), more)
  }
  if (definition.format === 'money') {
    return (more ? copy.more : copy.less)(formatMoney(amount))
  }
  if (definition.format === 'price') {
    return (more ? copy.more : copy.less)(`$${amount.toFixed(2)}`)
  }
  if (definition.format === 'ratio') return (more ? copy.higher : copy.lower)(amount.toFixed(2))
  if (definition.format === 'outOf100' || definition.format === 'percent') {
    return (more ? copy.higher : copy.lower)(copy.points(amount))
  }
  return (more ? copy.more : copy.fewer)(grouped.format(amount))
}

/** Only identical displayed values fold. Missing, one-town, open rows and
 * heroes never fold. */
export function shouldFold(row, values, open = false) {
  if (open || NUMBER_HERO_KEYS.includes(keyOf(row)) || (values?.length ?? 0) < 2) return false
  if (values.some(reading => reading.measured === false || !isNumber(reading.value))) return false
  const key = keyOf(row)
  const baseFormatted = formatMetric(key, values[0].value)
  return values.every(reading => formatMetric(key, reading.value) === baseFormatted)
}

/** Return the next folded metric keys (an array). While paused, recompute
 * displayed equality fully. While playing, a previous fold can only survive
 * or be promoted to a row: newly equal rows wait until the next pause. Open
 * rows, missing readings and rows hidden by current rules never remain folded.
 */
export function nextFoldKeys(arms, rows, tick, previousKeys, playing, openKeys = []) {
  const previous = new Set(previousKeys ?? [])
  const open = new Set(openKeys)
  return visibleRows(arms, rows, tick)
    .filter(row => (!playing || previous.has(keyOf(row))) && shouldFold(row, rowValues(arms, row, tick), open.has(keyOf(row))))
    .map(keyOf)
}

/** Already-selected folded rows -> [{kind:'equal', label, items}].
 * items: {key,name,values:[formatted strings],equal}; equal values occur once.
 */
export function foldLines(arms, rows, tick) {
  if ((arms?.length ?? 0) < 2) return []
  const equal = []
  for (const row of rows ?? []) {
    const definition = rowDefinition(row)
    const readings = rowValues(arms, row, tick)
    if (readings.some(reading => !reading.measured || !isNumber(reading.value))) continue
    const values = readings.map(reading => reading.formatted)
    if (!values.every(value => value === values[0])) continue
    equal.push({ key: definition.key, name: definition.name, values: [values[0]], equal: true })
  }
  return [
    ...(equal.length ? [{ kind: 'equal', label: COPY.numbers.fold.equal(arms.length), items: equal }] : []),
  ]
}

/** Counts per non-control town from current displayed values. Includes heroes
 * once and visible rows; warm-up/one-town => []; unmeasured pairs omitted.
 * Fold placement never overrides a row's current comparison status. */
export function tally(arms, rows, tick) {
  if ((arms?.length ?? 0) < 2 || tick <= WARMUP_TICKS) return []
  const unique = new Map([...NUMBER_HERO_KEYS, ...visibleRows(arms, rows, tick)].map(row => [keyOf(row), row]))
  const counts = arms.slice(1).map(arm => ({ label: arm.label, color: arm.color, better: 0, worse: 0, different: 0, same: 0 }))
  for (const row of unique.values()) {
    const values = rowValues(arms, row, tick)
    counts.forEach((count, index) => {
      const base = values[0]
      const other = values[index + 1]
      if (!base.measured || !other.measured || !isNumber(base.value) || !isNumber(other.value)) return
      const status = rowStatus(row, base.value, other.value, tick)
      if (Object.hasOwn(count, status)) count[status] += 1
    })
  }
  return counts
}

function listedParts(rows, wordFor) {
  const copy = COPY.numbers.verdict
  return rows.flatMap((row, index) => [
    ...(index ? [{ text: index === rows.length - 1 ? copy.and : copy.comma }] : []),
    { text: wordFor(row, index), rowId: keyOf(row) },
  ])
}

/** Per comparison town [{label,color,parts:[{text,rowId?}]}]. Joined text
 * matches the approved demo sentence. Warm-up and one-town => []. Only rows
 * with a verdictWord can be named. Every verdict identifies its town. */
export function verdictParts(arms, rows, tick) {
  if ((arms?.length ?? 0) < 2 || tick <= WARMUP_TICKS) return []
  const named = visibleRows(arms, rows, tick).map(rowDefinition).filter(row => row.verdictWord)
  const copy = COPY.numbers.verdict
  const readings = new Map(named.map(row => [row.key, rowValues(arms, row, tick)]))
  const feelings = rowValues(arms, 'happiness', tick)
  return arms.slice(1).map((arm, index) => {
    const townIndex = index + 1
    const parts = []
    const append = text => parts.push({ text })
    const between = () => { if (parts.length) append(copy.space) }
    const status = row => {
      const values = readings.get(row.key)
      return rowStatus(row, values[0].value, values[townIndex].value, tick)
    }
    const feeling = rowStatus('happiness', feelings[0].value, feelings[townIndex].value, tick)
    const leads = named.filter(row => ['jobs', 'pay', 'savings', 'businesses'].includes(row.verdictWord))
      .sort((a, b) => ['jobs', 'pay', 'savings', 'businesses'].indexOf(a.verdictWord) - ['jobs', 'pay', 'savings', 'businesses'].indexOf(b.verdictWord))
    const ahead = leads.filter(row => status(row) === 'better')
    const behind = leads.filter(row => status(row) === 'worse')
    const groups = [{ rows: ahead, prefix: copy.ahead }, { rows: behind, prefix: copy.behind }].filter(group => group.rows.length)
    groups.forEach((group, groupIndex) => {
      between()
      append(group.prefix(arm.label))
      parts.push(...listedParts(group.rows, row => copy.words[row.verdictWord]))
      const last = groupIndex === groups.length - 1
      append(last && ['better', 'worse', 'same'].includes(feeling)
        ? ({ better: copy.feelBetter, worse: copy.feelWorse, same: copy.feelSame })[feeling]
        : copy.stop)
    })
    if (!groups.length && ['better', 'worse'].includes(feeling)) append(copy.feelOnly(arm.label, copy.feeling[feeling]))

    const prices = named.filter(row => ['food', 'services'].includes(row.verdictWord))
    for (const [priceStatus, plural, singular] of [
      ['worse', copy.costMore, copy.costMoreSingular],
      ['better', copy.costLess, copy.costLessSingular],
    ]) {
      const changed = prices.filter(row => status(row) === priceStatus)
      if (!changed.length) continue
      between()
      parts.push(...listedParts(changed, (row, i) => i === 0 ? capitalise(copy.words[row.verdictWord]) : copy.words[row.verdictWord].toLowerCase()))
      const singularSubject = changed.length === 1 && copy.singularWords.includes(changed[0].verdictWord)
      append(singularSubject ? singular : plural)
    }

    const gap = named.find(row => row.verdictWord === 'gap' && status(row) !== 'notMeasured')
    const poorer = named.find(row => row.verdictWord === 'poorerHalf' && status(row) !== 'notMeasured')
    if (gap) {
      between()
      append(copy.gapStart)
      parts.push({ text: copy.words.gap, rowId: gap.key })
      append(({ same: copy.gapSame, worse: copy.gapHigher, better: copy.gapLower })[status(gap)])
    }
    if (poorer) {
      const values = readings.get(poorer.key)
      const poorerDirection = status(poorer) === 'same' ? 'same' : values[townIndex].value < values[0].value ? 'worse' : 'better'
      if (gap) append(status(gap) === poorerDirection ? copy.poorerAnd : copy.poorerStart)
      else { between(); append(copy.poorerOnly) }
      parts.push({ text: copy.words.poorerHalf, rowId: poorer.key })
      append((status(poorer) === 'same' ? copy.poorerSame : values[townIndex].value < values[0].value ? copy.poorerLess : copy.poorerMore)(arm.label))
    } else if (gap) append(copy.gapTown(arm.label))

    if (!parts.length) {
      const measured = leads.some(row => status(row) !== 'notMeasured') || feeling !== 'notMeasured'
      append((measured ? copy.noNamedDifference : copy.noComparison)(arm.label))
    }
    if ((arms.length > 2 && !parts[0].text.includes(arm.label)) || !parts.some(part => part.text.includes(arm.label))) {
      parts.unshift({ text: copy.townLead(arm.label) })
    }
    return { label: arm.label, color: arm.color, parts }
  })
}

/** Price note only for higher output that survives rounding after warm-up and
 * a visibly higher food, services or healthcare price; rent is not in output.
 * Same-start note only if all displayed starts are known and agree, and the
 * start does not repeat any current displayed reading. */
export function heroNotes(arms, row, tick) {
  const key = keyOf(row)
  if (key === 'salesExceptRentThisWeek' && (arms?.length ?? 0) > 1) {
    if (tick <= WARMUP_TICKS) return []
    const output = rowValues(arms, key, tick)
    const prices = ['priceFood', 'priceServices', 'priceHealthcare'].map(price => ({
      key: price, values: rowValues(arms, price, tick),
    }))
    return arms.slice(1).flatMap((arm, i) => {
      const a = output[0].value
      const b = output[i + 1].value
      if (!isNumber(a) || !isNumber(b) || b <= a || sameOutput(a, b)) return []
      const higher = prices.some(price => rowStatus(price.key, price.values[0].value, price.values[i + 1].value) === 'worse')
      if (!higher) return []
      return [arms.length === 2 ? COPY.numbers.heroes.priceNote : COPY.numbers.heroes.priceNoteTown(arm.label)]
    })
  }
  if (key !== 'happiness' || !arms?.length) return []
  const starts = arms.map(arm => seriesUpTo(arm, key, tick)[0]?.value ?? null)
  if (starts.some(value => !isNumber(value))) return []
  const formatted = starts.map(value => formatMetric(key, value))
  if (!formatted.every(value => value === formatted[0])) return []
  if (rowValues(arms, key, tick).some(reading => reading.formatted === formatted[0])) return []
  return [COPY.numbers.heroes.sameStart(arms.length, Math.round(starts[0]))]
}
