/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: { extend: {
    colors: { page:'var(--page)', panel:'var(--panel)', panel2:'var(--panel2)', panel3:'var(--panel3)', ink:'var(--ink)', ink2:'var(--ink2)', ink3:'var(--ink3)', ink4:'var(--ink4)', acc:'var(--acc)', good:'var(--good)', warn:'var(--warn)', crit:'var(--crit)', ai:'var(--ai)', s1:'var(--s1)', s2:'var(--s2)', s3:'var(--s3)', s4:'var(--s4)' },
    borderColor: { line:'var(--line)', line2:'var(--line2)' },
    fontFamily: { sans:['Barlow','system-ui','sans-serif'], num:['"Barlow Semi Condensed"','Barlow','sans-serif'], mono:['"JetBrains Mono"','ui-monospace','monospace'] },
  } },
  plugins: [],
}
