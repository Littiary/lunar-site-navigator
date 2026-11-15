import { useState } from "react";
import { LINKS, type Link } from "../site/links";
import { Brand } from "./Mark";

export type Page = "home" | "compare";

const ITEMS: { link: Link; label: string; page?: Page }[] = [
  { link: LINKS.compare, label: "Compare", page: "compare" },
  { link: LINKS.learn, label: LINKS.learn.label },
  { link: LINKS.accuracy, label: LINKS.accuracy.label },
  { link: LINKS.evidence, label: LINKS.evidence.label },
];

/** Sticky top bar; on narrow screens the links fold into a menu button. */
export function Nav({ page }: { page: Page }) {
  const [open, setOpen] = useState(false);
  return (
    <header className="nav">
      <div className="nav-in">
        <Brand />
        <button type="button" className="nav-toggle" aria-expanded={open} aria-controls="nav-links" onClick={() => setOpen(!open)}>
          <span className="sr">Menu</span>
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h16M4 12h16M4 17h16" stroke="currentColor" strokeWidth="2" strokeLinecap="round" /></svg>
        </button>
        <nav id="nav-links" className={open ? "open" : ""} aria-label="Site">
          {ITEMS.map(({ link, label, page: target }) => (
            <a key={link.href} href={link.href} aria-current={target === page ? "page" : undefined}>{label}</a>
          ))}
          <a className="nav-gh" href={LINKS.github.href}>GitHub</a>
        </nav>
      </div>
    </header>
  );
}
