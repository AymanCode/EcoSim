// Pure display formatters shared by the dashboard and the Government Console.

const signedPrefix = (num) => (num < 0 ? '-' : '');
export const formatInteger = (value) => Number(value || 0).toLocaleString(undefined, { maximumFractionDigits: 0 });
export const formatDecimal = (value, decimals = 1) => Number(value || 0).toLocaleString(undefined, {
  minimumFractionDigits: decimals,
  maximumFractionDigits: decimals
});
export const formatPercent = (value, decimals = 1) => `${formatDecimal(value, decimals)}%`;
export const formatTick = (value) => formatInteger(value).padStart(5, '0');
export const formatCurrency = (value, decimals = 0) => {
  const num = Number(value || 0);
  return `${signedPrefix(num)}$${Math.abs(num).toLocaleString(undefined, {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals
  })}`;
};
export const formatCompactCurrency = (value) => {
  const num = Number(value || 0);
  const abs = Math.abs(num);
  if (abs >= 1_000_000_000_000) return `${signedPrefix(num)}$${(abs / 1_000_000_000_000).toFixed(2)}T`;
  if (abs >= 1_000_000_000) return `${signedPrefix(num)}$${(abs / 1_000_000_000).toFixed(2)}B`;
  if (abs >= 1_000_000) return `${signedPrefix(num)}$${(abs / 1_000_000).toFixed(2)}M`;
  if (abs >= 1_000) return `${signedPrefix(num)}$${(abs / 1_000).toFixed(1)}K`;
  return `${signedPrefix(num)}$${abs.toFixed(0)}`;
};
export const formatMillionsAdaptive = (valueInMillions) => formatCompactCurrency(Number(valueInMillions || 0) * 1_000_000);
export const signedMillions = (v) => `${Number(v) > 0 ? '+' : ''}${formatMillionsAdaptive(v)}`;

export const formatPolicyName = (value) => {
  const raw = String(value || 'Policy');
  const known = {
    bailout_budget: 'Bailout budget',
    bailout_target: 'Bailout target',
    bailout_policy: 'Bailout policy',
    rent_stabilization_level: 'Rent stabilization',
    price_stabilization_level: 'Price stabilization',
    price_stabilization_target: 'Price target',
    wageTax: 'Wage tax',
    profitTax: 'Corporate profit tax',
    minimumWage: 'Minimum wage floor',
    unemploymentBenefitRate: 'Unemployment benefits',
    enableLlmGovernment: 'Policy assistant'
  };
  if (known[raw]) return known[raw];
  return raw.replace(/_/g, ' ').replace(/([a-z])([A-Z])/g, '$1 $2').replace(/\b\w/g, c => c.toUpperCase());
};
export const formatPolicyValue = (key, value) => {
  const normalized = String(key || '').toLowerCase();
  if (normalized.includes('budget') || normalized.includes('wage') || normalized.includes('tax') || normalized.includes('benefit')) {
    if (normalized.includes('tax') || normalized.includes('benefit')) return typeof value === 'number' && Math.abs(value) <= 1 ? formatPercent(value * 100, 1) : String(value);
    return formatCurrency(value);
  }
  if (value === 'off' || value === 'none' || value === false) return normalized.includes('target') ? 'None' : 'Off';
  if (value === true) return 'On';
  return String(value || 'None').replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
};
export const formatPolicyMessage = (action) => {
  const key = action?.policy || action?.type || action?.key || action?.lever || 'policy';
  const value = action?.value ?? action?.new_value ?? action?.level ?? action?.target;
  if (value !== undefined && value !== null) return `${formatPolicyName(key)} set to ${formatPolicyValue(key, value)}`;
  return action?.reason || formatPolicyName(key);
};

export const compactMoney = (v) => formatCompactCurrency(v);
export const signedMoney = (v) => `${Number(v) >= 0 ? '+' : ''}${formatCompactCurrency(v)}`;
export const pct1 = (v) => formatPercent(v, 1);
export const dec1 = (v) => formatDecimal(v, 1);
export const dec3 = (v) => formatDecimal(v, 3);
export const ms = (v) => `${Math.round(Number(v) || 0)} ms`;
export const score = (v) => `${Math.round(Number(v) || 0)}`;
export const usd2 = (v) => formatCurrency(v, 2);

export const readableName = (name) => {
  const raw = String(name || '');
  const sectorOf = (value) => {
    const sector = String(value || 'Unknown');
    return sector.charAt(0).toUpperCase() + sector.slice(1).replace(/_/g, ' ');
  };
  const productMatch = raw.match(/^([A-Za-z]+)Product(\d+)$/);
  if (productMatch) return `${sectorOf(productMatch[1])} Firm #${productMatch[2]}`;
  const coMatch = raw.match(/^([A-Za-z]+)Co(\d+)$/);
  if (coMatch) return `${sectorOf(coMatch[1])} Firm #${coMatch[2]}`;
  const subjectMatch = raw.match(/^Subject-(\d+)$/i);
  if (subjectMatch) return `Agent ${subjectMatch[1]}`;
  const baselineMatch = raw.match(/^Baseline([A-Za-z]+)$/);
  if (baselineMatch) return `Baseline ${sectorOf(baselineMatch[1])}`;
  const spaced = raw.replace(/([a-z])([A-Z])/g, '$1 $2').replace(/(\D)(\d+)$/g, '$1 $2');
  if (spaced !== raw) return spaced.trim();
  return raw || 'Unknown';
};

export const FORMATTERS = { money: compactMoney, moneyS: signedMoney, usd2, pct1, int: formatInteger, dec1, dec3, ms, score };
