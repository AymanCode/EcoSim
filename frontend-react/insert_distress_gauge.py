import os

with open('src/App.jsx', 'r', encoding='utf-8') as f:
    lines = f.readlines()

component_code = """
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

"""

# Insert right before WealthDistributionChart
target = '// --- WEALTH INEQUALITY VISUALIZATION ---'
for i, line in enumerate(lines):
    if target in line:
        lines.insert(i, component_code)
        break

# Now insert it into the dashboard row!
# The layout currently has:
#                 {/* WEALTH INEQUALITY ROW */}
#                 <div className="col-span-12 grid grid-cols-1 md:grid-cols-3 gap-3 xl:gap-4 mb-2">
# Let's change md:grid-cols-3 to md:grid-cols-4 and add the gauge!
for i, line in enumerate(lines):
    if 'WEALTH INEQUALITY ROW' in line:
        lines[i+1] = lines[i+1].replace('md:grid-cols-3', 'md:grid-cols-4')
        gauge_call = '                  <SystemDistressGauge unemployment={metrics.unemployment} happiness={metrics.happiness} />\n'
        # Insert after <div className="...">
        lines.insert(i+2, gauge_call)
        break

with open('src/App.jsx', 'w', encoding='utf-8') as f:
    f.writelines(lines)
