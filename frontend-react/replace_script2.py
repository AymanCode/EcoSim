import os

with open('src/App.jsx', 'r', encoding='utf-8') as f:
    lines = f.readlines()

def replace_lines(start_str, end_str, new_content_list, offset_start=0):
    start_idx = -1
    end_idx = -1
    for i, line in enumerate(lines):
        if start_str in line and start_idx == -1:
            start_idx = i
            break
            
    if start_idx != -1:
        for i in range(start_idx, len(lines)):
            if end_str in lines[i]:
                end_idx = i
                break
                
    if start_idx != -1 and end_idx != -1:
        return lines[:start_idx + offset_start] + new_content_list + lines[end_idx+1:]
    return lines

# Replace gradients
start_grad = '<stop offset="5%"'
end_grad = '<stop offset="95%"'
new_grads = [
    '                  <stop offset="0%" stopColor={colors[dIdx % colors.length]} stopOpacity={0.6} />\n',
    '                  <stop offset="50%" stopColor={colors[dIdx % colors.length]} stopOpacity={0.1} />\n',
    '                  <stop offset="100%" stopColor={colors[dIdx % colors.length]} stopOpacity={0} />\n'
]
lines = replace_lines(start_grad, end_grad, new_grads)

# Replace Tooltip
start_tooltip = '<Tooltip'
end_tooltip = '/>'
new_tooltip = [
    '            <Tooltip\n',
    '              content={({ active, payload }) => {\n',
    '                if (active && payload && payload.length) {\n',
    '                  return (\n',
    '                    <div className="bg-slate-900/90 backdrop-blur-md border border-slate-600/50 rounded shadow-[0_0_15px_rgba(14,165,233,0.3)] px-3 py-1.5 flex flex-col items-center z-50">\n',
    '                      <span className="font-bold flex items-center text-[11px] font-mono text-sky-300 drop-shadow-md">\n',
    '                        {formatValue(payload[0].value)}{suffix}\n',
    '                      </span>\n',
    '                    </div>\n',
    '                  );\n',
    '                }\n',
    '                return null;\n',
    '              }}\n',
    '              cursor={{ stroke: \'rgba(56, 189, 248, 0.5)\', strokeWidth: 1, strokeDasharray: \'4 4\' }}\n',
    '              isAnimationActive={false}\n',
    '            />\n'
]

# Be careful, there might be multiple tooltips? I only want the one in LineChart, but if there are multiple it's okay to replace all or just the first.
# Wait, let's only replace the first one after LineChart signature.

start_idx = -1
end_idx = -1
for i, line in enumerate(lines):
    if 'const LineChart =' in line and start_idx == -1:
        for j in range(i, len(lines)):
            if '<Tooltip' in lines[j] and start_idx == -1:
                start_idx = j
            if start_idx != -1 and '/>' in lines[j] and 'isAnimationActive={false}' in lines[j-1]:
                end_idx = j
                break
        break

if start_idx != -1 and end_idx != -1:
    lines = lines[:start_idx] + new_tooltip + lines[end_idx+1:]
    print('Replaced tooltip in LineChart')

with open('src/App.jsx', 'w', encoding='utf-8') as f:
    f.writelines(lines)
