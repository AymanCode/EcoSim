import os

with open('src/App.jsx', 'r', encoding='utf-8') as f:
    lines = f.readlines()

old_table_row_start = '<tr key={row.id} className="border-t border-slate-800/60">'
new_table_row_start = '<tr key={row.id} className={`border-t ${row.cash < 1000 || row.lastProfit < 0 ? "border-rose-900/50 bg-rose-500/5" : "border-slate-800/60 hover:bg-slate-800/30"} transition-colors`}>\n'

for i, line in enumerate(lines):
    if old_table_row_start in line:
        lines[i] = line.replace(old_table_row_start, new_table_row_start)
        break

new_heatmap = """                          <div className="absolute inset-0 p-4 pt-16 flex flex-col z-0">
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
"""

start_idx = -1
end_idx = -1
for i, line in enumerate(lines):
    if 'hologram-container pointer-events-none px-6' in line:
        start_idx = i
        break

if start_idx != -1:
    for i in range(start_idx, len(lines)):
        if '/>' in lines[i] and 'NeuralBuilding' in lines[i-1] or 'NeuralBuilding' in lines[i-2] or 'NeuralBuilding' in lines[i-3] or 'NeuralBuilding' in lines[i-4]:
             # We know NeuralBuilding is a self closing tag. Let's look for </NeuralBuilding> or />
            pass
        if '</div>' in lines[i]:
            # Let's count divs from start_idx
            # Wait, easier to just hardcode end_idx based on the known offset!
            end_idx = start_idx + 8
            break

if start_idx != -1:
    lines = lines[:start_idx] + [new_heatmap] + lines[end_idx+1:]
    with open('src/App.jsx', 'w', encoding='utf-8') as f:
        f.writelines(lines)
    print(f'Successfully updated Firms tab table and heatmap from line {start_idx} to {end_idx}')
else:
    print('Could not find bounds for NeuralBuilding')
