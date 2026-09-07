export default function SectionTitle({ title, meta, right }) {
  return (
    <div className="ttl">
      <h4>{title}</h4>
      {right != null ? right : meta != null ? <small>{meta}</small> : null}
    </div>
  );
}
