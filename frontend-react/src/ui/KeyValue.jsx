const TONE = {
  good: 'var(--good)',
  warn: 'var(--warn)',
  crit: 'var(--crit)',
  ai: 'var(--ai)',
  acc: 'var(--acc)',
  muted: 'var(--ink3)',
};

export default function KeyValue({ label, value, tone }) {
  return (
    <div className="row">
      <span className="k">{label}</span>
      <span className="n" style={{ color: TONE[tone] || 'var(--ink)' }}>{value}</span>
    </div>
  );
}
