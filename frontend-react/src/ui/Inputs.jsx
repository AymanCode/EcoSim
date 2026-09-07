export const Slider = ({ label, value, min, max, step, format = v => v, onChange, description }) => {
  const range = Number(max) - Number(min);
  const pct = range ? ((Number(value) - Number(min)) / range) * 100 : 0;

  return (
    <div className="field">
      <div className="fh">
        <label>{label}</label>
        <span className="val">{format(value)}</span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        style={{ '--p': `${pct}%` }}
        onChange={e => onChange(parseFloat(e.target.value))}
      />
      {description && <div className="desc">{description}</div>}
    </div>
  );
};

export const Select = ({ label, value, options, onChange, description }) => (
  <div className="field">
    <div className="fh">
      <label>{label}</label>
    </div>
    <select className="select" value={value} onChange={e => onChange(e.target.value)}>
      {options.map(option => (
        <option key={option.value} value={option.value}>{option.label}</option>
      ))}
    </select>
    {description && <div className="desc">{description}</div>}
  </div>
);

export const Toggle = ({ label, description, checked, onChange }) => (
  <button
    type="button"
    className={`toggle${checked ? ' on' : ''}`}
    onClick={() => onChange(!checked)}
  >
    <div>
      <div className="tl">{label}</div>
      {description && <div className="td">{description}</div>}
    </div>
    <span className="sw" />
  </button>
);

export const NumberInput = ({ label, value, min = 0, max = Number.MAX_SAFE_INTEGER, step = 1, onChange, description }) => (
  <div className="field">
    <div className="fh">
      <label>{label}</label>
    </div>
    <input
      type="number"
      aria-label={label}
      min={min}
      max={max}
      step={step}
      value={value}
      onChange={e => {
        const parsed = Number(e.target.value);
        if (!Number.isFinite(parsed)) return;
        const bounded = Math.max(Number(min), Math.min(Number(max), Math.trunc(parsed)));
        onChange(bounded);
      }}
    />
    {description && <div className="desc">{description}</div>}
  </div>
);

export const Search = ({ value, onChange, placeholder }) => (
  <input
    type="text"
    className="search"
    value={value}
    onChange={e => onChange(e.target.value)}
    placeholder={placeholder}
  />
);
