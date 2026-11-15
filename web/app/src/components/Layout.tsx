import { useEffect, useState, type ReactNode } from "react";
import { at, GITHUB, loadNotice, SLIDES } from "../lib";

type Page = "home" | "compare";

export function Mark() {
  // A low Sun over a horizon line: the subject of the tool.
  return (
    <svg className="mark" viewBox="0 0 32 32" aria-hidden="true">
      <circle cx="21" cy="12" r="5" fill="#ffd966" />
      <path d="M2 23 L9 19 L13 21 L19 16 L24 19 L30 17 L30 30 L2 30 Z" fill="#232833" stroke="#9ccbf5" strokeWidth="1.4" strokeLinejoin="round" />
    </svg>
  );
}

export function Nav({ page }: { page: Page }) {
  const [open, setOpen] = useState(false);
  const links: [string, string, boolean][] = [
    [at("compare/"), "Compare", page === "compare"],
    [at("learn.html"), "How to read it", false],
    [at("accuracy.html"), "Accuracy and limits", false],
    [at("evidence.html"), "Evidence", false],
  ];
  return (
    <header className="nav">
      <div className="nav-in">
        <a className="brand" href={at("")} aria-label="Lunar Site Navigator, home">
          <Mark />
          <span>Lunar Site Navigator</span>
        </a>
        <button type="button" className="nav-toggle" aria-expanded={open} aria-controls="nav-links" onClick={() => setOpen(!open)}>
          <span className="sr">Menu</span>
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h16M4 12h16M4 17h16" stroke="currentColor" strokeWidth="2" strokeLinecap="round" /></svg>
        </button>
        <nav id="nav-links" className={open ? "open" : ""} aria-label="Site">
          {links.map(([href, label, current]) => (
            <a key={href} href={href} aria-current={current ? "page" : undefined}>{label}</a>
          ))}
          <a className="nav-gh" href={GITHUB}>GitHub</a>
        </nav>
      </div>
    </header>
  );
}

// The notice of the site build (web/site_notice.txt), shown on every page when there is one.
export function Notice() {
  const [text, setText] = useState<string | null>(null);
  useEffect(() => { loadNotice().then((n) => setText(n?.notice ?? null)); }, []);
  if (!text) return null;
  return <div className="site-notice" role="note">{text}</div>;
}

export function Footer() {
  return (
    <footer className="foot">
      <div className="foot-in">
        <div>
          <a className="brand" href={at("")}><Mark /><span>Lunar Site Navigator</span></a>
          <p className="muted">Team <strong>Kestro Aerospace</strong>: Kaan Eşrefoğlu, Barkın Kocatepe.<br />
            NASA Space Apps Challenge 2026, Aachen. Challenge: <em>Lunar Landing Site Navigator</em>.</p>
        </div>
        <FooterCol title="Explore" links={[[at("compare/"), "Compare two sites"], [at("viewer/index.html"), "Single-site viewer and Moon globe"], [at("classic.html"), "Classic comparison page"]]} />
        <FooterCol title="Read" links={[[at("learn.html"), "How to read it"], [at("accuracy.html"), "Accuracy and limits"], [at("evidence.html"), "Evidence"], [SLIDES, "Slides (PDF)"]]} />
        <FooterCol title="Source" links={[[GITHUB, "Code on GitHub"], [`${GITHUB}/blob/main/docs/contract/SPEC.md`, "Package contract"], [`${GITHUB}/blob/main/validation/card/validation_card.md`, "Validation card"], [`${GITHUB}/blob/main/LICENSE`, "Apache License 2.0"]]} />
      </div>
    </footer>
  );
}

function FooterCol({ title, links }: { title: string; links: [string, string][] }) {
  return (
    <div className="foot-col">
      <h3>{title}</h3>
      <ul>{links.map(([href, label]) => <li key={href}><a href={href}>{label}</a></li>)}</ul>
    </div>
  );
}

export function Shell({ page, children }: { page: Page; children: ReactNode }) {
  return (
    <>
      <a className="skip" href="#content">Skip to content</a>
      <Nav page={page} />
      <Notice />
      <div id="content">{children}</div>
      <Footer />
    </>
  );
}
