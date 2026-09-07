// Supply-and-demand mark from the design prototype's LOGOS[1]: an axis, a
// demand curve, a supply curve, and their equilibrium point.
export default function Logo() {
  return (
    <svg viewBox="0 0 32 32" fill="none" aria-hidden="true">
      <path d="M6 5v21h21" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" opacity="0.42" />
      <path d="M8 8C14 10 18 14 26 23" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" />
      <path d="M8 24C14 20 18 15 26 9" stroke="var(--acc)" strokeWidth="2.4" strokeLinecap="round" />
      <circle cx="17.2" cy="15.6" r="3.1" fill="var(--acc)" stroke="var(--panel)" strokeWidth="1.6" />
    </svg>
  );
}
