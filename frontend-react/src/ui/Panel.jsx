export default function Panel({ hot, className, style, children }) {
  const cls = ['panel', hot && 'hot', className].filter(Boolean).join(' ');
  return (
    <div className={cls} style={style}>
      {children}
    </div>
  );
}
