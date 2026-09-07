export default function PageHeader({ eyebrow, title, summary, action }) {
  return (
    <div className="ph">
      <div>
        <div className="eyebrow">{eyebrow}</div>
        <h3>{title}</h3>
        {summary && <p className="sum">{summary}</p>}
      </div>
      {action}
    </div>
  );
}
