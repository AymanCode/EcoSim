import { Play, Pause, RotateCcw, Sun, Moon } from 'lucide-react';
import Pill from '../ui/Pill.jsx';
import { formatTick } from '../format.js';

// Breadcrumb titles keyed by view id, from the prototype's CRUMB table.
const CRUMB = {
  CONFIG: 'Preflight',
  DASHBOARD: 'Command deck',
  SUBJECTS: 'Population',
  FIRMS: 'Markets',
  FINANCE: 'Finance',
  GOVERNMENT: 'Government',
  LOGS: 'Logs'
};

export default function TopBar({
  view,
  tick,
  running,
  initialized,
  connected,
  onToggleRun,
  onReset,
  onToggleTheme,
  theme
}) {
  const pillTone = running ? 'good' : initialized ? 'warn' : connected ? 'muted' : 'crit';
  const pillLabel = running ? 'Running' : initialized ? 'Suspended' : connected ? 'Ready' : 'Backend offline';

  return (
    <div className="topbar">
      <div className="crumb">EcoSim <span>/</span> {CRUMB[view] || view}</div>
      <span className="tickbox">
        <span className="dot" />
        <span className="k">TICK</span>
        <span className="v">{initialized ? formatTick(tick) : 'STANDBY'}</span>
      </span>
      <Pill tone={pillTone}>{pillLabel}</Pill>
      <span style={{ marginLeft: 'auto' }} />
      {initialized && (
        <>
          <button
            type="button"
            className="btn"
            onClick={onToggleRun}
            aria-label={running ? 'Suspend simulation' : 'Resume simulation'}
          >
            {running ? <Pause size={14} /> : <Play size={14} />}
            {running ? 'Suspend' : 'Resume'}
          </button>
          <button
            type="button"
            className="btn danger"
            onClick={onReset}
            aria-label="Reset simulation"
            title="Reset"
          >
            <RotateCcw size={14} />
          </button>
        </>
      )}
      <button type="button" className="btn" onClick={onToggleTheme} aria-label="Toggle theme">
        {theme === 'paper' ? <Moon size={14} /> : <Sun size={14} />}
      </button>
    </div>
  );
}
