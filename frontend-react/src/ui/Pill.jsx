export default function Pill({ tone = 'muted', children }) {
  return (
    <span className={`pill ${tone}`}>
      <i />
      {children}
    </span>
  );
}
