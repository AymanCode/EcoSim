export const LOG_TYPES = ['All', 'System', 'Market', 'Agent', 'Firm', 'Policy', 'Bank'];
export const SEVERITY_TYPES = ['All', 'Info', 'Warning', 'Error'];

export const normalizeLog = (log = {}, index = 0, indexWithinTick = 0) => {
  const rawType = String(log.rawType || log.type || 'SYS').toUpperCase();
  const message = String(log.message || log.txt || '');
  let type = log.type && ['System', 'Market', 'Agent', 'Firm', 'Policy', 'Bank'].includes(log.type)
    ? log.type
    : (rawType === 'GOV' ? 'Policy' : rawType === 'ECO' ? 'Market' : rawType === 'WARN' ? 'System' : rawType === 'BANK' ? 'Bank' : 'System');
  if (/firm/i.test(message)) type = 'Firm';
  if (/subject|agent|household/i.test(message)) type = 'Agent';
  if (/bank|loan|credit|deposit/i.test(message)) type = 'Bank';

  const entityMatch = message.match(/^([A-Za-z0-9#\s]+?)\s+(?:entered|reported|failed|changed|halted|recovered|posted|issued|completed|initialized)/i)
    || message.match(/^((?:Food|Housing|Services|Healthcare)\s+Firm\s*#?\d*)/i)
    || message.match(/^(Subject-\d+|Agent\s+\d+|Household\s*#?\d*)/i);

  const entity = log.entity || (entityMatch ? entityMatch[1].trim() : (type === 'System' ? 'Simulation Core' : `${type} Core`));

  const isDistressOrError = /error|critical|failed|distress/i.test(message);
  const isWarning = rawType === 'WARN' || /warn|risk|stress/i.test(message);
  const severity = log.severity || (isDistressOrError ? 'Error' : isWarning ? 'Warning' : 'Info');
  const durationMatch = message.match(/(\d+(?:\.\d+)?)\s*ms/i);
  const tick = log.tick ?? 0;
  const withinTick = log.indexWithinTick != null ? log.indexWithinTick : indexWithinTick;
  const id = log.id || `${tick}:${withinTick}`;
  return {
    ...log,
    id,
    indexWithinTick: withinTick,
    index: log.index ?? index,
    tick,
    type,
    rawType,
    entity,
    message,
    severity,
    sev: severity.toLowerCase(),
    duration: durationMatch ? `${durationMatch[1]} ms` : (log.duration || log.change || '-')
  };
};
