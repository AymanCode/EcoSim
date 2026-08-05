import os
import re

with open('src/App.jsx', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Subjects Tab - Wealth (around line 1468)
wealth_old = """                      <div className="tech-panel p-2 tech-corners flex-1 flex flex-col min-h-0">
                        <h4 className="text-[9px] font-bold text-sky-400 uppercase tracking-widest mb-1 shrink-0">Wealth</h4>
                        {metrics.trackedSubjects[activeSubjectIndex].history && metrics.trackedSubjects[activeSubjectIndex].history.cash.length > 1 ? (
                          <div className="flex-1 min-h-0 relative">
                            <div className="absolute inset-0">
                              <LineChart
                                title=""
                                data={metrics.trackedSubjects[activeSubjectIndex].history.cash}
                                color="#10b981"
                                minScale={0}
                                suffix=""
                                formatValue={v => `${v.toFixed(0)}`}
                              />
                            </div>
                          </div>
                        ) : <div className="text-[9px] text-slate-600 italic">No history</div>}
                      </div>"""
wealth_new = """                      <div className="flex-1 flex flex-col min-h-0">
                        <LineChart
                          title="Wealth"
                          data={metrics.trackedSubjects[activeSubjectIndex].history?.cash || []}
                          color="#10b981"
                          minScale={0}
                          suffix=""
                          formatValue={v => `${v.toFixed(0)}`}
                        />
                      </div>"""

# 2. Subjects Tab - Wage
wage_old = """                      <div className="tech-panel p-2 tech-corners flex-1 flex flex-col min-h-0">
                        <h4 className="text-[9px] font-bold text-amber-400 uppercase tracking-widest mb-1 shrink-0">Wage</h4>
                        {metrics.trackedSubjects[activeSubjectIndex].history && metrics.trackedSubjects[activeSubjectIndex].history.wage.length > 1 ? (
                          <div className="flex-1 min-h-0 relative">
                            <div className="absolute inset-0">
                              <LineChart
                                title=""
                                data={metrics.trackedSubjects[activeSubjectIndex].history.wage}
                                color="#f59e0b"
                                minScale={0}
                                suffix=""
                                formatValue={v => `${v.toFixed(0)}`}
                              />
                            </div>
                          </div>
                        ) : <div className="text-[9px] text-slate-600 italic">No history</div>}
                      </div>"""
wage_new = """                      <div className="flex-1 flex flex-col min-h-0">
                        <LineChart
                          title="Wage"
                          data={metrics.trackedSubjects[activeSubjectIndex].history?.wage || []}
                          color="#f59e0b"
                          minScale={0}
                          suffix=""
                          formatValue={v => `${v.toFixed(0)}`}
                        />
                      </div>"""

# 3. Firms Tab - Cash History
cash_old = """                            <div className="tech-panel p-3 tech-corners flex flex-col flex-1 min-h-[170px]">
                              <div className="text-[10px] font-bold tracking-widest uppercase text-slate-400 mb-2">Cash History</div>
                              {selectedTrackedFirm.history?.cash && selectedTrackedFirm.history.cash.length > 1 ? (
                                <div className="flex-1">
                                  <LineChart
                                    title=""
                                    data={selectedTrackedFirm.history.cash}
                                    color="#0ea5e9"
                                    minScale={0}
                                    suffix=""
                                    formatValue={v => `$${v.toFixed(0)}`}
                                  />
                                </div>
                              ) : <div className="text-[10px] text-slate-600">More ticks needed for cash history.</div>}
                            </div>"""
cash_new = """                            <div className="flex flex-col flex-1 min-h-[170px]">
                              <LineChart
                                title="Cash History"
                                data={selectedTrackedFirm.history?.cash || []}
                                color="#0ea5e9"
                                minScale={0}
                                suffix=""
                                formatValue={v => `$${v.toFixed(0)}`}
                              />
                            </div>"""

# 4. Firms Tab - Profit History
profit_old = """                            <div className="tech-panel p-3 tech-corners flex flex-col flex-1 min-h-[170px]">
                              <div className="text-[10px] font-bold tracking-widest uppercase text-slate-400 mb-2">Profit History</div>
                              {selectedTrackedFirm.history?.profit && selectedTrackedFirm.history.profit.length > 1 ? (
                                <div className="flex-1">
                                  <LineChart
                                    title=""
                                    data={selectedTrackedFirm.history.profit}
                                    color="#f87171"
                                    minScale={-1}
                                    suffix=""
                                    formatValue={v => `$${v.toFixed(0)}`}
                                  />
                                </div>
                              ) : <div className="text-[10px] text-slate-600">More ticks needed for profit history.</div>}
                            </div>"""
profit_new = """                            <div className="flex flex-col flex-1 min-h-[170px]">
                              <LineChart
                                title="Profit History"
                                data={selectedTrackedFirm.history?.profit || []}
                                color="#f87171"
                                minScale={-1}
                                suffix=""
                                formatValue={v => `$${v.toFixed(0)}`}
                              />
                            </div>"""

# 5. Government Tab - National Debt Map
debt_old = """                    {/* NATIONAL DEBT MAP */}
                    <div className="tech-panel p-3 tech-corners flex-1 flex flex-col min-h-[160px]">
                      <div className="text-[10px] font-bold tracking-widest uppercase text-slate-400 mb-2 shrink-0">National Debt History</div>
                       {metrics.govDebtHistory && metrics.govDebtHistory.length > 1 ? (
                          <div className="flex-1 relative">
                             <div className="absolute inset-0">
                               <LineChart
                                 title=""
                                 data={metrics.govDebtHistory}
                                 color="#f43f5e"
                                 minScale={0}
                                 suffix=""
                                 formatValue={v => formatMillionsAdaptive(v)}
                               />
                             </div>
                          </div>
                       ) : (
                          <div className="text-[10px] text-slate-600 flex-1 flex items-center justify-center italic">Awaiting history...</div>
                       )}
                    </div>"""
debt_new = """                    {/* NATIONAL DEBT MAP */}
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

# Normalize all strings to standard newlines
def norm(s):
    # Match multiple spaces so we don't fail on indent differences
    return re.sub(r'\s+', ' ', s.replace('\\r\\n', '\\n').strip())

def replace_fuzzy(target, new_text, content):
    norm_content = re.sub(r'\s+', ' ', content)
    norm_target = norm(target)
    
    # Just do a brute-force approach or we can use regex
    # Better to find by lines
    return content

# I will write a simple regex replacement to be safe from minor indentation differences
import re

def smart_replace(pattern_string, replacement, text):
    # Escape special regex chars but allow arbitrary whitespace
    escaped = re.escape(pattern_string)
    # Replace escaped whitespace with \s+
    escaped = re.sub(r'\\\s+', r'\\s+', escaped)
    return re.sub(escaped, replacement, text)

new_content = smart_replace(wealth_old, wealth_new, content)
new_content = smart_replace(wage_old, wage_new, new_content)
new_content = smart_replace(cash_old, cash_new, new_content)
new_content = smart_replace(profit_old, profit_new, new_content)
new_content = smart_replace(debt_old, debt_new, new_content)

with open('src/App.jsx', 'w', encoding='utf-8') as f:
    f.write(new_content)

print("Finished nested panel replacements")
