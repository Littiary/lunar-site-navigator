import { LINKS, type Link } from "../site/links";
import { Brand } from "./Mark";

const COLUMNS: { title: string; links: Link[] }[] = [
  { title: "Explore", links: [LINKS.compare, { ...LINKS.viewer, label: "Single-site viewer and Moon globe" }, LINKS.classic] },
  { title: "Read", links: [LINKS.learn, LINKS.accuracy, LINKS.evidence, { ...LINKS.slides, label: "Slides (PDF)" }] },
  { title: "Source", links: [LINKS.github, LINKS.contract, LINKS.card, LINKS.license] },
];

export function Footer() {
  return (
    <footer className="foot">
      <div className="foot-in">
        <div>
          <Brand />
          <p className="muted">Team <strong>Kestro Aerospace</strong>: Kaan Eşrefoğlu, Barkın Kocatepe.<br />
            NASA Space Apps Challenge 2026, Aachen. Challenge: <em>Lunar Landing Site Navigator</em>.</p>
        </div>
        {COLUMNS.map(({ title, links }) => (
          <div key={title} className="foot-col">
            <h3>{title}</h3>
            <ul>{links.map((l) => <li key={l.href}><a href={l.href}>{l.label}</a></li>)}</ul>
          </div>
        ))}
      </div>
    </footer>
  );
}
