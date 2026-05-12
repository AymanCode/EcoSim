import React, { useState, useEffect, useRef } from 'react';
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
  Lock
} from 'lucide-react';
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer,
  BarChart, Bar, Cell, LabelList
} from 'recharts';

// --- STYLES ---
// "Oberon Command" Theme - Sharp, Technical, Cold
const techStyles = `
  @import url('https://fonts.googleapis.com/css2?family=Chakra+Petch:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;700&display=swap');

  .font-display { font-family: 'Chakra Petch', sans-serif; }
  .font-mono { font-family: 'JetBrains Mono', monospace; }

  .bg-tech-grid {
    background-color: #0b0c15;
    background-image: 
      linear-gradient(rgba(56, 189, 248, 0.03) 1px, transparent 1px),
      linear-gradient(90deg, rgba(56, 189, 248, 0.03) 1px, transparent 1px);
    background-size: 30px 30px;
  }

  .tech-panel {
    background: rgba(17, 24, 39, 0.7);
    backdrop-filter: blur(12px);
    border: 1px solid rgba(56, 189, 248, 0.15);
    box-shadow: 0 0 15px rgba(0, 0, 0, 0.5);
    position: relative;
    overflow: hidden;
  }

  /* The "Bracket" corners effect */
  .tech-corners {
    position: relative;
  }
  .tech-corners::before {
    content: '';
    position: absolute;
    top: 0; left: 0;
    width: 10px; height: 10px;
    border-top: 2px solid #0ea5e9;
    border-left: 2px solid #0ea5e9;
    z-index: 10;
  }
  .tech-corners::after {
    content: '';
    position: absolute;
    bottom: 0; right: 0;
    width: 10px; height: 10px;
    border-bottom: 2px solid #0ea5e9;
    border-right: 2px solid #0ea5e9;
    z-index: 10;
  }

  .btn-tech {
    background: rgba(14, 165, 233, 0.1);
    border: 1px solid rgba(14, 165, 233, 0.3);
    color: #38bdf8;
    transition: all 0.2s ease;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    font-weight: 600;
  }
  
  .btn-tech:hover:not(:disabled) {
    background: rgba(14, 165, 233, 0.2);
    border-color: #38bdf8;
    box-shadow: 0 0 10px rgba(56, 189, 248, 0.3);
  }

  .btn-tech:active:not(:disabled) {
    transform: scale(0.98);
  }

  .btn-tech.active {
    background: #0ea5e9;
    color: #000;
    box-shadow: 0 0 15px rgba(14, 165, 233, 0.5);
  }
  
  .btn-tech:disabled {
    opacity: 0.5;
    cursor: not-allowed;
    border-color: #334155;
    color: #475569;
  }
  
  .btn-danger {
    border-color: rgba(239, 68, 68, 0.4);
    color: #f87171;
    background: rgba(239, 68, 68, 0.1);
  }
  .btn-danger:hover {
    border-color: #ef4444;
    box-shadow: 0 0 10px rgba(239, 68, 68, 0.3);
  }
  
  .btn-primary-large {
    background: rgba(14, 165, 233, 0.15);
    border: 1px solid #0ea5e9;
    color: #38bdf8;
    box-shadow: 0 0 20px rgba(14, 165, 233, 0.2);
  }
  .btn-primary-large:hover {
    background: #0ea5e9;
    color: #000;
    box-shadow: 0 0 30px rgba(14, 165, 233, 0.6);
  }

  .progress-bar {
    background: rgba(14, 165, 233, 0.1);
    border: 1px solid rgba(14, 165, 233, 0.2);
    height: 8px;
    width: 100%;
    position: relative;
  }
  
  .progress-fill {
    background: #0ea5e9;
    height: 100%;
    box-shadow: 0 0 8px rgba(14, 165, 233, 0.6);
  }

  /* Custom range input */
  input[type=range] {
    -webkit-appearance: none;
    background: transparent;
  }
  input[type=range]::-webkit-slider-thumb {
    -webkit-appearance: none;
    height: 16px;
    width: 8px;
    background: #38bdf8;
    cursor: pointer;
    margin-top: -6px;
    box-shadow: 0 0 5px #38bdf8;
  }
  input[type=range]::-webkit-slider-runnable-track {
    width: 100%;
    height: 4px;
    background: #1e293b;
    border: 1px solid #334155;
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
  return (
    <div className="flex flex-col items-center justify-center relative pointer-events-none shadow-xl rounded-full bg-slate-900/60 backdrop-blur-md p-2 border border-slate-700/50">
      <svg fill="none" viewBox={`0 0 ${size} ${size}`} className="transform -rotate-90" style={{ width: size, height: size }}>
        <circle cx={size / 2} cy={size / 2} r={radius} stroke="currentColor" strokeWidth="4" className="text-slate-800" />
        <circle cx={size / 2} cy={size / 2} r={radius} stroke={color} strokeWidth="4" strokeDasharray={circumference} strokeDashoffset={offset} className="transition-all duration-1000 ease-out" style={{ filter: `drop-shadow(0 0 6px ${color})` }} />
      </svg>
      <div className="absolute flex flex-col items-center justify-center">
        <span className="font-display font-bold text-lg" style={{ color }}>{value.toFixed(0)}</span>
      </div>
      <div className="mt-2 text-[9px] uppercase tracking-widest text-slate-400 font-bold bg-slate-900/80 px-2 py-0.5 rounded shadow-sm border border-slate-800">{label}</div>
    </div>
  );
};

const NavButton = ({ icon: Icon, label, isActive, onClick, disabled }) => (
  <button
    onClick={disabled ? null : onClick}
    className={`group relative flex flex-col items-center justify-center w-full py-3 transition-all duration-300
      ${isActive ? 'text-sky-400 bg-sky-500/10 border-l-2 border-sky-400 shadow-[inset_10px_0_20px_rgba(14,165,233,0.15)] relative before:absolute before:left-[-2px] before:top-0 before:bottom-0 before:w-[2px] before:bg-sky-400 before:shadow-[0_0_10px_2px_#38bdf8]' : 'text-slate-500 hover:text-slate-300 hover:bg-white/5 border-l-2 border-transparent'}
      ${disabled ? 'opacity-30 cursor-not-allowed' : 'cursor-pointer'}
    `}
  >
    <Icon size={20} className={`mb-1 transition-transform duration-300 ${isActive ? 'scale-110' : 'group-hover:scale-110'}`} />
    <span className={`text-[9px] font-mono tracking-widest transition-opacity duration-300 ${isActive ? 'font-bold' : ''}`}>{label}</span>

    {/* Floating sliding tooltip on hover */}
    <div className="absolute left-full ml-2 px-3 py-1.5 bg-slate-800/90 backdrop-blur-md text-sky-300 text-[10px] font-mono rounded border border-slate-700/80 opacity-0 -translate-x-2 group-hover:translate-x-0 group-hover:opacity-100 transition-all duration-300 pointer-events-none whitespace-nowrap z-50 shadow-xl shadow-black/50">
      {label} {disabled && <span className="text-rose-400 ml-1">(LOCKED)</span>}
    </div>
  </button>
);
const StatTile = ({ label, value, trend, suffix = "", alert = false }) => {
  const [isHovered, setIsHovered] = React.useState(false);
  const glowColor = trend > 0 ? 'rgba(16, 185, 129, 0.2)' : trend < 0 ? 'rgba(244, 63, 94, 0.2)' : 'rgba(14, 165, 233, 0.15)';
  const borderColor = alert ? 'border-rose-500/50' : 'border-slate-700/50';
  const shadowStyle = isHovered ? { boxShadow: `0 0 20px ${glowColor} inset, 0 0 10px ${glowColor}` } : {};

  return (
    <div 
      className={`tech-panel p-4 flex flex-col tech-corners group backdrop-blur-md bg-slate-900/40 border ${borderColor} transition-all duration-300 relative overflow-hidden`}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      style={shadowStyle}
    >
      <div className="absolute inset-0 bg-gradient-to-br from-white/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500 pointer-events-none"></div>
      <div className="flex justify-between items-start mb-1 relative z-10">
        <span className="text-[11px] uppercase tracking-wider text-slate-400 font-display pr-2 leading-tight group-hover:text-slate-300 transition-colors">{label}</span>
        {trend !== undefined && trend !== null && (
          <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded shrink-0 whitespace-nowrap transition-colors duration-500 ease-in-out ${trend > 0 ? 'bg-emerald-500/10 text-emerald-400' : 'bg-rose-500/10 text-rose-400'}`}>
            {trend > 0 ? '▲' : '▼'} {Math.abs(trend)}%
          </span>
        )}
      </div>
      <div className="flex items-baseline space-x-1 overflow-hidden mt-1 relative z-10">
        <span className="text-xl md:text-2xl font-display font-bold text-slate-100 group-hover:text-white transition-colors truncate">
          {value}
        </span>
        <span className="text-[10px] text-slate-500 font-mono shrink-0 group-hover:text-slate-400">{suffix}</span>
      </div>
      <div className="w-full h-[2px] bg-slate-800/80 mt-2 relative overflow-hidden shrink-0 rounded-full z-10">
        <div className={`absolute top-0 left-0 h-full w-1/3 animate-[pulse_2s_ease-in-out_infinite] ${trend && trend < 0 ? 'bg-rose-500' : 'bg-sky-500'}`}></div>
      </div>
    </div>
  );
};

const TechSlider = ({ label, value, onChange, min, max, step, format = v => v }) => (
  <div className="mb-6">
    <div className="flex justify-between items-end mb-2 font-display">
      <label className="text-sm text-slate-300 font-medium tracking-wide">{label}</label>
      <span className="text-sky-400 font-mono bg-sky-950/30 px-2 py-0.5 rounded text-sm border border-sky-500/20">
        {format(value)}
      </span>
    </div>
    <div className="relative flex items-center">
      <div className="h-2 w-2 bg-slate-600 rounded-full mr-2"></div>
      <input
        type="range"
        min={min} max={max} step={step}
        value={value}
        onChange={(e) => onChange(parseFloat(e.target.value))}
        className="w-full"
      />
      <div className="h-2 w-2 bg-sky-500 rounded-full ml-2 shadow-[0_0_5px_rgba(14,165,233,0.8)]"></div>
    </div>
  </div>
);


// --- SYSTEM DISTRESS GAUGE ---
const SystemDistressGauge = ({ unemployment, happiness }) => {
  // Simple heuristic for demo purposes
  const distress = Math.min(100, Math.max(0, (unemployment * 2.5) + (100 - happiness)));
  const normalized = distress / 100;
  
  let color = '#10b981'; // Green
  let status = 'NOMINAL';
  if (normalized > 0.4) { color = '#fbbf24'; status = 'ELEVATED'; } // Yellow
  if (normalized > 0.6) { color = '#f97316'; status = 'HIGH'; } // Orange
  if (normalized > 0.8) { color = '#ef4444'; status = 'CRITICAL'; } // Red

  // Calculate arc path
  const radius = 60;
  const circumference = radius * Math.PI; // Semi-circle
  const strokeDashoffset = circumference - (normalized * circumference);

  return (
    <div className="flex-1 border border-slate-700/50 rounded bg-slate-900/40 flex flex-col overflow-hidden w-full tech-panel tech-corners p-3 relative group backdrop-blur-md">
      <div className="absolute inset-0 bg-gradient-to-t from-rose-500/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-700 pointer-events-none"></div>
      
      <div className="flex justify-between items-start mb-2 relative z-10">
        <h4 className="text-[10px] font-bold text-slate-400 uppercase tracking-wider leading-none">System Distress</h4>
        <span className="text-[9px] font-mono border border-slate-700 bg-slate-800 px-1 rounded shadow-sm" style={{ color }}>{status}</span>
      </div>
      
      <div className="flex-1 flex flex-col items-center justify-center relative z-10 mt-4">
        <div className="relative w-32 h-16 overflow-hidden">
          <svg viewBox="0 0 140 70" className="w-full h-full overflow-visible drop-shadow-lg">
            {/* Background Arc */}
            <path d="M 10,70 A 60,60 0 0,1 130,70" fill="none" stroke="#1e293b" strokeWidth="12" strokeLinecap="round" />
            {/* Glow Filter */}
            <defs>
              <filter id="distress-glow" x="-20%" y="-20%" width="140%" height="140%">
                <feGaussianBlur stdDeviation="3" result="blur" />
                <feComposite in="SourceGraphic" in2="blur" operator="over" />
              </filter>
            </defs>
            {/* Foreground Arc */}
            <path 
              d="M 10,70 A 60,60 0 0,1 130,70" 
              fill="none" 
              stroke={color} 
              strokeWidth="12" 
              strokeLinecap="round"
              strokeDasharray={circumference}
              strokeDashoffset={strokeDashoffset}
              filter="url(#distress-glow)"
              className="transition-all duration-1000 ease-out"
            />
          </svg>
          <div className="absolute bottom-0 left-0 w-full text-center">
            <span className="text-2xl font-display font-bold drop-shadow-md" style={{ color }}>{distress.toFixed(0)}</span>
          </div>
        </div>
      </div>
    </div>
  );
};

// --- WEALTH INEQUALITY VISUALIZATION ---
const WealthDistributionChart = ({ gini, top10, bottom50 }) => {
  // Determine current state color
  const getCurrentColor = (g) => {
    if (g < 0.30) return "#10b981"; // Green - healthy
    if (g < 0.40) return "#84cc16"; // Light green
    if (g < 0.50) return "#fbbf24"; // Yellow - moderate
    if (g < 0.60) return "#f97316"; // Orange - concerning
    if (g < 0.70) return "#ef4444"; // Red - high
    return "#dc2626"; // Dark red - crisis
  };

  const currentColor = getCurrentColor(gini);
  const wealthData = [
    { label: 'Bot 50%', share: parseFloat(bottom50.toFixed(1)), color: '#6b7280' },
    { label: 'Mid 40%', share: parseFloat((100 - top10 - bottom50).toFixed(1)), color: '#3b82f6' },
    { label: 'Top 10%', share: parseFloat(top10.toFixed(1)), color: '#ef4444' },
  ];

  return (
    <div className="flex-1 relative border border-slate-700/50 bg-slate-900/40 rounded flex flex-col p-2 overflow-hidden w-full tech-panel tech-corners">
      <div className="flex justify-between items-start z-10 w-full px-2 pt-1 min-h-[40px]">
        <div>
          <h4 className="text-[10px] font-bold text-slate-400 uppercase tracking-wider leading-none">Wealth Distribution</h4>
          <div className="text-lg font-mono font-bold mt-1 shadow-sm" style={{ color: currentColor }}>
            {gini.toFixed(3)}
          </div>
        </div>
        <div className="text-[9px] text-slate-500 uppercase text-right mt-0.5">Gini Coeff</div>
      </div>

      {/* Visual Bar Distribution Area */}
      <div className="h-32 w-full pt-2">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={wealthData} margin={{ top: 20, right: 10, bottom: 0, left: 10 }}>
            <Bar dataKey="share" radius={[4, 4, 0, 0]}>
              {wealthData.map((entry, i) => (
                <Cell key={i} fill={entry.color} />
              ))}
              <LabelList dataKey="share" position="top" style={{ fontSize: '11px', fill: '#e2e8f0', fontFamily: 'monospace' }} formatter={(v) => `${v}%`} />
            </Bar>
            <XAxis dataKey="label" tick={{ fontSize: 10, fill: '#94a3b8', fontFamily: 'monospace' }} axisLine={false} tickLine={false} />
            <YAxis hide />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Background Decor */}
      <div className="absolute top-0 right-0 w-32 h-32 bg-sky-500/5 rounded-full blur-2xl -mr-10 -mt-10 pointer-events-none"></div>
    </div>
  );
};

// --- REUSABLE CHART COMPONENT ---
const LineChart = ({ title, data, color, suffix = "", formatValue = v => v.toFixed(1) }) => {
  // Normalize data to array of arrays for multi-line support
  const datasets = Array.isArray(data[0]) ? data : [data];
  const colors = Array.isArray(color) ? color : [color];

  // Check if we have enough data in the primary dataset
  if (!datasets[0] || datasets[0].length < 1) {
    return (
      <div className="flex-1 flex items-center justify-center text-slate-600 font-mono text-xs border border-slate-700/50 bg-slate-900/40 rounded h-32">
        AWAITING DATA
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

  const lastValue = normalizedDatasets[0][normalizedDatasets[0].length - 1].value;
  const safeGradientId = `grad-${title.replace(/[^a-zA-Z0-9]/g, '')}-${Math.floor(Math.random() * 1000)}`;

  return (
    <div className="flex-1 group relative border border-slate-700/50 rounded bg-slate-900/40 flex flex-col overflow-hidden w-full tech-panel tech-corners">

      {/* Chart Header - explicitly placed ABOVE the responsive container */}
      <div className="px-3 pt-3 pb-1 flex justify-between items-start z-10 w-full shrink-0 min-h-[45px]">
        <div>
          <h4 className="text-[11px] md:text-xs font-bold text-slate-400 uppercase tracking-wider leading-tight">{title}</h4>
          <div className="text-sm md:text-base font-mono font-bold text-slate-200 mt-1 shadow-sm">
            {formatValue(lastValue)}<span className="text-[10px] text-slate-500 ml-0.5">{suffix}</span>
          </div>
        </div>
      </div>

      {/* Chart Area - explicitly using h-32 Tailwind class to prevent cramming */}
      <div className="h-32 w-full px-1 pb-1 shrink-0">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={chartData} margin={{ top: 5, right: 0, left: 0, bottom: 0 }}>
            <defs>
              {normalizedDatasets.map((_, dIdx) => (
                <linearGradient key={dIdx} id={`${safeGradientId}-${dIdx}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={colors[dIdx % colors.length]} stopOpacity={0.6} />
                  <stop offset="50%" stopColor={colors[dIdx % colors.length]} stopOpacity={0.1} />
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
                    <div className="bg-slate-900/90 backdrop-blur-md border border-slate-600/50 rounded shadow-[0_0_15px_rgba(14,165,233,0.3)] px-3 py-1.5 flex flex-col items-center z-50">
                      <span className="font-bold flex items-center text-[11px] font-mono text-sky-300 drop-shadow-md">
                        {formatValue(payload[0].value)}{suffix}
                      </span>
                    </div>
                  );
                }
                return null;
              }}
              cursor={{ stroke: 'rgba(56, 189, 248, 0.5)', strokeWidth: 1, strokeDasharray: '4 4' }}
              isAnimationActive={false}
            />
            {normalizedDatasets.map((_, dIdx) => (
              <Area
                key={dIdx}
                type="monotone"
                dataKey={`value${dIdx}`}
                stroke={colors[dIdx % colors.length]}
                strokeWidth={2}
                fillOpacity={1}
                fill={`url(#${safeGradientId}-${dIdx})`}
                isAnimationActive={false}
                activeDot={{ r: 3, strokeWidth: 1, stroke: colors[dIdx % colors.length], fill: '#0f172a' }}
              />
            ))}
          </AreaChart>
        </ResponsiveContainer>
      </div>
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
    trackedFirms: []
  });

  const [requestedSubjectIndex, setActiveSubjectIndex] = useState(0);
  const [requestedFirmIndex, setActiveFirmIndex] = useState(0);
  const [firmStats, setFirmStats] = useState(null);

  const [config, setConfig] = useState({
    wageTax: 0.05,
    profitTax: 0.30,
    inflationRate: 0.02,
    birthRate: 0.01,
    minimumWage: 20.0,
    unemploymentBenefitRate: 0.0,
    universalBasicIncome: 0.0,
    wealthTaxThreshold: 50000,
    wealthTaxRate: 0.0
  });

  // Setup State (for initialization)
  const [setupConfig, setSetupConfig] = useState({
    num_households: 1000,
    num_firms: 5,
    wage_tax: 0.15,
    profit_tax: 0.20,
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

  const formatCurrency = (value, decimals = 0) => {
    const num = Number(value || 0);
    return `$${num.toLocaleString(undefined, {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals
    })}`;
  };

  const formatMillionsAdaptive = (valueInMillions) => {
    const num = Number(valueInMillions || 0);
    const dollars = num * 1_000_000;
    const absDollars = Math.abs(dollars);

    if (absDollars >= 1_000_000_000_000) {
      return `$${(dollars / 1_000_000_000_000).toFixed(2)}T`;
    }
    if (absDollars >= 1_000_000_000) {
      return `$${(dollars / 1_000_000_000).toFixed(2)}B`;
    }
    if (absDollars >= 1_000_000) {
      return `$${(dollars / 1_000_000).toFixed(2)}M`;
    }
    if (absDollars >= 1_000) {
      return `$${(dollars / 1_000).toFixed(1)}K`;
    }
    return `$${dollars.toFixed(0)}`;
  };

  const formatCompact = (value) => Number(value || 0).toLocaleString();
  const selectedTrackedFirm = (metrics.trackedFirms && metrics.trackedFirms.length > 0 && metrics.trackedFirms[activeFirmIndex])
    ? metrics.trackedFirms[activeFirmIndex]
    : null;

  const renderFirmTable = (title, rows) => (
    <div className="tech-panel p-4 tech-corners">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-xs font-bold tracking-widest uppercase text-slate-300">{title}</h3>
        <span className="text-[10px] text-slate-500">{rows && rows.length ? rows.length : 0} tracked</span>
      </div>
      <div className="overflow-x-auto -mx-2">
        <table className="w-full text-[11px] text-slate-300 mx-2">
          <thead className="text-[9px] uppercase text-slate-500">
            <tr>
              <th className="text-left pb-1">Firm</th>
              <th className="text-left pb-1">Cat</th>
              <th className="text-right pb-1">Cash</th>
              <th className="text-right pb-1">Emp</th>
              <th className="text-right pb-1">Price</th>
              <th className="text-right pb-1">Wage</th>
              <th className="text-right pb-1">Profit</th>
            </tr>
          </thead>
          <tbody>
            {rows && rows.length ? rows.slice(0, 8).map(row => (
              <tr key={row.id} className={`border-t ${row.cash < 1000 || row.lastProfit < 0 ? "border-rose-900/50 bg-rose-500/5" : "border-slate-800/60 hover:bg-slate-800/30"} transition-colors`}>

                <td className="py-1 pr-2 font-display text-xs">{row.name}</td>
                <td className="py-1 pr-2 text-slate-500">{row.category}</td>
                <td className="py-1 pr-2 text-right">{formatCurrency(row.cash)}</td>
                <td className="py-1 pr-2 text-right">
                  {row.category === 'Healthcare'
                    ? (row.doctorEmployees || row.medicalEmployees || row.employees)
                    : row.employees}
                </td>
                <td className="py-1 pr-2 text-right">{formatCurrency(row.price, 2)}</td>
                <td className="py-1 pr-2 text-right">{formatCurrency(row.wageOffer, 2)}</td>
                <td className="py-1 pl-2 text-right">{formatCurrency(row.lastProfit, 2)}</td>
              </tr>
            )) : (
              <tr>
                <td colSpan={7} className="py-2 text-center text-slate-500 text-xs">No data yet</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

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

    const connect = () => {
      if (cancelled) return;
      ws.current = new WebSocket(wsEndpoint);

      ws.current.onopen = () => {
        setWsConnected(true);
        console.log("WS Connected");
      };

      ws.current.onmessage = (event) => {
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
            profitTax: cfg.profit_tax
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
            trackedFirms: []
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
            setLogs(prev => [...prev.slice(-20), ...data.logs]);
          }
        } else if (data.error) {
          console.error("Simulation error:", data.error);
          setIsInitializing(false);
        }
      };

      ws.current.onclose = () => {
        setWsConnected(false);
        console.log("WS Disconnected");
        setIsRunning(false);
        setIsInitializing(false);
        if (!cancelled) {
          reconnectTimerRef.current = setTimeout(connect, 1200);
        }
      };

      ws.current.onerror = (err) => {
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
      if (ws.current) {
        ws.current.close();
      }
    };
  }, [wsEndpoint]);

  const handleInitialize = () => {
    if (setupConfig.num_households < 1 || setupConfig.num_firms < 1) {
      console.error("Invalid setup config. num_households and num_firms must be >= 1.");
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

  return (
    <div className="min-h-screen bg-black text-slate-300 font-display selection:bg-sky-500/30 overflow-hidden flex">
      <style>{techStyles}</style>

      {/* SIDEBAR NAVIGATION */}
      <nav className="w-24 bg-slate-900/50 backdrop-blur-md border-r border-slate-800 flex flex-col justify-between z-20">
        <div>
          <div className="h-24 flex items-center justify-center border-b border-slate-800 mb-2">
            <Triangle className="text-sky-500 fill-sky-500/20" size={32} strokeWidth={1.5} />
          </div>
          {/* CONFIG is always active, but others are disabled until initialized */}
          <NavButton icon={Settings} label="Config" isActive={activeView === 'CONFIG'} onClick={() => setActiveView('CONFIG')} />
          <NavButton icon={Activity} label="Dash" isActive={activeView === 'DASHBOARD'} onClick={() => setActiveView('DASHBOARD')} disabled={!isInitialized} />
          <NavButton icon={Users} label="Subjects" isActive={activeView === 'SUBJECTS'} onClick={() => setActiveView('SUBJECTS')} disabled={!isInitialized} />
          <NavButton icon={Building2} label="Firms" isActive={activeView === 'FIRMS'} onClick={() => setActiveView('FIRMS')} disabled={!isInitialized} />
          <NavButton icon={Landmark} label="Gov" isActive={activeView === 'GOVERNMENT'} onClick={() => setActiveView('GOVERNMENT')} disabled={!isInitialized} />
          <NavButton icon={Terminal} label="Logs" isActive={activeView === 'LOGS'} onClick={() => setActiveView('LOGS')} disabled={!isInitialized} />
        </div>

        {/* CONNECTION STATUS */}
        <div className="flex flex-col items-center space-y-2 mt-auto group relative cursor-pointer">
          <div className={`h-2.5 w-2.5 rounded-full ${isInitialized ? 'bg-emerald-500 shadow-[0_0_10px_#10b981] animate-pulse' : 'bg-rose-500 shadow-[0_0_10px_#ef4444]'}`}></div>
          <span className={`text-[9px] font-mono tracking-widest font-bold ${isInitialized ? 'text-emerald-500' : 'text-rose-500'}`}>
            {isInitialized ? 'ONLINE' : 'OFFLINE'}
          </span>
          {/* Tooltip */}
          <div className="absolute left-full ml-4 bottom-0 px-2 py-1 bg-slate-800 text-slate-200 text-[10px] font-mono rounded border border-slate-700 opacity-0 group-hover:opacity-100 transition-opacity duration-200 pointer-events-none whitespace-nowrap z-50 shadow-xl">
            {isInitialized ? 'Connected to Simulation Core' : 'Awaiting Connection...'}
          </div>
        </div>
      </nav>

      {/* MAIN CONTENT AREA */}
      <main className="flex-1 bg-tech-grid relative flex flex-col">
        {/* TOP BAR */}
        <header className="h-16 border-b border-slate-800/50 bg-slate-900/30 flex items-center justify-between px-8 backdrop-blur-sm z-10">
          <div className="flex items-center space-x-6">
            <h1 className="text-xl font-bold tracking-widest text-slate-100">
              ECO<span className="text-sky-500">SIM</span> // OPEN PROJECT
            </h1>
            <div className="h-6 w-[1px] bg-slate-700"></div>
            <div className="flex items-center bg-slate-900 border border-slate-700/50 rounded-md px-3 py-1 shadow-[inset_0_2px_10px_rgba(0,0,0,0.5)]">
              <div className={`h-2 w-2 rounded-full mr-3 ${isInitialized ? 'bg-sky-500 shadow-[0_0_8px_#0ea5e9] animate-pulse' : 'bg-slate-600'}`}></div>
              <div className="font-mono text-sm text-sky-500/80 mr-2 uppercase text-[10px] tracking-widest">Tick</div>
              {isInitialized ? (
                <div className="font-mono text-lg font-bold text-sky-300 drop-shadow-[0_0_5px_rgba(56,189,248,0.8)] tracking-widest">
                  {tick.toString().padStart(5, '0')}
                </div>
              ) : (
                <span className="font-mono text-xs text-amber-500/70 tracking-widest animate-pulse">STANDBY</span>
              )}
            </div>
          </div>

          {isInitialized && (
            <div className="flex items-center space-x-4 animate-in fade-in slide-in-from-right-4 duration-500">
              <button onClick={toggleRun} className={`btn-tech px-6 py-2 flex items-center space-x-2 ${isRunning ? 'active' : ''}`}>
                {isRunning ? <Pause size={18} /> : <Play size={18} />}
                <span>{isRunning ? 'SUSPEND' : 'EXECUTE'}</span>
              </button>
              <button onClick={handleReset} className="btn-tech btn-danger p-2">
                <RotateCcw size={18} />
              </button>
            </div>
          )}
        </header>

        {/* CONTENT SCROLLABLE */}
        <div className="flex-1 overflow-auto relative flex flex-col">
          <div className="w-full max-w-[1900px] mx-auto px-4 md:px-6 xl:px-10 2xl:px-12 py-6 pb-20 relative flex-1 flex flex-col">

            {/* DASHBOARD VIEW */}
            {activeView === 'DASHBOARD' && (
              <div className="grid grid-cols-12 gap-4 animate-in fade-in slide-in-from-bottom-4 duration-500">

                {/* KEY METRICS ROW - COMPACT */}
                <div className="col-span-12 grid grid-cols-2 sm:grid-cols-4 xl:grid-cols-8 gap-3 xl:gap-4 mb-2">
                  <StatTile label="GDP Output" value={formatMillionsAdaptive(metrics.gdp)} trend={2.4} />
                  <StatTile label="Net Worth" value={formatMillionsAdaptive(metrics.netWorth || 0)} trend={1.5} />
                  <StatTile label="Gov Profit" value={formatMillionsAdaptive(metrics.govProfit || 0)} trend={metrics.govProfit > 0 ? 1 : -1} />
                  <StatTile label="Gov Debt" value={formatMillionsAdaptive(metrics.govDebt || 0)} trend={-0.8} />
                  <StatTile label="Unemployment" value={`${metrics.unemployment.toFixed(1)}%`} trend={-1.2} />
                  <StatTile label="Employment" value={`${(100 - metrics.unemployment).toFixed(1)}%`} trend={1.2} />
                  <StatTile label="Avg Wage" value={`$${metrics.avgWage.toFixed(2)}`} trend={0.5} />
                  <StatTile label="Happiness" value={`${metrics.happiness.toFixed(1)}`} trend={0.1} />
                </div>

                {/* WEALTH INEQUALITY ROW */}
                <div className="col-span-12 grid grid-cols-1 md:grid-cols-4 gap-3 xl:gap-4 mb-2">
                  <SystemDistressGauge unemployment={metrics.unemployment} happiness={metrics.happiness} />
                  <StatTile label="Gini Coefficient" value={`${(metrics.giniCoefficient || 0).toFixed(3)}`} suffix="/1.0" />
                  <StatTile label="Top 10% Wealth Share" value={`${(metrics.top10Share || 0).toFixed(1)}%`} />
                  <StatTile label="Bottom 50% Share" value={`${(metrics.bottom50Share || 0).toFixed(1)}%`} />
                </div>

                {/* MAIN VISUALIZER - MULTI-GRAPH GRID */}
                <div className="col-span-12 tech-panel flex-1 flex flex-col p-4 w-full">
                  <div className="flex justify-between items-center mb-2 shrink-0">
                    <h3 className="font-display font-bold text-lg text-slate-200 flex items-center">
                      <BarChart3 className="mr-2 text-sky-500" size={18} />
                      ECONOMIC MONITOR
                    </h3>
                    <div className="flex space-x-2">
                      <span className="px-2 py-0.5 bg-slate-800 text-[10px] font-mono text-slate-400 border border-slate-700">REALTIME</span>
                      <span className="px-2 py-0.5 bg-slate-800 text-[10px] font-mono text-slate-400 border border-slate-700">MACRO</span>
                    </div>
                  </div>

                  <div className="grid grid-cols-1 lg:grid-cols-2 2xl:grid-cols-3 gap-3 xl:gap-4">
                    {/* 1. GDP GROWTH */}
                    <LineChart
                      title="GDP GROWTH"
                      data={metrics.gdpHistory}
                      color="#38bdf8" // Sky Blue
                      minScale={0.5}
                      suffix=""
                      formatValue={v => formatMillionsAdaptive(v)}
                    />

                    {/* 2. WAGE TRENDS (Mean vs Median) */}
                    <LineChart
                      title="WAGE TRENDS (MEAN/MEDIAN)"
                      data={[metrics.wageHistory, metrics.medianWageHistory]}
                      color={["#10b981", "#fbbf24"]} // Emerald, Amber
                      minScale={0}
                      suffix=""
                      formatValue={v => `$${v.toFixed(2)}`}
                    />

                    {/* 3. UNEMPLOYMENT */}
                    <LineChart
                      title="UNEMPLOYMENT RATE"
                      data={metrics.unemploymentHistory}
                      color="#ef4444" // Red
                      minScale={0}
                      suffix="%"
                      formatValue={v => v.toFixed(1)}
                    />

                    {/* 4. TOTAL NET WORTH (Replaces Gov Debt) */}
                    <LineChart
                      title="TOTAL NET WORTH"
                      data={metrics.netWorthHistory || []}
                      color="#a855f7" // Purple
                      minScale={0}
                      suffix=""
                      formatValue={v => formatMillionsAdaptive(v)}
                    />

                    {/* 5. HEALTH INDEX */}
                    <LineChart
                      title="HEALTH INDEX"
                      data={metrics.healthHistory}
                      color="#ec4899" // Pink
                      minScale={0}
                      suffix="/100"
                      formatValue={v => v.toFixed(1)}
                    />

                    {/* 6. MARKET PRICES (Food, Housing, Services, Healthcare) */}
                    <LineChart
                      title="MARKET PRICES (F/H/S/HC)"
                      data={[
                        metrics.priceHistory?.food || [],
                        metrics.priceHistory?.housing || [],
                        metrics.priceHistory?.services || [],
                        metrics.priceHistory?.healthcare || []
                      ]}
                      color={["#d97706", "#10b981", "#06b6d4", "#f43f5e"]} // Amber, Emerald, Cyan, Rose
                      minScale={0}
                      suffix=""
                      formatValue={v => `$${v.toFixed(2)}`}
                    />

                    {/* 7. MARKET SUPPLY (Food, Housing, Services, Healthcare) */}
                    <LineChart
                      title="TOTAL SUPPLY (F/H/S/HC)"
                      data={[
                        metrics.supplyHistory?.food || [],
                        metrics.supplyHistory?.housing || [],
                        metrics.supplyHistory?.services || [],
                        metrics.supplyHistory?.healthcare || []
                      ]}
                      color={["#d97706", "#10b981", "#06b6d4", "#f43f5e"]} // Amber, Emerald, Cyan, Rose
                      minScale={0}
                      suffix=""
                      formatValue={v => Math.floor(v)}
                    />

                    {/* 8. FISCAL BALANCE (Profit) */}
                    <LineChart
                      title="FISCAL BALANCE (PROFIT)"
                      data={metrics.govProfitHistory}
                      color="#8b5cf6" // Violet
                      minScale={-5}
                      suffix=""
                      formatValue={v => formatMillionsAdaptive(v)}
                    />

                    {/* 9. WEALTH INEQUALITY - Visual Distribution */}
                    <WealthDistributionChart
                      gini={metrics.giniCoefficient || 0}
                      top10={metrics.top10Share || 0}
                      bottom50={metrics.bottom50Share || 0}
                    />
                  </div>
                </div>

                {/* SYSTEM ADVISORY FOOTER */}
                <div className="col-span-12">
                  <div className="tech-panel p-3 border-l-2 border-amber-500 bg-amber-500/5 flex justify-between items-center">
                    <div className="flex items-start space-x-2">
                      <Zap className="text-amber-500 shrink-0 mt-0.5" size={14} />
                      <div>
                        <h4 className="text-amber-400 font-bold text-xs">SYSTEM ADVISORY</h4>
                        <p className="text-[10px] text-slate-400 mt-1 leading-relaxed">
                          Monitor inflation risk. Supply chain nominal.
                        </p>
                      </div>
                    </div>
                    <div className="flex space-x-4 text-xs font-mono text-slate-500">
                      <span>FIRMS: <span className="text-slate-300">{metrics.firmCountHistory && metrics.firmCountHistory.length > 0 ? metrics.firmCountHistory[metrics.firmCountHistory.length - 1].value : setupConfig.num_firms * 4}</span></span>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* SUBJECTS VIEW */}
            {activeView === 'SUBJECTS' && (
              <div className="animate-in fade-in slide-in-from-bottom-4 duration-500 flex-1 flex flex-col min-h-0">
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

                {/* TOP TABS - SUBJECT SELECTION */}
                <div className="flex flex-wrap gap-2 mb-4 shrink-0 w-full">
                  {metrics.trackedSubjects && metrics.trackedSubjects.length > 0 ? (
                    metrics.trackedSubjects.map((subject, idx) => (
                      <button
                        key={subject.id}
                        onClick={() => setActiveSubjectIndex(idx)}
                        className={`flex-1 min-w-[100px] sm:min-w-[120px] tech-panel p-2 text-left transition-all ${activeSubjectIndex === idx
                          ? 'border-sky-500 bg-sky-500/10'
                          : 'hover:bg-white/5 border-slate-700/50'
                          }`}
                      >
                        <div className="flex justify-between items-start mb-0.5">
                          <span className="text-[10px] font-mono text-slate-500">ID: {subject.id.toString().padStart(4, '0')}</span>
                          <div className={`h-1.5 w-1.5 rounded-full ${subject.state === 'WORKING' ? 'bg-emerald-500 shadow-[0_0_5px_#10b981]' :
                            subject.state === 'MED_SCHOOL' ? 'bg-violet-500 shadow-[0_0_5px_#8b5cf6]' :
                              subject.state === 'UNEMPLOYED' ? 'bg-rose-500 shadow-[0_0_5px_#f43f5e]' :
                                'bg-amber-500'
                            }`}></div>
                        </div>
                        <div className="font-display font-bold text-xs text-slate-200 truncate">{subject.name}</div>
                        <div className="text-[9px] text-slate-400">{subject.state}</div>
                      </button>
                    ))
                  ) : (
                    <div className="text-slate-500 italic p-4">Waiting for subject tracking data...</div>
                  )}
                </div>

                {/* MAIN CONTENT GRID */}
                {metrics.trackedSubjects && metrics.trackedSubjects[activeSubjectIndex] && (
                  <div className="flex-1 grid grid-cols-12 gap-4 min-h-0 overflow-hidden pb-2">

                    {/* LEFT COLUMN - BIO & EMPLOYMENT */}
                    <div className="col-span-3 flex flex-col space-y-3 overflow-y-auto pr-1 no-scrollbar h-full">
                      {/* ID CARD */}
                      <div className="tech-panel p-2 tech-corners">
                        <h4 className="text-[9px] font-bold text-sky-400 uppercase tracking-widest mb-1 flex items-center">
                          <Users size={10} className="mr-1" /> Bio-Metric
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
                            <span className="font-mono text-xs text-sky-400">{metrics.trackedSubjects[activeSubjectIndex].state}</span>
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
                        <h4 className="text-[9px] font-bold text-amber-400 uppercase tracking-widest mb-1 flex items-center">
                          <Building2 size={10} className="mr-1" /> Employment
                        </h4>
                        <div className="space-y-2">
                          <div>
                            <div className="text-[9px] text-slate-500 mb-0.5">EMPLOYER</div>
                            <div className="font-display text-sm text-slate-200 truncate">
                              {metrics.trackedSubjects[activeSubjectIndex].employer}
                            </div>
                          </div>
                          <div className="flex justify-between">
                            <div>
                              <div className="text-[9px] text-slate-500 mb-0.5">WAGE</div>
                              <div className="font-mono text-sm text-emerald-400">
                                ${metrics.trackedSubjects[activeSubjectIndex].wage.toFixed(2)}
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
                        <h4 className="text-[9px] font-bold text-violet-400 uppercase tracking-widest mb-1 flex items-center">
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
                            <span className="text-[9px] text-slate-500">SUBJECT TARGET</span>
                            <span className="font-mono text-xs text-slate-300">
                              {formatCurrency(metrics.trackedSubjects[activeSubjectIndex].expectedWage || 0, 2)}
                            </span>
                          </div>
                        </div>
                      </div>

                      {/* SUBJECT EXPECTED WAGE DRIVERS */}
                      <div className="tech-panel p-2 tech-corners">
                        <h4 className="text-[9px] font-bold text-fuchsia-400 uppercase tracking-widest mb-1 flex items-center">
                          <Terminal size={10} className="mr-1" /> Target Wage Drivers
                        </h4>
                        <div className="space-y-1">
                          <div className="flex justify-between items-center border-b border-slate-800 pb-0.5">
                            <span className="text-[9px] text-slate-500">MODE</span>
                            <span className="font-mono text-[10px] text-fuchsia-300">
                              {metrics.trackedSubjects[activeSubjectIndex].expectedWageReason?.mode || 'N/A'}
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
                        <h4 className="text-[10px] font-bold text-cyan-400 uppercase tracking-widest mb-3 border-b border-slate-800 pb-2">Skills & Morale</h4>
                        <div className="space-y-4">
                          <div>
                            <div className="flex justify-between items-center mb-1.5">
                              <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">Competency Level</span>
                              <span className="font-mono text-sm text-slate-200">
                                {(metrics.trackedSubjects[activeSubjectIndex].skills * 100).toFixed(0)}%
                              </span>
                            </div>
                            <div className="w-full h-2 bg-slate-800 rounded-full overflow-hidden shadow-inner">
                              <div className="h-full bg-cyan-500 shadow-[0_0_10px_#06b6d4]" style={{ width: `${Math.max(2, metrics.trackedSubjects[activeSubjectIndex].skills * 100)}%` }}></div>
                            </div>
                          </div>
                          <div>
                            <div className="flex justify-between items-center mb-1.5">
                              <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">Morale Index</span>
                              <span className="font-mono text-sm text-slate-200">
                                {(metrics.trackedSubjects[activeSubjectIndex].morale * 100).toFixed(0)}%
                              </span>
                            </div>
                            <div className="w-full h-2 bg-slate-800 rounded-full overflow-hidden shadow-inner">
                              <div className="h-full bg-amber-500 shadow-[0_0_10px_#f59e0b]" style={{ width: `${Math.max(2, metrics.trackedSubjects[activeSubjectIndex].morale * 100)}%` }}></div>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* CENTER COLUMN - VISUALIZER */}
                    <div className="col-span-6 relative flex items-center justify-center overflow-hidden h-full rounded-lg border border-slate-800/50 bg-slate-900/20 shadow-inner">

                      {/* Neural Avatar with Health Status Glow */}
                      <div className={`absolute inset-0 z-0 pointer-events-none transition-all duration-1000 ${
                        (metrics.trackedSubjects[activeSubjectIndex].health || 1) < 0.3 
                        ? 'shadow-[inset_0_0_100px_rgba(244,63,94,0.2)] bg-rose-500/5' 
                        : (metrics.trackedSubjects[activeSubjectIndex].happiness || 0) > 0.8
                          ? 'shadow-[inset_0_0_100px_rgba(16,185,129,0.1)] bg-emerald-500/5'
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
                            {metrics.trackedSubjects[activeSubjectIndex].name}
                            {(metrics.trackedSubjects[activeSubjectIndex].health || 1) < 0.3 && (
                               <span className="text-[10px] bg-rose-500/20 text-rose-400 border border-rose-500/50 px-1.5 py-0.5 rounded animate-pulse">CRITICAL HEALTH</span>
                            )}
                          </h2>
                          <div className="text-xs font-mono text-sky-400 mt-0.5">
                            ID: {metrics.trackedSubjects[activeSubjectIndex].id.toString().padStart(4, '0')}
                          </div>
                        </div>
                        <div className="text-right">
                          <div className={`text-xl font-bold font-display drop-shadow-md ${metrics.trackedSubjects[activeSubjectIndex].state === 'WORKING'
                            ? 'text-emerald-400'
                            : metrics.trackedSubjects[activeSubjectIndex].state === 'MED_SCHOOL'
                              ? 'text-violet-400'
                              : 'text-sky-400'
                            }`}>
                            {metrics.trackedSubjects[activeSubjectIndex].state}
                          </div>
                        </div>
                      </div>

                      {/* Floating Gauges HUD */}
                      <div className="absolute bottom-6 left-6 right-6 flex justify-around z-10">
                        <CircularProgress
                          value={(metrics.trackedSubjects[activeSubjectIndex].health || 0) * 100}
                          color={(metrics.trackedSubjects[activeSubjectIndex].health || 1) < 0.3 ? "#f43f5e" : "#06b6d4"}
                          label="Health"
                          size={75}
                        />
                        <CircularProgress
                          value={(metrics.trackedSubjects[activeSubjectIndex].happiness || 0) * 100}
                          color="#10b981"
                          label="Happiness"
                          size={75}
                        />
                        <CircularProgress
                          value={(metrics.trackedSubjects[activeSubjectIndex].morale || 0) * 100}
                          color="#f59e0b"
                          label="Morale"
                          size={75}
                        />
                      </div>
                      
                      {/* Thought Bubble / Needs */}
                      <div className="absolute top-20 right-8 z-10 max-w-[150px]">
                        {metrics.trackedSubjects[activeSubjectIndex].needs && Object.entries(metrics.trackedSubjects[activeSubjectIndex].needs)
                          .filter(([_, value]) => value > 0)
                          .sort((a, b) => b[1] - a[1])
                          .slice(0, 1)
                          .map(([need], i) => (
                            <div key={i} className="bg-slate-900/80 border border-slate-600 rounded-lg rounded-tr-none p-2 shadow-xl backdrop-blur animate-bounce" style={{ animationDuration: '3s' }}>
                              <div className="text-[9px] text-slate-400 uppercase mb-1">Primary Need</div>
                              <div className="text-xs font-bold text-rose-400 font-mono flex items-center gap-1">
                                ! LACKING {need.toUpperCase()}
                              </div>
                            </div>
                          ))}
                      </div>
                    </div>

                    {/* RIGHT COLUMN - FINANCIALS & NEEDS */}
                    <div className="col-span-3 flex flex-col space-y-3 overflow-y-auto pl-1 no-scrollbar h-full">
                      {/* FINANCIAL HEALTH */}
                      <div className="tech-panel p-2 tech-corners">
                        <h4 className="text-[9px] font-bold text-rose-400 uppercase tracking-widest mb-1 flex items-center">
                          <DollarSign size={10} className="mr-1" /> Finances
                        </h4>
                        <div className="space-y-2">
                          <div className="flex justify-between items-end">
                            <span className="text-[9px] text-slate-500">LIQUID</span>
                            <span className="font-mono text-sm text-white">
                              ${metrics.trackedSubjects[activeSubjectIndex].cash.toFixed(0)}
                            </span>
                          </div>
                          <div className="flex justify-between items-end">
                            <span className="text-[9px] text-slate-500">NET WORTH</span>
                            <span className="font-mono text-sm text-purple-400">
                              ${metrics.trackedSubjects[activeSubjectIndex].netWorth.toFixed(0)}
                            </span>
                          </div>
                          {/* MEDICAL DEBT (RESTORED) */}
                          {metrics.trackedSubjects[activeSubjectIndex].medicalDebt > 0 && (
                            <div className="flex justify-between items-end">
                              <span className="text-[9px] text-slate-500">DEBT</span>
                              <span className="font-mono text-sm text-rose-400">
                                ${metrics.trackedSubjects[activeSubjectIndex].medicalDebt.toFixed(0)}
                              </span>
                            </div>
                          )}
                        </div>
                      </div>

                      {/* CHARTS (RESTORED) */}
                        <div className="flex-1 flex flex-col min-h-0">
                          <LineChart
                            title="Wealth"
                            data={metrics.trackedSubjects[activeSubjectIndex].history?.cash || []}
                            color="#10b981"
                            minScale={0}
                            suffix=""
                            formatValue={v => `${v.toFixed(0)}`}
                          />
                        </div>
                        <div className="flex-1 flex flex-col min-h-0">
                          <LineChart
                            title="Wage"
                            data={metrics.trackedSubjects[activeSubjectIndex].history?.wage || []}
                            color="#f59e0b"
                            minScale={0}
                            suffix=""
                            formatValue={v => `${v.toFixed(0)}`}
                          />
                        </div>
                      {/* INVENTORY */}
                      <div className="tech-panel p-2 tech-corners">
                        <h4 className="text-[9px] font-bold text-slate-400 uppercase tracking-widest mb-1">Inventory</h4>
                        <div className="flex justify-between items-center">
                          <span className="text-[9px] text-slate-500">FOOD</span>
                          <span className="font-mono text-xs text-slate-300">
                            {(metrics.trackedSubjects[activeSubjectIndex].needs?.food ?? 0).toFixed(0)}
                          </span>
                        </div>
                        <div className="flex justify-between items-center mt-1">
                          <span className="text-[9px] text-slate-500">HOUSING</span>
                          <span className="font-mono text-xs text-slate-300">
                            {metrics.trackedSubjects[activeSubjectIndex].needs?.housing ? 'YES' : 'NO'}
                          </span>
                        </div>
                        <div className="flex justify-between items-center mt-1">
                          <span className="text-[9px] text-slate-500">HEALTHCARE</span>
                          <span className="font-mono text-xs text-slate-300">
                            {(metrics.trackedSubjects[activeSubjectIndex].needs?.healthcare ?? 0).toFixed(0)}
                          </span>
                        </div>
                      </div>

                      {/* TRAITS & MODIFIERS */}
                      <div className="tech-panel p-2 tech-corners">
                        <h4 className="text-[9px] font-bold text-cyan-300 uppercase tracking-widest mb-1">Traits & Modifiers</h4>
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
              <div className="animate-in fade-in slide-in-from-bottom-4 duration-500">
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
                  <div className="grid grid-cols-12 gap-4 h-[calc(100vh-220px)] min-h-[620px]">
                    <div className="col-span-8 flex flex-col h-full space-y-4">
                      <div className="grid grid-cols-4 gap-4 shrink-0">
                        <StatTile label="Total Firms" value={formatCompact(firmStats.total_firms)} />
                        <StatTile label="Total Employees" value={formatCompact(firmStats.total_employees)} />
                        <StatTile label="Avg Wage Offer" value={formatCurrency(firmStats.avg_wage_offer || 0, 2)} />
                        <StatTile label="Struggling Firms" value={formatCompact(firmStats.struggling_firms || 0)} />
                      </div>

                      <div className="flex flex-col flex-1 min-h-0 space-y-4">
                        <div className="tech-panel tech-corners relative flex-1 min-h-[14rem] overflow-hidden">
                          <div className="absolute top-0 left-0 right-0 h-24 bg-gradient-to-b from-slate-900 via-slate-900/80 to-transparent z-10 pointer-events-none"></div>
                          <div className="absolute top-4 left-4 z-20">
                            <div className="text-[10px] uppercase text-slate-300 tracking-widest font-bold drop-shadow-md">Market Mood</div>
                            <div className="text-xl font-display text-white drop-shadow-md">
                              {firmStats.struggling_firms > 0.15 * firmStats.total_firms ? 'VOLATILE' : 'STABLE'}
                            </div>
                            <div className="text-[10px] text-slate-300 font-medium drop-shadow-md mt-1">
                              Avg price {formatCurrency(firmStats.avg_price || 0, 2)} | Avg quality {(firmStats.avg_quality || 0).toFixed(2)}
                            </div>
                          </div>
                          <div className="absolute top-4 right-4 text-right text-[10px] text-slate-300 font-medium z-20 drop-shadow-md">
                            {firmStats.market_sentiment || 'Calm winds'}
                          </div>
                          <div className="absolute inset-0 p-4 pt-24 flex flex-col z-0">
                            <div className="grid grid-cols-2 md:grid-cols-4 gap-2 h-full">
                              {firmStats.categories && firmStats.categories.map((cat, i) => {
                                const isDistressed = cat.avg_cash < 2000;
                                const isBooming = cat.avg_cash > 10000;
                                return (
                                  <div key={i} className={`relative rounded-lg border overflow-hidden flex flex-col justify-end p-2 transition-all duration-500 ${
                                    isDistressed ? 'border-rose-500/50 shadow-[inset_0_0_20px_rgba(244,63,94,0.2)]' :
                                    isBooming ? 'border-emerald-500/50 shadow-[inset_0_0_20px_rgba(16,185,129,0.2)]' :
                                    'border-slate-700/50 bg-slate-800/20'
                                  }`}>
                                    <div className={`absolute inset-0 opacity-20 ${isDistressed ? 'bg-rose-500 animate-[pulse_2s_ease-in-out_infinite]' : isBooming ? 'bg-emerald-500' : 'bg-sky-500'}`}></div>
                                    <div className="relative z-10">
                                      <div className={`text-[10px] font-bold uppercase tracking-wider ${isDistressed ? 'text-rose-400' : isBooming ? 'text-emerald-400' : 'text-slate-400'}`}>
                                        {cat.category}
                                      </div>
                                      <div className="flex justify-between items-end mt-1">
                                        <div className="text-xl font-mono text-white">{cat.firm_count}</div>
                                        <div className="text-[9px] text-slate-500 mb-0.5">FIRMS</div>
                                      </div>
                                    </div>
                                  </div>
                                );
                              })}
                            </div>
                          </div>
                        </div>

                        <div className="flex flex-col gap-4">
                          <div className="tech-panel p-4 tech-corners">
                            <div className="flex justify-between items-center mb-3">
                              <h3 className="text-xs font-bold uppercase tracking-widest text-slate-300">Sector Breakdown</h3>
                              <span className="text-[10px] text-slate-300 font-medium">Avg price {formatCurrency(firmStats.avg_price || 0, 2)}</span>
                            </div>
                            {firmStats.categories && firmStats.categories.length ? (
                              <div className="grid grid-cols-2 xl:grid-cols-4 gap-3">
                                {firmStats.categories.map(cat => (
                                  <div key={cat.category} className="border border-slate-800 rounded-md p-3 bg-slate-900/30">
                                    <div className="text-xs font-display text-slate-200">{cat.category}</div>
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

                          <div className="grid grid-cols-2 gap-4 pb-2">
                            {renderFirmTable("Top Cash Positions", firmStats.top_cash || [])}
                            {renderFirmTable("Top Employers", firmStats.top_employers || [])}
                          </div>
                        </div>
                      </div>
                    </div>

                    <div className="col-span-4 flex flex-col space-y-4 min-h-0 h-full">
                      <div className="tech-panel p-3 tech-corners shrink-0">
                        <div className="flex items-center justify-between mb-2">
                          <h3 className="text-xs uppercase font-bold tracking-widest text-slate-300">Tracked Firms</h3>
                          <span className="text-[10px] text-slate-500">{firmCount} monitored</span>
                        </div>
                        <div className="flex flex-wrap gap-2">
                          {metrics.trackedFirms && metrics.trackedFirms.length ? (
                            metrics.trackedFirms.slice(0, 7).map((firm, idx) => (
                              <button
                                key={firm.id}
                                onClick={() => setActiveFirmIndex(idx)}
                                className={`px-3 py-1 text-[11px] rounded border truncate max-w-[8rem] ${activeFirmIndex === idx ? 'border-sky-500 text-sky-300 bg-sky-500/10' : 'border-slate-700 text-slate-400 hover:bg-white/5'}`}
                              >
                                {firm.name}
                              </button>
                            ))
                          ) : (
                            <div className="text-slate-500 text-xs">Sampling firms...</div>
                          )}
                        </div>
                      </div>

                      {selectedTrackedFirm ? (
                        <>
                          <div className="tech-panel p-4 tech-corners space-y-3 shrink-0">
                            <div className="flex justify-between items-center">
                              <div>
                                <h3 className="text-lg font-display text-white">{selectedTrackedFirm.name}</h3>
                                <div className="text-[11px] text-slate-500">{selectedTrackedFirm.category}</div>
                              </div>
                              <div className={`text-xs font-bold ${selectedTrackedFirm.state === 'DISTRESS' ? 'text-rose-400' : selectedTrackedFirm.state === 'SCALING' ? 'text-emerald-400' : 'text-sky-400'}`}>
                                {selectedTrackedFirm.state}
                              </div>
                            </div>
                            <div className="grid grid-cols-2 gap-3 text-sm">
                              <div>
                                <div className="text-[10px] text-slate-500 uppercase">Cash</div>
                                <div className="font-mono text-slate-200">{formatCurrency(selectedTrackedFirm.cash)}</div>
                              </div>
                              <div>
                                <div className="text-[10px] text-slate-500 uppercase">Inventory</div>
                                <div className="font-mono text-slate-200">{selectedTrackedFirm.inventory?.toFixed(1)}</div>
                              </div>
                              <div>
                                <div className="text-[10px] text-slate-500 uppercase">Employees</div>
                                <div className="font-mono text-slate-200">
                                  {selectedTrackedFirm.category === 'Healthcare'
                                    ? (selectedTrackedFirm.doctorEmployees || selectedTrackedFirm.medicalEmployees || selectedTrackedFirm.employees)
                                    : selectedTrackedFirm.employees}
                                </div>
                              </div>
                              <div>
                                <div className="text-[10px] text-slate-500 uppercase">Quality</div>
                                <div className="font-mono text-slate-200">{(selectedTrackedFirm.quality || 0).toFixed(1)}</div>
                              </div>
                            </div>
                            <div className="grid grid-cols-2 gap-3 text-sm">
                              <div>
                                <div className="text-[10px] text-slate-500 uppercase">Price</div>
                                <div className="font-mono text-emerald-400">{formatCurrency(selectedTrackedFirm.price, 2)}</div>
                              </div>
                              <div>
                                <div className="text-[10px] text-slate-500 uppercase">Wage Offer</div>
                                <div className="font-mono text-amber-400">{formatCurrency(selectedTrackedFirm.wageOffer, 2)}</div>
                              </div>
                            </div>
                            <div className="grid grid-cols-2 gap-3 text-sm">
                              <div>
                                <div className="text-[10px] text-slate-500 uppercase">
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
                                <div className="text-[10px] text-slate-500 uppercase">Profit</div>
                                <div className={`font-mono ${selectedTrackedFirm.lastProfit >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                                  {formatCurrency(selectedTrackedFirm.lastProfit, 2)}
                                </div>
                              </div>
                            </div>
                            {selectedTrackedFirm.category === 'Healthcare' && (
                              <div className="grid grid-cols-2 gap-3 text-sm">
                                <div>
                                  <div className="text-[10px] text-slate-500 uppercase">Visits (Tick)</div>
                                  <div className="font-mono text-slate-200">{(selectedTrackedFirm.visitsCompleted || 0).toFixed(0)}</div>
                                </div>
                                <div>
                                  <div className="text-[10px] text-slate-500 uppercase">Doctors</div>
                                  <div className="font-mono text-slate-200">{selectedTrackedFirm.doctorEmployees || 0}</div>
                                </div>
                              </div>
                            )}
                          </div>

                          <div className="flex-1 flex flex-col gap-3 min-h-0">
                            <div className="flex flex-col flex-1 min-h-[170px]">
                              <LineChart
                                title="Cash History"
                                data={selectedTrackedFirm.history?.cash || []}
                                color="#0ea5e9"
                                minScale={0}
                                suffix=""
                                formatValue={v => `$${v.toFixed(0)}`}
                              />
                            </div>
                            <div className="flex flex-col flex-1 min-h-[170px]">
                              <LineChart
                                title="Profit History"
                                data={selectedTrackedFirm.history?.profit || []}
                                color="#f87171"
                                minScale={-1}
                                suffix=""
                                formatValue={v => `$${v.toFixed(0)}`}
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

            {/* GOVERNMENT VIEW */}
            {activeView === 'GOVERNMENT' && (
              <div className="animate-in fade-in slide-in-from-bottom-4 duration-500">
                <style>{`
                  @keyframes holo-pulse {
                    0% { opacity: 0.8; }
                    50% { opacity: 1; }
                    100% { opacity: 0.8; }
                  }
                `}</style>
                <div className="grid grid-cols-12 gap-4 h-[calc(100vh-220px)] min-h-[620px]">
                  
                  {/* LEFT COLUMN - POLICY STANCE & STATE CAPACITY */}
                  <div className="col-span-3 flex flex-col space-y-4 h-full min-h-0 overflow-y-auto pr-1 no-scrollbar">
                    
                    {/* INTERACTIVE POLICY STANCE */}
                    <div className="bg-slate-900/40 border border-slate-800/60 p-4 rounded-lg flex-1 flex flex-col relative overflow-hidden">
                      {/* Subtle purple accent for policy element */}
                      <div className="absolute top-0 left-0 w-full h-px bg-gradient-to-r from-transparent via-violet-500/20 to-transparent"></div>
                      <div className="flex items-center space-x-2 mb-4 pb-2 shrink-0 border-b border-slate-800/60">
                        <Landmark className="text-violet-400/80" size={14} />
                        <h3 className="text-[11px] font-semibold uppercase tracking-widest text-slate-400">Policy Overrides</h3>
                      </div>
                      <div className="flex-1 overflow-y-auto no-scrollbar space-y-5 pr-2">
                        <TechSlider
                          label="Income Tax (Wage)"
                          value={config.wageTax}
                          min={0} max={0.5} step={0.01}
                          onChange={v => handleConfigChange('wageTax', v)}
                          format={v => `${(v * 100).toFixed(1)}%`}
                        />
                        <TechSlider
                          label="Corporate Tax"
                          value={config.profitTax}
                          min={0} max={0.5} step={0.01}
                          onChange={v => handleConfigChange('profitTax', v)}
                          format={v => `${(v * 100).toFixed(1)}%`}
                        />
                        <TechSlider
                          label="Wealth Tax"
                          value={config.wealthTaxRate}
                          min={0} max={0.1} step={0.005}
                          onChange={v => handleConfigChange('wealthTaxRate', v)}
                          format={v => `${(v * 100).toFixed(1)}%`}
                        />
                        <TechSlider
                          label="Unemployment Ben."
                          value={config.unemploymentBenefitRate}
                          min={0} max={1.0} step={0.05}
                          onChange={v => handleConfigChange('unemploymentBenefitRate', v)}
                          format={v => `${(v * 100).toFixed(0)}%`}
                        />
                        <TechSlider
                          label="Min Wage"
                          value={config.minimumWage}
                          min={0} max={50} step={1}
                          onChange={v => handleConfigChange('minimumWage', v)}
                          format={v => `$${v.toFixed(2)}`}
                        />
                      </div>
                    </div>

                    {/* STATE CAPACITY */}
                    <div className="bg-slate-900/40 border border-slate-800/60 p-4 rounded-lg shrink-0">
                      <div className="absolute top-0 left-0 w-full h-px bg-gradient-to-r from-transparent via-cyan-500/20 to-transparent"></div>
                      <div className="flex items-center space-x-2 mb-3 pb-2 border-b border-slate-800/60">
                        <Globe className="text-cyan-500/70" size={14} />
                        <h3 className="text-[11px] font-semibold uppercase tracking-widest text-slate-400">State Capacity</h3>
                      </div>
                      <div className="space-y-1.5">
                        <div className="flex justify-between items-center py-1.5 px-2 rounded hover:bg-slate-800/30 transition-colors">
                          <span className="text-[11px] text-slate-400">Gov Owned Firms</span>
                          <span className="font-mono text-[13px] text-slate-200">{metrics.govOwnedFirms || 0}</span>
                        </div>
                        <div className="flex justify-between items-center py-1.5 px-2 rounded hover:bg-slate-800/30 transition-colors">
                          <span className="text-[11px] text-slate-400">Active Loans</span>
                          <span className="font-mono text-[13px] text-slate-200">{formatMillionsAdaptive(metrics.activeLoans || 0)}</span>
                        </div>
                        <div className="flex justify-between items-center py-1.5 px-2 rounded hover:bg-slate-800/30 transition-colors">
                          <span className="text-[11px] text-slate-400">Bond Purchases</span>
                          <span className="font-mono text-[13px] text-slate-200">{formatMillionsAdaptive(metrics.bondPurchases || 0)}</span>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* CENTER COLUMN - VISUAL & SYSTEM LOGS */}
                  <div className="col-span-6 flex flex-col space-y-4 min-h-0 h-full">
                    
                    {/* MACRO IMPACT DASHBOARD (Replaces 3D Neural Avatar) */}
                    {/* Visual anchor - the hologram element remains the focal point above this in the final design if restored, but here we treat this panel as the primary data anchor */}
                    <div className="bg-slate-900/60 border border-slate-700/50 p-5 rounded-lg shrink-0 relative overflow-hidden backdrop-blur-sm">
                      <div className="flex justify-between items-end mb-5 border-b border-slate-800 pb-3">
                        <div>
                          <div className="text-[10px] uppercase text-cyan-500/70 tracking-widest font-bold mb-1">Central Authority</div>
                          <div className="text-lg font-display text-slate-100">Macro Impact</div>
                        </div>
                        <div className="flex items-center space-x-2 bg-cyan-950/30 px-2 py-1 rounded border border-cyan-900/50">
                          <div className="h-1.5 w-1.5 bg-cyan-500 rounded-full shadow-[0_0_4px_#06b6d4]"></div>
                          <span className="text-[10px] text-cyan-400 font-mono">LIVE TELEMETRY</span>
                        </div>
                      </div>
                      
                      <div className="grid grid-cols-2 gap-3">
                        <div className="bg-slate-900/50 border border-slate-800/50 rounded-md p-3 flex flex-col justify-between">
                          <span className="text-[11px] text-slate-400 mb-1">Gross Domestic Product</span>
                          <div className="flex justify-between items-end mt-1">
                            <span className="font-mono text-[17px] text-slate-100">{formatMillionsAdaptive(metrics.gdp || 0)}</span>
                            <span className="text-[10px] font-mono text-emerald-400 bg-emerald-950/30 px-1 rounded border border-emerald-900/50">+2.4%</span>
                          </div>
                        </div>
                        <div className="bg-slate-900/50 border border-slate-800/50 rounded-md p-3 flex flex-col justify-between">
                          <span className="text-[11px] text-slate-400 mb-1">Avg Subject Happiness</span>
                          <div className="flex justify-between items-end mt-1">
                            <span className="font-mono text-[17px] text-slate-100">{(metrics.happiness || 0).toFixed(1)} <span className="text-[11px] text-slate-500">/ 100</span></span>
                            <span className="text-[10px] font-mono text-emerald-400 bg-emerald-950/30 px-1 rounded border border-emerald-900/50">+0.8%</span>
                          </div>
                        </div>
                        <div className="bg-slate-900/50 border border-slate-800/50 rounded-md p-3 flex flex-col justify-between">
                          <span className="text-[11px] text-slate-400 mb-1">Distressed Firms</span>
                          <div className="flex justify-between items-end mt-1">
                            <span className="font-mono text-[17px] text-slate-100">{formatCompact(metrics.burn_mode_firm_count || 0)}</span>
                            <span className={`text-[10px] font-mono px-1 rounded border ${((metrics.burn_mode_firm_count || 0) > 0) ? 'text-rose-400 bg-rose-950/30 border-rose-900/50' : 'text-slate-400 bg-slate-800/50 border-slate-700/50'}`}>
                              {((metrics.burn_mode_firm_count || 0) > 0) ? '+1.2%' : '0.0%'}
                            </span>
                          </div>
                        </div>
                        <div className="bg-slate-900/50 border border-slate-800/50 rounded-md p-3 flex flex-col justify-between">
                          <span className="text-[11px] text-slate-400 mb-1">Unemployment Rate</span>
                          <div className="flex justify-between items-end mt-1">
                            <span className="font-mono text-[17px] text-slate-100">{(metrics.unemploymentRate * 100 || 0).toFixed(1)}%</span>
                            <span className={`text-[10px] font-mono px-1 rounded border ${metrics.unemploymentRate > 0.05 ? 'text-rose-400 bg-rose-950/30 border-rose-900/50' : 'text-emerald-400 bg-emerald-950/30 border-emerald-900/50'}`}>
                              {metrics.unemploymentRate > 0.05 ? '+0.5%' : '-0.2%'}
                            </span>
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* ACTIVE DIRECTIVES (Replaces Live Reasoning Feed) */}
                    <div className="bg-slate-900/40 border border-slate-800/60 p-5 rounded-lg flex-1 flex flex-col relative overflow-hidden">
                      <div className="flex justify-between items-center mb-4 pb-2 border-b border-slate-800/60 shrink-0 relative z-10">
                        <div className="flex items-center space-x-2">
                          <Activity className="text-violet-400/80" size={14} />
                          <h3 className="text-[11px] font-semibold uppercase tracking-widest text-slate-400">Active Directives</h3>
                        </div>
                      </div>
                      
                      <div className="flex-1 overflow-y-auto no-scrollbar space-y-2.5 relative z-10 pr-1">
                        {metrics.policyChanges && metrics.policyChanges.length > 0 ? (
                           metrics.policyChanges.slice().reverse().map((action, i) => (
                             <div key={i} className={`p-3.5 rounded-md border transition-all duration-300 ${i === 0 ? 'bg-slate-800/50 border-violet-500/30 shadow-[inset_2px_0_0_#8b5cf6]' : 'bg-slate-900/30 border-slate-800/50'}`}>
                               <div className="flex justify-between items-start mb-2">
                                 <div className="flex items-center space-x-2">
                                   <div className={`p-1 rounded ${i === 0 ? 'text-violet-400 bg-violet-500/10' : 'text-slate-500 bg-slate-800/50'}`}>
                                     <Terminal size={12} />
                                   </div>
                                   <span className={`text-[13px] font-semibold tracking-wide ${i === 0 ? 'text-slate-100' : 'text-slate-300'}`}>
                                     {action.type}
                                   </span>
                                 </div>
                                 <span className="text-[10px] font-mono text-slate-500 bg-slate-950 px-1.5 py-0.5 rounded border border-slate-800">
                                   TICK {action.tick}
                                 </span>
                               </div>
                               <div className="text-[12px] text-slate-400 leading-relaxed bg-slate-950/30 p-2.5 rounded-sm border border-slate-800/30">
                                 {action.reason}
                               </div>
                             </div>
                           ))
                        ) : (
                           <div className="text-slate-600 text-sm p-8 text-center h-full flex flex-col items-center justify-center space-y-3 border border-dashed border-slate-800/60 rounded-md">
                              <Terminal size={24} className="opacity-20 mb-1" />
                              <p className="font-mono text-[12px]">NO ACTIVE DIRECTIVES</p>
                              <p className="text-[10px] uppercase tracking-widest">Awaiting central authority protocols</p>
                           </div>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* RIGHT COLUMN - BUDGET & FISCAL HEALTH */}
                  <div className="col-span-3 flex flex-col space-y-4 h-full min-h-0 overflow-y-auto pl-1 no-scrollbar">
                    
                    {/* BUDGET OVERVIEW */}
                    <div className="bg-slate-900/40 border border-slate-800/60 p-4 rounded-lg">
                      <div className="absolute top-0 left-0 w-full h-px bg-gradient-to-r from-transparent via-emerald-500/20 to-transparent"></div>
                      <div className="flex items-center space-x-2 mb-4 pb-2 border-b border-slate-800/60">
                        <DollarSign className="text-emerald-500/70" size={14} />
                        <h3 className="text-[11px] font-semibold uppercase tracking-widest text-slate-400">Fiscal Flow</h3>
                      </div>
                      
                      <div className="space-y-3.5">
                        <div className="border-l border-emerald-500/40 pl-2.5">
                          <div className="text-[10px] text-slate-500 mb-0.5 uppercase tracking-wide">Daily Revenue</div>
                          <div className="font-mono text-[13px] text-emerald-400">+{formatMillionsAdaptive(metrics.govRevenue || 0)}</div>
                        </div>
                        
                        <div className="border-l border-rose-500/40 pl-2.5">
                          <div className="text-[10px] text-slate-500 mb-0.5 uppercase tracking-wide">Transfers / Welfare</div>
                          <div className="font-mono text-[13px] text-rose-400">-{formatMillionsAdaptive(metrics.govTransfers || 0)}</div>
                        </div>
                        
                        <div className="border-l border-amber-500/40 pl-2.5">
                          <div className="text-[10px] text-slate-500 mb-0.5 uppercase tracking-wide">Infrastructure</div>
                          <div className="font-mono text-[13px] text-amber-400">-{formatMillionsAdaptive(metrics.govInvestments || 0)}</div>
                        </div>

                        <div className="border-l border-slate-600/40 pl-2.5">
                          <div className="text-[10px] text-slate-500 mb-0.5 uppercase tracking-wide">Targeted Loans</div>
                          <div className="font-mono text-[13px] text-slate-300">-{formatMillionsAdaptive(metrics.govLoans || 0)}</div>
                        </div>

                        <div className={`mt-5 pt-3 border-t border-slate-800/60 flex justify-between items-end`}>
                          <div className="text-[11px] font-semibold uppercase text-slate-400 tracking-wide">Net Flow</div>
                          <div className={`font-mono text-[15px] ${metrics.govProfit >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                            {metrics.govProfit >= 0 ? '+' : ''}{formatMillionsAdaptive(metrics.govProfit || 0)}
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* NATIONAL DEBT MAP */}
                    <div className="flex-1 flex flex-col min-h-[160px] bg-slate-900/40 border border-slate-800/60 p-4 rounded-lg relative">
                      <div className="absolute top-0 left-0 w-full h-px bg-gradient-to-r from-transparent via-rose-500/20 to-transparent"></div>
                      <LineChart
                        title="National Debt History"
                        data={metrics.govDebtHistory || []}
                        color="#f43f5e"
                        minScale={0}
                        suffix=""
                        formatValue={v => formatMillionsAdaptive(v)}
                      />
                    </div>
                  </div>

                </div>
              </div>
            )}

            {/* CONFIG VIEW */}
            {activeView === 'CONFIG' && (
              <div className="grid grid-cols-2 gap-8 max-w-4xl mx-auto animate-in fade-in zoom-in-95 duration-300">
                <div className="col-span-2 mb-6 border-b border-sky-500/30 pb-4">
                  <h2 className="text-4xl font-display font-bold text-transparent bg-clip-text bg-gradient-to-r from-sky-400 to-emerald-400 mb-2 flex items-center tracking-widest">
                    <Terminal className="mr-3 text-sky-400" size={32} />
                    {isInitialized ? 'RUNTIME_CONFIG' : 'BOOT_SEQUENCE'}
                  </h2>
                  <p className="text-slate-400 font-mono text-sm tracking-wide">
                    {isInitialized
                      ? "> Macroeconomic parameter adjustment protocol [ACTIVE]"
                      : "> Initializing macroeconomic physics engine. Awaiting parameter input."}
                  </p>
                  {!wsConnected && (
                    <div className="mt-4 p-3 bg-rose-500/10 border border-rose-500/50 rounded font-mono text-rose-400 text-xs flex items-center animate-pulse">
                      <Zap className="mr-2" size={14} />
                      CRITICAL ERROR: Backend telemetry offline. Target: {wsEndpoint}
                    </div>
                  )}
                </div>

                {/* System Scale - Only visible during setup */}
                {!isInitialized && (
                  <div className="col-span-2 tech-panel p-8 tech-corners mb-4 relative overflow-hidden">
                    <div className="absolute top-0 right-0 w-32 h-32 bg-sky-500/10 blur-[50px] rounded-full pointer-events-none"></div>
                    <div className="flex items-center space-x-3 mb-8 pb-4 border-b border-slate-700/50">
                      <Users className="text-sky-400" />
                      <h3 className="text-xl font-bold font-mono tracking-widest text-slate-200">SYSTEM SCALE</h3>
                    </div>
                    <div className="grid grid-cols-1 gap-8">
                      <TechSlider
                        label="Population Scale (Households)"
                        value={setupConfig.num_households}
                        min={100} max={10000} step={100}
                        onChange={v => handleSetupChange('num_households', v)}
                        format={v => v.toLocaleString()}
                      />
                    </div>
                  </div>
                )}

                {/* Fiscal Controls */}
                <div className="tech-panel p-8 tech-corners">
                  <div className="flex items-center space-x-3 mb-8 pb-4 border-b border-slate-700/50">
                    <Globe className="text-sky-400" />
                    <h3 className="text-xl font-bold text-slate-200">FISCAL POLICY</h3>
                  </div>

                  <TechSlider
                    label="Wage Tax Rate"
                    value={isInitialized ? config.wageTax : setupConfig.wage_tax}
                    min={0} max={0.5} step={0.01}
                    onChange={v => isInitialized ? handleConfigChange('wageTax', v) : handleSetupChange('wage_tax', v)}
                    format={v => `${(v * 100).toFixed(0)}%`}
                  />
                  <TechSlider
                    label="Corp Profit Tax"
                    value={isInitialized ? config.profitTax : setupConfig.profit_tax}
                    min={0} max={0.6} step={0.01}
                    onChange={v => isInitialized ? handleConfigChange('profitTax', v) : handleSetupChange('profit_tax', v)}
                    format={v => `${(v * 100).toFixed(0)}%`}
                  />
                  <div className="text-xs text-slate-500 border border-slate-800 rounded p-3 bg-slate-900/30">
                    Live runtime controls are currently: wage tax and profit tax.
                  </div>
                </div>

                {/* Social Policy Controls */}
                <div className="tech-panel p-8 tech-corners">
                  <div className="flex items-center space-x-3 mb-8 pb-4 border-b border-slate-700/50">
                    <Users className="text-emerald-400" />
                    <h3 className="text-xl font-bold text-slate-200">SOCIAL POLICY</h3>
                  </div>

                  <TechSlider
                    label="Minimum Wage Floor"
                    value={config.minimumWage}
                    min={0} max={100} step={1}
                    onChange={v => handleConfigChange('minimumWage', v)}
                    format={v => `$${v.toFixed(0)}`}
                  />
                  <TechSlider
                    label="Unemployment Benefits"
                    value={config.unemploymentBenefitRate}
                    min={0} max={1.0} step={0.05}
                    onChange={v => handleConfigChange('unemploymentBenefitRate', v)}
                    format={v => `${(v * 100).toFixed(0)}% of avg wage`}
                  />
                  <div className="text-xs text-slate-500 border border-slate-800 rounded p-3 bg-slate-900/30">
                    Live runtime controls are currently: minimum wage and unemployment benefits.
                    Inflation, birth rate, UBI, and wealth-tax controls are not wired into the live simulation loop yet.
                  </div>
                </div>

                {/* Stabilization Sandbox */}
                <div className="col-span-2 tech-panel p-8 tech-corners">
                  <div className="flex items-center space-x-3 mb-6 pb-4 border-b border-slate-700/50">
                    <Activity className="text-rose-400" />
                    <h3 className="text-xl font-bold text-slate-200">STABILIZATION SANDBOX</h3>
                  </div>
                  <label className="flex items-center space-x-3 text-slate-300 text-sm font-display tracking-wide">
                    <input
                      type="checkbox"
                      checked={setupConfig.disable_stabilizers}
                      onChange={(e) => handleSetupChange('disable_stabilizers', e.target.checked)}
                      className="form-checkbox h-4 w-4 text-sky-500"
                    />
                    <span>Disable automatic stabilizers for selected agents</span>
                  </label>
                  <p className="text-xs text-slate-500 mt-2">
                    Use this to observe raw policy effects without safety nets. When enabled, choose which agents stop smoothing their decisions.
                  </p>
                  {setupConfig.disable_stabilizers && (
                    <div className="grid grid-cols-2 gap-3 mt-6">
                      {stabilizerAgentOptions.map(opt => {
                        const active = (setupConfig.disabled_agents || []).includes(opt.key);
                        return (
                          <button
                            type="button"
                            key={opt.key}
                            onClick={() => toggleStabilizerAgent(opt.key)}
                            className={`btn-tech px-4 py-2 text-sm ${active ? 'active' : ''}`}
                          >
                            {opt.label}
                          </button>
                        );
                      })}
                    </div>
                  )}
                </div>

                <div className="col-span-2 flex justify-end space-x-4 mt-6">
                  {isInitialized ? (
                    <button className="btn-tech px-8 py-3 flex items-center space-x-2 active bg-sky-500 text-white shadow-lg shadow-sky-500/20">
                      <Save size={18} />
                      <span className="font-mono tracking-widest">COMMIT PARAMS</span>
                    </button>
                  ) : (
                    <button
                      onClick={handleInitialize}
                      disabled={isInitializing || !wsConnected}
                      className={`relative overflow-hidden w-full py-6 flex items-center justify-center space-x-3 text-lg font-bold font-mono tracking-[0.2em] rounded border transition-all duration-500
                        ${(isInitializing || !wsConnected) 
                          ? 'border-slate-700 bg-slate-800/50 text-slate-500 cursor-not-allowed' 
                          : 'border-sky-500 bg-sky-500/10 text-sky-300 hover:bg-sky-500/20 hover:text-white shadow-[0_0_20px_rgba(14,165,233,0.3)] hover:shadow-[0_0_40px_rgba(14,165,233,0.6)]'
                        }
                      `}
                    >
                      {isInitializing ? (
                        <>
                          <div className="animate-spin h-5 w-5 border-2 border-sky-500 border-t-transparent rounded-full"></div>
                          <span className="animate-pulse">INITIALIZING CORE...</span>
                        </>
                      ) : (
                        <>
                          <Zap size={24} className={wsConnected ? "text-sky-400 animate-pulse" : ""} />
                          <span>INITIALIZE PROTOCOL</span>
                          {/* Scanline effect */}
                          <div className="absolute inset-0 bg-gradient-to-b from-transparent via-white/5 to-transparent h-full w-full -translate-y-full hover:animate-[scanline_2s_linear_infinite] pointer-events-none"></div>
                        </>
                      )}
                    </button>
                  )}
                </div>
              </div>
            )}

            {/* LOGS VIEW */}
            {activeView === 'LOGS' && (
              <div className="max-w-5xl mx-auto tech-panel h-[600px] flex flex-col p-0 tech-corners animate-in fade-in duration-300">
                <div className="bg-slate-900/80 p-3 border-b border-slate-700 flex justify-between items-center">
                  <span className="font-mono text-sm text-sky-400 flex items-center">
                    <Terminal size={14} className="mr-2" />
                    /var/logs/ecosim_events.log
                  </span>
                  <span className="text-xs text-slate-500">AUTO-SCROLL: ON</span>
                </div>
                <div className="flex-1 overflow-y-auto p-4 font-mono text-sm space-y-1 bg-black/40">
                  {logs.length === 0 && <div className="text-slate-600 italic">No events recorded in current session.</div>}
                  {logs.map((log, i) => (
                    <div key={i} className="flex space-x-4 border-b border-slate-800/30 pb-1 mb-1 hover:bg-white/5 p-1 rounded">
                      <span className="text-slate-500 w-16 text-right">{log.tick ? log.tick.toString().padStart(4, '0') : '0000'}</span>
                      <span className={`w-12 font-bold ${log.type === 'WARN' ? 'text-amber-500' :
                        log.type === 'ECO' ? 'text-emerald-500' :
                          log.type === 'GOV' ? 'text-purple-400' :
                            log.type === 'SYS' ? 'text-slate-100' :
                              'text-sky-500'
                        }`}>{log.type}</span>
                      <span className="text-slate-300">{log.txt}</span>
                    </div>
                  ))}
                  <div ref={logsEndRef} />
                </div>
              </div>
            )}

            {/* Page wrapper close */}
          </div>
        </div>
      </main>

      {/* Background Decor */}
      <div className="absolute top-0 right-0 w-[500px] h-[500px] bg-sky-500/5 rounded-full blur-[100px] pointer-events-none -z-10"></div>
    </div>
  );
}
