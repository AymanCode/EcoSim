import os

with open('src/App.jsx', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_center_col = """                    {/* CENTER COLUMN - VISUALIZER */}
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
                          .map(([need, value], i) => (
                            <div key={i} className="bg-slate-900/80 border border-slate-600 rounded-lg rounded-tr-none p-2 shadow-xl backdrop-blur animate-bounce" style={{ animationDuration: '3s' }}>
                              <div className="text-[9px] text-slate-400 uppercase mb-1">Primary Need</div>
                              <div className="text-xs font-bold text-rose-400 font-mono flex items-center gap-1">
                                ! LACKING {need.toUpperCase()}
                              </div>
                            </div>
                          ))}
                      </div>
                    </div>
"""

start_idx = -1
end_idx = -1

for i, line in enumerate(lines):
    if '{/* CENTER COLUMN - VISUALIZER */}' in line and start_idx == -1:
        start_idx = i
        break

if start_idx != -1:
    for i in range(start_idx, len(lines)):
        if '{/* RIGHT COLUMN - FINANCIALS & NEEDS */}' in lines[i]:
            end_idx = i
            break

if start_idx != -1 and end_idx != -1:
    lines = lines[:start_idx] + [new_center_col + "\n"] + lines[end_idx:]
    with open('src/App.jsx', 'w', encoding='utf-8') as f:
        f.writelines(lines)
    print(f'Successfully replaced Subject Center Col from {start_idx} to {end_idx}')
else:
    print('Could not find bounds for Subject Center Col')
