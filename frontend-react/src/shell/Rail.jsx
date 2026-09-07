import { Settings, Activity, Users, Building2, Wallet, Landmark, Terminal } from 'lucide-react';
import Logo from './Logo.jsx';

// Order and icon mapping come from the prototype's NAV table.
const NAV_ITEMS = [
  { id: 'CONFIG', label: 'Config', Icon: Settings },
  { id: 'DASHBOARD', label: 'Command', Icon: Activity },
  { id: 'SUBJECTS', label: 'Population', Icon: Users },
  { id: 'FIRMS', label: 'Markets', Icon: Building2 },
  { id: 'FINANCE', label: 'Finance', Icon: Wallet },
  { id: 'GOVERNMENT', label: 'Government', Icon: Landmark },
  { id: 'LOGS', label: 'Logs', Icon: Terminal }
];

export default function Rail({ view, onSelect, enabled, connected, sessionId }) {
  const tooltip = connected
    ? `Connected to Simulation Core${sessionId ? ` · Session ${String(sessionId).slice(0, 8)}` : ''}`
    : 'Awaiting Connection...';

  return (
    <nav className="rail">
      <div className="mark"><Logo /></div>
      <div className="wordmark">Eco<span>Sim</span></div>
      <div>
        {NAV_ITEMS.map(({ id, label, Icon }) => {
          const disabled = id !== 'CONFIG' && !enabled;
          return (
            <button
              key={id}
              type="button"
              className={`nav ${view === id ? 'on' : ''}`}
              disabled={disabled}
              onClick={() => {
                if (disabled) return;
                onSelect(id);
              }}
            >
              <Icon />
              {label}
            </button>
          );
        })}
      </div>
      <div className="online" title={tooltip}>
        <i />
        {connected ? 'ONLINE' : 'OFFLINE'}
        <span className="sr-only">{tooltip}</span>
      </div>
    </nav>
  );
}
