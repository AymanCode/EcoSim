import { useEffect, useRef, useState } from 'react';

export const series = (h) => (Array.isArray(h) ? h : []);
export const latest = (h, fallback = 0) => { const s = series(h); return s.length ? Number(s[s.length - 1].value) : fallback; };
export const backN = (h, n) => { const s = series(h); return s.length ? Number(s[Math.max(0, s.length - 1 - n)].value) : 0; };
export const deltaVs = (current, h, n = 1) => { const base = backN(h, n); const diff = Number(current) - base; return { diff, pct: base ? (diff / Math.abs(base)) * 100 : 0 }; };
export const stress = (m) => Math.min(100, Math.max(0, (m.unemployment || 0) * 0.45 + (100 - (m.happiness || 0)) * 0.4 + (m.firmDistressPressure || 0) * 0.15));
export const employment = (m) => 100 - (m.unemployment || 0);
export const appendCurrent = (h, tick, value) => { const s = series(h); if (!s.length || Number(s[s.length - 1].tick) < Number(tick)) return [...s, { tick, value }]; return s; };

export const useTickHistory = (tick, values, max = 250) => {
  const [history, setHistory] = useState(() => {
    if (tick != null && values) {
      const init = {};
      for (const [k, v] of Object.entries(values)) {
        init[k] = [{ tick, value: v }];
      }
      return init;
    }
    return {};
  });

  const valuesRef = useRef(values);
  const lastTickRef = useRef(tick ?? null);

  useEffect(() => {
    valuesRef.current = values;
  }, [values]);

  useEffect(() => {
    if (tick != null && (lastTickRef.current == null || tick > lastTickRef.current)) {
      lastTickRef.current = tick;
      const currentValues = valuesRef.current || {};
      setHistory((prev) => {
        const next = { ...prev };
        for (const [k, v] of Object.entries(currentValues)) {
          const arr = next[k] ? [...next[k]] : [];
          arr.push({ tick, value: v });
          next[k] = arr.length > max ? arr.slice(-max) : arr;
        }
        return next;
      });
    }
  }, [tick, max]);

  return history;
};

