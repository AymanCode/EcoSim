import { pct1, formatPolicyMessage } from '../format.js';

export default function StatusStrip({
  sessionId,
  metrics = {},
  firmStats,
  tick: _tick,
  population,
  config = {},
  policyChanges = []
}) {
  const change = policyChanges?.[0];

  return (
    <div className="strip">
      <span>session <b>{String(sessionId || '').slice(0, 8)}</b></span>
      <span className="sep" />
      <span>compute <b>{Math.round(metrics.tickComputeMs || 0)} ms</b>/tick</span>
      <span className="sep" />
      <span>households <b>{population}</b></span>
      <span className="sep" />
      <span>firms <b>{firmStats?.total_firms ?? '—'}</b></span>
      <span className="sep" />
      <span>unemployment <b>{pct1(metrics.unemployment)}</b></span>
      <span className="sep" />
      <span>policy <b>{config.enableLlmGovernment ? 'manual + assistant' : 'manual'}</b></span>
      <span style={{ marginLeft: 'auto' }}>
        {change
          ? (<>last change <b>t{policyChanges[0].tick}</b> · {formatPolicyMessage(change)}</>)
          : 'no policy changes yet'}
      </span>
    </div>
  );
}
