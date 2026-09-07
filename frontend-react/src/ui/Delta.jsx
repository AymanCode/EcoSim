export default function Delta({ diff, pct, unit, upBad = false, vsTick }) {
  const arrow = diff > 0 ? '▲' : diff < 0 ? '▼' : '—';
  const text =
    unit === 'pct'
      ? `${Math.abs(pct).toFixed(1)}%`
      : unit === 'pts'
        ? `${Math.abs(diff).toFixed(1)} pts`
        : `${Math.abs(Math.round(diff))}`;
  const direction = diff === 0 ? '' : (diff > 0) !== upBad ? 'up' : 'down';

  return (
    <span
      className={`delta ${direction}`.trim()}
      title={vsTick !== undefined ? `vs tick ${vsTick}` : undefined}
    >
      {arrow} {text}
    </span>
  );
}
