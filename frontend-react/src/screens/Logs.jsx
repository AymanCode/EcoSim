import { useEffect, useMemo, useRef } from 'react'
import PageHeader from '../ui/PageHeader.jsx'
import Panel from '../ui/Panel.jsx'
import Chip from '../ui/Chip.jsx'
import KeyValue from '../ui/KeyValue.jsx'
import StatTile from '../ui/StatTile.jsx'
import { Search } from '../ui/Inputs.jsx'
import { formatInteger, ms } from '../format.js'
import { normalizeLog, LOG_TYPES } from '../logs.js'

function severityDotColor(log) {
  const sev = (log?.sev || log?.severity || 'info').toLowerCase()
  if (sev === 'error') return 'var(--crit)'
  if (sev === 'warning' || sev === 'warn') return 'var(--warn)'
  return 'var(--ink4)'
}

function severityTone(log) {
  const sev = (log?.sev || log?.severity || 'info').toLowerCase()
  if (sev === 'error') return 'crit'
  if (sev === 'warning' || sev === 'warn') return 'warn'
  return undefined
}

const SEVERITY_OPTIONS = [
  { value: 'All', label: 'All severities' },
  { value: 'Info', label: 'Info' },
  { value: 'Warning', label: 'Warning' },
  { value: 'Error', label: 'Error' },
]

export function RawJsonBlock({ value }) {
  if (!value) return null
  const json = JSON.stringify(value, null, 2)
  const renderLine = (line, index) => {
    const match = line.match(/^(\s*)"([^"]+)":\s?(.*?)(,?)$/)
    if (!match) {
      return (
        <div key={index} style={{ color: 'var(--ink4)' }}>
          {line || ' '}
        </div>
      )
    }
    const [, indent, key, rawValue, comma] = match
    const trimmed = rawValue.trim()
    const valueColor = trimmed.startsWith('"')
      ? 'var(--ink2)'
      : trimmed === 'true' || trimmed === 'false'
        ? 'var(--acc)'
        : trimmed === 'null'
          ? 'var(--ink4)'
          : 'var(--ink3)'
    return (
      <div key={index}>
        <span style={{ color: 'var(--ink4)' }}>{indent}"</span>
        <span style={{ color: 'var(--acc)' }}>{key}</span>
        <span style={{ color: 'var(--ink4)' }}>": </span>
        <span style={{ color: valueColor }}>{rawValue}</span>
        <span style={{ color: 'var(--ink4)' }}>{comma}</span>
      </div>
    )
  }

  return (
    <pre
      className="json"
      style={{
        marginTop: 4,
        maxHeight: 260,
        overflow: 'auto',
        fontFamily: 'var(--mono)',
        fontSize: '11px',
        background: 'var(--page)',
        border: '1px solid var(--line)',
        borderRadius: 5,
        padding: 10,
        color: 'var(--ink3)',
        whiteSpace: 'pre-wrap',
        wordBreak: 'break-word',
        lineHeight: 1.5,
      }}
    >
      {json.split('\n').map(renderLine)}
    </pre>
  )
}

export default function Logs({
  logs = [],
  tick = 0,
  metrics = {},
  logIndex,
  selectedLogId,
  logId,
  onSelectLog,
  typeFilter = 'All',
  onTypeFilter,
  severityFilter = 'All',
  onSeverityFilter,
  search = '',
  onSearch,
  density = 'comfortable',
  onDensity,
  autoScroll = false,
  onAutoScroll,
  histories = {},
}) {
  const logsContainerRef = useRef(null)

  const tickHist = histories || {}

  const normalizedLogs = useMemo(() => {
    const tickCounts = new Map()
    return (logs || []).map((l, i) => {
      const t = l.tick ?? 0
      const count = tickCounts.get(t) || 0
      tickCounts.set(t, count + 1)
      return normalizeLog(l, i, l.indexWithinTick != null ? l.indexWithinTick : count)
    })
  }, [logs])

  const typeCounts = useMemo(() => {
    const counts = { All: normalizedLogs.length }
    LOG_TYPES.forEach((t) => {
      if (t !== 'All') counts[t] = 0
    })
    normalizedLogs.forEach((l) => {
      counts[l.type] = (counts[l.type] || 0) + 1
    })
    return counts
  }, [normalizedLogs])

  const filteredLogs = useMemo(() => {
    const q = (search || '').trim().toLowerCase()
    return normalizedLogs.filter((log) => {
      const matchesSearch =
        !q || `${log.tick} ${log.type} ${log.entity} ${log.message}`.toLowerCase().includes(q)
      const matchesType =
        !typeFilter ||
        typeFilter === 'All' ||
        log.type === typeFilter
      const matchesSeverity =
        !severityFilter ||
        severityFilter === 'All' ||
        log.severity === severityFilter ||
        log.sev === severityFilter.toLowerCase()
      return matchesSearch && matchesType && matchesSeverity
    })
  }, [normalizedLogs, search, typeFilter, severityFilter])

  const isNumericMode = selectedLogId === undefined && logId === undefined && typeof logIndex === 'number'

  const selectedLog = useMemo(() => {
    if (filteredLogs.length === 0) return null
    const targetId = selectedLogId ?? logId ?? (typeof logIndex === 'string' ? logIndex : null)
    if (targetId) {
      const found = filteredLogs.find((l) => l.id === targetId)
      if (found) return found
    }
    if (isNumericMode && logIndex >= 0 && logIndex < filteredLogs.length) {
      return filteredLogs[logIndex]
    }
    return filteredLogs[filteredLogs.length - 1] || null
  }, [filteredLogs, selectedLogId, logId, logIndex, isNumericMode])

  const sameEntityLogs = useMemo(() => {
    if (!selectedLog || !selectedLog.entity) return []
    return normalizedLogs
      .filter((l) => l.entity === selectedLog.entity && l.id !== selectedLog.id)
      .slice(-6)
      .reverse()
  }, [selectedLog, normalizedLogs])

  const recentMinTick = Math.max(0, (tick || 0) - 60)
  const recentWarnings = useMemo(() => {
    return normalizedLogs.filter((l) => {
      const isWarn = l.severity === 'Warning' || l.sev === 'warning'
      return isWarn && (tick > 0 ? l.tick >= recentMinTick : true)
    }).length
  }, [normalizedLogs, tick, recentMinTick])

  const recentErrors = useMemo(() => {
    return normalizedLogs.filter((l) => {
      const isErr = l.severity === 'Error' || l.sev === 'error'
      return isErr && (tick > 0 ? l.tick >= recentMinTick : true)
    }).length
  }, [normalizedLogs, tick, recentMinTick])

  useEffect(() => {
    if (autoScroll && logsContainerRef.current) {
      logsContainerRef.current.scrollTop = logsContainerRef.current.scrollHeight
    }
  }, [autoScroll, logs?.length])

  const cellPadding = density === 'compact' ? '4px 8px' : '7px 8px'

  return (
    <>
      <PageHeader
        eyebrow="Logs"
        title="Audit console"
        summary="Client-buffered live events. Newest at the bottom, auto-scroll on."
        action={
          <div style={{ display: 'flex', gap: 8 }}>
            <button
              type="button"
              className="btn"
              onClick={() => onDensity?.(density === 'compact' ? 'comfortable' : 'compact')}
            >
              {density === 'compact' ? 'Compact' : 'Comfortable'}
            </button>
            <button
              type="button"
              className="btn"
              style={autoScroll ? { borderColor: 'var(--acc)' } : {}}
              onClick={() => onAutoScroll?.(!autoScroll)}
            >
              Auto-scroll {autoScroll ? 'on' : 'off'}
            </button>
          </div>
        }
      />

      <div className="chips" style={{ marginBottom: 10, alignItems: 'center' }}>
        {LOG_TYPES.map((type) => (
          <Chip
            key={type}
            on={typeFilter === type}
            onClick={() => onTypeFilter?.(type)}
          >
            {type}{' '}
            <b className="mono" style={{ fontWeight: 500, marginLeft: 4, color: 'var(--ink3)' }}>
              {typeCounts[type] ?? 0}
            </b>
          </Chip>
        ))}
        <span style={{ width: 1, height: 16, background: 'var(--line2)', margin: '0 6px' }} />
        {SEVERITY_OPTIONS.map((opt) => (
          <Chip
            key={opt.value}
            on={severityFilter === opt.value}
            onClick={() => onSeverityFilter?.(opt.value)}
          >
            {opt.label}
          </Chip>
        ))}
      </div>

      <div className="g12">
        <div className="s9 col">
          <div className="g4">
            <div className="tile">
              <div className="l">
                <span>Events</span>
              </div>
              <div className="v num" id="evcount">
                {formatInteger(normalizedLogs.length)}
              </div>
              <div className="foot">
                <span className="cap">buffered</span>
              </div>
            </div>
            <div className="tile">
              <div className="l">
                <span>Warnings</span>
              </div>
              <div className="v num" style={{ color: 'var(--warn)' }}>
                {formatInteger(recentWarnings)}
              </div>
              <div className="foot">
                <span className="cap">last 60 ticks</span>
              </div>
            </div>
            <div className="tile">
              <div className="l">
                <span>Errors</span>
              </div>
              <div className="v num" style={{ color: 'var(--crit)' }}>
                {formatInteger(recentErrors)}
              </div>
              <div className="foot">
                <span className="cap">last 60 ticks</span>
              </div>
            </div>
            <StatTile
              label="Tick time"
              value={metrics?.tickComputeMs || 0}
              format={ms}
              history={tickHist.tickMs}
              tick={tick}
              caption="Latest"
            />
          </div>

          <Panel style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 480 }}>
            <div style={{ marginBottom: 6 }}>
              <Search
                value={search}
                onChange={onSearch}
                placeholder="Search tick, entity, or message…"
              />
            </div>
            <div className="tablefill" ref={logsContainerRef}>
              <table className={density === 'compact' ? 'compact' : 'comfortable'}>
                <thead>
                  <tr>
                    <th style={{ width: 64 }}>Tick</th>
                    <th style={{ width: 90 }}>Type</th>
                    <th style={{ width: 140 }}>Entity</th>
                    <th>Message</th>
                    <th className="ar" style={{ width: 90 }}>
                      Duration
                    </th>
                  </tr>
                </thead>
                <tbody id="logbody">
                  {filteredLogs.map((log, rowIndex) => {
                    const isSelected = selectedLog
                      ? (selectedLog.id ? log.id === selectedLog.id : rowIndex === logIndex)
                      : false
                    const sev = (log.sev || log.severity || 'info').toLowerCase()
                    const dotColor = severityDotColor(log)
                    return (
                      <tr
                        key={log.id || `${log.tick}-${log.index ?? rowIndex}`}
                        className={`sev-${sev}${isSelected ? ' sel' : ''}`}
                        onClick={() => onSelectLog?.(isNumericMode ? rowIndex : log.id)}
                      >
                        <td className="n" style={{ padding: cellPadding }}>
                          {log.tick}
                        </td>
                        <td style={{ padding: cellPadding }}>
                          <i
                            className="sdot"
                            style={{
                              margin: '0 7px 0 0',
                              verticalAlign: 'middle',
                              background: dotColor,
                            }}
                          />
                          {log.rawType || log.type.toUpperCase()}
                        </td>
                        <td style={{ padding: cellPadding }}>{log.entity}</td>
                        <td style={{ whiteSpace: 'normal', padding: cellPadding }}>{log.message}</td>
                        <td className="n ar" style={{ padding: cellPadding }}>
                          {log.duration ?? '—'}
                        </td>
                      </tr>
                    )
                  })}
                  {filteredLogs.length === 0 && (
                    <tr>
                      <td
                        colSpan={5}
                        style={{ textAlign: 'center', color: 'var(--ink4)', padding: '24px 0' }}
                      >
                        No matching events
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </Panel>
        </div>

        <Panel className="s3">
          <div className="ttl">
            <h4>Selected event</h4>
            <small className="mono">{selectedLog ? `t${selectedLog.tick}` : ''}</small>
          </div>
          {selectedLog ? (
            <>
              <KeyValue label="Type" value={selectedLog.rawType || selectedLog.type} />
              <KeyValue
                label="Severity"
                value={selectedLog.severity}
                tone={severityTone(selectedLog)}
              />
              <KeyValue label="Entity" value={selectedLog.entity} />
              <div className="lbl" style={{ marginTop: 10 }}>
                Message
              </div>
              <div
                style={{
                  fontSize: '13px',
                  color: 'var(--ink)',
                  margin: '4px 0 12px',
                  wordBreak: 'break-word',
                }}
              >
                {selectedLog.message}
              </div>
              <div className="lbl">Raw</div>
              <RawJsonBlock value={selectedLog} />
              <div className="ttl" style={{ marginTop: 14 }}>
                <h4>Same entity</h4>
                <small>
                  {selectedLog.entity} · last {sameEntityLogs.length}
                </small>
              </div>
              {sameEntityLogs.length > 0 ? (
                sameEntityLogs.map((l, i) => {
                  const lDotColor = severityDotColor(l)
                  return (
                    <div key={l.id || `${l.tick}-${l.index ?? i}`} className="sig">
                      <i
                        className="sdot"
                        style={{
                          margin: '0 7px 0 0',
                          verticalAlign: 'middle',
                          background: lDotColor,
                        }}
                      />
                      <div style={{ minWidth: 0, flex: 1 }}>
                        <div className="t" style={{ wordBreak: 'break-word' }}>
                          {l.message}
                        </div>
                      </div>
                      <span className="when">{`t${l.tick}`}</span>
                    </div>
                  )
                })
              ) : (
                <div className="muted" style={{ fontSize: '11.5px' }}>
                  No other events from this entity in the buffer.
                </div>
              )}
            </>
          ) : (
            <div className="muted" style={{ fontSize: '11.5px', padding: '12px 0' }}>
              No event selected.
            </div>
          )}
          <div className="ttl" style={{ marginTop: 14 }}>
            <h4>Buffer by type</h4>
            <small>{normalizedLogs.length} events</small>
          </div>
          <div className="ledger" data-static="1">
            {LOG_TYPES.slice(1).map((t) => {
              const c = typeCounts[t] || 0
              const pct =
                normalizedLogs.length > 0 ? Math.round((c / normalizedLogs.length) * 100) : 0
              return (
                <div key={t} className="lr">
                  <span>{t.toUpperCase()}</span>
                  <div className="tr">
                    <div className="fl" style={{ width: `${pct}%`, background: 'var(--ink3)' }} />
                  </div>
                  <span className="nv">{c}</span>
                </div>
              )
            })}
          </div>
        </Panel>
      </div>
    </>
  )
}
