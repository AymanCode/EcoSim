import os

with open('src/App.jsx', 'r', encoding='utf-8') as f:
    lines = f.readlines()

def replace_block(lines, start_sig, end_sig, new_content):
    start_idx = -1
    for i, line in enumerate(lines):
        if start_sig in line:
            start_idx = i
            break
            
    if start_idx != -1:
        end_idx = -1
        for i in range(start_idx, len(lines)):
            if end_sig in lines[i]:
                end_idx = i
                break
        
        if end_idx != -1:
            return lines[:start_idx] + [new_content + "\\n"] + lines[end_idx+1:]
    return lines

# 1. Subjects Tab - Wealth
start1 = '<h4 className="text-[9px] font-bold text-sky-400 uppercase tracking-widest mb-1 shrink-0">Wealth</h4>'
new1 = """                        <div className="flex-1 flex flex-col min-h-0">
                          <LineChart
                            title="Wealth"
                            data={metrics.trackedSubjects[activeSubjectIndex].history?.cash || []}
                            color="#10b981"
                            minScale={0}
                            suffix=""
                            formatValue={v => `${v.toFixed(0)}`}
                          />
                        </div>"""
lines = replace_block(lines, start1, ') : <div className="text-[9px] text-slate-600 italic">No history</div>}', new1)
# remove the wrapper start
for i, l in enumerate(lines):
    if new1 in l:
        if '<div className="tech-panel p-2 tech-corners flex-1 flex flex-col min-h-0">' in lines[i-1]:
            lines.pop(i-1)
        break

# 2. Subjects Tab - Wage
start2 = '<h4 className="text-[9px] font-bold text-amber-400 uppercase tracking-widest mb-1 shrink-0">Wage</h4>'
new2 = """                        <div className="flex-1 flex flex-col min-h-0">
                          <LineChart
                            title="Wage"
                            data={metrics.trackedSubjects[activeSubjectIndex].history?.wage || []}
                            color="#f59e0b"
                            minScale={0}
                            suffix=""
                            formatValue={v => `${v.toFixed(0)}`}
                          />
                        </div>"""
lines = replace_block(lines, start2, ') : <div className="text-[9px] text-slate-600 italic">No history</div>}', new2)
for i, l in enumerate(lines):
    if new2 in l:
        if '<div className="tech-panel p-2 tech-corners flex-1 flex flex-col min-h-0">' in lines[i-1]:
            lines.pop(i-1)
        break

# 3. Firms Tab - Cash History
start3 = '<div className="text-[10px] font-bold tracking-widest uppercase text-slate-400 mb-2">Cash History</div>'
new3 = """                            <div className="flex flex-col flex-1 min-h-[170px]">
                              <LineChart
                                title="Cash History"
                                data={selectedTrackedFirm.history?.cash || []}
                                color="#0ea5e9"
                                minScale={0}
                                suffix=""
                                formatValue={v => `$${v.toFixed(0)}`}
                              />
                            </div>"""
lines = replace_block(lines, start3, ') : <div className="text-[10px] text-slate-600">More ticks needed for cash history.</div>}', new3)
for i, l in enumerate(lines):
    if new3 in l:
        if '<div className="tech-panel p-3 tech-corners flex flex-col flex-1 min-h-[170px]">' in lines[i-1]:
            lines.pop(i-1)
        break

# 4. Firms Tab - Profit History
start4 = '<div className="text-[10px] font-bold tracking-widest uppercase text-slate-400 mb-2">Profit History</div>'
new4 = """                            <div className="flex flex-col flex-1 min-h-[170px]">
                              <LineChart
                                title="Profit History"
                                data={selectedTrackedFirm.history?.profit || []}
                                color="#f87171"
                                minScale={-1}
                                suffix=""
                                formatValue={v => `$${v.toFixed(0)}`}
                              />
                            </div>"""
lines = replace_block(lines, start4, ') : <div className="text-[10px] text-slate-600">More ticks needed for profit history.</div>}', new4)
for i, l in enumerate(lines):
    if new4 in l:
        if '<div className="tech-panel p-3 tech-corners flex flex-col flex-1 min-h-[170px]">' in lines[i-1]:
            lines.pop(i-1)
        break

# 5. Government Tab - National Debt History
start5 = '<div className="text-[10px] font-bold tracking-widest uppercase text-slate-400 mb-2 shrink-0">National Debt History</div>'
new5 = """                    {/* NATIONAL DEBT MAP */}
                    <div className="flex-1 flex flex-col min-h-[160px]">
                      <LineChart
                        title="National Debt History"
                        data={metrics.govDebtHistory || []}
                        color="#f43f5e"
                        minScale={0}
                        suffix=""
                        formatValue={v => formatMillionsAdaptive(v)}
                      />
                    </div>"""
lines = replace_block(lines, start5, ')}', new5)
for i, l in enumerate(lines):
    if new5 in l:
        if '{/* NATIONAL DEBT MAP */}' in lines[i-2]:
            lines.pop(i-2)
            lines.pop(i-2)
        break

with open('src/App.jsx', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("Finished nested panel replacements safely")
