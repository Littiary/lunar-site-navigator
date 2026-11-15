/** The logo: a low Sun over a horizon line, the subject of the tool. */
export function Mark() {
  return (
    <svg className="mark" viewBox="0 0 32 32" aria-hidden="true">
      <circle cx="21" cy="12" r="5" fill="#ffd966" />
      <path d="M2 23 L9 19 L13 21 L19 16 L24 19 L30 17 L30 30 L2 30 Z" fill="#232833" stroke="#9ccbf5" strokeWidth="1.4" strokeLinejoin="round" />
    </svg>
  );
}

export function Brand() {
  return (
    <a className="brand" href={import.meta.env.BASE_URL} aria-label="Lunar Site Navigator, home">
      <Mark />
      <span>Lunar Site Navigator</span>
    </a>
  );
}
