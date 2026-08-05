import os

with open('src/App.jsx', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_gov_view = """                  {/* LEFT COLUMN - POLICY STANCE & STATE CAPACITY */}
                  <div className="col-span-3 flex flex-col space-y-4 h-full min-h-0 overflow-y-auto pr-1 no-scrollbar">
                    
                    {/* INTERACTIVE POLICY STANCE */}
                    <div className="tech-panel p-4 tech-corners flex-1 flex flex-col">
                      <div className="flex items-center space-x-2 mb-3 border-b border-slate-700/50 pb-2 shrink-0">
                        <Landmark className="text-violet-400" size={16} />
                        <h3 className="text-xs font-bold uppercase tracking-widest text-slate-300">Policy Overrides</h3>
                      </div>
                      <div className="flex-1 overflow-y-auto no-scrollbar space-y-4 pr-2">
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
                    <div className="tech-panel p-4 tech-corners shrink-0">
                      <div className="flex items-center space-x-2 mb-3 border-b border-slate-700/50 pb-2">
                        <Globe className="text-teal-400" size={16} />
                        <h3 className="text-xs font-bold uppercase tracking-widest text-slate-300">State Capacity</h3>
                      </div>
                      <div className="space-y-2">
                        <div className="flex justify-between items-center bg-slate-900/60 p-2 rounded border border-slate-800 hover:border-slate-600 transition-colors">
                          <span className="text-[10px] text-slate-400 uppercase">Gov Owned Firms</span>
                          <span className="font-mono text-sm text-sky-300">{metrics.govOwnedFirms || 0}</span>
                        </div>
                        <div className="flex justify-between items-center bg-slate-900/60 p-2 rounded border border-slate-800 hover:border-slate-600 transition-colors">
                          <span className="text-[10px] text-slate-400 uppercase">Active Loans</span>
                          <span className="font-mono text-sm text-emerald-300">{formatMillionsAdaptive(metrics.activeLoans || 0)}</span>
                        </div>
                        <div className="flex justify-between items-center bg-slate-900/60 p-2 rounded border border-slate-800 hover:border-slate-600 transition-colors">
                          <span className="text-[10px] text-slate-400 uppercase">Bond Purchases</span>
                          <span className="font-mono text-sm text-amber-300">{formatMillionsAdaptive(metrics.bondPurchases || 0)}</span>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* CENTER COLUMN - VISUAL & SYSTEM LOGS */}
                  <div className="col-span-6 flex flex-col space-y-4 min-h-0 h-full">
                    <div className="tech-panel tech-corners relative min-h-[14rem] overflow-hidden flex flex-col shrink-0">
                      <div className="absolute top-4 left-4 z-10">
                        <div className="text-[10px] uppercase text-slate-500 tracking-widest">Central Authority</div>
                        <div className="text-xl font-display text-white drop-shadow-lg">GOVERNMENT CORE</div>
                      </div>
                      <div className="absolute top-4 right-4 text-right text-[10px] text-slate-500 z-10 flex items-center space-x-2 bg-slate-900/80 px-2 py-1 rounded backdrop-blur border border-slate-700">
                        <div className="h-2 w-2 bg-violet-500 rounded-full animate-pulse shadow-[0_0_8px_#8b5cf6]"></div>
                        <span className="text-violet-200">AI ADVISOR ONLINE</span>
                      </div>
                      
                      {/* 3D Holo */}
                      <div className="absolute inset-0 flex items-center justify-center pointer-events-none px-6">
                        <div className="w-full h-full max-w-full">
                          <NeuralGovernment active activityLevel={metrics.govProfit < 0 ? 'high' : 'normal'} />
                        </div>
                      </div>

                      {/* Overlay Info at bottom */}
                      <div className="absolute bottom-4 left-4 right-4 z-10 flex justify-between items-end">
                        <div className="bg-slate-900/80 p-2 border border-slate-700 rounded backdrop-blur shadow-[0_0_15px_rgba(14,165,233,0.1)]">
                          <div className="text-[9px] text-slate-400 uppercase">Current GDP Output</div>
                          <div className="font-mono text-lg text-white">{formatMillionsAdaptive(metrics.gdp || 0)}</div>
                        </div>
                        <div className="bg-slate-900/80 p-2 border border-slate-700 rounded backdrop-blur text-right shadow-[0_0_15px_rgba(14,165,233,0.1)]">
                          <div className="text-[9px] text-slate-400 uppercase">Avg Subject Happiness</div>
                          <div className="font-mono text-lg text-white">{(metrics.happiness || 0).toFixed(1)} / 100</div>
                        </div>
                      </div>
                    </div>

                    {/* ACTIONS - LIVE REASONING FEED */}
                    <div className="tech-panel p-4 tech-corners flex-1 flex flex-col relative overflow-hidden backdrop-blur-md bg-slate-900/80 border-slate-700/50">
                      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-slate-800/20 via-transparent to-transparent pointer-events-none"></div>
                      <div className="flex justify-between items-center mb-3 border-b border-slate-700/80 pb-2 shrink-0 relative z-10">
                        <div className="flex items-center space-x-2">
                          <Terminal className="text-sky-400" size={16} />
                          <h3 className="text-xs font-bold uppercase tracking-widest text-slate-200 shadow-sm">Live Reasoning Feed</h3>
                        </div>
                        <div className="flex space-x-1">
                          <div className="h-1.5 w-1.5 rounded-full bg-rose-500 animate-ping"></div>
                          <div className="h-1.5 w-1.5 rounded-full bg-amber-500"></div>
                          <div className="h-1.5 w-1.5 rounded-full bg-emerald-500"></div>
                        </div>
                      </div>
                      
                      <div className="flex-1 overflow-y-auto no-scrollbar space-y-2 relative z-10 font-mono">
                        {metrics.policyChanges && metrics.policyChanges.length > 0 ? (
                           metrics.policyChanges.slice(0, 8).map((action, i) => (
                             <div key={i} className={`p-2 rounded border-l-2 bg-gradient-to-r from-slate-800/80 to-transparent ${i === 0 ? 'border-sky-400 opacity-100 shadow-[inset_2px_0_10px_rgba(56,189,248,0.2)]' : 'border-slate-600 opacity-70'}`}>
                               <div className="flex justify-between items-start mb-1">
                                 <span className={`text-[10px] font-bold ${i === 0 ? 'text-sky-300' : 'text-slate-300'}`}>
                                   > {action.type}
                                 </span>
                                 <span className="text-[9px] text-slate-500 bg-slate-900 px-1 rounded">TICK {action.tick}</span>
                               </div>
                               <div className={`text-[10px] ${i === 0 ? 'text-sky-100' : 'text-slate-400'} mt-1 leading-relaxed whitespace-pre-wrap`}>
                                 {action.reason}
                               </div>
                             </div>
                           ))
                        ) : (
                           <div className="text-green-500/50 text-[10px] p-4 text-center h-full flex flex-col items-center justify-center space-y-2">
                              <Terminal size={24} className="opacity-20" />
                              <p>> SYSTEM IDLE. WAITING FOR TRIGGER PROTOCOLS...</p>
                           </div>
                        )}
                      </div>
                    </div>
                  </div>
"""

start_idx = -1
end_idx = -1

for i, line in enumerate(lines):
    if '{/* LEFT COLUMN - POLICY STANCE & STATE CAPACITY */}' in line and start_idx == -1:
        start_idx = i
        break

if start_idx != -1:
    for i in range(start_idx, len(lines)):
        if '{/* RIGHT COLUMN - BUDGET & FISCAL HEALTH */}' in lines[i]:
            end_idx = i
            break

if start_idx != -1 and end_idx != -1:
    lines = lines[:start_idx] + [new_gov_view + "\n"] + lines[end_idx:]
    with open('src/App.jsx', 'w', encoding='utf-8') as f:
        f.writelines(lines)
    print(f'Successfully replaced Government tab code from {start_idx} to {end_idx}')
else:
    print('Could not find bounds for Government tab')
