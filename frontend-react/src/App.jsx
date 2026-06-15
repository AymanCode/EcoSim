import React, { useState, useEffect, useLayoutEffect, useRef } from 'react';
import NeuralAvatar from './NeuralAvatar';
import NeuralBuilding from './NeuralBuilding';
import NeuralGovernment from './NeuralGovernment';
import {
  Play,
  Pause,
  Settings,
  Terminal,
  Activity,
  Users,
  Building2,
  Landmark,
  DollarSign,
  Zap,
  Save,
  RotateCcw,
  BarChart3,
  Globe,
  Triangle,
  Lock,
  Search,
  Filter,
  AlertTriangle,
  Database,
  Wallet,
  ShieldCheck,
  Eye
} from 'lucide-react';
import {
  AreaChart, Area, XAxis, YAxis, Tooltip,
  BarChart, Bar, Cell, LabelList
} from 'recharts';

// --- STYLES ---
const techStyles = `
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;700&display=swap');

  :root {
    --background-base: #0B1120;
    --topbar-height: 64px;
    --surface-low: #0F172A;
    --surface-mid: #111C31;
    --surface-high: #17233A;
    --border-soft: rgba(255, 255, 255, 0.06);
    --border-active: rgba(251, 191, 36, 0.38);
    --gold-accent: #FBBF24;
    --gold-soft: #F8DFA6;
    --green-positive: #6EE7B7;
    --amber-warning: #FBBF24;
    --red-negative: #BE5A67;
    --purple-ai: #A78BFA;
    --text-primary: #F4F7FB;
    --text-secondary: #CBD5E1;
    --text-muted: #64748B;
  }

  html,
  body,
  #root {
    min-height: 100%;
    background: var(--background-base);
  }
  body {
    margin: 0;
    background: var(--background-base);
  }
  #root {
    background: var(--background-base);
  }
  * {
    box-sizing: border-box;
  }

  .font-display { font-family: 'Inter', ui-sans-serif, system-ui, sans-serif; }
  .font-mono { font-family: 'JetBrains Mono', monospace; }
  .tabular-nums { font-variant-numeric: tabular-nums; }

  .bg-tech-grid {
    background-color: var(--background-base);
    background-image:
      radial-gradient(circle at 18% 0%, rgba(251, 191, 36, 0.055), transparent 32%),
      radial-gradient(circle at 82% 18%, rgba(129, 140, 248, 0.045), transparent 30%),
      linear-gradient(rgba(255, 255, 255, 0.025) 1px, transparent 1px),
      linear-gradient(90deg, rgba(255, 255, 255, 0.025) 1px, transparent 1px);
    background-size: auto, auto, 32px 32px, 32px 32px;
  }

  .tech-panel {
    background: linear-gradient(180deg, rgba(17, 28, 49, 0.92), rgba(15, 23, 42, 0.9));
    backdrop-filter: blur(12px);
    border: 1px solid var(--border-soft);
    border-radius: 8px;
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.035), 0 18px 44px rgba(2, 6, 23, 0.26);
    position: relative;
    overflow: visible;
  }

  .tech-corners {
    position: relative;
  }
  .tech-corners::before,
  .tech-corners::after {
    display: none;
  }
  .priority-corners::before {
    content: '';
    display: block;
    position: absolute;
    top: 0; left: 0;
    width: 16px; height: 16px;
    border-top: 1px solid var(--gold-accent);
    border-left: 1px solid var(--gold-accent);
    opacity: 0.56;
    z-index: 10;
  }
  .priority-corners::after {
    content: '';
    display: block;
    position: absolute;
    bottom: 0; right: 0;
    width: 16px; height: 16px;
    border-bottom: 1px solid var(--gold-accent);
    border-right: 1px solid var(--gold-accent);
    opacity: 0.56;
    z-index: 10;
  }

  .btn-tech {
    background: rgba(255, 255, 255, 0.045);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 8px;
    color: #CBD5E1;
    transition: all 0.2s ease;
    font-weight: 600;
  }
  .btn-tech:hover:not(:disabled) {
    background: rgba(255, 255, 255, 0.08);
    border-color: rgba(255, 255, 255, 0.12);
  }
  .btn-tech:active:not(:disabled) {
    transform: scale(0.98);
  }
  .btn-tech.active {
    background: rgba(255, 255, 255, 0.10);
    border-color: rgba(255, 255, 255, 0.12);
    color: var(--text-primary);
    box-shadow: none;
  }
  .btn-tech:disabled {
    opacity: 0.5;
    cursor: not-allowed;
    border-color: #334155;
    color: #66748C;
  }
  .btn-danger {
    border-color: rgba(190, 90, 103, 0.38);
    color: #E7A2AA;
    background: rgba(190, 90, 103, 0.08);
  }
  .btn-danger:hover {
    border-color: var(--red-negative);
    box-shadow: 0 0 10px rgba(190, 90, 103, 0.18);
  }
  .btn-primary-large {
    background: rgba(251, 191, 36, 0.12);
    border: 1px solid rgba(251, 191, 36, 0.32);
    color: #FFF7E0;
    box-shadow: none;
  }
  .btn-primary-large:hover {
    background: rgba(251, 191, 36, 0.18);
    color: #FFFFFF;
  }

  .progress-bar {
    background: rgba(251, 191, 36, 0.08);
    border: 1px solid rgba(251, 191, 36, 0.16);
    height: 8px;
    width: 100%;
    position: relative;
  }
  .progress-fill {
    background: var(--gold-accent);
    height: 100%;
    box-shadow: 0 0 8px rgba(251, 191, 36, 0.32);
  }

  .command-scroll {
    scrollbar-width: thin;
    scrollbar-color: rgba(135, 170, 210, 0.28) rgba(6, 10, 18, 0.3);
  }
  .command-scroll::-webkit-scrollbar {
    width: 8px;
    height: 8px;
  }
  .command-scroll::-webkit-scrollbar-track {
    background: rgba(6, 10, 18, 0.3);
  }
  .command-scroll::-webkit-scrollbar-thumb {
    background: rgba(135, 170, 210, 0.28);
    border-radius: 999px;
  }
  .command-scroll::-webkit-scrollbar-thumb:hover {
    background: rgba(251, 191, 36, 0.4);
  }
  .no-scrollbar {
    scrollbar-width: thin;
    scrollbar-color: rgba(135, 170, 210, 0.28) transparent;
  }

  input[type=range] {
    -webkit-appearance: none;
    background: transparent;
    height: 18px;
  }
  input[type=range]::-webkit-slider-thumb {
    -webkit-appearance: none;
    height: 14px;
    width: 14px;
    border-radius: 999px;
    background: #F59E0B;
    border: 2px solid #0B1120;
    cursor: pointer;
    margin-top: -5px;
    box-shadow: 0 1px 4px rgba(2, 6, 23, 0.5);
  }
  input[type=range]::-webkit-slider-runnable-track {
    width: 100%;
    height: 4px;
    background: linear-gradient(to right, #F59E0B var(--range-progress, 0%), #1E293B var(--range-progress, 0%));
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 999px;
  }
  input[type=range]::-moz-range-track {
    height: 4px;
    background: #1E293B;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 999px;
  }
  input[type=range]::-moz-range-progress {
    height: 4px;
    background: #F59E0B;
    border-radius: 999px;
  }
  input[type=range]::-moz-range-thumb {
    height: 14px;
    width: 14px;
    border-radius: 999px;
    background: #F59E0B;
    border: 2px solid #0B1120;
    cursor: pointer;
    box-shadow: 0 1px 4px rgba(2, 6, 23, 0.5);
  }
  select, input, button, table {
    font-family: 'Inter', ui-sans-serif, system-ui, sans-serif;
  }
  button:focus-visible,
  input:focus-visible,
  select:focus-visible {
    outline: 2px solid rgba(251, 191, 36, 0.72);
    outline-offset: 2px;
  }
  select:focus-visible {
    outline: 1px solid rgba(255, 255, 255, 0.16);
    outline-offset: 1px;
  }
`;

const resolveWebSocketEndpoint = () => {
  const configuredEndpoint = (import.meta.env.VITE_WS_URL || '').trim();
  if (configuredEndpoint) {
    return configuredEndpoint;
  }

  if (typeof window !== 'undefined') {
    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const host = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' ? 'localhost:8002' : window.location.host;
    return `${protocol}://${host}/ws`;
  }

  return 'ws://localhost:8002/ws';
};

// --- COMPONENTS ---

const CircularProgress = ({ value, color, label, size = 80 }) => {
  const radius = size / 2 - 4;
  const circumference = radius * 2 * Math.PI;
  const offset = circumference - (value / 100) * circumference;
  const refinedColor = color;
  return (
    <div className="flex flex-col items-center justify-center relative pointer-events-none rounded-full bg-slate-900/55 backdrop-blur-md p-2 border border-white/5">
      <svg fill="none" viewBox={`0 0 ${size} ${size}`} className="transform -rotate-90" style={{ width: size, height: size }}>
        <circle cx={size / 2} cy={size / 2} r={radius} stroke="currentColor" strokeWidth="2" className="text-slate-800" />
        <circle cx={size / 2} cy={size / 2} r={radius} stroke={refinedColor} strokeWidth="2.5" strokeDasharray={circumference} strokeDashoffset={offset} className="transition-all duration-1000 ease-out" style={{ filter: `drop-shadow(0 0 3px ${refinedColor}66)` }} />
      </svg>
      <div className="absolute flex flex-col items-center justify-center">
        <span className="font-display font-bold text-lg" style={{ color: refinedColor }}>{value.toFixed(0)}</span>
      </div>
      <div className="mt-2 text-[9px] uppercase tracking-widest text-slate-400 font-bold bg-slate-900/80 px-2 py-0.5 rounded border border-white/5">{label}</div>
    </div>
  );
};

const NavButton = ({ icon: Icon, label, isActive, onClick, disabled }) => (
  <button
    onClick={disabled ? null : onClick}
    className={`group relative flex flex-col items-center justify-center w-full py-3 transition-all duration-300
      ${isActive ? 'text-amber-300 bg-amber-400/10 border-l-2 border-amber-300 shadow-[inset_10px_0_18px_rgba(251,191,36,0.08)] relative before:absolute before:left-[-2px] before:top-0 before:bottom-0 before:w-[2px] before:bg-amber-300 before:shadow-[0_0_6px_1px_rgba(251,191,36,0.32)]' : 'text-slate-500 hover:text-slate-300 hover:bg-white/5 border-l-2 border-transparent'}
      ${disabled ? 'opacity-30 cursor-not-allowed' : 'cursor-pointer'}
    `}
  >
    <Icon size={20} className={`mb-1 transition-transform duration-300 ${isActive ? 'scale-110' : 'group-hover:scale-110'}`} />
    <span className={`text-[10px] font-display font-medium transition-opacity duration-300 ${isActive ? 'font-semibold' : ''}`}>{label}</span>
  </button>
);
const StatTile = ({ label, value, trend, suffix = "", alert = false, caption, valueVariant = 'metric' }) => {
  const [isHovered, setIsHovered] = React.useState(false);
  const glowColor = trend > 0 ? 'rgba(203, 213, 225, 0.08)' : trend < 0 ? 'rgba(190, 90, 103, 0.12)' : 'rgba(255, 255, 255, 0.07)';
  const borderColor = alert ? 'border-rose-400/35' : 'border-white/5';
  const shadowStyle = isHovered ? { boxShadow: `inset 0 1px 0 rgba(255,255,255,0.05), 0 12px 28px ${glowColor}` } : {};
  const valueClassName = valueVariant === 'badge'
    ? `inline-flex w-fit items-center rounded-full border border-white/10 bg-white/[0.055] px-2.5 py-1 text-xs font-display font-semibold ${alert ? 'text-[#D89B45]' : 'text-slate-300'}`
    : 'text-2xl md:text-[28px] leading-tight font-mono tabular-nums font-bold text-slate-100 group-hover:text-white transition-colors truncate';

  return (
    <div 
      className={`tech-panel p-4 flex flex-col group backdrop-blur-md border ${borderColor} bg-white/[0.045] hover:bg-white/[0.07] rounded-lg transition-all duration-300 relative overflow-hidden min-h-[104px]`}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      style={shadowStyle}
    >
      <div className="absolute inset-0 bg-gradient-to-br from-white/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500 pointer-events-none"></div>
      <div className="flex justify-between items-start mb-1 relative z-10">
        <span className="text-[12px] text-slate-400 font-display font-semibold pr-2 leading-tight group-hover:text-slate-300 transition-colors">{label}</span>
        {trend !== undefined && trend !== null && (
          <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded shrink-0 whitespace-nowrap transition-colors duration-500 ease-in-out ${trend > 0 ? 'bg-white/[0.055] text-slate-200' : 'bg-white/[0.055] text-rose-200'}`}>
            {trend > 0 ? '+' : '-'}{Math.abs(Number(trend)).toFixed(1)}%
          </span>
        )}
      </div>
      <div className="flex items-baseline space-x-1 overflow-hidden mt-1 relative z-10">
        <span className={valueClassName}>
          {value}
        </span>
        {suffix && <span className="text-[10px] text-slate-500 font-mono shrink-0 group-hover:text-slate-400">{suffix}</span>}
      </div>
      {caption && (
        <div className="mt-1 text-[12px] text-slate-500 leading-tight truncate relative z-10">{caption}</div>
      )}
      <div className="w-full h-[2px] bg-white/[0.055] mt-2 relative overflow-hidden shrink-0 rounded-full z-10">
        <div className={`absolute top-0 left-0 h-full w-1/3 ${trend && trend < 0 ? 'bg-rose-300/35' : 'bg-slate-300/28'}`}></div>
      </div>
    </div>
  );
};

const TechSlider = ({ label, value, onChange, min, max, step, format = v => v, description }) => (
  <div className="mb-5">
    <div className="flex justify-between items-end mb-2 font-display">
      <label className="text-sm text-slate-300 font-medium">{label}</label>
      <span className="text-amber-300 font-mono tabular-nums bg-white/[0.055] px-2 py-0.5 rounded text-sm border border-white/10">
        {format(value)}
      </span>
    </div>
    <div className="relative flex items-center">
      <div className="h-1.5 w-1.5 bg-slate-700 rounded-full mr-2"></div>
      <input
        type="range"
        min={min} max={max} step={step}
        value={value}
        onChange={(e) => onChange(parseFloat(e.target.value))}
        className="w-full"
        style={{ '--range-progress': `${((Number(value) - Number(min)) / (Number(max) - Number(min) || 1)) * 100}%` }}
      />
      <div className="h-1.5 w-1.5 bg-amber-500 rounded-full ml-2"></div>
    </div>
    <div className="mt-1 flex justify-between text-[10px] text-slate-600 font-mono tabular-nums">
      <span>{format(min)}</span>
      <span>{format(max)}</span>
    </div>
    {description && <p className="mt-1 text-[11px] leading-relaxed text-slate-500">{description}</p>}
  </div>
);

const TechNumberInput = ({ label, value, onChange, min = 0, max = Number.MAX_SAFE_INTEGER, step = 1, description }) => (
  <label className="block mb-5">
    <div className="flex justify-between items-center mb-2 font-display">
      <span className="text-sm text-slate-300 font-medium">{label}</span>
      <span className="text-[10px] text-slate-500 font-mono tabular-nums">integer</span>
    </div>
    <input
      type="number"
      aria-label={label}
      min={min}
      max={max}
      step={step}
      value={value}
      onChange={(event) => {
        const parsed = Number(event.target.value);
        if (!Number.isFinite(parsed)) return;
        const bounded = Math.max(Number(min), Math.min(Number(max), Math.trunc(parsed)));
        onChange(bounded);
      }}
      className="w-full bg-white/[0.055] border border-white/5 text-amber-300 font-mono tabular-nums text-sm rounded-md px-3 py-2 outline-none focus:border-amber-300/35 focus:ring-0 hover:bg-white/[0.075] transition-colors"
    />
    {description && <p className="mt-1 text-[11px] leading-relaxed text-slate-500">{description}</p>}
  </label>
);

const TechSelect = ({ label, value, onChange, options, description }) => (
  <label className="block">
    <div className="flex justify-between items-center mb-2 font-display">
      <span className="text-sm text-slate-300 font-medium">{label}</span>
      <span className="text-[10px] text-slate-500 font-display font-medium truncate max-w-[10rem]" title={String(value)}>{value}</span>
    </div>
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="w-full appearance-none bg-white/[0.055] border border-white/5 text-slate-300 text-[12px] rounded-md px-3 py-1.5 outline-none focus:border-white/10 focus:ring-0 hover:bg-white/[0.075] transition-colors"
    >
      {options.map(option => (
        <option key={option.value} value={option.value}>{option.label}</option>
      ))}
    </select>
    {description && <p className="mt-1 text-[11px] leading-relaxed text-slate-500">{description}</p>}
  </label>
);

const TechToggle = ({ label, checked, onChange, description }) => (
  <button
    type="button"
    onClick={() => onChange(!checked)}
    className={`w-full flex items-center justify-between gap-3 rounded border px-3 py-2 text-left transition-colors ${
      checked
        ? 'bg-white/[0.06] border-amber-400/30 text-slate-100'
        : 'bg-white/[0.04] border-white/5 text-slate-300 hover:bg-white/[0.06]'
    }`}
  >
    <span>
      <span className="block text-xs font-semibold">{label}</span>
      {description && <span className="block text-[10px] text-slate-500 mt-0.5">{description}</span>}
    </span>
    <span className={`h-5 w-9 rounded-full border p-0.5 ${checked ? 'border-amber-400/40 bg-amber-400/10' : 'border-slate-700 bg-slate-900/70'}`}>
      <span className={`block h-3.5 w-3.5 rounded-full transition-transform ${checked ? 'translate-x-4 bg-amber-400' : 'bg-slate-600'}`} />
    </span>
  </button>
);

const PageHeader = ({ eyebrow, title, summary, action }) => (
  <div className="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-3 mb-5">
    <div>
      <div className="text-[11px] uppercase tracking-[0.14em] text-amber-300/80 font-semibold">{eyebrow}</div>
      <h2 className="text-2xl lg:text-3xl font-bold text-slate-50 tracking-tight mt-1">{title}</h2>
      {summary && <p className="mt-2 text-sm text-slate-400 max-w-3xl leading-relaxed">{summary}</p>}
    </div>
    {action}
  </div>
);

const SectionHeader = ({ icon: Icon, title, meta, muted = false }) => (
  <div className="flex items-center justify-between gap-3 mb-3 pb-2 border-b border-slate-800/80">
    <div className="flex items-center gap-2 min-w-0">
      {Icon && <Icon className={`${muted ? 'text-slate-600' : 'text-amber-300'} shrink-0`} size={15} />}
      <h3 className={`text-[13px] font-semibold truncate ${muted ? 'text-slate-500' : 'text-slate-300'}`}>{title}</h3>
    </div>
    {meta && <div className={`text-[10px] font-display font-medium truncate ${muted ? 'text-slate-600' : 'text-slate-500'}`}>{meta}</div>}
  </div>
);

const StatusPill = ({ children, tone = 'system', title }) => {
  const tones = {
    system: 'border-white/10 bg-white/[0.055] text-amber-200',
    positive: 'border-white/10 bg-white/[0.055] text-emerald-200',
    warning: 'border-white/10 bg-white/[0.055] text-[#D89B45]',
    negative: 'border-white/10 bg-white/[0.055] text-rose-200',
    ai: 'border-white/10 bg-white/[0.055] text-indigo-200',
    muted: 'border-white/10 bg-white/[0.045] text-slate-400'
  };
  const dots = {
    system: 'bg-amber-300',
    positive: 'bg-emerald-300',
    warning: 'bg-[#D89B45]',
    negative: 'bg-rose-300',
    ai: 'bg-indigo-300',
    muted: 'bg-slate-500'
  };
  return (
    <span title={title} className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[11px] font-semibold shadow-none ${tones[tone] || tones.system}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${dots[tone] || dots.system}`} />
      {children}
    </span>
  );
};

const EmptyState = ({ icon: Icon = Database, title, children, muted = false }) => (
  <div className={`min-h-[150px] rounded-lg border border-dashed border-white/5 bg-slate-950/30 flex flex-col items-center justify-center text-center px-5 py-8 ${muted ? 'opacity-60' : ''}`}>
    <Icon size={24} className={`${muted ? 'text-slate-700' : 'text-slate-600'} mb-3`} />
    <div className={`text-sm font-semibold ${muted ? 'text-slate-500' : 'text-slate-300'}`}>{title}</div>
    {children && <div className={`mt-1 text-xs leading-relaxed max-w-md ${muted ? 'text-slate-600' : 'text-slate-500'}`}>{children}</div>}
  </div>
);

const FinanceLiquidityHologram = ({ activeLoans = 0 }) => (
  <div className="relative h-52 rounded-lg border border-white/5 bg-slate-950/35 overflow-hidden">
    <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(100,116,139,0.08),transparent_62%)]" />
    <div className="absolute inset-0 flex items-center justify-center">
      <div className="relative h-32 w-32 opacity-70">
        <div className="absolute inset-0 rounded-full border border-dashed border-slate-700/80" />
        <div className="absolute inset-6 rotate-45 border border-slate-700/70" />
        <div className="absolute left-1/2 top-0 h-full w-px -translate-x-1/2 bg-gradient-to-b from-transparent via-slate-700 to-transparent" />
        <div className="absolute top-1/2 left-0 h-px w-full -translate-y-1/2 bg-gradient-to-r from-transparent via-slate-700 to-transparent" />
        <div className="absolute left-1/2 top-1/2 h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full border border-slate-600 bg-slate-900" />
      </div>
    </div>
    <div className="absolute left-4 top-4">
      <div className="text-[10px] text-slate-500 font-semibold">Liquidity core</div>
      <div className="text-sm font-mono tabular-nums text-slate-500">{Number(activeLoans || 0).toLocaleString()} loan events</div>
    </div>
    <div className="absolute bottom-4 left-4 right-4 rounded border border-slate-800 bg-slate-950/65 px-3 py-2 text-xs text-slate-400">
      Bank telemetry inactive
    </div>
  </div>
);

const LiveRunProjection = () => (
  <div className="mt-4 h-44 rounded-lg border border-white/5 bg-slate-950/40 relative overflow-hidden priority-corners">
    <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(203,213,225,0.08),transparent_58%),radial-gradient(circle_at_50%_88%,rgba(251,191,36,0.06),transparent_38%)]" />
    <div className="absolute inset-x-8 bottom-7 h-px bg-gradient-to-r from-transparent via-slate-500/40 to-transparent" />
    <div className="absolute inset-0 flex items-center justify-center">
      <div className="relative h-28 w-28 animate-[spin_32s_linear_infinite] [transform-style:preserve-3d]">
        <div className="absolute inset-0 rounded-full border border-slate-300/25" />
        <div className="absolute inset-3 rounded-full border border-slate-500/30" />
        <div className="absolute left-1/2 top-0 h-full w-px -translate-x-1/2 bg-gradient-to-b from-transparent via-slate-300/35 to-transparent" />
        <div className="absolute top-1/2 left-0 h-px w-full -translate-y-1/2 bg-gradient-to-r from-transparent via-amber-300/35 to-transparent" />
        <div className="absolute inset-0 rounded-full border border-slate-400/20" style={{ transform: 'rotateX(64deg)' }} />
        <div className="absolute inset-0 rounded-full border border-slate-400/16" style={{ transform: 'rotateY(58deg)' }} />
        <div className="absolute inset-8 rotate-45 border border-amber-300/26" />
        <div className="absolute left-1/2 top-1/2 h-2.5 w-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full border border-slate-300/50 bg-slate-900" />
      </div>
    </div>
  </div>
);

const useMeasuredWidth = () => {
  const ref = useRef(null);
  const [width, setWidth] = useState(0);

  useLayoutEffect(() => {
    const node = ref.current;
    if (!node) return undefined;

    const updateWidth = (nextWidth = node.getBoundingClientRect().width) => {
      const rounded = Math.max(0, Math.floor(nextWidth));
      setWidth(prev => Math.abs(prev - rounded) > 1 ? rounded : prev);
    };

    updateWidth();

    if (typeof ResizeObserver === 'undefined') {
      const onResize = () => updateWidth();
      window.addEventListener('resize', onResize);
      return () => window.removeEventListener('resize', onResize);
    }

    const observer = new ResizeObserver(entries => {
      updateWidth(entries[0]?.contentRect?.width);
    });
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  return [ref, width];
};

const MeasuredChart = ({ height = 150, className = "", children }) => {
  const [ref, width] = useMeasuredWidth();

  return (
    <div ref={ref} className={`w-full min-w-0 ${className}`} style={{ height }}>
      {width > 2 ? children(width, height) : null}
    </div>
  );
};

const DetailRow = ({ label, value, tone = 'default', title }) => {
  const toneClass = tone === 'positive'
    ? 'text-emerald-400'
    : tone === 'negative'
      ? 'text-rose-500'
      : tone === 'warning'
        ? 'text-amber-500'
        : tone === 'ai'
          ? 'text-violet-300'
          : tone === 'muted'
            ? 'text-slate-600'
            : 'text-slate-200';
  return (
    <div className="flex items-center justify-between gap-3 border-b border-white/5 py-1.5 last:border-0">
      <span className="min-w-0 text-[11px] leading-tight text-slate-500">{label}</span>
      <span title={title} className={`shrink-0 font-mono tabular-nums text-xs ${toneClass} text-right truncate max-w-[70%]`}>{value}</span>
    </div>
  );
};

const Badge = ({ children, tone = 'system' }) => (
  <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-display font-semibold ${
    tone === 'negative'
      ? 'border-white/10 bg-white/[0.055] text-rose-500'
      : tone === 'warning'
        ? 'border-white/10 bg-white/[0.055] text-amber-500'
        : tone === 'ai'
          ? 'border-white/10 bg-white/[0.055] text-indigo-300'
          : tone === 'muted'
            ? 'border-white/10 bg-white/[0.045] text-slate-400'
            : 'border-white/10 bg-white/[0.055] text-slate-300'
  }`}>
    {children}
  </span>
);

const RawJsonBlock = ({ value }) => {
  const json = JSON.stringify(value, null, 2);
  const renderLine = (line, index) => {
    const match = line.match(/^(\s*)"([^"]+)":\s?(.*?)(,?)$/);
    if (!match) {
      return <div key={index} className="text-slate-600">{line || ' '}</div>;
    }
    const [, indent, key, rawValue, comma] = match;
    const trimmed = rawValue.trim();
    const valueClass = trimmed.startsWith('"')
      ? 'text-slate-300'
      : trimmed === 'true' || trimmed === 'false'
        ? 'text-amber-400/80'
        : trimmed === 'null'
          ? 'text-slate-600'
          : 'text-slate-400';
    return (
      <div key={index}>
        <span className="text-slate-700">{indent}"</span>
        <span className="text-amber-300/70">{key}</span>
        <span className="text-slate-700">": </span>
        <span className={valueClass}>{rawValue}</span>
        <span className="text-slate-700">{comma}</span>
      </div>
    );
  };

  return (
    <pre className="mt-3 max-h-[260px] overflow-auto command-scroll rounded-lg border border-white/5 bg-slate-950/75 p-3 text-[11px] leading-relaxed font-mono tabular-nums">
      {json.split('\n').map(renderLine)}
    </pre>
  );
};


// --- SYSTEM DISTRESS GAUGE ---
const SystemDistressGauge = ({ unemployment, happiness, firmDistress = 0 }) => {
  const unemploymentPressure = Math.min(100, Math.max(0, unemployment || 0));
  const happinessPressure = Math.min(100, Math.max(0, 100 - (happiness || 0)));
  const firmPressure = Math.min(100, Math.max(0, firmDistress || 0));
  const distress = Math.min(
    100,
    Math.max(0, unemploymentPressure * 0.45 + happinessPressure * 0.40 + firmPressure * 0.15)
  );
  const normalized = distress / 100;
  
  let color = '#6EAFA0';
  let status = 'NOMINAL';
  if (normalized > 0.4) { color = '#D89B45'; status = 'ELEVATED'; }
  if (normalized > 0.6) { color = '#B8763F'; status = 'HIGH'; }
  if (normalized > 0.8) { color = '#BE5A67'; status = 'CRITICAL'; }

  return (
    <div className="flex-1 border border-white/5 rounded bg-slate-900/40 flex flex-col overflow-hidden w-full tech-panel tech-corners p-3 relative group backdrop-blur-md">
      <div className="absolute inset-0 bg-white/[0.015] opacity-0 group-hover:opacity-100 transition-opacity duration-700 pointer-events-none"></div>
      
      <div className="flex justify-between items-start mb-2 relative z-10">
        <h4 className="text-[13px] font-semibold text-slate-300 leading-none">System distress</h4>
        <span className="text-[9px] font-mono border border-white/10 bg-white/[0.055] px-1.5 rounded shadow-none" style={{ color }}>{status}</span>
      </div>
      
      <div className="flex-1 flex flex-col justify-center relative z-10 mt-4">
        <div className="flex items-end justify-between gap-4">
          <span className="text-3xl font-mono font-bold tabular-nums" style={{ color }}>{distress.toFixed(0)}</span>
          <span className="text-[10px] text-slate-500">/100</span>
        </div>
        <div className="mt-4 h-1.5 rounded-full bg-slate-800/80 border border-white/5 overflow-hidden">
          <div
            className="h-full rounded-full transition-all duration-1000 ease-out"
            style={{ width: `${Math.max(2, distress)}%`, background: color, opacity: 0.76 }}
          />
        </div>
      </div>
    </div>
  );
};

// --- WEALTH INEQUALITY VISUALIZATION ---
const WealthDistributionChart = ({ gini, top10, bottom50 }) => {
  // Determine current state color
  const getCurrentColor = (g) => {
    if (g < 0.30) return "#6EE7B7";
    if (g < 0.40) return "#A7F3D0";
    if (g < 0.50) return "#FBBF24";
    if (g < 0.60) return "#D89B45";
    if (g < 0.70) return "#BE5A67";
    return "#9F4254";
  };

  const currentColor = getCurrentColor(gini);
  const wealthData = [
    { label: 'Bottom 50%', share: parseFloat(bottom50.toFixed(1)), color: '#64748B' },
    { label: 'Mid 40%', share: parseFloat((100 - top10 - bottom50).toFixed(1)), color: '#818CF8' },
    { label: 'Top 10%', share: parseFloat(top10.toFixed(1)), color: '#FBBF24' },
  ];

  return (
    <div className="relative border border-slate-700/40 bg-slate-900/30 rounded flex flex-col p-3 overflow-hidden w-full tech-panel">
      <div className="flex justify-between items-start z-10 w-full px-1 min-h-[44px]">
        <div>
          <h4 className="text-[13px] font-semibold text-slate-300 leading-none">Wealth distribution</h4>
          <div className="text-[10px] text-slate-500 mt-1">Wealth share by cohort</div>
          <div className="text-lg font-mono font-bold mt-1 shadow-sm" style={{ color: currentColor }}>
            {gini.toFixed(3)}
          </div>
        </div>
        <div className="text-[10px] text-slate-500 text-right mt-0.5">Gini coefficient</div>
      </div>

      {/* Visual Bar Distribution Area */}
      <MeasuredChart height={112} className="pt-1">
        {(width, measuredHeight) => (
          <BarChart width={width} height={measuredHeight} data={wealthData} margin={{ top: 20, right: 10, bottom: 0, left: 10 }}>
            <Bar dataKey="share" radius={[4, 4, 0, 0]}>
              {wealthData.map((entry, i) => (
                <Cell key={i} fill={entry.color} />
              ))}
              <LabelList dataKey="share" position="top" style={{ fontSize: '11px', fill: '#e2e8f0', fontFamily: 'monospace' }} formatter={(v) => `${v}%`} />
            </Bar>
            <XAxis dataKey="label" tick={{ fontSize: 10, fill: '#94a3b8', fontFamily: 'monospace' }} axisLine={false} tickLine={false} />
            <YAxis hide />
          </BarChart>
        )}
      </MeasuredChart>

      {/* Background Decor */}
      <div className="absolute top-0 right-0 w-32 h-32 bg-amber-400/5 rounded-full blur-2xl pointer-events-none"></div>
    </div>
  );
};

// --- REUSABLE CHART COMPONENT ---
const LineChart = ({
  title,
  data,
  color,
  suffix = "",
  formatValue = v => v.toFixed(1),
  legend,
  height = 150,
  subtitle,
  headlineValue,
  headlineLabel = "Current",
  timeRange = "Last 250 ticks"
}) => {
  // Normalize data to array of arrays for multi-line support
  const datasets = Array.isArray(data?.[0]) ? data : [data || []];
  const colors = Array.isArray(color) ? color : [color];

  // Check if we have enough data in the primary dataset
  if (!datasets[0] || datasets[0].length < 1) {
    return (
      <div className="tech-panel flex-1 min-h-[180px] flex items-center justify-center text-slate-500 text-xs border border-white/5 rounded-lg bg-slate-900/55">
        <EmptyState title="Awaiting telemetry">This chart will populate as ticks are received.</EmptyState>
      </div>
    );
  }

  // Keep charts visible with a single sample by duplicating the point.
  const normalizedDatasets = datasets.map(ds => {
    if (!Array.isArray(ds) || ds.length !== 1) return ds;
    const first = ds[0];
    return [
      first,
      { tick: (first?.tick ?? 0) + 1, value: first?.value ?? 0 }
    ];
  });

  // Pre-process data for Recharts (array of objects)
  const chartData = normalizedDatasets[0].map((_, i) => {
    const point = { index: i };
    normalizedDatasets.forEach((ds, dIdx) => {
      point[`value${dIdx}`] = ds[i]?.value || 0;
    });
    return point;
  });

  const lastValue = normalizedDatasets[0][normalizedDatasets[0].length - 1]?.value ?? 0;
  const safeGradientId = `grad-${title.replace(/[^a-zA-Z0-9]/g, '')}`;

  return (
    <div className="flex-1 group relative border border-white/5 rounded-lg bg-slate-900/40 flex flex-col overflow-hidden w-full min-w-0 tech-panel">

      {/* Chart Header - explicitly placed ABOVE the responsive container */}
      <div className="px-4 pt-4 pb-2 flex justify-between items-start gap-3 z-10 w-full shrink-0 min-h-[58px]">
        <div className="min-w-0">
          <h4 className="text-[13px] font-semibold text-slate-300 leading-tight truncate">{title}</h4>
          <div className="text-sm md:text-base font-mono tabular-nums font-bold text-slate-100 mt-1 shadow-sm">
            {formatValue(headlineValue ?? lastValue)}<span className="text-[10px] text-slate-500 ml-0.5">{suffix}</span>
          </div>
          <div className="text-[10px] text-slate-500 mt-0.5">
            {headlineLabel}{subtitle ? ` Â· ${subtitle}` : ''}{timeRange ? ` Â· ${timeRange}` : ''}
          </div>
        </div>
        {legend && (
          <div className="flex flex-wrap justify-end gap-2 max-w-[45%]">
            {legend.map((item, idx) => (
              <span key={`${item}-${idx}`} className="inline-flex items-center gap-1 text-[10px] text-slate-400">
                <span className="h-2 w-2 rounded-full" style={{ backgroundColor: colors[idx % colors.length] }} />
                {item}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Chart Area - explicitly using h-32 Tailwind class to prevent cramming */}
      <MeasuredChart height={height} className="px-2 pb-2 shrink-0">
        {(width, measuredHeight) => (
          <AreaChart width={width} height={measuredHeight} data={chartData} margin={{ top: 10, right: 12, left: 6, bottom: 6 }}>
            <defs>
              {normalizedDatasets.map((_, dIdx) => (
                <linearGradient key={dIdx} id={`${safeGradientId}-${dIdx}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={colors[dIdx % colors.length]} stopOpacity={dIdx === 0 ? 0.08 : 0.055} />
                  <stop offset="52%" stopColor={colors[dIdx % colors.length]} stopOpacity={0.018} />
                  <stop offset="100%" stopColor={colors[dIdx % colors.length]} stopOpacity={0} />
                </linearGradient>
              ))}
            </defs>
            <XAxis dataKey="index" hide />
            <YAxis domain={['auto', 'auto']} hide />
            <Tooltip
              content={({ active, payload }) => {
                if (active && payload && payload.length) {
                  return (
                    <div className="bg-slate-950/95 backdrop-blur-md border border-white/10 rounded shadow-[0_12px_28px_rgba(2,6,23,0.34)] px-3 py-2 z-50">
                      {payload.map((entry, idx) => (
                        <div key={entry.dataKey} className="font-mono tabular-nums text-[11px] text-slate-200 flex items-center gap-2">
                          <span className="h-2 w-2 rounded-full" style={{ backgroundColor: colors[idx % colors.length] }} />
                          <span>{legend?.[idx] || `Series ${idx + 1}`}: {formatValue(entry.value)}{suffix}</span>
                        </div>
                      ))}
                    </div>
                  );
                }
                return null;
              }}
              cursor={{ stroke: 'rgba(203, 213, 225, 0.26)', strokeWidth: 1, strokeDasharray: '4 4' }}
              isAnimationActive={false}
            />
            {normalizedDatasets.map((_, dIdx) => (
              <Area
                key={dIdx}
                type="monotone"
                dataKey={`value${dIdx}`}
                stroke={colors[dIdx % colors.length]}
                strokeWidth={1.5}
                fillOpacity={0.6}
                fill={`url(#${safeGradientId}-${dIdx})`}
                isAnimationActive={false}
                activeDot={{ r: 2.5, strokeWidth: 1, stroke: colors[dIdx % colors.length], fill: '#0B1120' }}
              />
            ))}
          </AreaChart>
        )}
      </MeasuredChart>
    </div>
  );
};

export default function EcoSimUI() {
  const wsEndpoint = resolveWebSocketEndpoint();
  const [activeView, setActiveView] = useState('CONFIG'); // Start at CONFIG
  const [isInitialized, setIsInitialized] = useState(false);
  const [isRunning, setIsRunning] = useState(false);
  const [tick, setTick] = useState(0);
  const [logs, setLogs] = useState([]);
  const logsEndRef = useRef(null);
  const logsContainerRef = useRef(null);
  const ws = useRef(null);
  const reconnectTimerRef = useRef(null);
  const configUpdateTimer = useRef(null);
  const pendingConfigRef = useRef(null);
  const [isInitializing, setIsInitializing] = useState(false);
  const [wsConnected, setWsConnected] = useState(false);

  // Simulation State
  const [metrics, setMetrics] = useState({
    unemployment: 99.0,
    gdp: 0.0,
    govDebt: 0.0,
    govProfit: 0.0,
    happiness: 50,
    housingInv: 0,
    avgWage: 0.0,
    avgExpectedWage: 0.0,
    avgExpectedWageUnemployed: 0.0,
    giniCoefficient: 0.0,
    top10Share: 0.0,
    bottom50Share: 0.0,
    gdpHistory: [],
    unemploymentHistory: [],
    wageHistory: [],
    medianWageHistory: [],
    happinessHistory: [],
    healthHistory: [],
    govProfitHistory: [],
    govDebtHistory: [],
    firmCountHistory: [],
    giniHistory: [],
    top10ShareHistory: [],
    bottom50ShareHistory: [],
    priceHistory: { food: [], housing: [], services: [], healthcare: [] },
    supplyHistory: { food: [], housing: [], services: [], healthcare: [] },
    trackedSubjects: [],
    trackedFirms: [],
    policyChanges: [],
    latestGovernmentDecision: null,
    llmGovernment: { enabled: false, status: 'disabled', latestDecision: null },
    governmentPolicy: {}
  });

  const [requestedSubjectIndex, setActiveSubjectIndex] = useState(0);
  const [requestedFirmIndex, setActiveFirmIndex] = useState(0);
  const [firmStats, setFirmStats] = useState(null);
  const [subjectSearch, setSubjectSearch] = useState('');
  const [subjectFilter, setSubjectFilter] = useState('All');
  const [logSearch, setLogSearch] = useState('');
  const [logTypeFilter, setLogTypeFilter] = useState('All');
  const [logSeverityFilter, setLogSeverityFilter] = useState('All');
  const [selectedLogIndex, setSelectedLogIndex] = useState(0);
  const [autoScrollLogs, setAutoScrollLogs] = useState(true);
  const [logDensity, setLogDensity] = useState('comfortable');

  const [config, setConfig] = useState({
    wageTax: 0.05,
    profitTax: 0.30,
    inflationRate: 0.02,
    birthRate: 0.01,
    minimumWage: 20.0,
    unemploymentBenefitRate: 0.0,
    universalBasicIncome: 0.0,
    wealthTaxThreshold: 50000,
    wealthTaxRate: 0.0,
    enableLlmGovernment: false,
    benefitLevel: 'neutral',
    publicWorks: false,
    minimumWagePolicy: 'neutral',
    sectorSubsidyTarget: 'none',
    sectorSubsidyLevel: 0,
    infrastructureSpending: 'none',
    technologySpending: 'none',
    socialSpending: 'medium',
    priceStabilizationTarget: 'none',
    priceStabilizationLevel: 'off',
    rentStabilizationLevel: 'off',
    bailoutPolicy: 'off',
    bailoutTarget: 'none',
    bailoutBudget: 0
  });

  // Setup State (for initialization)
  const [setupConfig, setSetupConfig] = useState({
    num_households: 1000,
    num_firms: 5,
    seed: 42,
    wage_tax: 0.15,
    profit_tax: 0.20,
    enable_llm_government: false,
    disable_stabilizers: false,
    disabled_agents: []
  });
  const setupConfigRef = useRef(setupConfig);
  useEffect(() => {
    setupConfigRef.current = setupConfig;
  }, [setupConfig]);
  const stabilizerAgentOptions = [
    { key: 'households', label: 'Households' },
    { key: 'firms', label: 'Firms' },
    { key: 'government', label: 'Government' },
    { key: 'all', label: 'All Agents' }
  ];
  const subjectCount = metrics.trackedSubjects ? metrics.trackedSubjects.length : 0;
  const firmCount = metrics.trackedFirms ? metrics.trackedFirms.length : 0;
  const activeSubjectIndex = subjectCount > 0 && requestedSubjectIndex < subjectCount ? requestedSubjectIndex : 0;
  const activeFirmIndex = firmCount > 0 && requestedFirmIndex < firmCount ? requestedFirmIndex : 0;

  const signedPrefix = (num) => (num < 0 ? '-' : '');
  const formatInteger = (value) => Number(value || 0).toLocaleString(undefined, { maximumFractionDigits: 0 });
  const formatDecimal = (value, decimals = 1) => Number(value || 0).toLocaleString(undefined, {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals
  });
  const formatPercent = (value, decimals = 1) => `${formatDecimal(value, decimals)}%`;
  const formatTick = (value) => formatInteger(value).padStart(5, '0');
  const formatCurrency = (value, decimals = 0) => {
    const num = Number(value || 0);
    return `${signedPrefix(num)}$${Math.abs(num).toLocaleString(undefined, {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals
    })}`;
  };
  const formatCompactCurrency = (value) => {
    const num = Number(value || 0);
    const abs = Math.abs(num);
    if (abs >= 1_000_000_000_000) return `${signedPrefix(num)}$${(abs / 1_000_000_000_000).toFixed(2)}T`;
    if (abs >= 1_000_000_000) return `${signedPrefix(num)}$${(abs / 1_000_000_000).toFixed(2)}B`;
    if (abs >= 1_000_000) return `${signedPrefix(num)}$${(abs / 1_000_000).toFixed(2)}M`;
    if (abs >= 1_000) return `${signedPrefix(num)}$${(abs / 1_000).toFixed(1)}K`;
    return `${signedPrefix(num)}$${abs.toFixed(0)}`;
  };
  const formatMillionsAdaptive = (valueInMillions) => formatCompactCurrency(Number(valueInMillions || 0) * 1_000_000);
  const formatCompact = formatInteger;
  const latestValue = (series, fallback = 0) => Array.isArray(series) && series.length ? Number(series[series.length - 1]?.value ?? fallback) : fallback;
  const appendCurrentSample = (series, value) => {
    const nextValue = Number(value || 0);
    const samples = Array.isArray(series) ? [...series] : [];
    const last = samples[samples.length - 1];
    if (last && Number(last.tick) === Number(tick)) {
      return [...samples.slice(0, -1), { ...last, value: nextValue }];
    }
    return [...samples, { tick, value: nextValue }];
  };
  const formatDelta = (value, type = 'number') => {
    const num = Number(value || 0);
    const prefix = num > 0 ? '+' : num < 0 ? '-' : '';
    const abs = Math.abs(num);
    if (type === 'currency') return `${prefix}${formatCurrency(abs)}`;
    if (type === 'percent') return `${prefix}${formatPercent(abs)}`;
    return `${prefix}${formatDecimal(abs, 1)}`;
  };
  const formatSector = (value) => {
    const sector = String(value || 'Unknown');
    return sector.charAt(0).toUpperCase() + sector.slice(1).replace(/_/g, ' ');
  };
  const formatEntityName = (name) => {
    const raw = String(name || '');
    const productMatch = raw.match(/^([A-Za-z]+)Product(\d+)$/);
    if (productMatch) return `${formatSector(productMatch[1])} Firm #${productMatch[2]}`;
    const coMatch = raw.match(/^([A-Za-z]+)Co(\d+)$/);
    if (coMatch) return `${formatSector(coMatch[1])} Firm #${coMatch[2]}`;
    const subjectMatch = raw.match(/^Subject-(\d+)$/i);
    if (subjectMatch) return `Agent ${subjectMatch[1]}`;
    const baselineMatch = raw.match(/^Baseline([A-Za-z]+)$/);
    if (baselineMatch) return `Baseline ${formatSector(baselineMatch[1])}`;
    const spaced = raw.replace(/([a-z])([A-Z])/g, '$1 $2').replace(/(\D)(\d+)$/g, '$1 $2');
    if (spaced !== raw) return spaced.trim();
    return raw || 'Unknown';
  };
  const readableEntityName = formatEntityName;
  const firmStatusTone = (state) => {
    const normalized = String(state || '').toUpperCase();
    if (['DISTRESS', 'BURN', 'BANKRUPT'].includes(normalized)) return 'negative';
    if (['SCALING', 'GROWTH'].includes(normalized)) return 'positive';
    if (['WATCH', 'WARNING'].includes(normalized)) return 'warning';
    return 'system';
  };
  const sectorColor = (sector, stressed = false) => {
    if (stressed) return { bar: 'bg-[#351722]/75', border: 'border-[#7A3A49]/45', text: 'text-rose-100', fill: '#7A3A49' };
    const normalized = String(sector || '').toLowerCase();
    if (normalized.includes('food')) return { bar: 'bg-[#4A3820]/70', border: 'border-[#8A6B36]/35', text: 'text-slate-100', fill: '#8A6B36' };
    if (normalized.includes('housing')) return { bar: 'bg-[#123A3B]/70', border: 'border-[#3D787A]/35', text: 'text-slate-100', fill: '#3D787A' };
    if (normalized.includes('health')) return { bar: 'bg-[#2E2448]/70', border: 'border-[#6E5E9E]/35', text: 'text-slate-100', fill: '#6E5E9E' };
    if (normalized.includes('bank') || normalized.includes('finance')) return { bar: 'bg-[#43361D]/70', border: 'border-[#9A7938]/35', text: 'text-slate-100', fill: '#9A7938' };
    return { bar: 'bg-[#1F2D4A]/70', border: 'border-[#51678E]/35', text: 'text-slate-100', fill: '#51678E' };
  };
  const renderSectorBadge = (category) => {
    const colors = sectorColor(category, false);
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full border border-white/10 bg-white/[0.045] px-2 py-0.5 text-[11px] font-display font-semibold text-slate-300">
        <span className="h-1.5 w-1.5 rounded-full opacity-75" style={{ backgroundColor: colors.fill }} />
        {formatSector(category)}
      </span>
    );
  };
  const selectedTrackedFirm = (metrics.trackedFirms && metrics.trackedFirms.length > 0 && metrics.trackedFirms[activeFirmIndex])
    ? metrics.trackedFirms[activeFirmIndex]
    : null;
  const selectedFirmCashHistory = selectedTrackedFirm
    ? [...(selectedTrackedFirm.history?.cash || []), { tick, value: selectedTrackedFirm.cash || 0 }]
    : [];
  const selectedFirmProfitHistory = selectedTrackedFirm
    ? [...(selectedTrackedFirm.history?.profit || []), { tick, value: selectedTrackedFirm.lastProfit || 0 }]
    : [];
  const selectedSubject = (metrics.trackedSubjects && metrics.trackedSubjects.length > 0 && metrics.trackedSubjects[activeSubjectIndex])
    ? metrics.trackedSubjects[activeSubjectIndex]
    : null;
  const hasHousingSecurity = (subject) => Boolean(
    subject?.housingSecurity
    ?? subject?.needs?.housing
    ?? subject?.ownsHousing
    ?? subject?.hasRental
    ?? subject?.metHousingNeed
  );
  const housingStatusLabel = (subject) => {
    if (!hasHousingSecurity(subject)) return 'Lacking';
    if (subject?.hasRental) return 'Rented';
    if (subject?.ownsHousing) return 'Owned';
    if (subject?.metHousingNeed) return 'Met this tick';
    return 'Secure';
  };
  const primaryAgentRisk = (subject) => {
    if (!subject) return null;
    if (!hasHousingSecurity(subject)) return 'Housing';
    if ((subject.needs?.food ?? 0) <= 0) return 'Food';
    if ((subject.health ?? 1) < 0.45) return 'Healthcare';
    if ((subject.morale ?? 1) < 0.45) return 'Morale';
    return null;
  };
  const selectedSubjectPrimaryRisk = primaryAgentRisk(selectedSubject);
  const gdpCurrentHistory = appendCurrentSample(metrics.gdpHistory, metrics.gdp || 0);
  const wageCurrentHistory = appendCurrentSample(metrics.wageHistory, metrics.avgWage || 0);
  const selectedSubjectNetWorthHistory = selectedSubject
    ? appendCurrentSample(selectedSubject.history?.netWorth || [], selectedSubject.netWorth || 0)
    : [];
  const selectedSubjectWageHistory = selectedSubject
    ? appendCurrentSample(selectedSubject.history?.wage || [], selectedSubject.wage || 0)
    : [];
  const trackedFirmSnapshotById = new Map((metrics.trackedFirms || []).map(firm => [String(firm.id ?? firm.name), firm]));
  const currentFirmRows = (rows = []) => rows.map(row => {
    const live = trackedFirmSnapshotById.get(String(row.id ?? row.name));
    return live ? { ...row, ...live } : row;
  });
  const subjectFilters = ['All', 'Working', 'Unemployed', 'Lacking Housing', 'Low Health', 'Low Morale', 'High Wealth', 'At Risk'];
  const filteredSubjects = (metrics.trackedSubjects || [])
    .map((subject, index) => ({ subject, index }))
    .filter(({ subject }) => {
      const text = `${subject.id} ${subject.name} ${subject.state} ${subject.employer || ''}`.toLowerCase();
      const matchesSearch = !subjectSearch.trim() || text.includes(subjectSearch.toLowerCase());
      const lacksHousing = !hasHousingSecurity(subject);
      const lowHealth = (subject.health || 0) < 0.45;
      const lowMorale = (subject.morale || 0) < 0.45;
      const highWealth = (subject.netWorth || 0) > Math.max(10000, (metrics.netWorth || 0) * 1_000_000 / Math.max(1, metrics.trackedSubjects?.length || 1));
      const atRisk = lowHealth || lowMorale || lacksHousing || (subject.cash || 0) < 0;
      const matchesFilter = subjectFilter === 'All'
        || (subjectFilter === 'Working' && subject.state === 'WORKING')
        || (subjectFilter === 'Unemployed' && subject.state === 'UNEMPLOYED')
        || (subjectFilter === 'Lacking Housing' && lacksHousing)
        || (subjectFilter === 'Low Health' && lowHealth)
        || (subjectFilter === 'Low Morale' && lowMorale)
        || (subjectFilter === 'High Wealth' && highWealth)
        || (subjectFilter === 'At Risk' && atRisk);
      return matchesSearch && matchesFilter;
    });

  const normalizeLog = (log, index) => {
    const rawType = String(log.type || 'SYS').toUpperCase();
    const message = String(log.message || log.txt || '');
    let type = rawType === 'GOV' ? 'Policy' : rawType === 'ECO' ? 'Market' : rawType === 'WARN' ? 'Error' : rawType === 'BANK' ? 'Bank' : 'System';
    if (/firm/i.test(message)) type = 'Firm';
    if (/subject|agent|household/i.test(message)) type = 'Agent';
    if (/bank|loan|credit|deposit/i.test(message)) type = 'Bank';
    const severity = rawType === 'WARN' || /error|critical|failed/i.test(message) ? 'Error' : /warn|risk|stress/i.test(message) ? 'Warning' : 'Info';
    const durationMatch = message.match(/(\d+(?:\.\d+)?)\s*ms/i);
    return {
      ...log,
      index,
      tick: log.tick ?? 0,
      type,
      rawType,
      entity: log.entity || (type === 'System' ? 'Simulation Core' : type),
      message,
      severity,
      duration: durationMatch ? `${durationMatch[1]} ms` : (log.duration || log.change || '-')
    };
  };
  const normalizedLogs = logs.map(normalizeLog);
  const logTypes = ['All', 'System', 'Policy', 'Market', 'Agent', 'Firm', 'Bank', 'Error'];
  const severityTypes = ['All', 'Info', 'Warning', 'Error'];
  const logTypeCounts = normalizedLogs.reduce((acc, log) => {
    acc.All += 1;
    if (log.type !== 'Error') acc[log.type] = (acc[log.type] || 0) + 1;
    if (log.severity === 'Error') acc.Error = (acc.Error || 0) + 1;
    return acc;
  }, { All: 0, System: 0, Policy: 0, Market: 0, Agent: 0, Firm: 0, Bank: 0, Error: 0 });
  const filteredLogs = normalizedLogs.filter(log => {
    const search = logSearch.trim().toLowerCase();
    const matchesSearch = !search || `${log.tick} ${log.type} ${log.entity} ${log.message}`.toLowerCase().includes(search);
    const matchesType = logTypeFilter === 'All' || log.type === logTypeFilter || (logTypeFilter === 'Error' && log.severity === 'Error');
    const matchesSeverity = logSeverityFilter === 'All' || log.severity === logSeverityFilter;
    return matchesSearch && matchesType && matchesSeverity;
  });
  const selectedLog = filteredLogs[selectedLogIndex] || filteredLogs[0] || null;

  const renderFirmTable = (title, rows) => {
    const liveRows = currentFirmRows(rows || []);
    return (
    <div className="tech-panel p-4 rounded-lg border border-white/5 bg-slate-900/55">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-[13px] font-semibold text-slate-300">{title}</h3>
        <span className="text-[10px] text-slate-500">{liveRows.length} current rows</span>
      </div>
      <div className="overflow-y-auto command-scroll max-h-[290px]">
        <table className="w-full table-fixed text-[12.5px] text-slate-300">
          <thead className="sticky top-0 z-10 bg-slate-900/95 text-[11px] font-display text-slate-400">
            <tr>
              <th className="text-left py-2 pr-2 w-[30%]">Firm</th>
              <th className="text-left py-2 pr-2 w-[16%]">Sector</th>
              <th className="text-right py-2 pr-2">Cash</th>
              <th className="text-right py-2 pr-2">Employees</th>
              <th className="text-right py-2 pr-2">Price</th>
              <th className="text-right py-2 pr-2">Wage</th>
              <th className="text-right py-2">Profit</th>
            </tr>
          </thead>
          <tbody>
            {liveRows.length ? liveRows.slice(0, 8).map(row => {
              const selected = selectedTrackedFirm && String(row.id ?? row.name) === String(selectedTrackedFirm.id ?? selectedTrackedFirm.name);
              return (
              <tr
                key={row.id ?? row.name}
                className={`border-b border-white/5 transition-colors ${
                  selected
                    ? "bg-white/[0.065] text-slate-100"
                    : row.cash < 1000 || row.lastProfit < 0
                      ? "bg-[#351722]/25 text-slate-300"
                      : "hover:bg-white/[0.035] text-slate-300"
                }`}
              >

                <td className="py-2 pr-2 font-display text-xs text-slate-200 truncate" title={row.name}>{readableEntityName(row.name)}</td>
                <td className="py-2 pr-2 font-display text-slate-300">{renderSectorBadge(row.category)}</td>
                <td className="py-2 pr-2 text-right font-mono tabular-nums text-slate-200">{formatCurrency(row.cash)}</td>
                <td className="py-2 pr-2 text-right font-mono tabular-nums text-slate-200">
                  {row.category === 'Healthcare'
                    ? (row.doctorEmployees || row.medicalEmployees || row.employees)
                    : row.employees}
                </td>
                <td className="py-2 pr-2 text-right font-mono tabular-nums text-slate-200">{formatCurrency(row.price, 2)}</td>
                <td className="py-2 pr-2 text-right font-mono tabular-nums text-slate-200">{formatCurrency(row.wageOffer, 2)}</td>
                <td className={`py-2 text-right font-mono tabular-nums ${(row.lastProfit || 0) >= 0 ? 'text-slate-200' : 'text-rose-200'}`}>{formatCurrency(row.lastProfit, 2)}</td>
              </tr>
            )}) : (
              <tr>
                <td colSpan={7} className="py-2 text-center text-slate-500 text-xs">No data yet</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
  };

  useEffect(() => {
    if (autoScrollLogs) {
      const container = logsContainerRef.current;
      if (container) {
        container.scrollTop = container.scrollHeight;
      }
    }
  }, [logs, autoScrollLogs]);

  useEffect(() => {
    return () => {
      if (configUpdateTimer.current) {
        clearTimeout(configUpdateTimer.current);
      }
    };
  }, []);

  // WebSocket Connection (with auto-reconnect)
  useEffect(() => {
    let cancelled = false;
    let effectSocket = null;

    const connect = () => {
      if (cancelled) return;
      const socket = new WebSocket(wsEndpoint);
      ws.current = socket;
      effectSocket = socket;

      socket.onopen = () => {
        if (cancelled || ws.current !== socket) return;
        setWsConnected(true);
        console.log("WS Connected");
      };

      socket.onmessage = (event) => {
        if (cancelled || ws.current !== socket) return;
        const data = JSON.parse(event.data);
        if (data.type === "SETUP_COMPLETE") {
          setIsInitializing(false);
          setIsInitialized(true);
          setActiveView('DASHBOARD');
          setIsRunning(true);
          const cfg = setupConfigRef.current;
          // Sync local config with setup
          setConfig(prev => ({
            ...prev,
            wageTax: cfg.wage_tax,
            profitTax: cfg.profit_tax,
            enableLlmGovernment: cfg.enable_llm_government !== false
          }));
          // Add boot sequence logs
          setLogs([
            { tick: 0, type: 'SYS', txt: 'INITIALIZING KERNEL...' },
            { tick: 0, type: 'SYS', txt: 'LOADING CONFIGURATION MAP...' },
            { tick: 0, type: 'SYS', txt: `SPAWNING ${cfg.num_households} AGENTS...` },
            { tick: 0, type: 'ECO', txt: 'WARMUP PHASE STARTED' }
          ]);
          // Auto-start simulation after setup
          if (ws.current && ws.current.readyState === WebSocket.OPEN) {
            ws.current.send(JSON.stringify({ command: "START" }));
          }
        } else if (data.type === "RESET") {
          setTick(0);
          setLogs([]);
          setMetrics({
            unemployment: 99.0,
            gdp: 0,
            govDebt: 0,
            govProfit: 0,
            happiness: 50,
            housingInv: 0,
            avgWage: 0,
            avgExpectedWage: 0.0,
            avgExpectedWageUnemployed: 0.0,
            giniCoefficient: 0.0,
            top10Share: 0.0,
            bottom50Share: 0.0,
            gdpHistory: [],
            unemploymentHistory: [],
            wageHistory: [],
            medianWageHistory: [],
            happinessHistory: [],
            healthHistory: [],
            govProfitHistory: [],
            govDebtHistory: [],
            giniHistory: [],
            top10ShareHistory: [],
            bottom50ShareHistory: [],
            housingHistory: [],
            foodHistory: [],
            servicesHistory: [],
            priceHistory: { food: [], housing: [], services: [], healthcare: [] },
            supplyHistory: { food: [], housing: [], services: [], healthcare: [] },
            trackedSubjects: [],
            trackedFirms: [],
            policyChanges: [],
            latestGovernmentDecision: null,
            llmGovernment: { enabled: false, status: 'disabled', latestDecision: null },
            governmentPolicy: {}
          });
          setActiveSubjectIndex(0);
          setActiveFirmIndex(0);
          setFirmStats(null);
          setIsRunning(false);
          setIsInitialized(false);
          setActiveView('CONFIG'); // Go back to config on reset
        } else if (data.type === "STABILIZERS_UPDATED") {
          console.log("Stabilizers updated:", data.state);
        } else if (data.type === "STARTED") {
          setIsRunning(true);
        } else if (data.type === "STOPPED") {
          setIsRunning(false);
        } else if (data.metrics) {
          setTick(data.tick);
          // Merge with existing metrics to preserve defaults if backend is missing keys
          setMetrics(prev => ({
            ...prev,
            ...data.metrics,
            // Ensure nested objects/arrays are not overwritten with undefined if missing
            priceHistory: data.metrics.priceHistory || prev.priceHistory || { food: [], housing: [], services: [], healthcare: [] },
            supplyHistory: data.metrics.supplyHistory || prev.supplyHistory || { food: [], housing: [], services: [], healthcare: [] },
            netWorthHistory: data.metrics.netWorthHistory || prev.netWorthHistory || [],
            trackedSubjects: data.metrics.trackedSubjects || prev.trackedSubjects || [],
            trackedFirms: data.metrics.trackedFirms || prev.trackedFirms || []
          }));
          if (data.firm_stats) {
            setFirmStats(data.firm_stats);
          }
          if (data.logs && data.logs.length > 0) {
            setLogs(prev => [...prev.slice(-300), ...data.logs]);
          }
        } else if (data.error) {
          console.error("Simulation error:", data.error);
          setIsInitializing(false);
        }
      };

      socket.onclose = () => {
        if (ws.current !== socket) return;
        setWsConnected(false);
        console.log("WS Disconnected");
        setIsRunning(false);
        setIsInitializing(false);
        if (!cancelled) {
          reconnectTimerRef.current = setTimeout(connect, 1200);
        }
      };

      socket.onerror = (err) => {
        if (cancelled || ws.current !== socket) return;
        console.error("WebSocket error:", err);
        setIsInitializing(false);
      };
    };

    connect();

    return () => {
      cancelled = true;
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
      }
      if (effectSocket) {
        effectSocket.close();
      }
    };
  }, [wsEndpoint]);

  const handleInitialize = () => {
    if (setupConfig.num_households < 1 || setupConfig.num_firms < 1 || setupConfig.seed < 0) {
      console.error("Invalid setup config. num_households and num_firms must be >= 1; seed must be >= 0.");
      return;
    }
    if (ws.current && ws.current.readyState === WebSocket.OPEN) {
      setIsInitializing(true);
      ws.current.send(JSON.stringify({
        command: "SETUP",
        config: setupConfig
      }));
    } else {
      console.error("WebSocket is not connected. Cannot initialize.");
    }
  };

  const toggleRun = () => {
    if (ws.current && ws.current.readyState === WebSocket.OPEN) {
      if (isRunning) {
        ws.current.send(JSON.stringify({ command: "STOP" }));
      } else {
        ws.current.send(JSON.stringify({ command: "START" }));
      }
      // Don't update state here - wait for backend confirmation
    }
  };

  const handleReset = () => {
    if (ws.current && ws.current.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify({ command: "RESET" }));
    }
  };

  const flushConfigUpdates = () => {
    if (
      pendingConfigRef.current &&
      ws.current &&
      ws.current.readyState === WebSocket.OPEN &&
      isInitialized
    ) {
      const supportedRuntimeConfig = {
        wageTax: pendingConfigRef.current.wageTax,
        profitTax: pendingConfigRef.current.profitTax,
        minimumWage: pendingConfigRef.current.minimumWage,
        unemploymentBenefitRate: pendingConfigRef.current.unemploymentBenefitRate,
        enableLlmGovernment: pendingConfigRef.current.enableLlmGovernment,
        benefitLevel: pendingConfigRef.current.benefitLevel,
        publicWorks: pendingConfigRef.current.publicWorks,
        minimumWagePolicy: pendingConfigRef.current.minimumWagePolicy,
        sectorSubsidyTarget: pendingConfigRef.current.sectorSubsidyTarget,
        sectorSubsidyLevel: pendingConfigRef.current.sectorSubsidyLevel,
        infrastructureSpending: pendingConfigRef.current.infrastructureSpending,
        technologySpending: pendingConfigRef.current.technologySpending,
        socialSpending: pendingConfigRef.current.socialSpending,
        priceStabilizationTarget: pendingConfigRef.current.priceStabilizationTarget,
        priceStabilizationLevel: pendingConfigRef.current.priceStabilizationLevel,
        rentStabilizationLevel: pendingConfigRef.current.rentStabilizationLevel,
        bailoutPolicy: pendingConfigRef.current.bailoutPolicy,
        bailoutTarget: pendingConfigRef.current.bailoutTarget,
        bailoutBudget: pendingConfigRef.current.bailoutBudget,
      };
      ws.current.send(JSON.stringify({ command: "CONFIG", config: supportedRuntimeConfig }));
    }
    pendingConfigRef.current = null;
    configUpdateTimer.current = null;
  };

  const handleConfigChange = (key, value) => {
    const newConfig = { ...config, [key]: value };
    setConfig(newConfig);
    pendingConfigRef.current = newConfig;
    if (configUpdateTimer.current) {
      clearTimeout(configUpdateTimer.current);
    }
    configUpdateTimer.current = setTimeout(flushConfigUpdates, 400);
  };

  const resetPolicyDefaults = () => {
    const defaults = {
      wageTax: 0.15,
      profitTax: 0.20,
      minimumWage: 20,
      unemploymentBenefitRate: 0,
      enableLlmGovernment: false,
      benefitLevel: 'neutral',
      publicWorks: false,
      minimumWagePolicy: 'neutral',
      sectorSubsidyTarget: 'none',
      sectorSubsidyLevel: 0,
      infrastructureSpending: 'none',
      technologySpending: 'none',
      socialSpending: 'medium',
      priceStabilizationTarget: 'none',
      priceStabilizationLevel: 'off',
      rentStabilizationLevel: 'off',
      bailoutPolicy: 'off',
      bailoutTarget: 'none',
      bailoutBudget: 0
    };
    setConfig(prev => {
      const next = { ...prev, ...defaults };
      pendingConfigRef.current = next;
      if (configUpdateTimer.current) clearTimeout(configUpdateTimer.current);
      configUpdateTimer.current = setTimeout(flushConfigUpdates, 120);
      return next;
    });
    setSetupConfig(prev => ({
      ...prev,
      wage_tax: defaults.wageTax,
      profit_tax: defaults.profitTax,
      enable_llm_government: defaults.enableLlmGovernment,
      disable_stabilizers: false,
      disabled_agents: []
    }));
  };

  // Helper to update setup config
  const sendStabilizerCommand = (disableFlag, disabledAgents) => {
    if (ws.current && ws.current.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify({
        command: "STABILIZERS",
        disable_stabilizers: disableFlag,
        disabled_agents: disabledAgents
      }));
    }
  };

  const handleSetupChange = (key, value) => {
    setSetupConfig(prev => {
      const next = { ...prev, [key]: value };
      if (key === 'disable_stabilizers' && value === false) {
        next.disabled_agents = [];
      }
      if (isInitialized && (key === 'disable_stabilizers')) {
        sendStabilizerCommand(next.disable_stabilizers, next.disabled_agents);
      }
      return next;
    });
    // Also update the runtime config preview
    if (key === 'wage_tax') setConfig(prev => ({ ...prev, wageTax: value }));
    if (key === 'profit_tax') setConfig(prev => ({ ...prev, profitTax: value }));
    if (key === 'enable_llm_government') setConfig(prev => ({ ...prev, enableLlmGovernment: value }));
  };

  const toggleStabilizerAgent = (agentKey) => {
    setSetupConfig(prev => {
      const disabled = prev.disabled_agents || [];
      const exists = disabled.includes(agentKey);
      const updated = exists ? disabled.filter(a => a !== agentKey) : [...disabled, agentKey];
      const next = { ...prev, disabled_agents: updated };
      if (isInitialized) {
        sendStabilizerCommand(next.disable_stabilizers, next.disabled_agents);
      }
      return next;
    });
  };

  const enumOptions = {
    level4: [
      { value: 'none', label: 'None' },
      { value: 'low', label: 'Low' },
      { value: 'medium', label: 'Medium' },
      { value: 'high', label: 'High' },
    ],
    sectors: [
      { value: 'none', label: 'None' },
      { value: 'food', label: 'Food' },
      { value: 'housing', label: 'Housing' },
      { value: 'services', label: 'Services' },
      { value: 'healthcare', label: 'Healthcare' },
    ],
    stabilization: [
      { value: 'off', label: 'Off' },
      { value: 'monitor', label: 'Monitor' },
      { value: 'soft', label: 'Soft' },
      { value: 'strict', label: 'Strict' },
    ],
    benefit: [
      { value: 'low', label: 'Low' },
      { value: 'neutral', label: 'Neutral' },
      { value: 'high', label: 'High' },
      { value: 'crisis', label: 'Crisis' },
    ],
    wagePolicy: [
      { value: 'low', label: 'Low' },
      { value: 'neutral', label: 'Neutral' },
      { value: 'high', label: 'High' },
    ],
    bailoutPolicy: [
      { value: 'off', label: 'Off' },
      { value: 'sector', label: 'Sector' },
      { value: 'all', label: 'All' },
    ],
    subsidyLevels: [
      { value: '0', label: '0%' },
      { value: '10', label: '10%' },
      { value: '25', label: '25%' },
      { value: '50', label: '50%' },
    ],
    bailoutBudgets: [
      { value: '0', label: '$0' },
      { value: '5000', label: '$5K' },
      { value: '10000', label: '$10K' },
      { value: '25000', label: '$25K' },
      { value: '50000', label: '$50K' },
    ],
  };

  const llmGov = metrics.llmGovernment || { status: 'disabled', latestDecision: null };
  const rawLatestDecision = llmGov.latestDecision || metrics.latestGovernmentDecision || null;
  const hasLatestDecisionContent = rawLatestDecision && Object.keys(rawLatestDecision).length > 0 && Boolean(
    rawLatestDecision.rationale
    || rawLatestDecision.reasoning
    || rawLatestDecision.decision_summary
    || rawLatestDecision.primary_goal
    || rawLatestDecision.status
    || rawLatestDecision.appliedTick
    || rawLatestDecision.snapshotTick
    || Object.keys(rawLatestDecision.decisions || rawLatestDecision.applied_changes || {}).length
    || (Array.isArray(rawLatestDecision.rejected_changes) && rawLatestDecision.rejected_changes.length)
  );
  const latestDecisionTick = rawLatestDecision
    ? Number(rawLatestDecision.appliedTick ?? rawLatestDecision.tick ?? rawLatestDecision.snapshotTick ?? 0)
    : 0;
  const latestDecision = hasLatestDecisionContent && rawLatestDecision && (!latestDecisionTick || latestDecisionTick <= Number(tick || 0))
    ? rawLatestDecision
    : null;
  const currentRunPolicyChanges = (metrics.policyChanges || []).filter(action => Number(action.tick || 0) <= Number(tick || 0));
  const previousRunPolicyChanges = (metrics.policyChanges || []).filter(action => Number(action.tick || 0) > Number(tick || 0));
  const isPolicyAssistantActive = Boolean(config.enableLlmGovernment || setupConfig.enable_llm_government || llmGov.enabled);
  const llmStatusLabel = {
    disabled: 'Inactive',
    provider_unavailable: 'Policy assistant inactive',
    thinking: 'Policy evaluation running',
    ready: 'Policy assistant ready',
    applying: 'Applying policy',
    error: 'AI policy error'
  }[llmGov.status] || (isPolicyAssistantActive ? 'Policy assistant ready' : 'Inactive');
  const llmActivityLevel = llmGov.status === 'thinking' || llmGov.status === 'applying'
    ? 'high'
    : (metrics.govProfit || 0) < 0 ? 'high' : 'normal';
  const llmColorClass = llmGov.status === 'provider_unavailable' || llmGov.status === 'error'
    ? 'text-[#D89B45] border-white/10 bg-white/[0.055]'
    : llmGov.status === 'thinking' || llmGov.status === 'applying'
      ? 'text-amber-200 border-white/10 bg-white/[0.055]'
      : isPolicyAssistantActive
        ? 'text-emerald-200 border-white/10 bg-white/[0.055]'
        : 'text-slate-400 border-white/10 bg-white/[0.045]';
  const decisionAcceptedEntries = Object.entries(latestDecision?.decisions || latestDecision?.applied_changes || {}).filter(([, value]) => value !== undefined && value !== null);
  const decisionRejectedEntries = Array.isArray(latestDecision?.rejected_changes) ? latestDecision.rejected_changes : [];
  const decisionSummary = latestDecision?.rationale || latestDecision?.reasoning || latestDecision?.decision_summary || '';
  const decisionDebug = latestDecision?.parse_error || latestDecision?.raw_response || latestDecision?.error || latestDecision?.lastError || llmGov.lastError || '';
  const friendlyModelName = (() => {
    const raw = String(llmGov.model || llmGov.provider || 'Rule-based policy');
    const parts = raw.split('/');
    return parts[parts.length - 1] || raw;
  })();
  const formatPolicyName = (value) => {
    const raw = String(value || 'Policy');
    const known = {
      bailout_budget: 'Bailout budget',
      bailout_target: 'Bailout target',
      bailout_policy: 'Bailout policy',
      rent_stabilization_level: 'Rent stabilization',
      price_stabilization_level: 'Price stabilization',
      price_stabilization_target: 'Price target',
      wageTax: 'Wage tax',
      profitTax: 'Corporate profit tax',
      minimumWage: 'Minimum wage floor',
      unemploymentBenefitRate: 'Unemployment benefits',
      enableLlmGovernment: 'Policy assistant'
    };
    if (known[raw]) return known[raw];
    return raw.replace(/_/g, ' ').replace(/([a-z])([A-Z])/g, '$1 $2').replace(/\b\w/g, c => c.toUpperCase());
  };
  const formatPolicyValue = (key, value) => {
    const normalized = String(key || '').toLowerCase();
    if (normalized.includes('budget') || normalized.includes('wage') || normalized.includes('tax') || normalized.includes('benefit')) {
      if (normalized.includes('tax') || normalized.includes('benefit')) return typeof value === 'number' && Math.abs(value) <= 1 ? formatPercent(value * 100, 1) : String(value);
      return formatCurrency(value);
    }
    if (value === 'off' || value === 'none' || value === false) return normalized.includes('target') ? 'None' : 'Off';
    if (value === true) return 'On';
    return String(value || 'None').replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
  };
  const formatPolicyMessage = (action) => {
    const key = action?.policy || action?.type || action?.key || action?.lever || 'policy';
    const value = action?.value ?? action?.new_value ?? action?.level ?? action?.target;
    if (value !== undefined && value !== null) return `${formatPolicyName(key)} set to ${formatPolicyValue(key, value)}`;
    return action?.reason || formatPolicyName(key);
  };

  return (
    <div className="min-h-screen bg-[var(--background-base)] text-slate-300 font-display selection:bg-amber-400/25 overflow-hidden flex">
      <style>{techStyles}</style>

      {/* SIDEBAR NAVIGATION */}
      <nav className="w-28 bg-[#0B1120]/92 backdrop-blur-md border-r border-white/5 flex flex-col justify-between z-20 shrink-0">
        <div>
          <div className="h-20 flex flex-col items-center justify-center border-b border-slate-800/80 mb-2">
            <Triangle className="text-amber-300 fill-amber-300/10" size={28} strokeWidth={1.5} />
            <div className="mt-1 text-[10px] font-bold tracking-[0.16em] text-slate-200">EcoSim</div>
          </div>
          {/* CONFIG is always active, but others are disabled until initialized */}
          <NavButton icon={Settings} label="Config" isActive={activeView === 'CONFIG'} onClick={() => setActiveView('CONFIG')} />
          <NavButton icon={Activity} label="Command" isActive={activeView === 'DASHBOARD'} onClick={() => setActiveView('DASHBOARD')} disabled={!isInitialized} />
          <NavButton icon={Users} label="Population" isActive={activeView === 'SUBJECTS'} onClick={() => setActiveView('SUBJECTS')} disabled={!isInitialized} />
          <NavButton icon={Building2} label="Markets" isActive={activeView === 'FIRMS'} onClick={() => setActiveView('FIRMS')} disabled={!isInitialized} />
          <NavButton icon={Wallet} label="Finance" isActive={activeView === 'FINANCE'} onClick={() => setActiveView('FINANCE')} disabled={!isInitialized} />
          <NavButton icon={Landmark} label="Government" isActive={activeView === 'GOVERNMENT'} onClick={() => setActiveView('GOVERNMENT')} disabled={!isInitialized} />
          <NavButton icon={Terminal} label="Logs" isActive={activeView === 'LOGS'} onClick={() => setActiveView('LOGS')} disabled={!isInitialized} />
        </div>

        {/* CONNECTION STATUS */}
        <div className="flex flex-col items-center space-y-2 mt-auto group relative cursor-pointer">
          <div className={`h-2.5 w-2.5 rounded-full ${isInitialized ? 'bg-emerald-500' : 'bg-rose-500/80'}`}></div>
          <span className={`text-[9px] font-mono tracking-widest font-bold ${isInitialized ? 'text-emerald-500' : 'text-rose-400'}`}>
            {isInitialized ? 'ONLINE' : 'OFFLINE'}
          </span>
          {/* Tooltip */}
          <div className="absolute left-full ml-4 bottom-0 px-2 py-1 bg-slate-800 text-slate-200 text-[10px] font-mono rounded border border-slate-700 opacity-0 group-hover:opacity-100 transition-opacity duration-200 pointer-events-none whitespace-nowrap z-50 shadow-xl">
            {isInitialized ? 'Connected to Simulation Core' : 'Awaiting Connection...'}
          </div>
        </div>
      </nav>

      {/* MAIN CONTENT AREA */}
      <main className="flex-1 bg-tech-grid relative flex flex-col min-w-0">
        {/* TOP BAR */}
        <header className="h-[var(--topbar-height)] border-b border-white/5 bg-[#0F172A]/88 flex items-center justify-between px-8 backdrop-blur-md z-10 shrink-0">
          <div className="flex items-center space-x-6">
            <h1 className="text-lg font-bold tracking-tight text-slate-100">
              Eco<span className="text-amber-300">Sim</span> Command Deck
            </h1>
            <div className="h-6 w-[1px] bg-slate-700"></div>
            <div className="flex items-center bg-slate-900 border border-slate-700/50 rounded-md px-3 py-1 shadow-[inset_0_2px_10px_rgba(0,0,0,0.5)]">
              <div className={`h-2 w-2 rounded-full mr-3 ${isInitialized ? 'bg-amber-300 shadow-[0_0_8px_rgba(251,191,36,0.45)] animate-pulse' : 'bg-slate-600'}`}></div>
              <div className="font-mono text-sm text-amber-300/80 mr-2 uppercase text-[10px] tracking-widest">Tick</div>
              {isInitialized ? (
                <div className="font-mono tabular-nums text-lg font-bold text-amber-200 drop-shadow-[0_0_5px_rgba(251,191,36,0.28)] tracking-widest">
                  {formatTick(tick)}
                </div>
              ) : (
                <span className="font-mono text-xs text-amber-500/70 tracking-widest animate-pulse">STANDBY</span>
              )}
            </div>
            <StatusPill tone={isRunning ? 'positive' : isInitialized ? 'warning' : 'muted'}>
              {isRunning ? 'Running' : isInitialized ? 'Suspended' : wsConnected ? 'Ready' : 'Backend offline'}
            </StatusPill>
          </div>

          {isInitialized && (
            <div className="flex items-center space-x-4 animate-in fade-in slide-in-from-right-4 duration-500">
              <button onClick={toggleRun} className={`btn-tech px-5 py-2 flex items-center space-x-2 ${isRunning ? 'active' : ''}`} aria-label={isRunning ? 'Suspend simulation' : 'Resume simulation'}>
                {isRunning ? <Pause size={18} /> : <Play size={18} />}
                <span>{isRunning ? 'Suspend' : 'Resume'}</span>
              </button>
              <button onClick={handleReset} className="btn-tech btn-danger p-2" aria-label="Reset simulation" title="Reset simulation">
                <RotateCcw size={18} />
              </button>
            </div>
          )}
        </header>

        {/* CONTENT SCROLLABLE */}
        <div className="h-[calc(100vh-var(--topbar-height))] overflow-auto command-scroll relative flex flex-col">
          <div className="w-full max-w-[1840px] mx-auto px-4 md:px-6 xl:px-8 2xl:px-10 py-6 pb-10 relative flex-1 flex flex-col min-h-0">

            {/* DASHBOARD VIEW */}
            {activeView === 'DASHBOARD' && (
              <div className="animate-in fade-in slide-in-from-bottom-4 duration-500">
                <PageHeader
                  eyebrow="Command"
                  title="Economic Command Deck"
                  summary={`Current tick shows ${formatMillionsAdaptive(metrics.gdp)} GDP output, ${formatPercent(metrics.unemployment || 0)} unemployment, and a ${metrics.govProfit >= 0 ? 'positive' : 'negative'} fiscal balance of ${formatMillionsAdaptive(metrics.govProfit || 0)}.`}
                />

                <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3 xl:gap-4 mb-4">
                  <StatTile label="GDP Output" value={formatMillionsAdaptive(metrics.gdp)} caption="Current economic output" />
                  <StatTile label="Unemployment" value={formatPercent(metrics.unemployment || 0)} caption="Current tick" alert={(metrics.unemployment || 0) > 25} />
                  <StatTile label="Employment" value={formatPercent(100 - (metrics.unemployment || 0))} caption="Current tick" />
                  <StatTile label="Average Wage" value={formatCurrency(metrics.avgWage || 0, 2)} caption="Current worker mean" />
                  <StatTile label="Macro Stress" value={formatDecimal(Math.min(100, Math.max(0, (metrics.unemployment || 0) * 0.45 + (100 - (metrics.happiness || 0)) * 0.4 + (metrics.firmDistressPressure || 0) * 0.15)), 0)} suffix="/100" caption="Composite pressure" alert={(metrics.unemployment || 0) > 35} />
                  <StatTile label="Fiscal Balance" value={formatMillionsAdaptive(metrics.govProfit || 0)} caption="Current tick net fiscal flow" alert={(metrics.govProfit || 0) < 0} />
                </div>

                <div className="grid grid-cols-12 gap-4">
                  <div className="col-span-12 xl:col-span-7 min-h-[330px]">
                    <LineChart
                      title="Economic pulse"
                      data={gdpCurrentHistory}
                      color="#FBBF24"
                      headlineValue={metrics.gdp || 0}
                      headlineLabel="Current GDP output"
                      subtitle="GDP output over time"
                      timeRange="Last 250 ticks"
                      height={240}
                      formatValue={v => formatMillionsAdaptive(v)}
                    />
                  </div>

                  <div className="col-span-12 xl:col-span-5 tech-panel p-4">
                    <SectionHeader icon={AlertTriangle} title="Population Stress" meta={`Tick ${formatTick(tick)}`} />
                    <div className="grid grid-cols-2 gap-3">
                      <SystemDistressGauge
                        unemployment={metrics.unemployment}
                        happiness={metrics.happiness}
                        firmDistress={metrics.firmDistressPressure || metrics.burn_mode_firm_count || 0}
                      />
                      <div className="space-y-3">
                        <StatTile label="Happiness" value={formatDecimal(metrics.happiness || 0, 1)} suffix="/100" caption="Current population mean" />
                        <StatTile label="Health Index" value={formatDecimal(latestValue(metrics.healthHistory, 0), 1)} suffix="/100" caption="Latest sampled history" />
                      </div>
                    </div>
                  </div>

                  <div className="col-span-12 lg:col-span-4 tech-panel p-4">
                    <SectionHeader icon={Building2} title="Market map" meta={firmStats ? `Sized by firm count Â· ${formatInteger(firmStats.total_firms)} firms` : 'Awaiting firms'} />
                    {firmStats?.categories?.length ? (
                      <div className="space-y-3">
                        {firmStats.categories.map(cat => {
                          const totalFirms = Math.max(1, firmStats.total_firms || 1);
                          const share = Math.max(5, (cat.firm_count || 0) / totalFirms * 100);
                          const distressed = (cat.avg_cash || 0) < 2000;
                          const colors = sectorColor(cat.category, distressed);
                          return (
                            <div key={cat.category}>
                              <div className="flex justify-between text-xs mb-1">
                                <span className="text-slate-300">{formatSector(cat.category)}</span>
                                <span className="font-mono tabular-nums text-slate-500">{formatInteger(cat.firm_count)} firms Â· avg cash {formatCurrency(cat.avg_cash || 0)}</span>
                              </div>
                              <div className="h-8 rounded bg-slate-950/60 border border-slate-800 overflow-hidden">
                                <div
                                  className={`h-full ${colors.bar} flex items-center px-2 text-[10px] text-slate-100`}
                                  style={{ width: `${Math.min(100, share)}%` }}
                                >
                                  {formatInteger(cat.total_employees || 0)} employees
                                </div>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    ) : (
                      <EmptyState title="Market telemetry pending">Sector health appears after the simulation emits firm statistics.</EmptyState>
                    )}
                  </div>

                  <div className="col-span-12 lg:col-span-4 tech-panel p-4">
                    <SectionHeader icon={Wallet} title="Finance summary" meta={metrics.activeLoans ? `${formatInteger(metrics.activeLoans)} government-backed loans` : 'Telemetry coverage'} />
                    <div className="grid grid-cols-2 gap-3">
                      <StatTile label="Government-backed loans" value={formatInteger(metrics.activeLoans || 0)} caption="Current active loan count" />
                      <StatTile label="Treasury debt" value={formatMillionsAdaptive(metrics.govDebt || 0)} caption="Negative treasury balance" alert={(metrics.govDebt || 0) > 0} />
                    </div>
                    <div className="mt-3">
                      <EmptyState icon={Wallet} title="Bank reserve telemetry unavailable">This run is not exposing bank reserve telemetry.</EmptyState>
                    </div>
                  </div>

                  <div className="col-span-12 lg:col-span-4 tech-panel priority-corners p-4">
                    <SectionHeader icon={Landmark} title="Policy Assistant" meta={llmStatusLabel} />
                    <div className="space-y-3">
                      <StatusPill tone={llmGov.status === 'thinking' || llmGov.status === 'applying' ? 'system' : llmGov.status === 'error' ? 'warning' : isPolicyAssistantActive ? 'ai' : 'muted'}>
                        {llmStatusLabel}
                      </StatusPill>
                      <p className="text-sm text-slate-300 leading-relaxed">
                        {latestDecision?.rationale || latestDecision?.reasoning || latestDecision?.decision_summary || 'Manual controls are active. Enable the AI Policy Engine from Government once policy-run history is available.'}
                      </p>
                      <div className="rounded border border-slate-800 bg-slate-950/45 p-3 text-xs text-slate-500">
                        Suggested next inspection: {(metrics.unemployment || 0) > 20 ? 'Population stress and labor conditions.' : (metrics.govProfit || 0) < 0 ? 'Fiscal balance and stabilization tools.' : 'Markets and sector concentration.'}
                      </div>
                    </div>
                  </div>

                  <div className="col-span-12 lg:col-span-8 grid grid-cols-1 xl:grid-cols-2 gap-4">
                    <LineChart
                      title="Wage trend"
                      data={[wageCurrentHistory, metrics.medianWageHistory]}
                      color={["#FBBF24", "#B8C7D9"]}
                      legend={["Mean wage", "Median wage"]}
                      headlineValue={metrics.avgWage || 0}
                      headlineLabel="Current average wage"
                      subtitle="Mean wage over time"
                      timeRange="Last 250 ticks"
                      height={160}
                      formatValue={v => formatCurrency(v, 2)}
                    />
                    <LineChart
                      title="Market prices"
                      data={[
                        metrics.priceHistory?.food || [],
                        metrics.priceHistory?.housing || [],
                        metrics.priceHistory?.services || [],
                        metrics.priceHistory?.healthcare || []
                      ]}
                      color={["#FBBF24", "#B8C7D9", "#8EA8C3", "#C4CAD6"]}
                      legend={["Food", "Housing", "Services", "Healthcare"]}
                      headlineLabel="Latest sampled"
                      subtitle="Average sector prices"
                      timeRange="Last 250 ticks"
                      height={160}
                      formatValue={v => formatCurrency(v, 2)}
                    />
                  </div>

                  <div className="col-span-12 lg:col-span-4 tech-panel p-4">
                    <SectionHeader icon={Terminal} title="Recent signals" meta="Economic signals" />
                    <div className="space-y-2 max-h-[270px] overflow-y-auto command-scroll pr-1">
                      {[
                        {
                          label: `Unemployment ${formatPercent(metrics.unemployment || 0)}`,
                          body: (metrics.unemployment || 0) > 25 ? 'Unemployment remains elevated.' : 'Labor market pressure is contained.',
                          tone: (metrics.unemployment || 0) > 25 ? 'warning' : 'positive'
                        },
                        {
                          label: `Fiscal flow ${formatDelta((metrics.govProfit || 0) * 1_000_000, 'currency')}`,
                          body: (metrics.govProfit || 0) < 0 ? 'Fiscal balance is negative this tick.' : 'Fiscal balance is positive this tick.',
                          tone: (metrics.govProfit || 0) < 0 ? 'negative' : 'positive'
                        },
                        {
                          label: `${formatInteger(metrics.activeLoans || 0)} loans`,
                          body: (metrics.activeLoans || 0) > 0 ? 'Government-backed loans are active.' : 'No government-backed loans are active.',
                          tone: (metrics.activeLoans || 0) > 0 ? 'warning' : 'muted'
                        },
                        {
                          label: `Stress ${formatDecimal(Math.min(100, Math.max(0, (metrics.unemployment || 0) * 0.45 + (100 - (metrics.happiness || 0)) * 0.4 + (metrics.firmDistressPressure || 0) * 0.15)), 0)}/100`,
                          body: 'Population stress combines unemployment, happiness, and firm pressure.',
                          tone: (metrics.unemployment || 0) > 35 ? 'negative' : 'system'
                        }
                      ].map((signal, i) => (
                        <div key={i} className="rounded border border-slate-800/80 bg-slate-950/35 p-2">
                          <div className="flex justify-between gap-2 mb-1">
                            <Badge tone={signal.tone}>{signal.label}</Badge>
                            <span className="font-mono text-[10px] text-slate-500">TICK {formatTick(tick)}</span>
                          </div>
                          <div className="text-xs text-slate-300 leading-snug">{signal.body}</div>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="col-span-12">
                    <WealthDistributionChart
                      gini={metrics.giniCoefficient || 0}
                      top10={metrics.top10Share || 0}
                      bottom50={metrics.bottom50Share || 0}
                    />
                  </div>
                </div>
              </div>
            )}

            {/* SUBJECTS VIEW */}
            {activeView === 'SUBJECTS' && (
              <div className="animate-in fade-in slide-in-from-bottom-4 duration-500 flex-1 flex flex-col min-h-0">
                <PageHeader
                  eyebrow="Population"
                  title="Population Intelligence"
                  summary="Search tracked agents, inspect the selected household economy, and monitor needs, risk drivers, and history."
                />
                <style>{`
                @keyframes hologram-spin {
                  0% { transform: rotateY(0deg); }
                  100% { transform: rotateY(360deg); }
                }
                .hologram-container {
                  perspective: 1000px;
                }
                .hologram-body {
                  animation: hologram-spin 10s linear infinite;
                  transform-style: preserve-3d;
                }
              `}</style>

                <div className="tech-panel p-4 mb-4 shrink-0">
                  <div className="flex flex-col xl:flex-row xl:items-center gap-3">
                    <div className="relative flex-1">
                      <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
                      <input
                        value={subjectSearch}
                        onChange={(e) => setSubjectSearch(e.target.value)}
                        placeholder="Search agents, state, employer, or ID"
                        className="w-full rounded border border-slate-800 bg-slate-950/70 py-2 pl-9 pr-3 text-sm text-slate-200 placeholder:text-slate-600"
                      />
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {subjectFilters.map(filter => (
                        <button
                          key={filter}
                          type="button"
                          onClick={() => setSubjectFilter(filter)}
                          className={`rounded-full border px-3 py-1.5 text-[11px] ${subjectFilter === filter ? 'border-amber-500/60 bg-amber-500/12 text-amber-200' : 'border-slate-800 text-slate-500 hover:text-slate-300'}`}
                        >
                          {filter}
                        </button>
                      ))}
                    </div>
                  </div>
                  <div className="mt-3 max-h-[140px] overflow-y-auto command-scroll">
                    <table className="w-full table-fixed text-[12.5px]">
                      <thead className="sticky top-0 bg-slate-950/95 text-[11px] text-slate-500">
                        <tr>
                          <th className="text-left py-2 px-2 w-[18%]">Agent</th>
                          <th className="text-left py-2 px-2 w-[14%]">Status</th>
                          <th className="text-left py-2 px-2 w-[14%]">Housing</th>
                          <th className="text-left py-2 px-2">Employer</th>
                          <th className="text-right py-2 px-2 w-[12%]">Cash</th>
                          <th className="text-right py-2 px-2 w-[12%]">Health</th>
                          <th className="text-right py-2 px-2 w-[12%]">Morale</th>
                        </tr>
                      </thead>
                      <tbody>
                        {filteredSubjects.map(({ subject, index }) => (
                          <tr
                            key={subject.id}
                            onClick={() => setActiveSubjectIndex(index)}
                            className={`border-t border-slate-900 cursor-pointer ${activeSubjectIndex === index ? 'bg-amber-500/10 text-amber-100' : 'hover:bg-slate-800/45 text-slate-300'}`}
                          >
                            <td className="py-2.5 px-2 font-semibold truncate">{readableEntityName(subject.name)}</td>
                            <td className="py-2 px-2"><Badge tone={subject.state === 'WORKING' ? 'positive' : subject.state === 'UNEMPLOYED' ? 'negative' : 'ai'}>{String(subject.state || 'Unknown').replace(/_/g, ' ')}</Badge></td>
                            <td className="py-2 px-2">
                              <Badge tone={hasHousingSecurity(subject) ? 'positive' : 'negative'}>
                                {housingStatusLabel(subject)}
                              </Badge>
                            </td>
                            <td className="py-2 px-2 truncate" title={subject.employer}>{readableEntityName(subject.employer)}</td>
                            <td className="py-2 px-2 text-right font-mono tabular-nums">{formatCurrency(subject.cash || 0)}</td>
                            <td className="py-2 px-2 text-right font-mono tabular-nums">{formatPercent((subject.health || 0) * 100, 0)}</td>
                            <td className="py-2 px-2 text-right font-mono tabular-nums">{formatPercent((subject.morale || 0) * 100, 0)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    {filteredSubjects.length === 0 && <EmptyState title="No agents match the filters">Try a broader cohort or wait for tracking data.</EmptyState>}
                  </div>
                </div>

                {/* MAIN CONTENT GRID */}
                {selectedSubject && (
                  <div className="flex-1 grid grid-cols-12 gap-4 min-h-0 pb-2">

                    {/* LEFT COLUMN - BIO & EMPLOYMENT */}
                    <div className="col-span-12 xl:col-span-3 flex flex-col space-y-3 overflow-y-auto command-scroll pr-1 max-h-[calc(100vh-var(--topbar-height)-330px)]">
                      {/* ID CARD */}
                      <div className="tech-panel p-2 tech-corners">
                        <h4 className="text-[12px] font-semibold text-amber-300 mb-1 flex items-center">
                          <Users size={10} className="mr-1" /> Identity
                        </h4>
                        <div className="space-y-1">
                          <div className="flex justify-between items-center border-b border-slate-800 pb-0.5">
                            <span className="text-[9px] text-slate-500">AGE</span>
                            <span className="font-mono text-xs text-slate-200">{metrics.trackedSubjects[activeSubjectIndex].age}</span>
                          </div>
                          <div className="flex justify-between items-center border-b border-slate-800 pb-0.5">
                            <span className="text-[9px] text-slate-500">HEALTH</span>
                            <span className={`font-mono text-xs ${(metrics.trackedSubjects[activeSubjectIndex].health || 1) > 0.8 ? 'text-emerald-400' : 'text-rose-400'}`}>
                              {((metrics.trackedSubjects[activeSubjectIndex].health || 1) * 100).toFixed(0)}%
                            </span>
                          </div>
                          <div className="flex justify-between items-center">
                            <span className="text-[9px] text-slate-500">STATUS</span>
                            <span className="font-mono text-xs text-amber-400">{metrics.trackedSubjects[activeSubjectIndex].state}</span>
                          </div>
                          <div className="flex justify-between items-center border-t border-slate-800 pt-0.5">
                            <span className="text-[9px] text-slate-500">MEDICAL TRACK</span>
                            <span className="font-mono text-xs text-violet-300">
                              {(metrics.trackedSubjects[activeSubjectIndex].medicalStatus || 'none').toUpperCase()}
                            </span>
                          </div>
                        </div>
                      </div>

                      {/* EMPLOYMENT DATA */}
                      <div className="tech-panel p-2 tech-corners">
                        <h4 className="text-[12px] font-semibold text-amber-300 mb-1 flex items-center">
                          <Building2 size={10} className="mr-1" /> Employment
                        </h4>
                        <div className="space-y-2">
                          <div>
                            <div className="text-[9px] text-slate-500 mb-0.5">EMPLOYER</div>
                            <div className="font-display text-sm text-slate-200 truncate">
                              {readableEntityName(metrics.trackedSubjects[activeSubjectIndex].employer)}
                            </div>
                          </div>
                          <div className="flex justify-between">
                            <div>
                              <div className="text-[9px] text-slate-500 mb-0.5">WAGE</div>
                              <div className="font-mono text-sm text-emerald-400">
                                {formatCurrency(metrics.trackedSubjects[activeSubjectIndex].wage, 2)}
                              </div>
                            </div>
                            <div className="text-right">
                              <div className="text-[9px] text-slate-500 mb-0.5">SHIFT</div>
                              <div className="font-mono text-[10px] text-slate-300">
                                {metrics.trackedSubjects[activeSubjectIndex].state === 'WORKING'
                                  ? 'ACTIVE'
                                  : metrics.trackedSubjects[activeSubjectIndex].state === 'MED_SCHOOL'
                                    ? 'TRAINING'
                                    : 'OFF'}
                              </div>
                            </div>
                          </div>
                        </div>
                      </div>

                      {/* POPULATION WAGE EXPECTATIONS */}
                      <div className="tech-panel p-2 tech-corners">
                        <h4 className="text-[12px] font-semibold text-violet-300 mb-1 flex items-center">
                          <Activity size={10} className="mr-1" /> Wage Expectations
                        </h4>
                        <div className="space-y-1">
                          <div className="flex justify-between items-center border-b border-slate-800 pb-0.5">
                            <span className="text-[9px] text-slate-500">AVG (ALL HH)</span>
                            <span className="font-mono text-xs text-violet-300">{formatCurrency(metrics.avgExpectedWage || 0, 2)}</span>
                          </div>
                          <div className="flex justify-between items-center border-b border-slate-800 pb-0.5">
                            <span className="text-[9px] text-slate-500">AVG (UNEMPLOYED)</span>
                            <span className="font-mono text-xs text-violet-300">{formatCurrency(metrics.avgExpectedWageUnemployed || 0, 2)}</span>
                          </div>
                          <div className="flex justify-between items-center">
                            <span className="text-[9px] text-slate-500">AGENT TARGET</span>
                            <span className="font-mono text-xs text-slate-300">
                              {formatCurrency(metrics.trackedSubjects[activeSubjectIndex].expectedWage || 0, 2)}
                            </span>
                          </div>
                        </div>
                      </div>

                      {/* SUBJECT EXPECTED WAGE DRIVERS */}
                      <div className="tech-panel p-2 tech-corners">
                        <h4 className="text-[12px] font-semibold text-fuchsia-300 mb-1 flex items-center">
                          <Terminal size={10} className="mr-1" /> Wage drivers
                        </h4>
                        <div className="space-y-1">
                          <div className="flex justify-between items-center border-b border-slate-800 pb-0.5">
                            <span className="text-[9px] text-slate-500">MODE</span>
                            <span className="font-mono text-[10px] text-fuchsia-300">
                              {metrics.trackedSubjects[activeSubjectIndex].expectedWageReason?.mode || 'Unavailable'}
                            </span>
                          </div>
                          <div className="flex justify-between items-center border-b border-slate-800 pb-0.5">
                            <span className="text-[9px] text-slate-500">RESERVATION</span>
                            <span className="font-mono text-xs text-slate-300">
                              {formatCurrency(metrics.trackedSubjects[activeSubjectIndex].reservationWage || 0, 2)}
                            </span>
                          </div>
                          <div className="flex justify-between items-center border-b border-slate-800 pb-0.5">
                            <span className="text-[9px] text-slate-500">GAP VS CURRENT</span>
                            <span className={`font-mono text-xs ${((metrics.trackedSubjects[activeSubjectIndex].expectedWageReason?.gapToCurrentWage || 0) >= 0 ? 'text-amber-300' : 'text-emerald-300')}`}>
                              {formatCurrency(metrics.trackedSubjects[activeSubjectIndex].expectedWageReason?.gapToCurrentWage || 0, 2)}
                            </span>
                          </div>
                          <div className="flex justify-between items-center border-b border-slate-800 pb-0.5">
                            <span className="text-[9px] text-slate-500">UNEMP DURATION</span>
                            <span className="font-mono text-xs text-slate-300">
                              {(metrics.trackedSubjects[activeSubjectIndex].unemploymentDuration || 0).toFixed(0)} ticks
                            </span>
                          </div>
                          <div className="grid grid-cols-2 gap-2 pt-0.5">
                            <div className="text-[9px] text-slate-500">Duration Pressure: <span className="font-mono text-slate-300">{(metrics.trackedSubjects[activeSubjectIndex].expectedWageReason?.durationPressure || 0).toFixed(3)}</span></div>
                            <div className="text-[9px] text-slate-500">Cash Pressure: <span className="font-mono text-slate-300">{(metrics.trackedSubjects[activeSubjectIndex].expectedWageReason?.cashPressure || 0).toFixed(3)}</span></div>
                            <div className="text-[9px] text-slate-500">Health Pressure: <span className="font-mono text-slate-300">{(metrics.trackedSubjects[activeSubjectIndex].expectedWageReason?.healthPressure || 0).toFixed(3)}</span></div>
                            <div className="text-[9px] text-slate-500">Decay Factor: <span className="font-mono text-slate-300">{(metrics.trackedSubjects[activeSubjectIndex].expectedWageReason?.decayFactor || 0).toFixed(3)}</span></div>
                          </div>
                          <div className="flex justify-between items-center border-t border-slate-800 pt-1">
                            <span className="text-[9px] text-slate-500">MARKET ANCHOR (EST)</span>
                            <span className="font-mono text-xs text-slate-300">
                              {formatCurrency(metrics.trackedSubjects[activeSubjectIndex].expectedWageReason?.marketAnchorEstimate || 0, 2)}
                            </span>
                          </div>
                          {(metrics.trackedSubjects[activeSubjectIndex].expectedWageReason?.tags || []).length > 0 && (
                            <div className="flex flex-wrap gap-1 pt-1">
                              {(metrics.trackedSubjects[activeSubjectIndex].expectedWageReason?.tags || []).map((tag, idx) => (
                                <span key={`${tag}-${idx}`} className="text-[9px] px-1.5 py-0.5 rounded border border-fuchsia-500/40 text-fuchsia-300 bg-fuchsia-500/5">
                                  {String(tag).replace(/_/g, ' ')}
                                </span>
                              ))}
                            </div>
                          )}
                        </div>
                      </div>

                      {/* SKILLS & PERFORMANCE (RESTORED) */}
                      <div className="tech-panel p-3 tech-corners flex-1 flex flex-col justify-center">
                        <h4 className="text-[13px] font-semibold text-amber-300 mb-3 border-b border-slate-800 pb-2">Skills & morale</h4>
                        <div className="space-y-4">
                          <div>
                            <div className="flex justify-between items-center mb-1.5">
                              <span className="text-[11px] text-slate-500 font-medium">Competency level</span>
                              <span className="font-mono text-sm text-slate-200">
                                {(metrics.trackedSubjects[activeSubjectIndex].skills * 100).toFixed(0)}%
                              </span>
                            </div>
                            <div className="w-full h-2 bg-slate-800 rounded-full overflow-hidden shadow-inner">
                              <div className="h-full bg-amber-400 shadow-[0_0_6px_rgba(251,191,36,0.28)]" style={{ width: `${Math.max(2, metrics.trackedSubjects[activeSubjectIndex].skills * 100)}%` }}></div>
                            </div>
                          </div>
                          <div>
                            <div className="flex justify-between items-center mb-1.5">
                              <span className="text-[11px] text-slate-500 font-medium">Morale index</span>
                              <span className="font-mono text-sm text-slate-200">
                                {(metrics.trackedSubjects[activeSubjectIndex].morale * 100).toFixed(0)}%
                              </span>
                            </div>
                            <div className="w-full h-2 bg-slate-800 rounded-full overflow-hidden shadow-inner">
                              <div className="h-full bg-amber-300 shadow-[0_0_6px_rgba(248,223,166,0.24)]" style={{ width: `${Math.max(2, metrics.trackedSubjects[activeSubjectIndex].morale * 100)}%` }}></div>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* CENTER COLUMN - VISUALIZER */}
                    <div className="col-span-12 xl:col-span-6 relative flex items-center justify-center overflow-hidden min-h-[430px] rounded-lg border border-slate-800/50 bg-slate-900/20 shadow-inner priority-corners">

                      {/* Neural Avatar with Health Status Glow */}
                      <div className={`absolute inset-0 z-0 pointer-events-none transition-all duration-1000 ${
                        (metrics.trackedSubjects[activeSubjectIndex].health || 1) < 0.3 
                        ? 'shadow-[inset_0_0_90px_rgba(190,90,103,0.14)] bg-rose-400/5' 
                        : (metrics.trackedSubjects[activeSubjectIndex].happiness || 0) > 0.8
                          ? 'shadow-[inset_0_0_90px_rgba(110,231,183,0.1)] bg-emerald-400/5'
                          : ''
                      }`}>
                        <NeuralAvatar
                          active={true}
                          mood={(metrics.trackedSubjects[activeSubjectIndex].health || 1) < 0.3 ? 'distressed' : metrics.trackedSubjects[activeSubjectIndex].happiness > 0.7 ? 'happy' : 'neutral'}
                          variant="human"
                        />
                      </div>

                      {/* Header Overlay (Minimal) */}
                      <div className="absolute top-0 left-0 right-0 p-3 flex justify-between items-start z-10 bg-gradient-to-b from-slate-900/90 to-transparent">
                        <div>
                          <h2 className="text-2xl font-display font-bold text-white drop-shadow-md flex items-center gap-2">
                            {readableEntityName(metrics.trackedSubjects[activeSubjectIndex].name)}
                            {(metrics.trackedSubjects[activeSubjectIndex].health || 1) < 0.3 && (
                               <span className="text-[10px] bg-rose-400/12 text-rose-200 border border-rose-300/35 px-1.5 py-0.5 rounded animate-pulse">CRITICAL HEALTH</span>
                            )}
                          </h2>
                          <div className="text-xs font-mono text-amber-400 mt-0.5">
                            Internal ID: {metrics.trackedSubjects[activeSubjectIndex].id.toString().padStart(4, '0')}
                          </div>
                        </div>
                        <div className="text-right">
                          <div className={`text-xl font-bold font-display drop-shadow-md ${metrics.trackedSubjects[activeSubjectIndex].state === 'WORKING'
                            ? 'text-emerald-400'
                            : metrics.trackedSubjects[activeSubjectIndex].state === 'MED_SCHOOL'
                              ? 'text-violet-400'
                              : 'text-amber-400'
                            }`}>
                            {metrics.trackedSubjects[activeSubjectIndex].state}
                          </div>
                        </div>
                      </div>

                      {/* Floating Gauges HUD */}
                      <div className="absolute bottom-6 left-6 right-6 flex justify-around z-10">
                        <CircularProgress
                          value={(metrics.trackedSubjects[activeSubjectIndex].health || 0) * 100}
                          color={(metrics.trackedSubjects[activeSubjectIndex].health || 1) < 0.3 ? "#BE5A67" : "#FBBF24"}
                          label="Health"
                          size={75}
                        />
                        <CircularProgress
                          value={(metrics.trackedSubjects[activeSubjectIndex].happiness || 0) * 100}
                          color="#6EE7B7"
                          label="Happiness"
                          size={75}
                        />
                        <CircularProgress
                          value={(metrics.trackedSubjects[activeSubjectIndex].morale || 0) * 100}
                          color="#F8DFA6"
                          label="Morale"
                          size={75}
                        />
                      </div>
                      
                      {/* Thought Bubble / Needs */}
                      <div className="absolute top-20 right-8 z-10 max-w-[150px]">
                        {selectedSubjectPrimaryRisk && (
                          <div className="bg-slate-900/80 border border-slate-600 rounded-lg rounded-tr-none p-2 shadow-xl backdrop-blur animate-bounce" style={{ animationDuration: '3s' }}>
                            <div className="text-[10px] text-slate-400 mb-1">Primary risk: {selectedSubjectPrimaryRisk}</div>
                            <div className="text-xs font-semibold text-rose-300 font-display">
                              {selectedSubjectPrimaryRisk === 'Food'
                                ? 'Food inventory is 0.'
                                : selectedSubjectPrimaryRisk === 'Housing'
                                  ? 'Housing security is not met.'
                                  : `${selectedSubjectPrimaryRisk} pressure is elevated.`}
                            </div>
                          </div>
                        )}
                      </div>
                    </div>

                    {/* RIGHT COLUMN - FINANCIALS & NEEDS */}
                    <div className="col-span-12 xl:col-span-3 flex flex-col space-y-3 overflow-y-auto command-scroll pl-1 max-h-[calc(100vh-var(--topbar-height)-330px)]">
                      {/* FINANCIAL HEALTH */}
                      <div className="tech-panel p-2 tech-corners">
                        <h4 className="text-[12px] font-semibold text-rose-300 mb-1 flex items-center">
                          <DollarSign size={10} className="mr-1" /> Finances
                        </h4>
                        <div className="space-y-2">
                          <div className="flex justify-between items-end">
                            <span className="text-[9px] text-slate-500">LIQUID</span>
                            <span className="font-mono text-sm text-white">
                              {formatCurrency(metrics.trackedSubjects[activeSubjectIndex].cash)}
                            </span>
                          </div>
                          <div className="flex justify-between items-end">
                            <span className="text-[9px] text-slate-500">HOUSEHOLD NET WORTH</span>
                            <span className="font-mono text-sm text-purple-400">
                              {formatCurrency(metrics.trackedSubjects[activeSubjectIndex].netWorth)}
                            </span>
                          </div>
                          {/* MEDICAL DEBT (RESTORED) */}
                          {metrics.trackedSubjects[activeSubjectIndex].medicalDebt > 0 && (
                            <div className="flex justify-between items-end">
                              <span className="text-[9px] text-slate-500">DEBT</span>
                              <span className="font-mono text-sm text-rose-400">
                                {formatCurrency(metrics.trackedSubjects[activeSubjectIndex].medicalDebt)}
                              </span>
                            </div>
                          )}
                        </div>
                      </div>

                      {/* CHARTS (RESTORED) */}
                        <div className="shrink-0 flex flex-col min-h-[150px]">
                          <LineChart
                            title="Wealth"
                            data={selectedSubjectNetWorthHistory}
                            color="#FBBF24"
                            minScale={0}
                            suffix=""
                            headlineValue={metrics.trackedSubjects[activeSubjectIndex].netWorth || 0}
                            headlineLabel="Current household net worth"
                            subtitle="Agent wealth over time"
                            formatValue={v => formatCurrency(v)}
                          />
                        </div>
                        <div className="shrink-0 flex flex-col min-h-[150px]">
                          <LineChart
                            title="Wage"
                            data={selectedSubjectWageHistory}
                            color="#A78BFA"
                            minScale={0}
                            suffix=""
                            headlineValue={metrics.trackedSubjects[activeSubjectIndex].wage || 0}
                            headlineLabel="Current wage"
                            subtitle="Agent wage over time"
                            formatValue={v => formatCurrency(v, 2)}
                          />
                        </div>
                      {/* INVENTORY */}
                      <div className="tech-panel p-2 tech-corners">
                        <h4 className="text-[12px] font-semibold text-slate-300 mb-1">Needs & inventory</h4>
                        <div className="flex justify-between items-center">
                          <span className="text-[9px] text-slate-500">FOOD</span>
                          <span className="font-mono text-xs text-slate-300">
                            {(metrics.trackedSubjects[activeSubjectIndex].needs?.food ?? 0).toFixed(0)}
                          </span>
                        </div>
                        <div className="flex justify-between items-center mt-1">
                          <span className="text-[9px] text-slate-500">HOUSING STATUS</span>
                          <span className={`font-mono text-xs ${hasHousingSecurity(metrics.trackedSubjects[activeSubjectIndex]) ? 'text-emerald-300' : 'text-rose-300'}`}>
                            {housingStatusLabel(metrics.trackedSubjects[activeSubjectIndex]).toUpperCase()}
                          </span>
                        </div>
                        {metrics.trackedSubjects[activeSubjectIndex].monthlyRent > 0 && (
                          <div className="flex justify-between items-center mt-1">
                            <span className="text-[9px] text-slate-500">RENT</span>
                            <span className="font-mono text-xs text-slate-300">
                              {formatCurrency(metrics.trackedSubjects[activeSubjectIndex].monthlyRent, 2)}
                            </span>
                          </div>
                        )}
                        <div className="flex justify-between items-center mt-1">
                          <span className="text-[9px] text-slate-500">HEALTHCARE</span>
                          <span className="font-mono text-xs text-slate-300">
                            {(metrics.trackedSubjects[activeSubjectIndex].needs?.healthcare ?? 0).toFixed(0)}
                          </span>
                        </div>
                      </div>

                      {/* TRAITS & MODIFIERS */}
                      <div className="tech-panel p-2 tech-corners">
                        <h4 className="text-[12px] font-semibold text-amber-300 mb-1">Advanced model factors</h4>
                        <div className="grid grid-cols-2 gap-x-2 gap-y-1">
                          <div className="text-[9px] text-slate-500">Spending: <span className="font-mono text-slate-300">{(metrics.trackedSubjects[activeSubjectIndex].traits?.spendingTendency || 0).toFixed(2)}</span></div>
                          <div className="text-[9px] text-slate-500">Frugality: <span className="font-mono text-slate-300">{(metrics.trackedSubjects[activeSubjectIndex].traits?.frugality || 0).toFixed(2)}</span></div>
                          <div className="text-[9px] text-slate-500">Saving: <span className="font-mono text-slate-300">{(metrics.trackedSubjects[activeSubjectIndex].traits?.savingTendency || 0).toFixed(2)}</span></div>
                          <div className="text-[9px] text-slate-500">Price Sens: <span className="font-mono text-slate-300">{(metrics.trackedSubjects[activeSubjectIndex].traits?.priceSensitivity || 0).toFixed(2)}</span></div>
                          <div className="text-[9px] text-slate-500">Quality Bias: <span className="font-mono text-slate-300">{(metrics.trackedSubjects[activeSubjectIndex].traits?.qualityLavishness || 0).toFixed(2)}</span></div>
                          <div className="text-[9px] text-slate-500">Skill Growth: <span className="font-mono text-slate-300">{((metrics.trackedSubjects[activeSubjectIndex].traits?.skillGrowthRate || 0) * 100).toFixed(2)}%</span></div>
                          <div className="text-[9px] text-slate-500">Health Decay/Yr: <span className="font-mono text-slate-300">{((metrics.trackedSubjects[activeSubjectIndex].traits?.healthDecayPerYear || 0) * 100).toFixed(1)}%</span></div>
                          <div className="text-[9px] text-slate-500">Healthcare Seek: <span className="font-mono text-slate-300">{(metrics.trackedSubjects[activeSubjectIndex].traits?.healthcareSeekBasePct || 0).toFixed(1)}%</span></div>
                          <div className="text-[9px] text-slate-500">Min Food: <span className="font-mono text-slate-300">{(metrics.trackedSubjects[activeSubjectIndex].traits?.minFoodPerTick || 0).toFixed(2)}</span></div>
                          <div className="text-[9px] text-slate-500">Min Services: <span className="font-mono text-slate-300">{(metrics.trackedSubjects[activeSubjectIndex].traits?.minServicesPerTick || 0).toFixed(2)}</span></div>
                        </div>
                      </div>
                    </div>

                  </div>
                )}
              </div>
            )}

            {/* FIRMS VIEW */}
            {activeView === 'FIRMS' && (
              <div className="animate-in fade-in slide-in-from-bottom-4 duration-500 flex-1 min-h-0">
                <PageHeader
                  eyebrow="Markets"
                  title="Markets & Firms"
                  summary="Sector health, firm dossier, selected-firm hologram, and sampled financial history."
                />
                <style>{`
                @keyframes hologram-spin {
                  0% { transform: rotateY(0deg); }
                  100% { transform: rotateY(360deg); }
                }
                .hologram-container {
                  perspective: 1000px;
                }
                .hologram-body {
                  animation: hologram-spin 18s linear infinite;
                  transform-style: preserve-3d;
                }
              `}</style>
                {!firmStats ? (
                  <div className="tech-panel p-6 text-center text-slate-500 text-sm">
                    Awaiting firm telemetry...
                  </div>
                ) : (
                  <div className="grid grid-cols-12 gap-4 min-h-0">
                    <div className="col-span-12 xl:col-span-8 flex flex-col min-h-0 space-y-4">
                      <div className="grid grid-cols-4 gap-4 shrink-0">
                        <StatTile label="Total Firms" value={formatCompact(firmStats.total_firms)} />
                        <StatTile label="Total Employees" value={formatCompact(firmStats.total_employees)} />
                        <StatTile label="Avg Wage Offer" value={formatCurrency(firmStats.avg_wage_offer || 0, 2)} />
                        <StatTile label="Struggling Firms" value={formatCompact(firmStats.struggling_firms || 0)} />
                      </div>

                      <div className="flex flex-col flex-1 min-h-0 space-y-4">
                        <div className="tech-panel tech-corners relative flex-1 min-h-[14rem] overflow-hidden rounded-lg border border-white/5 bg-slate-900/55">
                          <div className="absolute top-0 left-0 right-0 h-24 bg-gradient-to-b from-slate-900 via-slate-900/80 to-transparent z-10 pointer-events-none"></div>
                          <div className="absolute top-4 left-4 z-20">
                            <div className="text-[10px] text-slate-300 font-semibold drop-shadow-md">Market mood</div>
                            <div className="text-xl font-display text-slate-100 drop-shadow-md">
                              {firmStats.struggling_firms > 0.15 * firmStats.total_firms ? 'Volatile' : 'Stable'}
                            </div>
                            <div className="text-[10px] text-slate-300 font-medium drop-shadow-md mt-1">
                              Avg price {formatCurrency(firmStats.avg_price || 0, 2)} | Avg quality {(firmStats.avg_quality || 0).toFixed(2)}
                            </div>
                            <div className="text-[10px] text-slate-500 mt-1">Sized by firm count</div>
                          </div>
                          <div className="absolute top-4 right-4 text-right text-[10px] text-slate-300 font-medium z-20 drop-shadow-md">
                            {firmStats.market_sentiment || (firmStats.struggling_firms > 0 ? 'Stress pockets detected' : 'Stable conditions')}
                          </div>
                          <div className="absolute inset-0 p-4 pt-24 flex flex-col z-0">
                            <div className="flex gap-2 h-full">
                              {firmStats.categories && firmStats.categories.map((cat, i) => {
                                const isDistressed = cat.avg_cash < 2000;
                                const isBooming = cat.avg_cash > 10000;
                                const sectorWidth = Math.max(12, ((cat.firm_count || 0) / Math.max(1, firmStats.total_firms || 1)) * 100);
                                const colors = sectorColor(cat.category, isDistressed);
                                return (
                                  <div key={i} className={`relative rounded-lg border overflow-hidden flex flex-col justify-end p-2 transition-all duration-500 bg-slate-950/40 ${
                                    isDistressed ? 'border-[#7A3A49]/45 shadow-[inset_0_0_18px_rgba(122,58,73,0.12)]' :
                                    isBooming ? 'border-[#3D787A]/35 shadow-[inset_0_0_18px_rgba(61,120,122,0.1)]' :
                                    `${colors.border} bg-slate-800/20`
                                  }`} style={{ flexBasis: `${sectorWidth}%`, flexGrow: sectorWidth }}>
                                    <div className={`absolute inset-0 opacity-75 ${isDistressed ? 'bg-[#351722]/70 animate-[pulse_2s_ease-in-out_infinite]' : isBooming ? 'bg-[#123A3B]/65' : colors.bar}`}></div>
                                    <div className="relative z-10">
                                      <div className={`text-[10px] font-semibold ${isDistressed ? 'text-rose-100' : isBooming ? 'text-slate-100' : colors.text}`}>
                                        {formatSector(cat.category)}
                                      </div>
                                      <div className="flex justify-between items-end mt-1">
                                        <div className="text-xl font-mono text-slate-100">{cat.firm_count}</div>
                                        <div className="text-[9px] text-slate-500 mb-0.5">firms</div>
                                      </div>
                                      <div className="text-[9px] text-slate-500 mt-0.5">avg cash {formatCurrency(cat.avg_cash || 0)}</div>
                                    </div>
                                  </div>
                                );
                              })}
                            </div>
                          </div>
                        </div>

                        <div className="flex flex-col gap-4">
                          <div className="tech-panel p-4 tech-corners rounded-lg border border-white/5 bg-slate-900/55">
                            <div className="flex justify-between items-center mb-3">
                              <h3 className="text-[13px] font-semibold text-slate-300">Sector breakdown</h3>
                              <span className="text-[10px] text-slate-300 font-medium">Avg price {formatCurrency(firmStats.avg_price || 0, 2)}</span>
                            </div>
                            {firmStats.categories && firmStats.categories.length ? (
                              <div className="grid grid-cols-2 xl:grid-cols-4 gap-3">
                                {firmStats.categories.map(cat => (
                                  <div key={cat.category} className={`border rounded-lg p-3 bg-slate-950/35 ${sectorColor(cat.category, cat.avg_cash < 2000).border}`}>
                                    <div className={`text-xs font-display ${sectorColor(cat.category, cat.avg_cash < 2000).text}`}>{formatSector(cat.category)}</div>
                                    <div className="text-[10px] text-slate-400 mb-2">{cat.firm_count} firms</div>
                                    <div className="text-[11px] text-slate-400">Employees: <span className="text-slate-200">{formatCompact(cat.total_employees)}</span></div>
                                    {cat.category === 'Healthcare' && (
                                      <div className="text-[11px] text-slate-400">Doctors: <span className="text-slate-200">{formatCompact(cat.doctor_employees || 0)}</span></div>
                                    )}
                                    {cat.category === 'Healthcare' && (
                                      <div className="text-[11px] text-slate-400">Visit Rev: <span className="text-slate-200">{formatCurrency(cat.visit_revenue || 0, 2)}</span></div>
                                    )}
                                    <div className="text-[11px] text-slate-400">Avg Cash: <span className="text-slate-200">{formatCurrency(cat.avg_cash || 0)}</span></div>
                                    <div className="text-[11px] text-slate-400">Avg Price: <span className="text-slate-200">{formatCurrency(cat.avg_price || 0, 2)}</span></div>
                                  </div>
                                ))}
                              </div>
                            ) : (
                              <div className="text-slate-500 text-xs">No category data yet.</div>
                            )}
                          </div>

                          <div className="grid grid-cols-1 2xl:grid-cols-2 gap-4 pb-2">
                            {renderFirmTable("Top Cash Positions", firmStats.top_cash || [])}
                            {renderFirmTable("Top Employers", firmStats.top_employers || [])}
                          </div>
                        </div>
                      </div>
                    </div>

                    <div className="col-span-12 xl:col-span-4 flex flex-col space-y-4 min-h-0 max-h-[calc(100vh-var(--topbar-height)-150px)] overflow-y-auto command-scroll">
                      <div className="tech-panel p-3 shrink-0 rounded-lg border border-white/5 bg-slate-900/55">
                        <div className="flex items-center justify-between mb-2">
                          <h3 className="text-[13px] font-semibold text-slate-300">Watchlist</h3>
                          <span className="text-[10px] text-slate-500">{firmCount} monitored</span>
                        </div>
                        <div className="flex flex-wrap gap-2">
                          {metrics.trackedFirms && metrics.trackedFirms.length ? (
                            metrics.trackedFirms.slice(0, 7).map((firm, idx) => (
                              <button
                                key={firm.id}
                                onClick={() => setActiveFirmIndex(idx)}
                                className={`px-3 py-1 text-[11px] rounded-lg border truncate max-w-[8rem] transition-colors ${activeFirmIndex === idx ? 'border-white/15 text-slate-100 bg-white/[0.08]' : 'border-white/5 bg-white/[0.035] text-slate-400 hover:bg-white/[0.10] hover:text-slate-200'}`}
                              >
                                {readableEntityName(firm.name)}
                              </button>
                            ))
                          ) : (
                            <div className="text-slate-500 text-xs">Sampling firms...</div>
                          )}
                        </div>
                      </div>

                      {selectedTrackedFirm ? (
                        <>
                          <div className="tech-panel priority-corners p-0 overflow-hidden shrink-0 rounded-lg border border-white/5 bg-slate-900/55">
                            <div className="h-56 relative bg-slate-950/55 border-b border-white/5">
                              <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(203,213,225,0.10),transparent_58%),radial-gradient(circle_at_50%_82%,rgba(251,191,36,0.075),transparent_38%)] pointer-events-none"></div>
                              <NeuralBuilding
                                active
                                activityLevel={selectedTrackedFirm.state === 'DISTRESS' || selectedTrackedFirm.state === 'BURN' ? 'high' : 'normal'}
                                tier={String(selectedTrackedFirm.category || '').toLowerCase().includes('housing') ? 3 : String(selectedTrackedFirm.category || '').toLowerCase().includes('food') ? 3 : 2}
                                sector={selectedTrackedFirm.category}
                                status={selectedTrackedFirm.state}
                              />
                              <div className="absolute left-4 top-4 right-4 flex items-start justify-between gap-3">
                                <div className="min-w-0">
                                  <div className="text-[10px] text-slate-300 font-semibold">Selected firm hologram</div>
                                  <div className="text-xl font-semibold text-slate-100 truncate" title={selectedTrackedFirm.name}>{readableEntityName(selectedTrackedFirm.name)}</div>
                                  <div className="text-[11px] text-slate-400 mt-1">{formatSector(selectedTrackedFirm.category)} operating mesh</div>
                                </div>
                                <Badge tone={firmStatusTone(selectedTrackedFirm.state)}>{selectedTrackedFirm.state}</Badge>
                              </div>
                            </div>
                          </div>

                          <div className="tech-panel p-4 priority-corners space-y-3 shrink-0 rounded-lg border border-white/5 bg-slate-900/55">
                            <div className="flex justify-between items-center">
                              <div>
                                <h3 className="text-lg font-display text-slate-100">{readableEntityName(selectedTrackedFirm.name)}</h3>
                                <div className="text-[11px] text-slate-500" title={selectedTrackedFirm.name}>Sector: {formatSector(selectedTrackedFirm.category)} Â· Internal ID: {selectedTrackedFirm.name}</div>
                              </div>
                              <Badge tone={firmStatusTone(selectedTrackedFirm.state)}>{selectedTrackedFirm.state}</Badge>
                            </div>
                            <div className="grid grid-cols-2 gap-3 text-sm">
                              <div>
                                <div className="text-[10px] text-slate-500">Cash</div>
                                <div className="font-mono text-slate-200">{formatCurrency(selectedTrackedFirm.cash)}</div>
                              </div>
                              <div>
                                <div className="text-[10px] text-slate-500">Inventory</div>
                                <div className="font-mono text-slate-200">{selectedTrackedFirm.inventory?.toFixed(1)}</div>
                              </div>
                              <div>
                                <div className="text-[10px] text-slate-500">Employees</div>
                                <div className="font-mono text-slate-200">
                                  {selectedTrackedFirm.category === 'Healthcare'
                                    ? (selectedTrackedFirm.doctorEmployees || selectedTrackedFirm.medicalEmployees || selectedTrackedFirm.employees)
                                    : selectedTrackedFirm.employees}
                                </div>
                              </div>
                              <div>
                                <div className="text-[10px] text-slate-500">Quality</div>
                                <div className="font-mono text-slate-200">{(selectedTrackedFirm.quality || 0).toFixed(1)}</div>
                              </div>
                            </div>
                            <div className="grid grid-cols-2 gap-3 text-sm">
                              <div>
                                <div className="text-[10px] text-slate-500">Price</div>
                                <div className="font-mono text-slate-200">{formatCurrency(selectedTrackedFirm.price, 2)}</div>
                              </div>
                              <div>
                                <div className="text-[10px] text-slate-500">Wage offer</div>
                                <div className="font-mono text-slate-200">{formatCurrency(selectedTrackedFirm.wageOffer, 2)}</div>
                              </div>
                            </div>
                            <div className="grid grid-cols-2 gap-3 text-sm">
                              <div>
                                <div className="text-[10px] text-slate-500">
                                  {selectedTrackedFirm.category === 'Healthcare' ? 'Visit Revenue' : 'Revenue'}
                                </div>
                                <div className="font-mono text-slate-200">
                                  {formatCurrency(
                                    selectedTrackedFirm.category === 'Healthcare'
                                      ? (selectedTrackedFirm.visitRevenue ?? selectedTrackedFirm.lastRevenue)
                                      : selectedTrackedFirm.lastRevenue,
                                    2
                                  )}
                                </div>
                              </div>
                              <div>
                                <div className="text-[10px] text-slate-500">Profit</div>
                                <div className={`font-mono ${selectedTrackedFirm.lastProfit >= 0 ? 'text-slate-200' : 'text-rose-200'}`}>
                                  {formatCurrency(selectedTrackedFirm.lastProfit, 2)}
                                </div>
                              </div>
                            </div>
                            {selectedTrackedFirm.category === 'Healthcare' && (
                              <div className="grid grid-cols-2 gap-3 text-sm">
                                <div>
                                  <div className="text-[10px] text-slate-500">Visits this tick</div>
                                  <div className="font-mono text-slate-200">{(selectedTrackedFirm.visitsCompleted || 0).toFixed(0)}</div>
                                </div>
                                <div>
                                  <div className="text-[10px] text-slate-500">Doctors</div>
                                  <div className="font-mono text-slate-200">{selectedTrackedFirm.doctorEmployees || 0}</div>
                                </div>
                              </div>
                            )}
                          </div>

                          <div className="flex-1 flex flex-col gap-3 min-h-0">
                            <div className="flex flex-col flex-1 min-h-[170px]">
                              <LineChart
                                title="Cash History"
                                data={selectedFirmCashHistory}
                                color="#FBBF24"
                                minScale={0}
                                suffix=""
                                subtitle="Includes current inspector value"
                                formatValue={v => formatCurrency(v)}
                              />
                            </div>
                            <div className="flex flex-col flex-1 min-h-[170px]">
                              <LineChart
                                title="Profit History"
                                data={selectedFirmProfitHistory}
                                color="#CBD5E1"
                                minScale={-1}
                                suffix=""
                                subtitle="Includes current inspector value"
                                formatValue={v => formatCurrency(v)}
                              />
                            </div>
                          </div>
                        </>
                      ) : (
                        <div className="tech-panel p-4 text-sm text-slate-500">
                          No tracked firms yet.
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* FINANCE VIEW */}
            {activeView === 'FINANCE' && (
              <div className="animate-in fade-in slide-in-from-bottom-4 duration-500 flex-1 min-h-0">
                <PageHeader
                  eyebrow="Finance"
                  title="Finance & Credit"
                  summary="Treasury-backed credit and fiscal exposure using live simulation telemetry."
                />
                <div className="grid grid-cols-12 gap-4">
                  <div className="col-span-12 grid grid-cols-2 md:grid-cols-3 xl:grid-cols-5 gap-3">
                    <StatTile label="Government-backed loans" value={formatInteger(metrics.activeLoans || 0)} caption="Current active loan count" />
                    <StatTile label="Active credit events" value={formatInteger(metrics.activeLoans || 0)} caption="Current run loan events" />
                    <StatTile label="Liquidity Stress" value={(metrics.govDebt || 0) > 0 ? 'Elevated' : 'Low'} caption="Treasury proxy" alert={(metrics.govDebt || 0) > 0} valueVariant="badge" />
                    <StatTile label="Treasury debt" value={formatMillionsAdaptive(metrics.govDebt || 0)} caption="Current debt exposure" alert={(metrics.govDebt || 0) > 0} />
                    <StatTile label="Latest fiscal flow" value={formatMillionsAdaptive(metrics.govProfit || 0)} caption="Current tick net flow" alert={(metrics.govProfit || 0) < 0} />
                  </div>

                  <div className="col-span-12 xl:col-span-7">
                    <LineChart
                      title="Treasury exposure"
                      data={[metrics.govDebtHistory || [], metrics.govProfitHistory || []]}
                      color={["#FBBF24", "#B8C7D9"]}
                      legend={["Government Debt", "Fiscal Balance"]}
                      subtitle="Government debt and fiscal balance over time"
                      timeRange="Last 250 ticks"
                      height={260}
                      formatValue={v => formatMillionsAdaptive(v)}
                    />
                  </div>

                  <div className="col-span-12 xl:col-span-5 tech-panel p-4 rounded-lg border border-white/5 bg-slate-900/55">
                    <SectionHeader icon={ShieldCheck} title="Risk alerts" meta="Credit availability" />
                    {(metrics.activeLoans || 0) > 0 ? (
                      <div className="space-y-3">
                        <div className="rounded-lg border border-white/10 bg-white/[0.055] p-3">
                          <div className="font-semibold text-slate-200">Government loan exposure active</div>
                          <div className="mt-1 text-xs text-slate-400">{formatInteger(metrics.activeLoans)} firms have active government-backed loans.</div>
                        </div>
                        <DetailRow label="Treasury Debt" value={formatMillionsAdaptive(metrics.govDebt || 0)} tone={(metrics.govDebt || 0) > 0 ? 'negative' : 'positive'} />
                        <DetailRow label="Latest Fiscal Flow" value={formatMillionsAdaptive(metrics.govProfit || 0)} tone={(metrics.govProfit || 0) >= 0 ? 'positive' : 'negative'} />
                      </div>
                    ) : (
                      <EmptyState icon={Wallet} title="No active loans">The credit channel has no active government-backed loans in the current tick.</EmptyState>
                    )}
                  </div>

                  <div className="col-span-12 xl:col-span-4 tech-panel p-4 rounded-lg border border-white/5 bg-slate-900/55">
                    <SectionHeader icon={Building2} title="Telemetry coverage" meta="Coverage gaps" />
                    <div className="space-y-2 text-xs">
                      <DetailRow label="Bank reserves" value="N/A" tone="muted" />
                      <DetailRow label="Private loan balance" value="N/A" tone="muted" />
                      <DetailRow label="Default rate" value="N/A" tone="muted" />
                      <DetailRow label="Interest rate" value="N/A" tone="muted" />
                      <p className="pt-2 text-slate-500 leading-relaxed">This run is not exposing bank reserve telemetry.</p>
                    </div>
                  </div>
                  <div className="col-span-12 xl:col-span-4 tech-panel p-4 rounded-lg border border-white/5 bg-slate-900/55 opacity-75">
                    <SectionHeader icon={Users} title="Household deposits" meta="Inactive" muted />
                    <EmptyState icon={Users} title="Deposit telemetry inactive" muted>Household deposits are not tracked in this run.</EmptyState>
                  </div>
                  <div className="col-span-12 xl:col-span-4 tech-panel p-4 rounded-lg border border-white/5 bg-slate-900/55">
                    <SectionHeader icon={Database} title="Bank inspector" meta="Inactive" muted />
                    <FinanceLiquidityHologram activeLoans={metrics.activeLoans || 0} />
                  </div>
                </div>
              </div>
            )}

            {/* GOVERNMENT VIEW */}
            {activeView === 'GOVERNMENT' && (
              <div className="animate-in fade-in slide-in-from-bottom-4 duration-500 flex-1 min-h-0">
                <PageHeader
                  eyebrow="Government"
                  title="Government Console"
                  summary="Manual policy controls, fiscal health, stabilization tools, and decision audit trail."
                />
                <div className="grid grid-cols-12 gap-4 min-h-0">
                  <div className="col-span-12 xl:col-span-3 flex flex-col gap-4 min-h-0 max-h-[calc(100vh-var(--topbar-height)-150px)] overflow-y-auto command-scroll pr-1">
                    <div className="tech-panel priority-corners p-4 rounded-lg border border-white/5 bg-slate-900/55">
                      <div className="flex items-center justify-between mb-4 pb-2 border-b border-white/5">
                        <div className="flex items-center gap-2">
                          <Landmark className="text-amber-300" size={15} />
                          <h3 className="text-[13px] font-semibold text-slate-300">Policy console</h3>
                        </div>
                        <span className={`text-[9px] font-display font-semibold px-2 py-1 rounded border ${llmColorClass}`}>
                          {llmStatusLabel}
                        </span>
                      </div>
                      <div className="space-y-5">
                        <TechToggle
                          label="AI Policy Engine"
                          checked={config.enableLlmGovernment}
                          onChange={v => handleConfigChange('enableLlmGovernment', v)}
                          description={isPolicyAssistantActive ? llmStatusLabel : 'Policy Assistant inactive. Manual controls remain available.'}
                        />
                        <TechSlider
                          label="Wage Tax"
                          value={config.wageTax}
                          min={0} max={0.5} step={0.01}
                          onChange={v => handleConfigChange('wageTax', v)}
                          format={v => `${(v * 100).toFixed(1)}%`}
                        />
                        <TechSlider
                          label="Profit Tax"
                          value={config.profitTax}
                          min={0} max={0.5} step={0.01}
                          onChange={v => handleConfigChange('profitTax', v)}
                          format={v => `${(v * 100).toFixed(1)}%`}
                        />
                        <TechSelect label="Benefit Level" value={config.benefitLevel} onChange={v => handleConfigChange('benefitLevel', v)} options={enumOptions.benefit} />
                        <TechSelect label="Minimum Wage Policy" value={config.minimumWagePolicy} onChange={v => handleConfigChange('minimumWagePolicy', v)} options={enumOptions.wagePolicy} />
                        <TechToggle label="Public Works" checked={config.publicWorks} onChange={v => handleConfigChange('publicWorks', v)} />
                      </div>
                    </div>

                    <div className="tech-panel tech-corners p-4 space-y-4 rounded-lg border border-white/5 bg-slate-900/55">
                      <div className="flex items-center gap-2 pb-2 border-b border-white/5">
                        <Activity className="text-amber-300" size={15} />
                        <h3 className="text-[13px] font-semibold text-slate-300">Market tools</h3>
                      </div>
                      <TechSelect label="Subsidy Target" value={config.sectorSubsidyTarget} onChange={v => handleConfigChange('sectorSubsidyTarget', v)} options={enumOptions.sectors} />
                      <TechSelect label="Subsidy Level" value={String(config.sectorSubsidyLevel)} options={enumOptions.subsidyLevels} onChange={v => handleConfigChange('sectorSubsidyLevel', Number(v))} />
                      <TechSelect label="Infrastructure" value={config.infrastructureSpending} onChange={v => handleConfigChange('infrastructureSpending', v)} options={enumOptions.level4} />
                      <TechSelect label="Technology" value={config.technologySpending} onChange={v => handleConfigChange('technologySpending', v)} options={enumOptions.level4} />
                      <TechSelect label="Social Spending" value={config.socialSpending} onChange={v => handleConfigChange('socialSpending', v)} options={enumOptions.level4} />
                    </div>
                  </div>

                  <div className="col-span-12 xl:col-span-5 flex flex-col gap-4 min-h-0">
                    <div className="tech-panel priority-corners relative overflow-hidden h-[330px] shrink-0 rounded-lg border border-white/5 bg-slate-900/55">
                      <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(203,213,225,0.08),transparent_58%),radial-gradient(circle_at_50%_82%,rgba(251,191,36,0.055),transparent_40%)] pointer-events-none"></div>
                      <NeuralGovernment active activityLevel={llmActivityLevel} mode={isPolicyAssistantActive ? llmGov.status : 'disabled'} />
                      <div className="absolute top-4 left-4 right-4 flex items-start justify-between gap-4">
                        <div>
                          <div className="text-[10px] text-amber-300/80 font-semibold">Government state</div>
                          <div className="text-2xl font-display text-slate-100 leading-tight">Policy engine status</div>
                        </div>
                        <div className={`text-[10px] font-display font-semibold px-2.5 py-1 rounded border ${llmColorClass}`}>
                          {llmStatusLabel}
                        </div>
                      </div>
                      <div className="absolute bottom-4 left-4 right-4 grid grid-cols-3 gap-2">
                        {isPolicyAssistantActive ? (
                          <>
                            <div className="bg-white/[0.045] border border-white/5 rounded-lg p-2">
                              <div className="text-[9px] text-slate-500">Snapshot</div>
                              <div className="font-mono text-sm text-slate-100">{llmGov.snapshotTick ?? '-'}</div>
                            </div>
                            <div className="bg-white/[0.045] border border-white/5 rounded-lg p-2">
                              <div className="text-[9px] text-slate-500">Applied</div>
                              <div className="font-mono text-sm text-slate-100">{llmGov.appliedTick ?? '-'}</div>
                            </div>
                            <div className="bg-white/[0.045] border border-white/5 rounded-lg p-2">
                              <div className="text-[9px] text-slate-500">Model</div>
                              <div className="font-mono text-[11px] text-slate-100 truncate" title={llmGov.model || llmGov.provider || 'rule-based'}>{friendlyModelName}</div>
                            </div>
                          </>
                        ) : (
                          <div className="col-span-3 bg-white/[0.045] border border-white/5 rounded-lg p-2">
                            <div className="text-[9px] text-slate-500">Status</div>
                            <div className="font-display text-sm text-slate-300">Policy Assistant inactive. Manual controls remain available.</div>
                          </div>
                        )}
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-3">
                      <div className="tech-panel tech-corners p-3 rounded-lg border border-white/5 bg-slate-900/55">
                        <div className="text-[10px] text-slate-500">GDP</div>
                        <div className="font-mono text-lg text-slate-100 mt-1">{formatMillionsAdaptive(metrics.gdp || 0)}</div>
                      </div>
                      <div className="tech-panel tech-corners p-3 rounded-lg border border-white/5 bg-slate-900/55">
                        <div className="text-[10px] text-slate-500">Unemployment</div>
                        <div className="font-mono text-lg text-slate-100 mt-1">{(metrics.unemployment || 0).toFixed(1)}%</div>
                      </div>
                      <div className="tech-panel tech-corners p-3 rounded-lg border border-white/5 bg-slate-900/55">
                        <div className="text-[10px] text-slate-500">Happiness</div>
                        <div className="font-mono text-lg text-slate-100 mt-1">{(metrics.happiness || 0).toFixed(1)} / 100</div>
                      </div>
                      <div className="tech-panel tech-corners p-3 rounded-lg border border-white/5 bg-slate-900/55">
                        <div className="text-[10px] text-slate-500">Net flow</div>
                        <div className={`font-mono text-lg mt-1 ${metrics.govProfit >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                          {metrics.govProfit >= 0 ? '+' : ''}{formatMillionsAdaptive(metrics.govProfit || 0)}
                        </div>
                      </div>
                    </div>

                    <div className="tech-panel priority-corners p-4 flex-1 min-h-[260px] flex flex-col rounded-lg border border-white/5 bg-slate-900/55">
                      <div className="flex items-center justify-between mb-3 pb-2 border-b border-white/5">
                        <div className="flex items-center gap-2">
                          <Terminal className="text-violet-300" size={14} />
                          <h3 className="text-[13px] font-semibold text-slate-300">Decision timeline</h3>
                        </div>
                        <span className="text-[10px] font-mono text-slate-500">
                          {decisionAcceptedEntries.length} accepted / {decisionRejectedEntries.length} rejected
                        </span>
                      </div>
                      <div className="flex-1 overflow-y-auto command-scroll space-y-3 pr-1">
                        {latestDecision ? (
                          <div className="border border-violet-500/25 bg-violet-500/5 rounded p-3">
                            <div className="flex justify-between gap-3 mb-2">
                              <span className="text-xs font-semibold text-slate-100">{latestDecision.primary_goal || latestDecision.status || 'Policy assessment'}</span>
                              <span className="text-[10px] font-mono text-slate-500">TICK {formatTick(latestDecision.appliedTick ?? latestDecision.tick ?? latestDecision.snapshotTick ?? 0)}</span>
                            </div>
                            <p className="text-xs leading-relaxed text-slate-400 mb-3">{decisionSummary || 'Policy assessment recorded.'}</p>
                            {decisionAcceptedEntries.length || decisionRejectedEntries.length ? (
                              <div className="grid grid-cols-2 gap-2">
                                <div className="bg-slate-950/60 border border-slate-800 rounded p-2">
                                  <div className="text-[10px] text-emerald-400 mb-1">Accepted</div>
                                  <div className="font-display text-[12px] text-slate-300 break-words">
                                    {decisionAcceptedEntries.map(([k, v]) => `${formatPolicyName(k)}: ${formatPolicyValue(k, v)}`).join(', ')}
                                  </div>
                                </div>
                                <div className="bg-slate-950/60 border border-slate-800 rounded p-2">
                                  <div className="text-[10px] text-rose-400 mb-1">Rejected</div>
                                  <div className="font-display text-[12px] text-slate-300 break-words">
                                    {decisionRejectedEntries.map(r => `${formatPolicyName(r.lever || r.group || 'change')}: ${r.reason}`).join(', ') || 'None'}
                                  </div>
                                </div>
                              </div>
                            ) : (
                              <EmptyState icon={Terminal} title="No policy changes applied" muted>The assessment did not change any manual controls.</EmptyState>
                            )}
                            {decisionDebug && (
                              <details className="mt-3 rounded border border-slate-800 bg-slate-950/50 p-2">
                                <summary className="cursor-pointer text-[10px] text-slate-500">Decision detail</summary>
                                <pre className="mt-2 max-h-36 overflow-auto command-scroll whitespace-pre-wrap text-[10px] text-slate-500">{String(decisionDebug)}</pre>
                              </details>
                            )}
                          </div>
                        ) : (
                          <EmptyState icon={Terminal} title="No policy decisions yet" muted>
                            Manual policy changes and AI recommendations will appear here.
                          </EmptyState>
                        )}
                        {currentRunPolicyChanges.map((action, i) => (
                          <div key={`${action.tick}-${i}`} className="bg-white/[0.04] border border-white/5 rounded-lg p-3">
                            <div className="flex justify-between gap-3 mb-1">
                              <span className="text-xs font-semibold text-slate-200">{formatPolicyName(action.policy || action.type || 'policy')}</span>
                              <span className="text-[10px] font-mono text-slate-500">TICK {formatTick(action.tick || 0)}</span>
                            </div>
                            <div className="text-[12px] text-slate-500 leading-relaxed">{formatPolicyMessage(action)}</div>
                          </div>
                        ))}
                        {previousRunPolicyChanges.length > 0 && (
                          <details className="rounded-lg border border-white/5 bg-white/[0.04] p-3">
                            <summary className="cursor-pointer text-xs text-slate-400">Previous run history ({previousRunPolicyChanges.length})</summary>
                            <div className="mt-2 space-y-2">
                              {previousRunPolicyChanges.map((action, i) => (
                                <div key={`previous-${action.tick}-${i}`} className="text-[11px] text-slate-500">
                                  Tick {formatTick(action.tick || 0)} Â· {formatPolicyMessage(action)}
                                </div>
                              ))}
                            </div>
                          </details>
                        )}
                      </div>
                    </div>
                  </div>

                  <div className="col-span-12 xl:col-span-4 flex flex-col gap-4 min-h-0 max-h-[calc(100vh-var(--topbar-height)-150px)] overflow-y-auto command-scroll pl-1">
                    <div className="grid grid-cols-2 gap-3">
                      <div className="tech-panel tech-corners p-4 rounded-lg border border-white/5 bg-slate-900/55">
                        <div className="flex items-center gap-2 mb-3">
                          <DollarSign className="text-emerald-400" size={15} />
                          <h3 className="text-[13px] font-semibold text-slate-300">Fiscal flow</h3>
                        </div>
                        <div className="space-y-2 text-xs">
                          <div className="flex justify-between"><span className="text-slate-500">Revenue</span><span className="font-mono text-emerald-400">+{formatMillionsAdaptive(metrics.govRevenue || 0)}</span></div>
                          <div className="flex justify-between"><span className="text-slate-500">Transfers</span><span className="font-mono text-rose-400">-{formatMillionsAdaptive(metrics.govTransfers || 0)}</span></div>
                          <div className="flex justify-between"><span className="text-slate-500">Investments</span><span className="font-mono text-amber-300">-{formatMillionsAdaptive(metrics.govInvestments || 0)}</span></div>
                          <div className="flex justify-between"><span className="text-slate-500">Active Loans</span><span className="font-mono text-slate-300">{formatCompact(metrics.activeLoans || 0)}</span></div>
                        </div>
                      </div>
                      <div className="tech-panel tech-corners p-4 rounded-lg border border-white/5 bg-slate-900/55">
                        <div className="flex items-center gap-2 mb-3">
                          <Globe className="text-amber-300" size={15} />
                          <h3 className="text-[13px] font-semibold text-slate-300">State capacity</h3>
                        </div>
                        <div className="space-y-2 text-xs">
                          <div className="flex justify-between"><span className="text-slate-500">Gov Firms</span><span className="font-mono text-slate-200">{metrics.govOwnedFirms || 0}</span></div>
                          <div className="flex justify-between"><span className="text-slate-500">Bonds</span><span className="font-mono text-slate-200">{formatMillionsAdaptive(metrics.bondPurchases || 0)}</span></div>
                          <div className="flex justify-between"><span className="text-slate-500">Debt</span><span className="font-mono text-slate-200">{formatMillionsAdaptive(metrics.govDebt || 0)}</span></div>
                        </div>
                      </div>
                    </div>

                    <div className="tech-panel tech-corners p-4 space-y-4 rounded-lg border border-white/5 bg-slate-900/55">
                      <div className="flex items-center gap-2 pb-2 border-b border-white/5">
                        <Lock className="text-amber-300" size={14} />
                        <h3 className="text-[13px] font-semibold text-slate-300">Stabilization</h3>
                      </div>
                      <TechSelect label="Price Target" value={config.priceStabilizationTarget} onChange={v => handleConfigChange('priceStabilizationTarget', v)} options={enumOptions.sectors} />
                      <TechSelect label="Price Level" value={config.priceStabilizationLevel} onChange={v => handleConfigChange('priceStabilizationLevel', v)} options={enumOptions.stabilization} />
                      <TechSelect label="Rent Level" value={config.rentStabilizationLevel} onChange={v => handleConfigChange('rentStabilizationLevel', v)} options={enumOptions.stabilization} />
                    </div>

                    <div className="tech-panel tech-corners p-4 space-y-4 rounded-lg border border-white/5 bg-slate-900/55">
                      <div className="flex items-center gap-2 pb-2 border-b border-white/5">
                        <Zap className="text-rose-300" size={14} />
                        <h3 className="text-[13px] font-semibold text-slate-300">Bailouts</h3>
                      </div>
                      <TechSelect label="Policy" value={config.bailoutPolicy} onChange={v => handleConfigChange('bailoutPolicy', v)} options={enumOptions.bailoutPolicy} />
                      <TechSelect label="Target" value={config.bailoutTarget} onChange={v => handleConfigChange('bailoutTarget', v)} options={enumOptions.sectors} />
                      <TechSelect label="Budget" value={String(config.bailoutBudget)} options={enumOptions.bailoutBudgets} onChange={v => handleConfigChange('bailoutBudget', Number(v))} />
                    </div>

                    <div className="min-h-[180px] tech-panel tech-corners p-4 rounded-lg border border-white/5 bg-slate-900/55">
                      {(metrics.govDebt || 0) <= 0 && !(metrics.govDebtHistory || []).some(point => Number(point.value || 0) > 0) ? (
                        <EmptyState icon={Landmark} title="No national debt recorded">Treasury debt remains at $0 for this run.</EmptyState>
                      ) : (
                        <LineChart
                          title="National debt history"
                          data={metrics.govDebtHistory || []}
                          color="#FBBF24"
                          minScale={0}
                          suffix=""
                          headlineLabel="Latest sampled"
                          timeRange="Last 250 ticks"
                          formatValue={v => formatMillionsAdaptive(v)}
                        />
                      )}
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* CONFIG VIEW */}
            {activeView === 'CONFIG' && (
              <div className="animate-in fade-in zoom-in-95 duration-300">
                <PageHeader
                  eyebrow="Config"
                  title="Simulation Controls"
                  summary="Review the active run profile and adjust supported policy levers."
                />
                {!wsConnected && (
                  <div className="mb-4 p-3 bg-rose-400/10 border border-rose-300/35 rounded font-mono text-rose-200 text-xs flex items-center animate-pulse">
                    <Zap className="mr-2" size={14} />
                    Backend telemetry offline. Target: {wsEndpoint}
                  </div>
                )}

                <div className="grid grid-cols-12 gap-4 min-h-[calc(100vh-var(--topbar-height)-150px)] xl:grid-rows-[1fr_auto] items-stretch">
                  <div className="col-span-12 xl:col-span-3 tech-panel p-5 rounded-lg border border-white/5 bg-slate-900/55 h-full flex flex-col">
                    <SectionHeader icon={Users} title="Run profile" meta={isInitialized ? 'Live' : 'Preflight'} />
                    <TechSlider
                      label="Population Scale"
                      value={setupConfig.num_households}
                      min={100} max={10000} step={100}
                      onChange={v => handleSetupChange('num_households', v)}
                      format={v => formatInteger(v)}
                      description="Number of household agents created at launch."
                    />
                    <TechNumberInput
                      label="Simulation seed"
                      value={setupConfig.seed}
                      min={0}
                      max={2147483647}
                      step={1}
                      onChange={v => handleSetupChange('seed', v)}
                      description="Initializes stochastic model state for reproducible run profiles."
                    />
                      <TechToggle
                      label="Policy Assistant"
                      checked={setupConfig.enable_llm_government}
                      onChange={v => handleSetupChange('enable_llm_government', v)}
                      description="Inactive by default. Manual policy controls remain available."
                    />
                    <div className="mt-auto rounded-lg border border-white/5 bg-slate-950/35 p-3">
                      <DetailRow label="Backend" value={wsConnected ? 'Connected' : 'Offline'} tone={wsConnected ? 'positive' : 'negative'} />
                      <DetailRow label="Run State" value={isInitialized ? 'Initialized' : 'Not launched'} />
                      <DetailRow label="Tick" value={isInitialized ? formatTick(tick) : 'Standby'} />
                      <DetailRow label="Government-backed loans" value={isInitialized ? formatInteger(metrics.activeLoans || 0) : 'Pending launch'} />
                    </div>
                  </div>

                  <div className="col-span-12 xl:col-span-6 tech-panel p-5 rounded-lg border border-white/5 bg-slate-900/55 h-full flex flex-col">
                    <SectionHeader icon={Globe} title="Policy settings" meta="Supported runtime levers" />
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-x-6 gap-y-2">
                      <TechSlider
                        label="Wage Tax"
                        value={isInitialized ? config.wageTax : setupConfig.wage_tax}
                        min={0} max={0.5} step={0.01}
                        onChange={v => isInitialized ? handleConfigChange('wageTax', v) : handleSetupChange('wage_tax', v)}
                        format={v => formatPercent(v * 100, 0)}
                        description="Raises government revenue from household wages."
                      />
                      <TechSlider
                        label="Corporate Profit Tax"
                        value={isInitialized ? config.profitTax : setupConfig.profit_tax}
                        min={0} max={0.6} step={0.01}
                        onChange={v => isInitialized ? handleConfigChange('profitTax', v) : handleSetupChange('profit_tax', v)}
                        format={v => formatPercent(v * 100, 0)}
                        description="Collects a share of firm profit after sales."
                      />
                      <TechSlider
                        label="Minimum Wage Floor"
                        value={config.minimumWage}
                        min={0} max={100} step={1}
                        onChange={v => handleConfigChange('minimumWage', v)}
                        format={v => formatCurrency(v)}
                        description="Binds wage offers below the selected floor."
                      />
                      <TechSlider
                        label="Unemployment Benefits"
                        value={config.unemploymentBenefitRate}
                        min={0} max={1.0} step={0.05}
                        onChange={v => handleConfigChange('unemploymentBenefitRate', v)}
                        format={v => `${formatPercent(v * 100, 0)} avg wage`}
                        description="Transfers income to unemployed households."
                      />
                      <TechSelect label="Infrastructure" value={config.infrastructureSpending} onChange={v => handleConfigChange('infrastructureSpending', v)} options={enumOptions.level4} description="Public investment support for productivity." />
                      <TechSelect label="Social Spending" value={config.socialSpending} onChange={v => handleConfigChange('socialSpending', v)} options={enumOptions.level4} description="Stabilizes population welfare where supported." />
                    </div>
                    <div className="mt-auto tech-panel p-4 bg-slate-950/30 rounded-lg border border-white/5">
                      <SectionHeader icon={Activity} title="Stabilization Sandbox" meta={setupConfig.disable_stabilizers ? 'Manual overrides' : 'Automatic'} />
                      <TechToggle
                        label="Disable automatic stabilizers"
                        checked={setupConfig.disable_stabilizers}
                        onChange={(checked) => handleSetupChange('disable_stabilizers', checked)}
                        description="Use this to isolate direct policy effects before automatic stabilizers respond."
                      />
                      {setupConfig.disable_stabilizers && (
                        <div className="grid grid-cols-2 lg:grid-cols-4 gap-2 mt-3">
                          {stabilizerAgentOptions.map(opt => {
                            const active = (setupConfig.disabled_agents || []).includes(opt.key);
                            return (
                              <button
                                type="button"
                                key={opt.key}
                                onClick={() => toggleStabilizerAgent(opt.key)}
                                className={`btn-tech px-3 py-2 text-xs ${active ? 'active' : ''}`}
                              >
                                {opt.label}
                              </button>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="col-span-12 xl:col-span-3 tech-panel priority-corners p-5 rounded-lg border border-white/5 bg-slate-900/55 h-full flex flex-col">
                    <SectionHeader icon={Eye} title="Live Run Snapshot" meta={isInitialized ? 'Live values' : 'Pending launch'} />
                    <div className="space-y-2">
                      <DetailRow label="Current GDP" value={isInitialized ? formatMillionsAdaptive(metrics.gdp || 0) : 'Pending launch'} />
                      <DetailRow label="Unemployment" value={isInitialized ? formatPercent(metrics.unemployment || 0) : 'Pending launch'} />
                      <DetailRow label="Average Wage" value={isInitialized ? formatCurrency(metrics.avgWage || 0, 2) : formatCurrency(config.minimumWage || 0)} />
                      <DetailRow label="Fiscal balance" value={isInitialized ? formatMillionsAdaptive(metrics.govProfit || 0) : 'Not sampled'} tone={(metrics.govProfit || 0) >= 0 ? 'positive' : 'negative'} />
                      <DetailRow label="System Stress" value={isInitialized ? `${formatDecimal(Math.min(100, Math.max(0, (metrics.unemployment || 0) * 0.45 + (100 - (metrics.happiness || 0)) * 0.4)), 0)} / 100` : 'Not sampled'} />
                      <DetailRow label="Policy assistant" value={setupConfig.enable_llm_government ? 'Enabled' : 'Inactive'} tone={setupConfig.enable_llm_government ? 'ai' : 'default'} />
                      <DetailRow label="Government-backed loans" value={metrics.activeLoans ? `${formatInteger(metrics.activeLoans)} active` : 'No active loans'} />
                    </div>
                    <div className="mt-auto">
                      <LiveRunProjection />
                    </div>
                  </div>

                  <div className="col-span-12 tech-panel rounded-lg border border-white/5 bg-slate-900/55 p-3 flex flex-col sm:flex-row justify-end gap-3">
                    <button type="button" onClick={resetPolicyDefaults} className="btn-tech px-5 py-3">
                      Reset Defaults
                    </button>
                    {isInitialized ? (
                      <button type="button" onClick={flushConfigUpdates} className="btn-tech active px-6 py-3 flex items-center justify-center gap-2">
                        <Save size={18} />
                        Apply Changes
                      </button>
                    ) : (
                      <button
                        onClick={handleInitialize}
                        disabled={isInitializing || !wsConnected}
                        className={`btn-tech btn-primary-large px-6 py-3 flex items-center justify-center gap-2 ${(isInitializing || !wsConnected) ? 'cursor-not-allowed' : ''}`}
                      >
                        {isInitializing ? (
                          <>
                            <div className="animate-spin h-5 w-5 border-2 border-amber-500 border-t-transparent rounded-full"></div>
                            Initializing Core
                          </>
                        ) : (
                          <>
                            <Zap size={18} />
                            Launch Simulation
                          </>
                        )}
                      </button>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* LOGS VIEW */}
            {activeView === 'LOGS' && (
              <div className="animate-in fade-in duration-300 flex-1 min-h-0">
                <PageHeader
                  eyebrow="Logs"
                  title="Audit Console"
                  summary="Search, filter, and inspect the live tick stream without leaving the command shell."
                  action={
                    <div className="flex items-center gap-2">
                      <button type="button" onClick={() => setLogDensity(v => v === 'compact' ? 'comfortable' : 'compact')} className="btn-tech px-3 py-2 text-sm">
                        {logDensity === 'compact' ? 'Compact' : 'Comfortable'}
                      </button>
                      <button type="button" onClick={() => setAutoScrollLogs(v => !v)} className={`btn-tech px-3 py-2 text-sm ${autoScrollLogs ? 'active' : ''}`}>
                        Auto-scroll {autoScrollLogs ? 'On' : 'Off'}
                      </button>
                    </div>
                  }
                />
                <div className="grid grid-cols-12 gap-4 min-h-[calc(100vh-var(--topbar-height)-150px)]">
                  <div className="col-span-12 xl:col-span-2 tech-panel p-4 rounded-lg border border-white/5 bg-slate-900/55">
                    <SectionHeader icon={Filter} title="Event filters" meta={formatInteger(filteredLogs.length)} />
                    <div className="space-y-2">
                      {logTypes.map(type => (
                        <button
                          key={type}
                          type="button"
                          onClick={() => { setLogTypeFilter(type); setSelectedLogIndex(0); }}
                          className={`w-full text-left rounded-lg border px-3 py-2 text-xs transition-colors ${logTypeFilter === type ? 'border-white/10 bg-white/10 text-slate-200' : 'border-white/5 bg-white/[0.035] text-slate-400 hover:bg-white/5'}`}
                        >
                          <span>{type}</span>
                          <span className="float-right font-mono tabular-nums text-slate-500">{formatInteger(logTypeCounts[type] || 0)}</span>
                        </button>
                      ))}
                    </div>
                    <button
                      type="button"
                      onClick={() => { setLogTypeFilter('All'); setLogSeverityFilter('All'); setLogSearch(''); setSelectedLogIndex(0); }}
                      className="btn-tech mt-3 w-full px-3 py-2 text-xs"
                    >
                      Clear filters
                    </button>
                    <div className="mt-5">
                      <div className="text-[11px] text-slate-500 mb-2">Severity</div>
                      <div className="flex flex-wrap gap-2">
                        {severityTypes.map(type => (
                          <button
                            key={type}
                            type="button"
                            onClick={() => { setLogSeverityFilter(type); setSelectedLogIndex(0); }}
                            className={`rounded-full border px-3 py-1 text-[11px] transition-colors ${logSeverityFilter === type ? 'border-white/10 bg-white/10 text-slate-200' : 'border-white/5 bg-white/[0.035] text-slate-500 hover:bg-white/5'}`}
                          >
                            {type}
                          </button>
                        ))}
                      </div>
                    </div>
                  </div>

                  <div className="col-span-12 xl:col-span-7 tech-panel p-0 flex flex-col min-h-0 rounded-lg border border-white/5 bg-slate-900/55">
                    <div className="p-4 border-b border-white/5 flex flex-col lg:flex-row gap-3 lg:items-center lg:justify-between">
                      <div className="relative flex-1">
                        <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
                        <input
                          value={logSearch}
                          onChange={(e) => { setLogSearch(e.target.value); setSelectedLogIndex(0); }}
                          placeholder="Search tick, entity, or message"
                          className="w-full rounded-lg border border-white/5 bg-white/[0.045] py-2 pl-9 pr-3 text-sm text-slate-300 placeholder:text-slate-600 outline-none focus:border-white/10 focus:ring-0"
                        />
                      </div>
                      <div className="grid grid-cols-3 gap-2 text-xs min-w-[280px]">
                        <StatTile label="Events" value={formatInteger(normalizedLogs.length)} caption="Buffered" />
                        <StatTile label="Errors" value={formatInteger(normalizedLogs.filter(l => l.severity === 'Error').length)} caption="Current buffer" alert={normalizedLogs.some(l => l.severity === 'Error')} />
                        <StatTile label="Tick Time" value={`${formatDecimal(metrics.tickComputeMs || 0, 0)}ms`} caption="Latest" />
                      </div>
                    </div>
                    <div ref={logsContainerRef} className="flex-1 min-h-0 overflow-auto command-scroll">
                      <table className="w-full table-fixed text-xs">
                        <thead className="sticky top-0 z-10 bg-slate-950/95 border-b border-white/5 text-[11px] text-slate-300 font-display">
                          <tr>
                            <th className="text-right py-2 px-3 w-[92px]">Tick</th>
                            <th className="text-left py-2 px-3 w-[100px]">Type</th>
                            <th className="text-left py-2 px-3 w-[140px]">Entity</th>
                            <th className="text-left py-2 px-3">Message</th>
                            <th className="text-right py-2 px-3 w-[118px]">Duration</th>
                            <th className="text-left py-2 px-3 w-[104px]">Severity</th>
                          </tr>
                        </thead>
                        <tbody>
                          {filteredLogs.map((log, rowIndex) => (
                          <tr
                              key={`${log.tick}-${log.index}`}
                              onClick={() => setSelectedLogIndex(rowIndex)}
                              className={`border-b border-white/5 cursor-pointer transition-colors ${selectedLog?.index === log.index ? 'bg-white/10 text-slate-100' : 'hover:bg-white/5 text-slate-300'}`}
                            >
                              <td className={`${logDensity === 'compact' ? 'py-2' : 'py-3'} px-3 text-right font-mono tabular-nums text-slate-500`}>{formatTick(log.tick)}</td>
                              <td className={`${logDensity === 'compact' ? 'py-2' : 'py-3'} px-3`}><Badge tone={log.type === 'Policy' ? 'ai' : log.type === 'Error' ? 'negative' : 'system'}>{log.type}</Badge></td>
                              <td className={`${logDensity === 'compact' ? 'py-2' : 'py-3'} px-3 truncate text-slate-400`}>{log.entity}</td>
                              <td className={`${logDensity === 'compact' ? 'py-2' : 'py-3'} px-3 truncate`}>{log.message}</td>
                              <td className={`${logDensity === 'compact' ? 'py-2' : 'py-3'} px-3 text-right font-mono tabular-nums text-slate-500`}>{log.duration}</td>
                              <td className={`${logDensity === 'compact' ? 'py-2' : 'py-3'} px-3`}><Badge tone={log.severity === 'Error' ? 'negative' : log.severity === 'Warning' ? 'warning' : 'muted'}>{log.severity}</Badge></td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                      {filteredLogs.length === 0 && <EmptyState title="No matching events">Adjust filters or wait for the next tick.</EmptyState>}
                      <div ref={logsEndRef} />
                    </div>
                  </div>

                  <div className="col-span-12 xl:col-span-3 tech-panel p-4 min-h-0 rounded-lg border border-white/5 bg-slate-900/55">
                    <SectionHeader icon={Eye} title="Selected event" meta={selectedLog ? `Tick ${formatTick(selectedLog.tick)}` : 'None'} />
                    {selectedLog ? (
                      <div className="space-y-4">
                        <div className="rounded-lg border border-white/5 bg-slate-950/45 p-3">
                          <DetailRow label="Type" value={selectedLog.type} />
                          <DetailRow label="Severity" value={selectedLog.severity} tone={selectedLog.severity === 'Error' ? 'negative' : selectedLog.severity === 'Warning' ? 'warning' : 'default'} />
                          <DetailRow label="Entity" value={selectedLog.entity} />
                          <DetailRow label="Duration/Change" value={selectedLog.duration} />
                        </div>
                        <div>
                          <div className="text-[11px] text-slate-500 mb-2">Message</div>
                          <div className="rounded-lg border border-white/5 bg-slate-950/45 p-3 text-sm leading-relaxed text-slate-300 break-words">
                            {selectedLog.message}
                          </div>
                        </div>
                        <details className="rounded-lg border border-white/5 bg-slate-950/45 p-3">
                          <summary className="cursor-pointer text-[11px] text-slate-500">Show raw event</summary>
                          <RawJsonBlock value={selectedLog} />
                        </details>
                      </div>
                    ) : (
                      <EmptyState title="No event selected">Click a row to inspect its full payload.</EmptyState>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* Page wrapper close */}
          </div>
        </div>
      </main>

      {/* Background Decor */}
      <div className="absolute top-0 right-0 w-[500px] h-[500px] bg-amber-400/5 rounded-full blur-[100px] pointer-events-none -z-10"></div>
    </div>
  );
}


