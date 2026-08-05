import os

with open('src/App.jsx', 'r', encoding='utf-8') as f:
    lines = f.readlines()

start_idx = -1
end_idx = -1

for i, line in enumerate(lines):
    if 'className="flex justify-between items-start mb-1"' in line and start_idx == -1:
        start_idx = i
        break

if start_idx != -1:
    for i in range(start_idx, len(lines)):
        if ');' in lines[i].strip():
            end_idx = i
            break

if start_idx != -1 and end_idx != -1:
    new_lines = [
        '      <div className="flex justify-between items-start mb-1 relative z-10">\n',
        '        <span className="text-[11px] uppercase tracking-wider text-slate-400 font-display pr-2 leading-tight group-hover:text-slate-300 transition-colors">{label}</span>\n',
        '        {trend !== undefined && trend !== null && (\n',
        '          <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded shrink-0 whitespace-nowrap transition-colors duration-500 ease-in-out ${trend > 0 ? \'bg-emerald-500/10 text-emerald-400\' : \'bg-rose-500/10 text-rose-400\'}`}>\n',
        '            {trend > 0 ? \'▲\' : \'▼\'} {Math.abs(trend)}%\n',
        '          </span>\n',
        '        )}\n',
        '      </div>\n',
        '      <div className="flex items-baseline space-x-1 overflow-hidden mt-1 relative z-10">\n',
        '        <span className="text-xl md:text-2xl font-display font-bold text-slate-100 group-hover:text-white transition-colors truncate">\n',
        '          {value}\n',
        '        </span>\n',
        '        <span className="text-[10px] text-slate-500 font-mono shrink-0 group-hover:text-slate-400">{suffix}</span>\n',
        '      </div>\n',
        '      <div className="w-full h-[2px] bg-slate-800/80 mt-2 relative overflow-hidden shrink-0 rounded-full z-10">\n',
        '        <div className={`absolute top-0 left-0 h-full w-1/3 animate-[pulse_2s_ease-in-out_infinite] ${trend && trend < 0 ? \'bg-rose-500\' : \'bg-sky-500\'}`}></div>\n',
        '      </div>\n',
        '    </div>\n',
        '  );\n',
        '};\n'
    ]
    
    result = lines[:start_idx] + new_lines + lines[end_idx+1:]
    with open('src/App.jsx', 'w', encoding='utf-8') as f:
        f.writelines(result)
    print(f'Replaced lines {start_idx} to {end_idx}')
else:
    print(f'Failed to find bounds: {start_idx}, {end_idx}')
